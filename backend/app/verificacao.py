"""
Serviço B: Verificação e ajuste de planilha.

Regras de segurança funcional:
  - o arquivo original nunca é alterado (o serviço trabalha numa cópia em memória);
  - cada célula alterada e cada linha removida é registrada;
  - ajustes críticos (ex.: remover duplicidades) só são aplicados com autorização
    explícita e ficam marcados para revisão humana.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from .leitura import ErroValidacao
from .regras import CONJUNTOS_VERIFICACAO
from .util import lista_curta, localizar_coluna, localizar_colunas, normalizar_nome_coluna


@dataclass
class OpcoesVerificacao:
    conjunto: str
    aplicar_criticos: bool = False
    regras_desativadas: set[str] = field(default_factory=set)
    linhas_vazias_removidas: list[int] = field(default_factory=list)


class _Contexto:
    def __init__(self, opcoes: OpcoesVerificacao):
        self.opcoes = opcoes
        self.alteracoes: list[dict] = []
        self.ocorrencias: list[dict] = []

    def alterar(self, linha, coluna, antes, depois, regra, critico=False, observacao=""):
        self.alteracoes.append({
            "linha": int(linha), "coluna": coluna, "valor_original": antes, "valor_ajustado": depois,
            "regra": regra["id"], "descricao_regra": regra["descricao"], "critico": critico,
            "observacao": observacao,
        })

    def ocorrer(self, linha, coluna, tipo, mensagem, severidade, valor="", regra=""):
        self.ocorrencias.append({
            "linha": int(linha), "coluna": coluna, "tipo": tipo, "severidade": severidade,
            "valor": valor, "mensagem": mensagem, "regra": regra,
        })


# ---------------------------------------------------------------------------
# Funções de transformação
# ---------------------------------------------------------------------------

_INVISIVEIS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200d\u2060\ufeff]")
_QUEBRAS = re.compile(r"[\t\r\n\u00a0]")

_FORMATOS_DATA = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                  "%Y/%m/%d", "%Y%m%d", "%d/%m/%y"]


def _sem_invisiveis(v: str) -> str:
    return _INVISIVEIS.sub("", _QUEBRAS.sub(" ", v))


def _sem_espacos_extras(v: str) -> str:
    return re.sub(r" {2,}", " ", v.strip())


def interpretar_data(valor: str) -> datetime | None:
    s = valor.strip()
    if not s:
        return None
    if re.fullmatch(r"\d{5}(\.0+)?", s):  # número de série do Excel
        n = int(float(s))
        if 20000 <= n <= 80000:
            return datetime(1899, 12, 30) + timedelta(days=n)
    for formato in _FORMATOS_DATA:
        try:
            return datetime.strptime(s, formato)
        except ValueError:
            continue
    return None


def _aplicar_mapa(df, coluna, funcao, regra, ctx):
    antes = df[coluna]
    depois = antes.map(funcao)
    mudou = antes != depois
    for linha in df.index[mudou]:
        ctx.alterar(linha, coluna, antes[linha], depois[linha], regra)
    df.loc[mudou, coluna] = depois[mudou]


# ---------------------------------------------------------------------------
# Implementação de cada tipo de regra
# ---------------------------------------------------------------------------

def _r_caracteres(df, colunas, regra, ctx):
    for c in colunas:
        _aplicar_mapa(df, c, _sem_invisiveis, regra, ctx)


def _r_espacos(df, colunas, regra, ctx):
    for c in colunas:
        _aplicar_mapa(df, c, _sem_espacos_extras, regra, ctx)


def _r_maiusculas(df, colunas, regra, ctx):
    for c in colunas:
        _aplicar_mapa(df, c, str.upper, regra, ctx)


def _r_somente_digitos(df, colunas, regra, ctx):
    for c in colunas:
        _aplicar_mapa(df, c, lambda v: re.sub(r"\D", "", v) if re.search(r"\d", v) else v, regra, ctx)


def _r_completar_zeros(df, colunas, regra, ctx):
    tamanho = regra["tamanho"]
    for c in colunas:
        _aplicar_mapa(df, c, lambda v: v.zfill(tamanho) if v.isdigit() and len(v) < tamanho else v, regra, ctx)
        for linha in df.index[df[c].str.len() > tamanho]:
            ctx.ocorrer(linha, c, "TAMANHO_EXCEDIDO", f"Código com mais de {tamanho} posições.", "aviso",
                        df.at[linha, c], regra["id"])


def _r_data(df, colunas, regra, ctx):
    formato = regra["formato_saida"]
    for c in colunas:
        def converter(v):
            d = interpretar_data(v)
            return d.strftime(formato) if d else v
        _aplicar_mapa(df, c, converter, regra, ctx)
        for linha in df.index:
            v = df.at[linha, c]
            if v.strip() and interpretar_data(v) is None:
                ctx.ocorrer(linha, c, "DATA_NAO_RECONHECIDA", "Valor não pôde ser interpretado como data.",
                            "aviso", v, regra["id"])


def _r_obrigatorio(df, colunas, regra, ctx):
    for c in colunas:
        for linha in df.index[df[c].str.strip() == ""]:
            ctx.ocorrer(linha, c, "CAMPO_OBRIGATORIO_VAZIO", f"O campo '{c}' é obrigatório.",
                        regra.get("severidade", "bloqueante"), "", regra["id"])


def _r_formato(df, colunas, regra, ctx):
    for c in colunas:
        valores = df[c].str.strip()
        invalidos = ~valores.str.fullmatch(regra["padrao"])
        if regra.get("permite_vazio"):
            invalidos &= valores != ""
        for linha in df.index[invalidos]:
            ctx.ocorrer(linha, c, "FORMATO_INVALIDO", regra["descricao"] + ".",
                        regra.get("severidade", "aviso"), df.at[linha, c], regra["id"])


def _r_dominio(df, colunas, regra, ctx):
    permitidos = {v.upper() for v in regra["valores"]}
    for c in colunas:
        valores = df[c].str.strip().str.upper()
        invalidos = ~valores.isin(permitidos)
        if regra.get("permite_vazio"):
            invalidos &= valores != ""
        for linha in df.index[invalidos]:
            ctx.ocorrer(linha, c, "VALOR_NAO_PERMITIDO", regra["descricao"] + ".",
                        regra.get("severidade", "aviso"), df.at[linha, c], regra["id"])


def _r_duplicidade(df, colunas, regra, ctx):
    base = df[colunas].apply(lambda s: s.str.strip().str.upper())
    preenchido = (base != "").any(axis=1)
    chaves = base.apply(tuple, axis=1)
    duplicada = chaves.duplicated(keep="first") & preenchido
    if not duplicada.any():
        return
    primeira = {chave: linha for linha, chave in chaves[~chaves.duplicated(keep="first")].items()}
    rotulo_coluna = "(linha inteira)" if len(colunas) > 3 else ", ".join(colunas)

    for linha in df.index[duplicada]:
        ref = primeira[chaves[linha]]
        resumo = "; ".join(f"{c}={df.at[linha, c]}" for c in colunas[:3])
        if ctx.opcoes.aplicar_criticos:
            ctx.alterar(linha, rotulo_coluna, resumo, "(linha removida)", regra, critico=True,
                        observacao=f"Duplicada da linha {ref}")
        else:
            ctx.ocorrer(linha, rotulo_coluna, "DUPLICIDADE",
                        f"Repete a linha {ref}. A remoção é um ajuste crítico e precisa de autorização.",
                        "bloqueante", resumo, regra["id"])

    if ctx.opcoes.aplicar_criticos:
        df.drop(index=df.index[duplicada], inplace=True)


_EXECUTORES = {
    "caracteres_invalidos": _r_caracteres,
    "espacos": _r_espacos,
    "maiusculas": _r_maiusculas,
    "somente_digitos": _r_somente_digitos,
    "completar_zeros": _r_completar_zeros,
    "data": _r_data,
    "obrigatorio": _r_obrigatorio,
    "formato": _r_formato,
    "dominio": _r_dominio,
    "duplicidade": _r_duplicidade,
}


def _resolver_colunas(df, regra, obrigatorias: dict) -> list[str]:
    spec = regra["colunas"]
    if spec == "todas":
        return list(df.columns)
    if spec == "obrigatorias":
        return list(obrigatorias.values())
    if spec == "auto":  # colunas de data pelo nome
        return [c for c in df.columns if re.search(r"(^|_)(data|dt)(_|$)", normalizar_nome_coluna(c))]
    if regra["tipo"] == "duplicidade":
        unica = localizar_coluna(df.columns, spec)
        return [unica] if unica else []
    return localizar_colunas(df.columns, spec)


def verificar(df_entrada: pd.DataFrame, opcoes: OpcoesVerificacao) -> dict:
    conjunto = CONJUNTOS_VERIFICACAO.get(opcoes.conjunto)
    if not conjunto:
        raise ErroValidacao(f"Conjunto de regras '{opcoes.conjunto}' não existe.")

    obrigatorias, faltando = {}, []
    for item in conjunto["colunas_obrigatorias"]:
        coluna = localizar_coluna(df_entrada.columns, item["aliases"])
        if coluna:
            obrigatorias[item["nome"]] = coluna
        else:
            faltando.append(item["nome"])
    if faltando:
        raise ErroValidacao(f"Colunas obrigatórias não encontradas: {', '.join(faltando)}. "
                            f"Colunas recebidas: {lista_curta(df_entrada.columns)}.")

    df = df_entrada.copy()  # o original em memória também permanece intacto
    ctx = _Contexto(opcoes)

    regra_vazias = {"id": "linhas_vazias", "descricao": "Remove linhas totalmente vazias"}
    for linha in opcoes.linhas_vazias_removidas:
        ctx.alterar(linha, "(linha inteira)", "(vazia)", "(linha removida)", regra_vazias)

    aplicadas, ignoradas = [], []
    for regra in conjunto["regras"]:
        if regra["id"] in opcoes.regras_desativadas:
            ignoradas.append({"id": regra["id"], "descricao": regra["descricao"], "motivo": "Desativada pelo usuário"})
            continue
        colunas = _resolver_colunas(df, regra, obrigatorias)
        if not colunas:
            ignoradas.append({"id": regra["id"], "descricao": regra["descricao"],
                              "motivo": "Nenhuma coluna correspondente na planilha"})
            continue
        _EXECUTORES[regra["tipo"]](df, colunas, regra, ctx)
        aplicadas.append({"id": regra["id"], "descricao": regra["descricao"], "colunas": colunas,
                          "critica": regra.get("critica", False)})

    criticos = [a for a in ctx.alteracoes if a["critico"]]
    bloqueantes = sum(1 for o in ctx.ocorrencias if o["severidade"] == "bloqueante")
    ctx.ocorrencias.sort(key=lambda o: (o["severidade"] != "bloqueante", o["linha"]))
    ctx.alteracoes.sort(key=lambda a: (not a["critico"], a["linha"]))

    totais = {
        "linhas_entrada": len(df_entrada) + len(opcoes.linhas_vazias_removidas),
        "linhas_saida": len(df),
        "linhas_removidas": len(df_entrada) + len(opcoes.linhas_vazias_removidas) - len(df),
        "celulas_ajustadas": len({(a["linha"], a["coluna"]) for a in ctx.alteracoes
                                  if a["valor_ajustado"] != "(linha removida)"}),
        "ajustes_criticos": len(criticos),
        "ocorrencias_bloqueantes": bloqueantes,
        "ocorrencias_aviso": len(ctx.ocorrencias) - bloqueantes,
    }

    return {
        "status": "NOK" if bloqueantes else "OK",
        "requer_revisao": bool(criticos),
        "df_tratado": df.reset_index(drop=True),
        "alteracoes": ctx.alteracoes,
        "ocorrencias": ctx.ocorrencias,
        "totais": totais,
        "por_regra": dict(Counter(a["regra"] for a in ctx.alteracoes)),
        "por_tipo": dict(Counter(o["tipo"] for o in ctx.ocorrencias)),
        "parametros": {
            "conjunto": conjunto["id"],
            "conjunto_nome": conjunto["nome"],
            "versao_regras": conjunto["versao"],
            "colunas_obrigatorias": obrigatorias,
            "ajustes_criticos_autorizados": opcoes.aplicar_criticos,
            "regras_aplicadas": aplicadas,
            "regras_ignoradas": ignoradas,
        },
    }
