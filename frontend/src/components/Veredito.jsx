import { NOMES_SERVICO, NOMES_STATUS, formatarData } from "../api";

const CLASSE = { OK: "ok", NOK: "nok", ERRO_TECNICO: "erro" };

export default function Veredito({ execucao }) {
  const { status, servico, explicacao, mensagem, criado_em, usuario, duracao_ms, versao_regras, id, origem_explicacao } = execucao;
  return (
    <section className={`veredito ${CLASSE[status] || "erro"}`} aria-live="polite">
      <div className="veredito-status">
        <span className="veredito-palavra">{NOMES_STATUS[status] || status}</span>
        <span className="veredito-servico">{NOMES_SERVICO[servico]}</span>
      </div>
      <div className="veredito-texto">
        <p className="veredito-mensagem">{mensagem}</p>
        {explicacao && explicacao !== mensagem && <p>{explicacao}</p>}
        <p className="veredito-meta">
          Execução {id}, por {usuario}, em {formatarData(criado_em)}. Regras versão {versao_regras}.
          Processada em {(duracao_ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s.
          {origem_explicacao === "agente" && " Explicação gerada pelo agente."}
        </p>
      </div>
    </section>
  );
}
