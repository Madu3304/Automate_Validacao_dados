"""Leitura e validação estrutural de planilhas (.xlsx, .xlsm, .csv)."""
from pathlib import Path

import pandas as pd

from .config import EXTENSOES_PERMITIDAS, MAX_LINHAS
from .util import lista_curta


class ErroValidacao(Exception):
    """Problema na entrada do usuário (arquivo, estrutura ou parâmetros). Resulta em status NOK."""


def _ler_csv(caminho: Path) -> pd.DataFrame:
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(caminho, dtype=str, keep_default_na=False, sep=None,
                               engine="python", encoding=codificacao)
        except UnicodeDecodeError:
            continue
        except Exception as exc:  # noqa: BLE001
            raise ErroValidacao(f"Não foi possível ler o CSV '{caminho.name}': {exc}") from exc
    raise ErroValidacao(f"Codificação do arquivo '{caminho.name}' não reconhecida. Salve como UTF-8.")


def ler_planilha(caminho: Path, aba: str | None = None) -> tuple[pd.DataFrame, dict]:
    """
    Lê a planilha como texto (preserva zeros à esquerda) e devolve:
      - DataFrame cujo índice é o número da linha no Excel (cabeçalho = linha 1)
      - dicionário com abas, aba usada, colunas e linhas vazias ignoradas
    """
    extensao = caminho.suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ErroValidacao(f"Extensão '{extensao}' não suportada. Use {', '.join(sorted(EXTENSOES_PERMITIDAS))}.")

    if extensao == ".csv":
        df = _ler_csv(caminho)
        abas, aba_usada = [], None
    else:
        try:
            livro = pd.ExcelFile(caminho, engine="openpyxl")
        except Exception as exc:  # noqa: BLE001
            raise ErroValidacao(f"O arquivo '{caminho.name}' não é uma planilha Excel válida.") from exc
        abas = livro.sheet_names
        aba_usada = aba or abas[0]
        if aba_usada not in abas:
            raise ErroValidacao(f"A aba '{aba_usada}' não existe. Abas encontradas: {lista_curta(abas)}.")
        df = livro.parse(aba_usada, dtype=str, keep_default_na=False)

    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]

    # Colunas sem cabeçalho e sem dados são descartadas.
    manter = [not (c.startswith("Unnamed") and (df[c].str.strip() == "").all()) for c in df.columns]
    df = df.loc[:, manter]
    if df.shape[1] == 0:
        raise ErroValidacao("A planilha não possui colunas com cabeçalho na primeira linha.")

    sem_cabecalho = [c for c in df.columns if c.startswith("Unnamed")]
    if sem_cabecalho:
        raise ErroValidacao("Há colunas com dados mas sem cabeçalho. Preencha o nome de todas as colunas na linha 1.")

    df.index = range(2, len(df) + 2)
    vazias = (df.apply(lambda s: s.str.strip()) == "").all(axis=1)
    linhas_vazias = [int(i) for i in df.index[vazias]]
    df = df[~vazias]

    if df.empty:
        raise ErroValidacao("A planilha não possui linhas com dados.")
    if len(df) > MAX_LINHAS:
        raise ErroValidacao(f"A planilha tem {len(df)} linhas; o limite é {MAX_LINHAS}.")

    return df, {
        "abas": abas,
        "aba_usada": aba_usada,
        "colunas": list(df.columns),
        "linhas": len(df),
        "linhas_vazias": linhas_vazias,
    }
