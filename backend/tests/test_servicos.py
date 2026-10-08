import io
import os

import pandas as pd
import pytest


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("GDM_DATA_DIR", str(tmp_path / "dados"))
    import importlib

    import app.config
    import app.storage
    import app.main
    importlib.reload(app.config)
    importlib.reload(app.storage)
    importlib.reload(app.main)
    from fastapi.testclient import TestClient
    with TestClient(app.main.app) as c:
        yield c


def _xlsx(linhas: list[dict]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(linhas).to_excel(buf, index=False)
    return buf.getvalue()


def _df(linhas):
    df = pd.DataFrame(linhas).astype(str)
    df.index = range(2, len(df) + 2)
    return df


# --------------------------- Conciliação -----------------------------------

def test_conciliacao_classifica_divergencias():
    from app.conciliacao import OpcoesConciliacao, conciliar
    sap = _df([
        {"Material": "000000000000000001", "UMB": "PC", "NCM": "39174000"},
        {"Material": "000000000000000002", "UMB": "UN", "NCM": "39174000"},
        {"Material": "000000000000000002", "UMB": "UN", "NCM": "39174000"},
        {"Material": "000000000000000003", "UMB": "KG", "NCM": "39174000"},
    ])
    kl = _df([
        {"Código SAP": "1", "UM": "PC", "NCM": "3917.40.00"},
        {"Código SAP": "2", "UM": "PC", "NCM": "3917.40.00"},
        {"Código SAP": "9", "UM": "PC", "NCM": "3917.40.00"},
    ])
    r = conciliar(sap, kl, OpcoesConciliacao())
    tipos = r["por_tipo"]
    assert r["status"] == "NOK"
    assert r["totais"]["correspondencias"] == 2
    assert tipos["DUPLICIDADE_SAP"] == 1
    assert tipos["AUSENTE_NO_KLASSMATT"] == 1   # código 3
    assert tipos["AUSENTE_NO_SAP"] == 1         # código 9
    assert tipos["DIFERENCA_CAMPO"] == 1        # unidade do código 2 (NCM com pontos não diverge)


def test_conciliacao_ok_quando_so_ha_avisos():
    from app.conciliacao import OpcoesConciliacao, conciliar
    sap = _df([{"Material": "10", "Descrição": "Tubo PVC"}])
    kl = _df([{"Código SAP": "10", "Descrição Curta": "TUBO  PVC 25"}, {"Código SAP": "11", "Descrição Curta": "X"}])
    r = conciliar(sap, kl, OpcoesConciliacao())
    assert r["status"] == "OK"
    assert r["totais"]["avisos"] == 2


def test_normalizacao_da_chave():
    from app.conciliacao import normalizar_chave
    assert normalizar_chave("000000000000012345", "remover_zeros_esquerda") == "12345"
    assert normalizar_chave("12345", "completar_zeros_18") == "000000000000012345"
    assert normalizar_chave("12345.0", "manter") == "12345"
    assert normalizar_chave(" ab-1 ", "remover_zeros_esquerda") == "AB-1"


# --------------------------- Verificação -----------------------------------

def test_verificacao_ajusta_e_registra():
    from app.verificacao import OpcoesVerificacao, verificar
    df = _df([
        {"Material": "123", "Descrição": "  tubo   pvc ", "Unidade": "pc", "NCM": "3917.40.00", "Data Criação": "2026-03-15"},
        {"Material": "123", "Descrição": "outro", "Unidade": "UN", "NCM": "39174000", "Data Criação": "x"},
    ])
    original = df.copy()
    r = verificar(df, OpcoesVerificacao(conjunto="cadastro_materiais"))
    t = r["df_tratado"]
    assert t.loc[0, "Material"] == "000000000000000123"
    assert t.loc[0, "Descrição"] == "TUBO PVC"
    assert t.loc[0, "NCM"] == "39174000"
    assert t.loc[0, "Data Criação"] == "15/03/2026"
    assert pd.testing.assert_frame_equal(df, original) is None   # entrada intacta
    assert r["status"] == "NOK"                                   # duplicidade sem autorização
    assert any(o["tipo"] == "DUPLICIDADE" for o in r["ocorrencias"])
    assert any(o["tipo"] == "DATA_NAO_RECONHECIDA" for o in r["ocorrencias"])


def test_verificacao_ajuste_critico_autorizado():
    from app.verificacao import OpcoesVerificacao, verificar
    df = _df([{"Material": "1", "Descrição": "A"}, {"Material": "1", "Descrição": "B"}])
    r = verificar(df, OpcoesVerificacao(conjunto="cadastro_materiais", aplicar_criticos=True))
    assert r["status"] == "OK"
    assert r["requer_revisao"] is True
    assert len(r["df_tratado"]) == 1


def test_verificacao_coluna_obrigatoria_ausente():
    from app.leitura import ErroValidacao
    from app.verificacao import OpcoesVerificacao, verificar
    with pytest.raises(ErroValidacao):
        verificar(_df([{"Qualquer": "1"}]), OpcoesVerificacao(conjunto="cadastro_materiais"))


# ------------------------------- API ---------------------------------------

def test_api_conciliacao_ponta_a_ponta(cliente):
    sap = _xlsx([{"Material": "0001", "UMB": "PC"}, {"Material": "0002", "UMB": "PC"}])
    kl = _xlsx([{"Código SAP": "1", "UM": "PC"}, {"Código SAP": "2", "UM": "PC"}])
    resp = cliente.post("/api/conciliacao", files={
        "arquivo_sap": ("sap.xlsx", sap), "arquivo_klassmatt": ("klass.xlsx", kl)},
        headers={"X-Usuario": "teste"})
    dados = resp.json()
    assert resp.status_code == 200
    assert dados["status"] == "OK"
    nomes = [a["nome"] for a in dados["arquivos"]]
    assert "relatorio_conciliacao.xlsx" in nomes
    assert all(a["integro"] for a in dados["arquivos"] if a["categoria"] == "entrada")
    down = cliente.get(f"/api/execucoes/{dados['id']}/arquivos/relatorio_conciliacao.xlsx")
    assert down.status_code == 200
    assert cliente.get("/api/execucoes").json()[0]["id"] == dados["id"]


def test_api_verificacao_preserva_original(cliente):
    conteudo = _xlsx([{"Material": "5", "Descrição": " a "}])
    resp = cliente.post("/api/verificacao", files={"arquivo": ("cad.xlsx", conteudo)},
                        data={"conjunto_regras": "cadastro_materiais"})
    dados = resp.json()
    assert dados["status"] == "OK"
    original = cliente.get(f"/api/execucoes/{dados['id']}/arquivos/original.xlsx")
    assert original.content == conteudo
    assert "cad_tratada.xlsx" in [a["nome"] for a in dados["arquivos"]]


def test_api_arquivo_invalido_vira_nok(cliente):
    resp = cliente.post("/api/verificacao", files={"arquivo": ("x.txt", b"abc")})
    assert resp.json()["status"] == "NOK"


def test_api_id_invalido(cliente):
    assert cliente.get("/api/execucoes/../../etc").status_code == 404
