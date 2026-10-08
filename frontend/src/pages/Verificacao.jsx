import { useState } from "react";
import { api } from "../api";
import SeletorArquivo from "../components/SeletorArquivo";

const VAZIO = { arquivo: null, aba: "", chave: "", info: null };

export default function Verificacao({ catalogo, abrirExecucao }) {
  const conjuntos = catalogo.servicos.find((s) => s.id === "verificacao").conjuntos;
  const [arquivo, setArquivo] = useState(VAZIO);
  const [conjuntoId, setConjuntoId] = useState(conjuntos[0].id);
  const [desativadas, setDesativadas] = useState(new Set());
  const [criticos, setCriticos] = useState(false);
  const [executando, setExecutando] = useState(false);
  const [erro, setErro] = useState("");

  const conjunto = conjuntos.find((c) => c.id === conjuntoId);
  const temCritica = conjunto.regras.some((r) => r.critica && !desativadas.has(r.id));

  function trocarConjunto(id) {
    setConjuntoId(id);
    setDesativadas(new Set());
  }

  function alternar(id) {
    const nova = new Set(desativadas);
    nova.has(id) ? nova.delete(id) : nova.add(id);
    setDesativadas(nova);
  }

  async function enviar(e) {
    e.preventDefault();
    setExecutando(true);
    setErro("");
    try {
      const resultado = await api.verificar({
        arquivo: arquivo.arquivo, aba: arquivo.aba, conjunto_regras: conjuntoId,
        aplicar_criticos: criticos && temCritica ? "true" : "false",
        regras_desativadas: [...desativadas].join(","),
      });
      abrirExecucao(resultado.id, resultado);
    } catch (err) {
      setErro(err.message);
      setExecutando(false);
    }
  }

  return (
    <>
      <header className="cabecalho-pagina">
        <h1>Verificar e ajustar uma planilha</h1>
        <p className="lead">
          As regras geram uma cópia tratada e registram cada alteração. O arquivo que você enviar não é modificado.
        </p>
      </header>

      <form onSubmit={enviar} className="formulario">
        <SeletorArquivo id="arq-verificacao" titulo="Planilha" valor={arquivo} onChange={setArquivo}
          extensoes={catalogo.limites.extensoes} />

        <fieldset className="seletor">
          <legend>Conjunto de regras</legend>
          <div className="opcoes-radio">
            {conjuntos.map((c) => (
              <label key={c.id} className="radio">
                <input type="radio" name="conjunto" checked={conjuntoId === c.id} onChange={() => trocarConjunto(c.id)} />
                <span>
                  <strong>{c.nome}</strong> <span className="discreto">versão {c.versao}</span>
                  <br />{c.descricao}
                  {c.colunas_obrigatorias.length > 0 && (
                    <><br /><span className="discreto">Colunas obrigatórias: {c.colunas_obrigatorias.join(", ")}.</span></>
                  )}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="seletor">
          <legend>Regras que serão aplicadas</legend>
          <p className="ajuda">Desmarque o que não deve rodar nesta execução.</p>
          <ul className="lista-regras">
            {conjunto.regras.map((r) => (
              <li key={r.id}>
                <label className="radio">
                  <input type="checkbox" checked={!desativadas.has(r.id)} onChange={() => alternar(r.id)} />
                  <span>
                    {r.descricao}
                    {r.critica && <span className="marca marca-bloqueante">Ajuste crítico</span>}
                    {["obrigatorio", "formato", "dominio"].includes(r.tipo) && <span className="marca marca-neutra">Só aponta</span>}
                  </span>
                </label>
              </li>
            ))}
          </ul>

          {temCritica && (
            <label className="autorizacao">
              <input type="checkbox" checked={criticos} onChange={(e) => setCriticos(e.target.checked)} />
              <span>
                Autorizo aplicar os ajustes críticos. Eles ficarão marcados para revisão humana antes do uso da planilha.
                Sem autorização, os casos são apenas apontados como ocorrências.
              </span>
            </label>
          )}
        </fieldset>

        {erro && <p className="erro-campo" role="alert">{erro}</p>}

        <div className="acoes">
          <button type="submit" className="botao-primario" disabled={!arquivo.arquivo || executando}>
            {executando ? "Verificando…" : "Verificar e ajustar"}
          </button>
          {!arquivo.arquivo && <span className="discreto">Envie uma planilha para habilitar.</span>}
        </div>
      </form>
    </>
  );
}
