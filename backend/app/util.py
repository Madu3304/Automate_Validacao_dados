"""Funções auxiliares de normalização."""
import re
import unicodedata
from typing import Iterable


def sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def normalizar_nome_coluna(nome) -> str:
    s = sem_acentos(str(nome)).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def localizar_coluna(colunas: Iterable, candidatos: Iterable[str]) -> str | None:
    """Retorna a primeira coluna cujo nome normalizado corresponde a um dos candidatos (na ordem dos candidatos)."""
    mapa = {}
    for c in colunas:
        mapa.setdefault(normalizar_nome_coluna(c), c)
    for cand in candidatos:
        n = normalizar_nome_coluna(cand)
        if n in mapa:
            return mapa[n]
    return None


def localizar_colunas(colunas: Iterable, candidatos: Iterable[str]) -> list[str]:
    """Retorna todas as colunas que correspondem a algum candidato."""
    alvos = {normalizar_nome_coluna(c) for c in candidatos}
    return [c for c in colunas if normalizar_nome_coluna(c) in alvos]


def limpar_numero_excel(valor: str) -> str:
    """'12345.0' (número lido do Excel) vira '12345'."""
    if re.fullmatch(r"\d+\.0+", valor):
        return valor.split(".")[0]
    return valor


def sanitizar_nome_arquivo(nome: str) -> str:
    limpo = re.sub(r"[^\w\-]+", "_", sem_acentos(nome)).strip("_")
    return limpo[:80] or "planilha"


def lista_curta(itens, limite: int = 15) -> str:
    itens = [str(i) for i in itens]
    texto = ", ".join(itens[:limite])
    return texto + (f" (+{len(itens) - limite})" if len(itens) > limite else "")
