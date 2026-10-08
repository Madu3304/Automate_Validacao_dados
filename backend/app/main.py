"""
API da plataforma de governança de dados mestres.

Equivale à camada Power Automate da arquitetura: recebe as entradas, valida, guarda
os arquivos, executa as regras determinísticas, chama o agente para explicar o
resultado, registra a execução e devolve os dados para a tela.

Executar:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import stat
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import storage
from .agente import explicar
from .conciliacao import OpcoesConciliacao, conciliar
from .config import CORS_ORIGINS, EXTENSOES_PERMITIDAS, LIMITE_ITENS_API, MAX_UPLOAD_MB
from .leitura import ErroValidacao, ler_planilha
from .regras import (CONJUNTOS_VERIFICACAO, MODOS_NORMALIZACAO, REGRAS_CONCILIACAO, ROTULOS_TIPOS,
                     ROTULOS_TOTAIS)
from .relatorios import planilha_tratada, relatorio_conciliacao, relatorio_verificacao
from .util import localizar_coluna, sanitizar_nome_arquivo
from .verificacao import OpcoesVerificacao, verificar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gdm")

_ID_VALIDO = re.compile(r"[0-9a-f]{12}")
_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    storage.inicializar()
    yield


app = FastAPI(title="Governança de Dados Mestres: SAP x Klassmatt", version="1.0.0", lifespan=ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ErroValidacao)
async def _tratar_validacao(_request, exc: ErroValidacao):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _vazio(valor: str | None) -> str | None:
    return valor.strip() if valor and valor.strip() else None


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _salvar_upload(upload: UploadFile, pasta: Path, prefixo: str) -> tuple[Path, str]:
    nome_original = Path(upload.filename or "arquivo").name
    extensao = Path(nome_original).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ErroValidacao(f"'{nome_original}': extensão não suportada. "
                            f"Use {', '.join(sorted(EXTENSOES_PERMITIDAS))}.")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{prefixo}{extensao}"
    limite, total, excedeu = MAX_UPLOAD_MB * 1024 * 1024, 0, False
    with destino.open("wb") as f:
        while bloco := upload.file.read(1024 * 1024):
            total += len(bloco)
            if total > limite:
                excedeu = True
                break
            f.write(bloco)
    if excedeu:
        destino.unlink(missing_ok=True)
        raise ErroValidacao(f"'{nome_original}' passa do limite de {MAX_UPLOAD_MB} MB.")
    if total == 0:
        destino.unlink(missing_ok=True)
        raise ErroValidacao(f"'{nome_original}' está vazio.")
    return destino, nome_original


def _receber_original(upload: UploadFile, pasta: Path, prefixo: str, rotulo: str, reg: dict) -> Path:
    """Salva o original, registra o hash e deixa o arquivo somente leitura."""
    destino, nome_original = _salvar_upload(upload, pasta / "entrada", prefixo)
    os.chmod(destino, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    reg["arquivos"].append({
        "nome": destino.name, "rotulo": f"{rotulo} original", "categoria": "entrada",
        "caminho": f"entrada/{destino.name}", "nome_original": nome_original, "sha256": _sha256(destino),
    })
    return destino


def _registrar_saida(reg: dict, caminho: Path, rotulo: str):
    reg["arquivos"].append({"nome": caminho.name, "rotulo": rotulo, "categoria": "saida",
                            "caminho": f"saida/{caminho.name}"})


def _conferir_integridade(pasta: Path, reg: dict):
    for arq in reg["arquivos"]:
        if arq["categoria"] == "entrada":
            caminho = pasta / arq["caminho"]
            arq["integro"] = caminho.exists() and _sha256(caminho) == arq["sha256"]


def _resposta(reg: dict, itens: dict | None = None) -> dict:
    itens = itens if itens is not None else storage.carregar_itens(reg["id"])
    return {
        **reg,
        "itens": {k: v[:LIMITE_ITENS_API] for k, v in itens.items()},
        "itens_totais": {k: len(v) for k, v in itens.items()},
        "limite_itens": LIMITE_ITENS_API,
    }


_MENSAGENS = {
    ("conciliacao", "OK"): "Conciliação concluída sem divergências bloqueantes.",
    ("conciliacao", "NOK"): "Conciliação concluída com divergências bloqueantes.",
    ("verificacao", "OK"): "Planilha verificada e cópia tratada gerada.",
    ("verificacao", "NOK"): "Cópia tratada gerada, mas restam ocorrências bloqueantes.",
}


def _executar(servico: str, usuario: str | None, versao: str, conjunto: str,
              trabalho: Callable[[Path, dict], dict]) -> dict:
    exec_id = storage.novo_id()
    pasta = storage.pasta_execucao(exec_id)
    (pasta / "entrada").mkdir(parents=True, exist_ok=True)
    (pasta / "saida").mkdir(parents=True, exist_ok=True)

    reg = {
        "id": exec_id, "servico": servico, "status": "ERRO_TECNICO", "versao_regras": versao,
        "conjunto_regras": conjunto, "usuario": (usuario or "").strip()[:80] or "anônimo",
        "criado_em": storage.agora(), "duracao_ms": 0, "mensagem": "", "explicacao": "",
        "origem_explicacao": "", "resumo": {}, "arquivos": [],
    }
    inicio = time.perf_counter()
    itens: dict = {}
    try:
        itens = trabalho(pasta, reg) or {}
    except ErroValidacao as exc:
        reg["status"] = "NOK"
        reg["mensagem"] = str(exc)
        reg["explicacao"] = f"A execução não foi processada porque a entrada não passou na validação: {exc}"
        reg["origem_explicacao"] = "validacao"
    except Exception:  # noqa: BLE001
        log.exception("Falha técnica na execução %s", exec_id)
        reg["status"] = "ERRO_TECNICO"
        reg["mensagem"] = f"Falha inesperada no processamento. Informe o código {exec_id} ao suporte."
        reg["explicacao"] = reg["mensagem"]
    finally:
        reg["duracao_ms"] = int((time.perf_counter() - inicio) * 1000)
        _conferir_integridade(pasta, reg)
        storage.salvar_execucao(reg)
        storage.salvar_itens(exec_id, itens)
    log.info("Execução %s (%s) finalizada com %s em %d ms", exec_id, servico, reg["status"], reg["duracao_ms"])
    return _resposta(reg, itens)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/api/saude")
def saude():
    return {"status": "ok"}


@app.get("/api/servicos")
def servicos():
    """Catálogo usado pela tela inicial: serviços, regras e rótulos."""
    return {
        "servicos": [
            {"id": "conciliacao", "nome": "Conciliação SAP x Klassmatt",
             "versao_regras": REGRAS_CONCILIACAO["versao"],
             "modos_normalizacao": [{"id": k, "descricao": v} for k, v in MODOS_NORMALIZACAO.items()],
             "normalizacao_padrao": REGRAS_CONCILIACAO["normalizacao_chave_padrao"],
             "campos_comparados": [{"campo": c["campo"], "criticidade": c["criticidade"]}
                                   for c in REGRAS_CONCILIACAO["campos_comparados"]]},
            {"id": "verificacao", "nome": "Verificação e ajuste de planilha",
             "conjuntos": [
                 {"id": c["id"], "nome": c["nome"], "versao": c["versao"], "descricao": c["descricao"],
                  "colunas_obrigatorias": [o["nome"] for o in c["colunas_obrigatorias"]],
                  "regras": [{"id": r["id"], "descricao": r["descricao"], "critica": r.get("critica", False),
                              "tipo": r["tipo"]} for r in c["regras"]]}
                 for c in CONJUNTOS_VERIFICACAO.values()]},
        ],
        "rotulos": {"tipos": ROTULOS_TIPOS, "totais": ROTULOS_TOTAIS},
        "limites": {"tamanho_mb": MAX_UPLOAD_MB, "extensoes": sorted(EXTENSOES_PERMITIDAS)},
    }


@app.post("/api/inspecionar")
def inspecionar(arquivo: UploadFile = File(...), aba: str | None = Form(None)):
    """Lê abas e colunas de uma planilha sem registrar execução (para montar o formulário)."""
    with tempfile.TemporaryDirectory() as tmp:
        caminho, nome = _salvar_upload(arquivo, Path(tmp), "inspecao")
        df, info = ler_planilha(caminho, _vazio(aba))
    return {
        "arquivo": nome, "abas": info["abas"], "aba_usada": info["aba_usada"],
        "colunas": info["colunas"], "linhas": info["linhas"],
        "sugestoes": {
            "chave_sap": localizar_coluna(df.columns, REGRAS_CONCILIACAO["aliases_chave_sap"]),
            "chave_klassmatt": localizar_coluna(df.columns, REGRAS_CONCILIACAO["aliases_chave_klassmatt"]),
        },
    }


@app.post("/api/conciliacao")
def executar_conciliacao(
    arquivo_sap: UploadFile = File(...),
    arquivo_klassmatt: UploadFile = File(...),
    aba_sap: str | None = Form(None),
    aba_klassmatt: str | None = Form(None),
    chave_sap: str | None = Form(None),
    chave_klassmatt: str | None = Form(None),
    normalizacao_chave: str | None = Form(None),
    x_usuario: str | None = Header(None),
):
    def trabalho(pasta: Path, reg: dict) -> dict:
        cam_sap = _receber_original(arquivo_sap, pasta, "original_sap", "Planilha SAP", reg)
        cam_kl = _receber_original(arquivo_klassmatt, pasta, "original_klassmatt", "Planilha Klassmatt", reg)
        df_sap, info_sap = ler_planilha(cam_sap, _vazio(aba_sap))
        df_kl, info_kl = ler_planilha(cam_kl, _vazio(aba_klassmatt))

        res = conciliar(df_sap, df_kl, OpcoesConciliacao(
            chave_sap=_vazio(chave_sap), chave_klassmatt=_vazio(chave_klassmatt),
            normalizacao_chave=_vazio(normalizacao_chave)))

        explicacao = explicar("conciliacao", res)
        reg.update(
            status=res["status"], mensagem=_MENSAGENS[("conciliacao", res["status"])],
            explicacao=explicacao["texto"], origem_explicacao=explicacao["origem"],
            resumo={"totais": res["totais"], "por_tipo": res["por_tipo"],
                    "parametros": {**res["parametros"], "aba_sap": info_sap["aba_usada"],
                                   "aba_klassmatt": info_kl["aba_usada"]}},
        )
        relatorio = pasta / "saida" / "relatorio_conciliacao.xlsx"
        relatorio_conciliacao(relatorio, reg, res)
        _registrar_saida(reg, relatorio, "Relatório de conciliação")
        return {"divergencias": res["divergencias"]}

    return _executar("conciliacao", x_usuario, REGRAS_CONCILIACAO["versao"], REGRAS_CONCILIACAO["id"], trabalho)


@app.post("/api/verificacao")
def executar_verificacao(
    arquivo: UploadFile = File(...),
    conjunto_regras: str = Form("cadastro_materiais"),
    aba: str | None = Form(None),
    aplicar_criticos: bool = Form(False),
    regras_desativadas: str | None = Form(None),
    x_usuario: str | None = Header(None),
):
    conjunto = CONJUNTOS_VERIFICACAO.get(conjunto_regras)

    def trabalho(pasta: Path, reg: dict) -> dict:
        if not conjunto:
            raise ErroValidacao(f"Conjunto de regras '{conjunto_regras}' não existe.")
        caminho = _receber_original(arquivo, pasta, "original", "Planilha", reg)
        df, info = ler_planilha(caminho, _vazio(aba))
        desativadas = {r.strip() for r in (regras_desativadas or "").split(",") if r.strip()}

        res = verificar(df, OpcoesVerificacao(
            conjunto=conjunto_regras, aplicar_criticos=aplicar_criticos,
            regras_desativadas=desativadas, linhas_vazias_removidas=info["linhas_vazias"]))

        explicacao = explicar("verificacao", res)
        reg.update(
            status=res["status"], mensagem=_MENSAGENS[("verificacao", res["status"])],
            explicacao=explicacao["texto"], origem_explicacao=explicacao["origem"],
            resumo={"totais": res["totais"], "por_tipo": res["por_tipo"], "por_regra": res["por_regra"],
                    "requer_revisao": res["requer_revisao"],
                    "parametros": {**res["parametros"], "aba": info["aba_usada"]}},
        )
        base = sanitizar_nome_arquivo(Path(reg["arquivos"][0]["nome_original"]).stem)
        tratada = pasta / "saida" / f"{base}_tratada.xlsx"
        planilha_tratada(tratada, res["df_tratado"], info["aba_usada"] or "Dados")
        _registrar_saida(reg, tratada, "Planilha tratada (cópia)")
        relatorio = pasta / "saida" / "relatorio_alteracoes.xlsx"
        relatorio_verificacao(relatorio, reg, res)
        _registrar_saida(reg, relatorio, "Relatório de alterações")
        return {"ocorrencias": res["ocorrencias"], "alteracoes": res["alteracoes"]}

    versao = conjunto["versao"] if conjunto else "-"
    return _executar("verificacao", x_usuario, versao, conjunto_regras, trabalho)


@app.get("/api/execucoes")
def listar(servico: str | None = None, status: str | None = None, limite: int = Query(100, ge=1, le=500)):
    return [{k: v for k, v in r.items() if k != "explicacao"}
            for r in storage.listar_execucoes(servico, status, limite)]


@app.get("/api/indicadores")
def indicadores():
    return storage.indicadores()


def _obter_ou_404(exec_id: str) -> dict:
    reg = storage.obter_execucao(exec_id) if _ID_VALIDO.fullmatch(exec_id) else None
    if not reg:
        raise HTTPException(404, "Execução não encontrada.")
    return reg


@app.get("/api/execucoes/{exec_id}")
def detalhe(exec_id: str):
    return _resposta(_obter_ou_404(exec_id))


@app.get("/api/execucoes/{exec_id}/arquivos/{nome}")
def baixar(exec_id: str, nome: str):
    reg = _obter_ou_404(exec_id)
    arquivo = next((a for a in reg["arquivos"] if a["nome"] == nome), None)
    if not arquivo:
        raise HTTPException(404, "Arquivo não encontrado nesta execução.")
    caminho = storage.pasta_execucao(exec_id) / arquivo["caminho"]
    if not caminho.exists():
        raise HTTPException(410, "O arquivo não está mais disponível.")
    nome_download = arquivo.get("nome_original") or nome
    tipo = "text/csv" if caminho.suffix == ".csv" else _MIME_XLSX
    return FileResponse(caminho, filename=nome_download, media_type=tipo)
