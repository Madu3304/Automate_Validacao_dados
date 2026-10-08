"""
Regras de negócio versionadas.

Todas as decisões (o que comparar, o que é bloqueante, o que pode ser ajustado
automaticamente) ficam aqui, separadas do código de execução. Qualquer mudança
deve gerar uma nova versão e passar pela aprovação da Governança de Dados Mestres.
"""

# ---------------------------------------------------------------------------
# Serviço A: Conciliação SAP x Klassmatt
# ---------------------------------------------------------------------------

MODOS_NORMALIZACAO = {
    "remover_zeros_esquerda": "Remover zeros à esquerda de códigos numéricos (000000000000012345 vira 12345)",
    "completar_zeros_18": "Completar códigos numéricos com zeros até 18 posições (padrão do campo MATNR)",
    "manter": "Comparar o código como está, apenas sem espaços e em maiúsculas",
}

_ALIASES_CODIGO = ["material", "matnr", "codigo_material", "cod_material", "codigo_sap", "codigo"]
_ALIASES_DESCRICAO = ["descricao", "texto_breve", "texto_breve_material", "maktx", "descricao_material",
                      "descricao_curta", "descricao_padronizada"]
_ALIASES_UNIDADE = ["unidade", "um", "umb", "meins", "unidade_medida", "unidade_de_medida"]
_ALIASES_NCM = ["ncm", "steuc", "codigo_ncm"]

REGRAS_CONCILIACAO = {
    "id": "conciliacao_sap_klassmatt",
    "versao": "1.0.0",
    "normalizacao_chave_padrao": "remover_zeros_esquerda",
    # Ordem importa: o primeiro alias encontrado vira a coluna chave.
    "aliases_chave_sap": ["material", "matnr", "codigo_material", "cod_material", "codigo_sap", "codigo"],
    "aliases_chave_klassmatt": ["codigo_sap", "codigo_erp", "material", "codigo_material", "cod_material", "codigo"],
    "formato_chave": r"[A-Z0-9][A-Z0-9\-_./]{0,39}",
    "criticidade_tipos": {
        "CHAVE_VAZIA_SAP": "bloqueante",
        "CHAVE_VAZIA_KLASSMATT": "bloqueante",
        "FORMATO_CHAVE_INVALIDO": "aviso",
        "DUPLICIDADE_SAP": "bloqueante",
        "DUPLICIDADE_KLASSMATT": "bloqueante",
        "AUSENTE_NO_KLASSMATT": "bloqueante",
        "AUSENTE_NO_SAP": "aviso",
        "DIFERENCA_CAMPO": "aviso",  # sobrescrita pela criticidade de cada campo
    },
    # comparacao: "texto" ignora acentos, caixa e espaços; "exata" ignora só caixa e espaços
    # nas pontas; "digitos" compara apenas os números (útil para NCM com pontos).
    "campos_comparados": [
        {"campo": "Descrição", "sap": _ALIASES_DESCRICAO,
         "klassmatt": ["descricao_curta", "descricao_padronizada", "descricao", "descricao_sap"],
         "comparacao": "texto", "criticidade": "aviso"},
        {"campo": "Unidade de medida", "sap": _ALIASES_UNIDADE, "klassmatt": _ALIASES_UNIDADE,
         "comparacao": "exata", "criticidade": "bloqueante"},
        {"campo": "NCM", "sap": _ALIASES_NCM, "klassmatt": _ALIASES_NCM,
         "comparacao": "digitos", "criticidade": "bloqueante"},
        {"campo": "Grupo de mercadorias", "sap": ["grupo_mercadorias", "grupo_de_mercadorias", "matkl", "grupo"],
         "klassmatt": ["grupo_mercadorias", "grupo_de_mercadorias", "grupo", "classe"],
         "comparacao": "exata", "criticidade": "aviso"},
    ],
}

# ---------------------------------------------------------------------------
# Serviço B: Verificação e ajuste de planilha
# ---------------------------------------------------------------------------
# Tipos de regra:
#   caracteres_invalidos, espacos, maiusculas, completar_zeros, somente_digitos, data  -> ajustes
#   obrigatorio, formato, dominio                                                      -> apenas detecção
#   duplicidade                                                                         -> ajuste crítico
# "critica": True exige autorização explícita e gera pendência de revisão humana.

UNIDADES_APROVADAS = ["UN", "PC", "KG", "G", "M", "M2", "M3", "L", "ML", "CX", "PCT", "RL", "JG",
                      "PAR", "T", "CJ", "BR", "SC", "TB"]

