import { useState } from "react";
import { api } from "../api";

/**
 * Seleção de planilha com leitura prévia de abas e colunas.
 * valor = { arquivo, aba, chave, info }
 */
export default function SeletorArquivo({ id, titulo, ajuda, valor, onChange, campoChave, extensoes }) {
  const [lendo, setLendo] = useState(false);
  const [erro, setErro] = useState("");
  const [arrastando, setArrastando] = useState(false);

  async function inspecionar(arquivo, aba) {
    setLendo(true);
    setErro("");
    try {
      const info = await api.inspecionar(arquivo, aba);
      const chave = campoChave ? info.sugestoes?.[campoChave] || "" : "";
      onChange({ arquivo, aba: info.aba_usada || "", chave, info });
    } catch (e) {
      setErro(e.message);
      onChange({ arquivo: null, aba: "", chave: "", info: null });
    } finally {
      setLendo(false);
    }
  }

  function escolher(lista) {
    const arquivo = lista?.[0];
    if (arquivo) inspecionar(arquivo);
  }

  const info = valor.info;

  return (
    <fieldset className="seletor">
      <legend>{titulo}</legend>
      {ajuda && <p className="ajuda">{ajuda}</p>}

      <label
        htmlFor={id}
        className={`zona-arquivo${arrastando ? " arrastando" : ""}${valor.arquivo ? " preenchida" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setArrastando(true); }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => { e.preventDefault(); setArrastando(false); escolher(e.dataTransfer.files); }}
      >
        <input
          id={id}
          type="file"
          accept={extensoes.join(",")}
          className="visualmente-oculto"
          onChange={(e) => { escolher(e.target.files); e.target.value = ""; }}
        />
        {lendo ? (
          <span>Lendo a planilha…</span>
        ) : valor.arquivo ? (
          <span>
            <strong>{valor.arquivo.name}</strong>
            <span className="discreto"> {info?.linhas?.toLocaleString("pt-BR")} linhas, {info?.colunas?.length} colunas. Clique para trocar.</span>
          </span>
        ) : (
          <span>Arraste a planilha aqui ou <u>escolha um arquivo</u> ({extensoes.join(", ")})</span>
        )}
      </label>

      {erro && <p className="erro-campo" role="alert">{erro}</p>}

      {info && (
        <div className="linha-campos">
          {info.abas?.length > 0 && (
            <label className="campo">
              <span>Aba</span>
              <select value={valor.aba} onChange={(e) => inspecionar(valor.arquivo, e.target.value)}>
                {info.abas.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
          )}
          {campoChave && (
            <label className="campo">
              <span>Coluna do código</span>
              <select value={valor.chave} onChange={(e) => onChange({ ...valor, chave: e.target.value })}>
                <option value="">Identificar automaticamente</option>
                {info.colunas.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          )}
        </div>
      )}
    </fieldset>
  );
}
