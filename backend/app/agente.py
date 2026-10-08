"""
Camada de explicação do resultado (papel do agente do Copilot Studio na arquitetura).

- Sem configuração: gera a explicação localmente, a partir dos indicadores.
- Com GDM_AGENTE_URL: envia SOMENTE indicadores agregados (status, totais, contagem por tipo)
  para um endpoint externo (ex.: fluxo do Power Automate que executa o agente) e espera
  {"texto": "..."} de volta. Nenhum código, descrição ou valor das planilhas é enviado.
  Se o agente falhar, a explicação local é usada.
"""
import json
import logging
import urllib.request

from .config import AGENTE_TIMEOUT_S, AGENTE_URL

log = logging.getLogger(__name__)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _texto_conciliacao(r: dict) -> str:
    t = r["totais"]
    if r["status"] == "OK":
        partes = [f"Conciliação aprovada: {_plural(t['correspondencias'], 'código está', 'códigos estão')} "
                  f"nas duas bases e não há divergências bloqueantes."]
    else:
        partes = [f"Conciliação reprovada: há {_plural(t['divergencias_bloqueantes'], 'divergência bloqueante', 'divergências bloqueantes')} para corrigir."]

    pontos = []
    if t["ausentes_no_klassmatt"]:
        pontos.append(f"{_plural(t['ausentes_no_klassmatt'], 'código do SAP não tem', 'códigos do SAP não têm')} cadastro no Klassmatt")
    if t["ausentes_no_sap"]:
        pontos.append(f"{_plural(t['ausentes_no_sap'], 'código do Klassmatt não existe', 'códigos do Klassmatt não existem')} no SAP")
    dup = t["codigos_duplicados_sap"] + t["codigos_duplicados_klassmatt"]
    if dup:
        pontos.append(f"{_plural(dup, 'código aparece', 'códigos aparecem')} mais de uma vez na mesma base")
    if t["diferencas_de_campo"]:
        pontos.append(f"{_plural(t['diferencas_de_campo'], 'diferença', 'diferenças')} em campos complementares")
    if pontos:
        partes.append("Pontos encontrados: " + "; ".join(pontos) + ".")
    if t["avisos"] and r["status"] == "OK":
        partes.append(f"Os {_plural(t['avisos'], 'aviso', 'avisos')} não impedem a aprovação, mas merecem revisão.")
    if r["status"] == "NOK":
        partes.append("Sugestão: trate primeiro códigos vazios e duplicados, depois as ausências e, por fim, "
                      "as diferenças de campo. Em seguida, execute a conciliação novamente.")
    return " ".join(partes)


def _texto_verificacao(r: dict) -> str:
    t = r["totais"]
    partes = [f"A cópia tratada tem {_plural(t['linhas_saida'], 'linha', 'linhas')} e "
              f"{_plural(t['celulas_ajustadas'], 'célula foi ajustada', 'células foram ajustadas')} automaticamente. "
              f"O arquivo original foi preservado."]
    if t["linhas_removidas"]:
        partes.append(f"{_plural(t['linhas_removidas'], 'linha foi removida', 'linhas foram removidas')}.")
    if r.get("requer_revisao"):
        partes.append(f"{_plural(t['ajustes_criticos'], 'ajuste crítico precisa', 'ajustes críticos precisam')} "
                      f"de revisão humana antes de usar a planilha.")
    if t["ocorrencias_bloqueantes"]:
        partes.append(f"Ainda há {_plural(t['ocorrencias_bloqueantes'], 'ocorrência bloqueante', 'ocorrências bloqueantes')} "
                      f"que as regras não corrigem sozinhas; veja a lista de ocorrências.")
    elif t["ocorrencias_aviso"]:
        partes.append(f"Há {_plural(t['ocorrencias_aviso'], 'aviso', 'avisos')} para conferir, sem impedir o uso.")
    else:
        partes.append("Nenhuma pendência encontrada.")
    return " ".join(partes)


def explicar(servico: str, resultado: dict) -> dict:
    agregado = {
        "servico": servico,
        "status": resultado["status"],
        "totais": resultado["totais"],
        "por_tipo": resultado.get("por_tipo", {}),
        "requer_revisao": resultado.get("requer_revisao", False),
    }
    if AGENTE_URL:
        try:
            req = urllib.request.Request(AGENTE_URL, data=json.dumps(agregado).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=AGENTE_TIMEOUT_S) as resp:
                texto = json.loads(resp.read().decode("utf-8")).get("texto", "").strip()
            if texto:
                return {"texto": texto, "origem": "agente"}
        except Exception:  # noqa: BLE001
            log.warning("Agente externo indisponível; usando explicação local.", exc_info=True)

    texto = _texto_conciliacao(agregado) if servico == "conciliacao" else _texto_verificacao(agregado)
    return {"texto": texto, "origem": "regras_locais"}
