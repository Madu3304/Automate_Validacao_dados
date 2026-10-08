# Plataforma de Governança de Dados Mestres: SAP x Klassmatt

Mini sistema que implementa a **Opção 3** do documento de arquitetura: uma aplicação com dois serviços.

- **Serviço A: Conciliação SAP x Klassmatt.** Recebe as duas planilhas, valida estrutura, normaliza o código, compara as fontes, classifica divergências em bloqueantes ou avisos, gera relatório e retorna `OK`, `NOK` ou `ERRO_TECNICO`.
- **Serviço B: Verificação e ajuste de planilha.** Recebe uma planilha e um conjunto de regras, detecta problemas, aplica os ajustes autorizados numa **cópia**, registra cada alteração e devolve a planilha tratada e o relatório. O original fica intacto (somente leitura, com conferência de hash SHA-256).

## Correspondência com a arquitetura do documento

| Documento (Power Platform) | Este projeto |
|---|---|
| Power Apps (telas, upload, seleção de serviço) | `frontend/` em React |
| Power Automate (orquestração, validação, registro) | `backend/app/main.py` (FastAPI) |
| Regras determinísticas (Office Scripts / ações do fluxo) | `conciliacao.py`, `verificacao.py`, `regras.py` |
| Agente do Copilot Studio (classifica e explica) | `agente.py` (explicação local ou endpoint externo) |
| SharePoint / Dataverse (arquivos e histórico) | `dados/execucoes/<id>/` + SQLite `dados/execucoes.db` |

As decisões de negócio ficam todas em `backend/app/regras.py`, versionadas. A comparação e a limpeza nunca dependem de texto generativo: o agente só explica o resultado e recebe apenas indicadores agregados (nenhum código, descrição ou valor das planilhas).

## Como executar

Requisitos: Python 3.11+ e Node.js 18+.

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/gerar_exemplos.py   # cria planilhas fictícias em backend/exemplos/
uvicorn app.main:app --reload --port 8000

# Frontend (outro terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

A documentação interativa da API fica em http://localhost:8000/docs.

Testes do backend: `cd backend && pytest`.

## Endpoints

| Método | Rota | Uso |
|---|---|---|
| GET | `/api/servicos` | Catálogo de serviços, conjuntos de regras e rótulos |
| POST | `/api/inspecionar` | Lê abas e colunas de uma planilha (sem registrar execução) |
| POST | `/api/conciliacao` | `arquivo_sap`, `arquivo_klassmatt`, opcionais `aba_*`, `chave_*`, `normalizacao_chave` |
| POST | `/api/verificacao` | `arquivo`, `conjunto_regras`, opcionais `aba`, `aplicar_criticos`, `regras_desativadas` |
| GET | `/api/execucoes` | Histórico (filtros `servico`, `status`) |
| GET | `/api/execucoes/{id}` | Detalhe com divergências, ocorrências e alterações |
| GET | `/api/execucoes/{id}/arquivos/{nome}` | Download de relatórios, cópia tratada e originais |
| GET | `/api/indicadores` | Volume e status por serviço |

O usuário é enviado no cabeçalho `X-Usuario`. Em produção, troque por autenticação corporativa (Entra ID) e leia o usuário do token.

## Regras implementadas

**Conciliação** (versão 1.0.0): código vazio, código fora do formato, duplicidade em cada base, ausente no Klassmatt (bloqueante), ausente no SAP (aviso), e comparação de Descrição (aviso, ignora acentos, caixa e espaços), Unidade de medida (bloqueante), NCM (bloqueante, compara só dígitos) e Grupo de mercadorias (aviso). Campos sem coluna correspondente nas duas planilhas são listados como não comparados. A normalização do código pode remover zeros à esquerda, completar até 18 posições (MATNR) ou manter o valor.

**Verificação**, conjunto "Cadastro de materiais": remove caracteres invisíveis e quebras de linha, remove espaços extras, padroniza descrição e unidade em maiúsculas, completa zeros no código, deixa só dígitos no NCM, padroniza datas em dd/mm/aaaa (inclui número de série do Excel), aponta obrigatórios vazios, NCM sem 8 dígitos e unidade fora da lista aprovada. A remoção de duplicidades é **ajuste crítico**: só é aplicada com autorização explícita e fica marcada para revisão humana. O conjunto "Limpeza geral" serve para qualquer planilha.

Para criar uma regra nova, acrescente-a em `regras.py` e suba a versão do conjunto. Para um tipo de regra novo, crie a função em `verificacao.py` e registre em `_EXECUTORES`.

## Integração com o agente (opcional)

Defina `GDM_AGENTE_URL` com um endpoint HTTP (por exemplo, um fluxo do Power Automate com gatilho HTTP que executa o agente do Copilot Studio). O backend envia `{servico, status, totais, por_tipo, requer_revisao}` e espera `{"texto": "..."}`. Se o endpoint falhar, a explicação local é usada.

## Configuração (variáveis de ambiente)

| Variável | Padrão | Descrição |
|---|---|---|
| `GDM_DATA_DIR` | `backend/dados` | Pasta do banco e dos arquivos |
| `GDM_MAX_UPLOAD_MB` | 20 | Tamanho máximo por arquivo |
| `GDM_MAX_LINHAS` | 200000 | Linhas máximas por planilha |
| `GDM_LIMITE_ITENS_API` | 3000 | Itens devolvidos na tela (o relatório sempre traz todos) |
| `GDM_CORS` | `http://localhost:5173` | Origens permitidas |
| `GDM_AGENTE_URL` | vazio | Endpoint do agente externo |
| `VITE_API_URL` (frontend) | vazio | URL da API em produção |

## Limitações conhecidas

- O processamento é síncrono. Para arquivos muito grandes, mova a execução para uma fila (Celery, RQ ou Azure Functions) e faça a tela consultar o status.
- A planilha tratada é gravada com todos os valores como texto, o que preserva zeros à esquerda; fórmulas e formatação do original não são copiadas.
- Lê a aba escolhida (ou a primeira). Planilhas com várias abas precisam de uma execução por aba.
- Antes de usar dados reais, valide as regras com a área de negócio e teste com arquivos anonimizados (as premissas da seção 6 do documento continuam valendo).
