"""Configurações da aplicação (podem ser sobrescritas por variáveis de ambiente)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("GDM_DATA_DIR", BASE_DIR / "dados"))
ARQUIVOS_DIR = DATA_DIR / "execucoes"
DB_PATH = DATA_DIR / "execucoes.db"

MAX_UPLOAD_MB = int(os.getenv("GDM_MAX_UPLOAD_MB", "20"))
MAX_LINHAS = int(os.getenv("GDM_MAX_LINHAS", "200000"))
EXTENSOES_PERMITIDAS = {".xlsx", ".xlsm", ".csv"}

# Quantidade máxima de itens devolvidos na API (o relatório Excel sempre traz todos).
LIMITE_ITENS_API = int(os.getenv("GDM_LIMITE_ITENS_API", "3000"))

CORS_ORIGINS = [o.strip() for o in os.getenv("GDM_CORS", "http://localhost:5173").split(",") if o.strip()]

# Endpoint opcional de um agente externo (ex.: Copilot Studio via Power Automate/HTTP).
# Recebe apenas indicadores agregados, nunca o conteúdo das planilhas.
AGENTE_URL = os.getenv("GDM_AGENTE_URL", "").strip()
AGENTE_TIMEOUT_S = int(os.getenv("GDM_AGENTE_TIMEOUT_S", "20"))
