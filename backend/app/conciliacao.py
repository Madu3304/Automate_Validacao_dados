"""
Serviço A: Conciliação SAP x Klassmatt.

A comparação é 100% determinística (pandas). O agente só explica o resultado,
nunca decide se um registro diverge ou não.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pandas as pd

from .leitura import ErroValidacao
from .regras import MODOS_NORMALIZACAO, REGRAS_CONCILIACAO
from .util import limpar_numero_excel, lista_curta, localizar_coluna, sem_acentos


@dataclass
class OpcoesConciliacao:
    chave_sap: str | None = None
    chave_klassmatt: str | None = None
    normalizacao_chave: str | None = None


def normalizar_chave(valor: str, modo: str) -> str:
    v = re.sub(r"\s+", "", limpar_numero_excel(str(valor).strip())).upper()
    if v.isdigit():
        if modo == "remover_zeros_esquerda":
            v = v.lstrip("0") or "0"
        elif modo == "completar_zeros_18":
            v = v.zfill(18)
    return v


def normalizar_valor(valor: str, modo: str) -> str:
    v = limpar_numero_excel(str(valor).strip())
    if modo == "texto":
        return re.sub(r"\s+", " ", sem_acentos(v).upper()).strip()
    if modo == "digitos":
        return re.sub(r"\D", "", v)
    return v.upper()


def _resolver_chave(df: pd.DataFrame, informada: str | None, aliases: list[str], origem: str) -> str:
    if informada:
        coluna = informada if informada in df.columns else localizar_coluna(df.columns, [informada])
        if coluna:
            return coluna
        raise ErroValidacao(f"A coluna '{informada}' não existe na planilha {origem}. "
                            f"Colunas disponíveis: {lista_curta(df.columns)}.")
    coluna = localizar_coluna(df.columns, aliases)
    if not coluna:
        raise ErroValidacao(f"Não foi possível identificar a coluna de código na planilha {origem}. "
                            f"Informe a coluna chave. Colunas disponíveis: {lista_curta(df.columns)}.")
    return coluna


def _preparar(df: pd.DataFrame, coluna_chave: str, colunas_campos: list[str], modo: str) -> pd.DataFrame:
    base = pd.DataFrame({
        "_linha": df.index.astype(int),
        "_bruta": df[coluna_chave].str.strip().values,
    })
    base["_chave"] = base["_bruta"].map(lambda v: normalizar_chave(v, modo))
    for i, coluna in enumerate(colunas_campos):
        base[f"f{i}"] = df[coluna].values
    return base


def conciliar(df_sap: pd.DataFrame, df_klassmatt: pd.DataFrame, opcoes: OpcoesConciliacao,
              regras: dict = REGRAS_CONCILIACAO) -> dict:
    modo = opcoes.normalizacao_chave or regras["normalizacao_chave_padrao"]
    if modo not in MODOS_NORMALIZACAO:
        raise ErroValidacao(f"Regra de normalização '{modo}' desconhecida.")

    col_sap = _resolver_chave(df_sap, opcoes.chave_sap, regras["aliases_chave_sap"], "SAP")
    col_kl = _resolver_chave(df_klassmatt, opcoes.chave_klassmatt, regras["aliases_chave_klassmatt"], "Klassmatt")

    # Campos complementares: só compara os que existem nas duas planilhas.
    campos, ignorados = [], []
    for campo in regras["campos_comparados"]:
        cs = localizar_coluna([c for c in df_sap.columns if c != col_sap], campo["sap"])
        ck = localizar_coluna([c for c in df_klassmatt.columns if c != col_kl], campo["klassmatt"])
        if cs and ck:
            campos.append({**campo, "coluna_sap": cs, "coluna_klassmatt": ck})
        else:
            onde = "nas duas planilhas" if not cs and not ck else ("no SAP" if not cs else "no Klassmatt")
            ignorados.append({"campo": campo["campo"], "motivo": f"Coluna não encontrada {onde}"})

    sap = _preparar(df_sap, col_sap, [c["coluna_sap"] for c in campos], modo)
    kl = _preparar(df_klassmatt, col_kl, [c["coluna_klassmatt"] for c in campos], modo)

    criticidade = regras["criticidade_tipos"]
    divergencias: list[dict] = []

    def registrar(tipo, chave, mensagem, *, campo="", valor_sap="", valor_klassmatt="",
                  linha_sap="", linha_klassmatt="", nivel=None):
        divergencias.append({
            "tipo": tipo,
            "criticidade": nivel or criticidade[tipo],
            "chave": chave,
            "campo": campo,
            "valor_sap": valor_sap,
            "valor_klassmatt": valor_klassmatt,
            "linha_sap": linha_sap,
            "linha_klassmatt": linha_klassmatt,
            "mensagem": mensagem,
        })

    # 1) Validação das chaves em cada fonte
    for lado, dados, nome in (("sap", sap, "SAP"), ("klassmatt", kl, "Klassmatt")):
        for linha in dados.loc[dados["_chave"] == "", "_linha"]:
            registrar(f"CHAVE_VAZIA_{lado.upper()}", "", f"Linha sem código na planilha {nome}.",
                      **{f"linha_{lado}": int(linha)})

        validas = dados[dados["_chave"] != ""]
        fora_formato = validas[~validas["_chave"].str.fullmatch(regras["formato_chave"])]
        for _, r in fora_formato.iterrows():
            registrar("FORMATO_CHAVE_INVALIDO", r["_chave"],
                      f"Código '{r['_bruta']}' fora do formato esperado na planilha {nome}.",
                      **{f"linha_{lado}": int(r["_linha"])})

        repetidas = validas[validas.duplicated("_chave", keep=False)]
        for chave, grupo in repetidas.groupby("_chave", sort=True):
            linhas = ", ".join(str(int(x)) for x in grupo["_linha"])
            registrar(f"DUPLICIDADE_{lado.upper()}", chave,
                      f"Código repetido {len(grupo)} vezes na planilha {nome}.",
                      **{f"linha_{lado}": linhas})

    # 2) Cruzamento das fontes (primeira ocorrência de cada código)
    sap_u = sap[sap["_chave"] != ""].drop_duplicates("_chave")
    kl_u = kl[kl["_chave"] != ""].drop_duplicates("_chave")
    cruzado = sap_u.merge(kl_u, on="_chave", how="outer", suffixes=("_s", "_k"), indicator=True)

    so_sap = cruzado[cruzado["_merge"] == "left_only"]
    for _, r in so_sap.iterrows():
        registrar("AUSENTE_NO_KLASSMATT", r["_chave"],
                  f"Código {r['_bruta_s']} existe no SAP e não foi encontrado no Klassmatt.",
                  linha_sap=int(r["_linha_s"]))

    so_kl = cruzado[cruzado["_merge"] == "right_only"]
    for _, r in so_kl.iterrows():
        registrar("AUSENTE_NO_SAP", r["_chave"],
                  f"Código {r['_bruta_k']} existe no Klassmatt e não foi encontrado no SAP.",
                  linha_klassmatt=int(r["_linha_k"]))

    # 3) Comparação dos campos complementares
    ambos = cruzado[cruzado["_merge"] == "both"]
    chaves_com_diferenca = set()
    for i, campo in enumerate(campos):
        vs = ambos[f"f{i}_s"].map(lambda v, m=campo["comparacao"]: normalizar_valor(v, m))
        vk = ambos[f"f{i}_k"].map(lambda v, m=campo["comparacao"]: normalizar_valor(v, m))
        for _, r in ambos[vs != vk].iterrows():
            chaves_com_diferenca.add(r["_chave"])
            registrar("DIFERENCA_CAMPO", r["_chave"], f"{campo['campo']} diferente entre SAP e Klassmatt.",
                      campo=campo["campo"], valor_sap=r[f"f{i}_s"], valor_klassmatt=r[f"f{i}_k"],
                      linha_sap=int(r["_linha_s"]), linha_klassmatt=int(r["_linha_k"]),
                      nivel=campo["criticidade"])

    contagem = Counter(d["tipo"] for d in divergencias)
    bloqueantes = sum(1 for d in divergencias if d["criticidade"] == "bloqueante")
    totais = {
        "registros_sap": len(sap),
        "registros_klassmatt": len(kl),
        "codigos_unicos_sap": len(sap_u),
        "codigos_unicos_klassmatt": len(kl_u),
        "correspondencias": len(ambos),
        "correspondencias_sem_divergencia": len(ambos) - len(chaves_com_diferenca),
        "ausentes_no_klassmatt": len(so_sap),
        "ausentes_no_sap": len(so_kl),
        "codigos_duplicados_sap": contagem["DUPLICIDADE_SAP"],
        "codigos_duplicados_klassmatt": contagem["DUPLICIDADE_KLASSMATT"],
        "diferencas_de_campo": contagem["DIFERENCA_CAMPO"],
        "divergencias_bloqueantes": bloqueantes,
        "avisos": len(divergencias) - bloqueantes,
    }

    ordem = {"bloqueante": 0, "aviso": 1}
    divergencias.sort(key=lambda d: (ordem[d["criticidade"]], d["tipo"], d["chave"]))

    return {
        "status": "NOK" if bloqueantes else "OK",
        "totais": totais,
        "por_tipo": dict(contagem),
        "divergencias": divergencias,
        "parametros": {
            "coluna_chave_sap": col_sap,
            "coluna_chave_klassmatt": col_kl,
            "normalizacao_chave": modo,
            "campos_comparados": [
                {"campo": c["campo"], "coluna_sap": c["coluna_sap"], "coluna_klassmatt": c["coluna_klassmatt"],
                 "comparacao": c["comparacao"], "criticidade": c["criticidade"]} for c in campos
            ],
            "campos_ignorados": ignorados,
        },
    }