CONJUNTOS_VERIFICACAO = {
    "cadastro_materiais": {
        "id": "cadastro_materiais",
        "nome": "Cadastro de materiais",
        "versao": "1.0.0",
        "descricao": "Planilhas de carga ou revisão de materiais com código, descrição, unidade, NCM e datas.",
        "colunas_obrigatorias": [
            {"nome": "Código do material", "aliases": _ALIASES_CODIGO},
            {"nome": "Descrição", "aliases": _ALIASES_DESCRICAO},
        ],
        "regras": [
            {"id": "caracteres_invalidos", "tipo": "caracteres_invalidos", "colunas": "todas", "critica": False,
             "descricao": "Remove caracteres de controle, quebras de linha e espaços invisíveis"},
            {"id": "espacos_extras", "tipo": "espacos", "colunas": "todas", "critica": False,
             "descricao": "Remove espaços no início, no fim e espaços repetidos"},
            {"id": "texto_maiusculo", "tipo": "maiusculas", "colunas": _ALIASES_DESCRICAO + _ALIASES_UNIDADE,
             "critica": False, "descricao": "Padroniza descrição e unidade em letras maiúsculas"},
            {"id": "zeros_codigo", "tipo": "completar_zeros", "colunas": _ALIASES_CODIGO, "tamanho": 18,
             "critica": False, "descricao": "Completa códigos numéricos com zeros à esquerda até 18 posições"},
            {"id": "ncm_digitos", "tipo": "somente_digitos", "colunas": _ALIASES_NCM, "critica": False,
             "descricao": "Remove pontos, traços e espaços do NCM"},
            {"id": "datas", "tipo": "data", "colunas": "auto", "formato_saida": "%d/%m/%Y", "critica": False,
             "descricao": "Padroniza datas no formato dd/mm/aaaa"},
            {"id": "obrigatorios_preenchidos", "tipo": "obrigatorio", "colunas": "obrigatorias",
             "severidade": "bloqueante", "descricao": "Código e descrição devem estar preenchidos"},
            {"id": "ncm_formato", "tipo": "formato", "colunas": _ALIASES_NCM, "padrao": r"\d{8}",
             "permite_vazio": True, "severidade": "aviso", "descricao": "NCM deve ter 8 dígitos"},
            {"id": "unidade_aprovada", "tipo": "dominio", "colunas": _ALIASES_UNIDADE,
             "valores": UNIDADES_APROVADAS, "permite_vazio": True, "severidade": "aviso",
             "descricao": "Unidade de medida deve estar na lista aprovada"},
            {"id": "duplicidade_codigo", "tipo": "duplicidade", "colunas": _ALIASES_CODIGO, "critica": True,
             "descricao": "Remove linhas com código repetido, mantendo a primeira ocorrência"},
        ],
    },
    "limpeza_geral": {
        "id": "limpeza_geral",
        "nome": "Limpeza geral",
        "versao": "1.0.0",
        "descricao": "Qualquer planilha: remove caracteres inválidos e espaços extras, padroniza datas e trata linhas repetidas.",
        "colunas_obrigatorias": [],
        "regras": [
            {"id": "caracteres_invalidos", "tipo": "caracteres_invalidos", "colunas": "todas", "critica": False,
             "descricao": "Remove caracteres de controle, quebras de linha e espaços invisíveis"},
            {"id": "espacos_extras", "tipo": "espacos", "colunas": "todas", "critica": False,
             "descricao": "Remove espaços no início, no fim e espaços repetidos"},
            {"id": "datas", "tipo": "data", "colunas": "auto", "formato_saida": "%d/%m/%Y", "critica": False,
             "descricao": "Padroniza datas no formato dd/mm/aaaa"},
            {"id": "linhas_repetidas", "tipo": "duplicidade", "colunas": "todas", "critica": True,
             "descricao": "Remove linhas totalmente repetidas, mantendo a primeira ocorrência"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Rótulos usados no relatório e na interface
# ---------------------------------------------------------------------------

ROTULOS_TIPOS = {
    "CHAVE_VAZIA_SAP": "Código vazio no SAP",
    "CHAVE_VAZIA_KLASSMATT": "Código vazio no Klassmatt",
    "FORMATO_CHAVE_INVALIDO": "Código fora do formato",
    "DUPLICIDADE_SAP": "Código duplicado no SAP",
    "DUPLICIDADE_KLASSMATT": "Código duplicado no Klassmatt",
    "AUSENTE_NO_KLASSMATT": "Existe no SAP, falta no Klassmatt",
    "AUSENTE_NO_SAP": "Existe no Klassmatt, falta no SAP",
    "DIFERENCA_CAMPO": "Campo diferente",
    "CAMPO_OBRIGATORIO_VAZIO": "Campo obrigatório vazio",
    "FORMATO_INVALIDO": "Formato inválido",
    "VALOR_NAO_PERMITIDO": "Valor fora da lista aprovada",
    "DATA_NAO_RECONHECIDA": "Data não reconhecida",
    "TAMANHO_EXCEDIDO": "Tamanho acima do permitido",
    "DUPLICIDADE": "Linha duplicada",
}

ROTULOS_TOTAIS = {
    "registros_sap": "Linhas no SAP",
    "registros_klassmatt": "Linhas no Klassmatt",
    "codigos_unicos_sap": "Códigos únicos no SAP",
    "codigos_unicos_klassmatt": "Códigos únicos no Klassmatt",
    "correspondencias": "Códigos nas duas bases",
    "correspondencias_sem_divergencia": "Códigos conciliados sem diferença",
    "ausentes_no_klassmatt": "Faltam no Klassmatt",
    "ausentes_no_sap": "Faltam no SAP",
    "codigos_duplicados_sap": "Duplicados no SAP",
    "codigos_duplicados_klassmatt": "Duplicados no Klassmatt",
    "diferencas_de_campo": "Diferenças de campo",
    "divergencias_bloqueantes": "Divergências bloqueantes",
    "avisos": "Avisos",
    "linhas_entrada": "Linhas recebidas",
    "linhas_saida": "Linhas na cópia tratada",
    "linhas_removidas": "Linhas removidas",
    "celulas_ajustadas": "Células ajustadas",
    "ajustes_criticos": "Ajustes críticos",
    "ocorrencias_bloqueantes": "Ocorrências bloqueantes",
    "ocorrencias_aviso": "Ocorrências de aviso",
}
