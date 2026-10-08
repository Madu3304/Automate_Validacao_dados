// Cliente da API. Em produção defina VITE_API_URL (ex.: https://gdm.empresa.com).
const BASE = import.meta.env.VITE_API_URL ?? "";

let usuarioAtual = "";
export function definirUsuario(nome) {
  usuarioAtual = nome;
}

async function requisitar(caminho, opcoes = {}) {
  const headers = { ...(opcoes.headers || {}) };
  // Cabeçalhos HTTP aceitam apenas Latin-1: acentos do português passam, emojis não.
  if (usuarioAtual) headers["X-Usuario"] = usuarioAtual.replace(/[^\x20-\xff]/g, "");
  let resp;
  try {
    resp = await fetch(`${BASE}${caminho}`, { ...opcoes, headers });
  } catch {
    throw new Error("Não foi possível falar com o servidor. Verifique se a API está em execução.");
  }
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detalhe = Array.isArray(dados.detail)
      ? dados.detail.map((d) => d.msg).join("; ")
      : dados.detail;
    throw new Error(detalhe || `O servidor respondeu com erro ${resp.status}.`);
  }
  return dados;
}

function formulario(campos) {
  const fd = new FormData();
  Object.entries(campos).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") fd.append(k, v);
  });
  return fd;
}

export const api = {
  servicos: () => requisitar("/api/servicos"),
  inspecionar: (arquivo, aba) =>
    requisitar("/api/inspecionar", { method: "POST", body: formulario({ arquivo, aba }) }),
  conciliar: (campos) =>
    requisitar("/api/conciliacao", { method: "POST", body: formulario(campos) }),
  verificar: (campos) =>
    requisitar("/api/verificacao", { method: "POST", body: formulario(campos) }),
  execucoes: ({ servico, status } = {}) => {
    const q = new URLSearchParams();
    if (servico) q.set("servico", servico);
    if (status) q.set("status", status);
    return requisitar(`/api/execucoes?${q}`);
  },
  execucao: (id) => requisitar(`/api/execucoes/${id}`),
  indicadores: () => requisitar("/api/indicadores"),
  urlArquivo: (id, nome) => `${BASE}/api/execucoes/${id}/arquivos/${encodeURIComponent(nome)}`,
};

export const NOMES_SERVICO = {
  conciliacao: "Conciliação SAP x Klassmatt",
  verificacao: "Verificação e ajuste de planilha",
};

export const NOMES_STATUS = { OK: "OK", NOK: "NOK", ERRO_TECNICO: "Erro técnico" };

export function formatarData(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function formatarNumero(n) {
  return typeof n === "number" ? n.toLocaleString("pt-BR") : n;
}
