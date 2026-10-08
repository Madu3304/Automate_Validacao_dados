import { useEffect, useState } from "react";
import { NOMES_SERVICO, api, formatarData } from "../api";

export default function Inicio({ ir, abrirExecucao }) {
  const [recentes, setRecentes] = useState([]);

  useEffect(() => {
    api.execucoes().then((l) => setRecentes(l.slice(0, 6))).catch(() => setRecentes([]));
  }, []);

  return (
    <>
      <header className="cabecalho-pagina">
        <h1>Qual serviço você precisa hoje?</h1>
        <p className="lead">
          Os dois serviços usam regras aprovadas pela Governança de Dados Mestres. Cada execução fica registrada,
          com os arquivos originais preservados e os relatórios disponíveis para download.
        </p>
      </header>

      <div className="escolhas">
        <button type="button" className="escolha" onClick={() => ir("conciliacao")}>
          <span className="escolha-titulo">Conciliar SAP com Klassmatt</span>
          <span className="escolha-linha"><b>Você envia</b> a extração de materiais do SAP e a do Klassmatt.</span>
          <span className="escolha-linha"><b>Você recebe</b> OK ou NOK, as divergências classificadas e o relatório.</span>
        </button>
        <button type="button" className="escolha" onClick={() => ir("verificacao")}>
          <span className="escolha-titulo">Verificar e ajustar uma planilha</span>
          <span className="escolha-linha"><b>Você envia</b> uma planilha e escolhe o conjunto de regras.</span>
          <span className="escolha-linha"><b>Você recebe</b> uma cópia tratada e o registro de cada alteração. O original fica intacto.</span>
        </button>
      </div>

      <section className="secao">
        <h2>Últimas execuções</h2>
        {recentes.length === 0 ? (
          <p className="vazio">Nenhuma execução ainda. Escolha um serviço acima para começar.</p>
        ) : (
          <ul className="lista-recentes">
            {recentes.map((e) => (
              <li key={e.id}>
                <button type="button" className="linha-recente" onClick={() => abrirExecucao(e.id)}>
                  <span className={`pilula pilula-${e.status.toLowerCase()}`}>{e.status === "ERRO_TECNICO" ? "Erro" : e.status}</span>
                  <span className="recente-servico">{NOMES_SERVICO[e.servico]}</span>
                  <span className="discreto">{e.arquivos.filter((a) => a.categoria === "entrada").map((a) => a.nome_original).join(" e ")}</span>
                  <span className="discreto recente-data">{formatarData(e.criado_em)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
