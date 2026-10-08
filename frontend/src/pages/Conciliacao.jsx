import { useState } from "react";
import { api } from "../api";
import SeletorArquivo from "../components/SeletorArquivo";

const listar = (l) => (l.length > 1 ? `${l.slice(0, -1).join(", ")} e ${l[l.length - 1]}` : l.join(""));

const VAZIO = { arquivo: null, aba: "", chave: "", info: null };

export default function Conciliacao({ catalogo, abrirExecucao }) {
  const servico = catalogo.servicos.find((s) => s.id === "conciliacao");
  const [sap, setSap] = useState(VAZIO);
  const [klassmatt, setKlassmatt] = useState(VAZIO);
  const [normalizacao, setNormalizacao] = useState(servico.normalizacao_padrao);
  const [executando, setExecutando] = useState(false);
  const [erro, setErro] = useState("");

  const pronto = sap.arquivo && klassmatt.arquivo && !executando;

  async function enviar(e) {
    e.preventDefault();
    setExecutando(true);
    setErro("");
    try {
      const resultado = await api.conciliar({
        arquivo_sap: sap.arquivo, arquivo_klassmatt: klassmatt.arquivo,
        aba_sap: sap.aba, aba_klassmatt: klassmatt.aba,
        chave_sap: sap.chave, chave_klassmatt: klassmatt.chave,
        normalizacao_chave: normalizacao,
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
        <h1>Conciliar SAP com Klassmatt</h1>
        <p className="lead">
          Compara os códigos das duas bases e aponta o que falta, o que está duplicado e onde os campos
          complementares não batem ({listar(servico.campos_comparados.map((c) => c.campo))}).
          Regras versão {servico.versao_regras}.
        </p>
      </header>

      <form onSubmit={enviar} className="formulario">
        <div className="duas-colunas">
          <SeletorArquivo id="arq-sap" titulo="Planilha do SAP" ajuda="Extração de materiais (ex.: MM60, SE16N na MARA/MAKT)."
            valor={sap} onChange={setSap} campoChave="chave_sap" extensoes={catalogo.limites.extensoes} />
          <SeletorArquivo id="arq-klassmatt" titulo="Planilha do Klassmatt" ajuda="Exportação com o código SAP de cada item."
            valor={klassmatt} onChange={setKlassmatt} campoChave="chave_klassmatt" extensoes={catalogo.limites.extensoes} />
        </div>

        <fieldset className="seletor">
          <legend>Como comparar os códigos</legend>
          <div className="opcoes-radio">
            {servico.modos_normalizacao.map((m) => (
              <label key={m.id} className="radio">
                <input type="radio" name="normalizacao" value={m.id} checked={normalizacao === m.id}
                  onChange={() => setNormalizacao(m.id)} />
                <span>{m.descricao}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {erro && <p className="erro-campo" role="alert">{erro}</p>}

        <div className="acoes">
          <button type="submit" className="botao-primario" disabled={!pronto}>
            {executando ? "Conciliando…" : "Conciliar"}
          </button>
          {!sap.arquivo || !klassmatt.arquivo ? (
            <span className="discreto">Envie as duas planilhas para habilitar a conciliação.</span>
          ) : null}
        </div>
      </form>
    </>
  );
}
