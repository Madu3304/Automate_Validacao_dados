"""
Gera planilhas fictícias (anonimizadas) com problemas conhecidos para testar os dois serviços.

Uso:  python scripts/gerar_exemplos.py   ->  cria a pasta exemplos/
"""
from pathlib import Path

import pandas as pd

DESTINO = Path(__file__).resolve().parent.parent / "exemplos"

ITENS = [
    ("TUBO PVC SOLDÁVEL 25MM BARRA 6M", "BR", "3917.23.00", "TUBOS"),
    ("JOELHO 90 PVC SOLDÁVEL 25MM", "PC", "3917.40.00", "CONEXOES"),
    ("LUVA PVC SOLDÁVEL 32MM", "PC", "3917.40.00", "CONEXOES"),
    ("ADESIVO PLÁSTICO PVC 175G", "UN", "3506.91.10", "ADESIVOS"),
    ("REGISTRO GAVETA 3/4", "PC", "8481.80.95", "METAIS"),
    ("CAIXA D'ÁGUA 500L", "UN", "3925.10.00", "RESERVATORIOS"),
    ("TÊ PVC SOLDÁVEL 50MM", "PC", "3917.40.00", "CONEXOES"),
    ("FITA VEDA ROSCA 18MM X 10M", "RL", "3919.10.00", "ACESSORIOS"),
    ("CURVA 45 PVC ESGOTO 100MM", "PC", "3917.40.00", "CONEXOES"),
    ("TUBO PVC ESGOTO 100MM BARRA 6M", "BR", "3917.23.00", "TUBOS"),
]


def gerar():
    DESTINO.mkdir(exist_ok=True)
    sap, klass = [], []
    for i in range(30):
        codigo = 100001 + i
        desc, um, ncm, grupo = ITENS[i % len(ITENS)]
        sap.append({"Material": str(codigo).zfill(18), "Texto breve material": desc, "UMB": um,
                    "NCM": ncm.replace(".", ""), "Grupo de mercadorias": grupo})
        klass.append({"Código SAP": str(codigo), "Descrição Curta": desc, "UM": um, "NCM": ncm,
                      "Grupo": grupo, "Status Klassmatt": "ATIVO"})

    # Problemas planejados
    klass = [k for k in klass if k["Código SAP"] not in {"100003", "100011", "100020"}]   # faltam no Klassmatt
    klass.append({"Código SAP": "100900", "Descrição Curta": "ITEM SOMENTE NO KLASSMATT", "UM": "UN",
                  "NCM": "3917.40.00", "Grupo": "CONEXOES", "Status Klassmatt": "PENDENTE"})   # falta no SAP
    sap.append(dict(sap[4]))                                         # duplicado no SAP
    sap[6]["UMB"] = "UN"                                             # unidade diferente (bloqueante)
    sap[8]["NCM"] = "39174099"                                       # NCM diferente (bloqueante)
    klass[1]["Descrição Curta"] = "joelho 90  pvc soldavel 25mm"     # só caixa/acento/espaço: não diverge
    klass[12]["Descrição Curta"] = "CAIXA D'AGUA 1000L"              # descrição diferente (aviso)
    sap.append({"Material": "", "Texto breve material": "LINHA SEM CÓDIGO", "UMB": "UN", "NCM": "", "Grupo de mercadorias": ""})

    pd.DataFrame(sap).to_excel(DESTINO / "sap_materiais.xlsx", index=False, sheet_name="SAP")
    pd.DataFrame(klass).to_excel(DESTINO / "klassmatt_materiais.xlsx", index=False, sheet_name="Klassmatt")

    cadastro = pd.DataFrame([
        {"Material": "100001", "Descrição": "  tubo pvc soldável 25mm   barra 6m ", "Unidade": "br", "NCM": "3917.23.00", "Data Criação": "2026-03-15"},
        {"Material": "100002", "Descrição": "Joelho 90\nPVC 25mm", "Unidade": "pc", "NCM": "39174000", "Data Criação": "15/03/2026"},
        {"Material": "100003", "Descrição": "Luva\u200b PVC 32mm", "Unidade": "PÇ", "NCM": "3917400", "Data Criação": "46100"},
        {"Material": "100002", "Descrição": "Joelho 90 PVC 25mm", "Unidade": "PC", "NCM": "39174000", "Data Criação": "16.03.2026"},
        {"Material": "100005", "Descrição": "", "Unidade": "UN", "NCM": "", "Data Criação": "amanhã"},
        {"Material": "", "Descrição": "", "Unidade": "", "NCM": "", "Data Criação": ""},
        {"Material": "100006", "Descrição": "Fita veda rosca 18mm", "Unidade": "rl", "NCM": "3919-10-00", "Data Criação": "20260401"},
    ])
    cadastro.to_excel(DESTINO / "cadastro_para_ajuste.xlsx", index=False, sheet_name="Cadastro")
    print(f"Exemplos gerados em {DESTINO}")


if __name__ == "__main__":
    gerar()
