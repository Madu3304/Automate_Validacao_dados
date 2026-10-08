"""Histórico de execuções (SQLite) e armazenamento de arquivos por execução."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import ARQUIVOS_DIR, DATA_DIR, DB_PATH

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    id TEXT PRIMARY KEY,
    servico TEXT NOT NULL,
    status TEXT NOT NULL,
    versao_regras TEXT,
    conjunto_regras TEXT,
    usuario TEXT,
    criado_em TEXT NOT NULL,
    duracao_ms INTEGER,
    mensagem TEXT,
    explicacao TEXT,
    origem_explicacao TEXT,
    resumo TEXT,
    arquivos TEXT
);
CREATE INDEX IF NOT EXISTS ix_execucoes_data ON execucoes (criado_em DESC);
"""

_COLUNAS = ["id", "servico", "status", "versao_regras", "conjunto_regras", "usuario", "criado_em",
            "duracao_ms", "mensagem", "explicacao", "origem_explicacao", "resumo", "arquivos"]


def inicializar():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARQUIVOS_DIR.mkdir(parents=True, exist_ok=True)
    with conectar() as con:
        con.executescript(_ESQUEMA)


@contextmanager
def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def novo_id() -> str:
    return uuid.uuid4().hex[:12]


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pasta_execucao(exec_id: str) -> Path:
    return ARQUIVOS_DIR / exec_id


def salvar_execucao(reg: dict):
    dados = dict(reg)
    dados["resumo"] = json.dumps(reg.get("resumo") or {}, ensure_ascii=False, default=str)
    dados["arquivos"] = json.dumps(reg.get("arquivos") or [], ensure_ascii=False)
    with conectar() as con:
        con.execute(
            f"INSERT OR REPLACE INTO execucoes ({', '.join(_COLUNAS)}) VALUES ({', '.join('?' * len(_COLUNAS))})",
            [dados.get(c) for c in _COLUNAS],
        )


def _para_dict(row) -> dict:
    d = dict(row)
    d["resumo"] = json.loads(d["resumo"] or "{}")
    d["arquivos"] = json.loads(d["arquivos"] or "[]")
    return d


def obter_execucao(exec_id: str) -> dict | None:
    with conectar() as con:
        row = con.execute("SELECT * FROM execucoes WHERE id = ?", (exec_id,)).fetchone()
    return _para_dict(row) if row else None


def listar_execucoes(servico: str | None = None, status: str | None = None, limite: int = 100) -> list[dict]:
    filtros, params = [], []
    if servico:
        filtros.append("servico = ?")
        params.append(servico)
    if status:
        filtros.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    with conectar() as con:
        rows = con.execute(f"SELECT * FROM execucoes {where} ORDER BY criado_em DESC LIMIT ?",
                           [*params, limite]).fetchall()
    return [_para_dict(r) for r in rows]


def indicadores() -> list[dict]:
    with conectar() as con:
        rows = con.execute(
            "SELECT servico, status, COUNT(*) AS quantidade, CAST(AVG(duracao_ms) AS INTEGER) AS duracao_media_ms "
            "FROM execucoes GROUP BY servico, status ORDER BY servico, status").fetchall()
    return [dict(r) for r in rows]


def salvar_itens(exec_id: str, itens: dict):
    pasta = pasta_execucao(exec_id)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "itens.json").write_text(json.dumps(itens, ensure_ascii=False, default=str), encoding="utf-8")


def carregar_itens(exec_id: str) -> dict:
    caminho = pasta_execucao(exec_id) / "itens.json"
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))
