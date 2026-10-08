import { useEffect, useState } from "react";
import { NOMES_SERVICO, NOMES_STATUS, api, formatarData } from "../api";

export default function Historico({ abrirExecucao }) {
  const [filtros, setFiltros] = useState({ servico: "", status: "" });
  const [lista, setLista] = useState(null);
  const [indicadores, setIndicadores] = useState([]);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setLista(null);
    api.execucoes(filtros).then(setLista).catch((e) => setErro(e.message));
  }, [filtros]);

  useEffect(() => {
    api.indicadores().then(setIndicadores).catch(() => {});
  }, []);

  const porServico = Object.keys(NOMES_SERVICO).map((s) => {
    const linhas = indicadores.filter((i) => i.servico === s);
    const total = linhas.reduce((n, i) => n + i.quantidade, 0);
    const de = (st) => linhas.find((i) => i.status === st)?.quantidade || 0;
    return { s, total, ok: de("OK"), nok: de("NOK"), erro: de("ERRO_TECNICO") };
  });

  return (
    <>
      <header className="cabecalho-pagina">
        <h1>Histórico</h1>
        <p className="lead">Todas as execuções, com resultado, autor e arquivos. Use para auditoria e para acompanhar a qualidade dos dados.</p>
      </header>

      <section className="secao">
        <h2>Volume por serviço</h2>
        <div className="tabela-rolagem tabela-rolagem-compacta">
          <table>
            <thead><tr><th scope="col">Serviço</th><th scope="col">Execuções</th><th scope="col">OK</th><th scope="col">NOK</th><th scope="col">Erro técnico</th></tr></thead>
            <tbody>
              {porServico.map((l) => (
                <tr key={l.s}>
                  <th scope="row">{NOMES_SERVICO[l.s]}</th>
                  <td className="numerico">{l.total}</td><td className="numerico">{l.ok}</td>
                  <td className="numerico">{l.nok}</td><td className="numerico">{l.erro}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="secao">
        <h2>Execuções</h2>
        <div className="filtros">
          <label className="campo">
            <span>Serviço</span>
            <select value={filtros.servico} onChange={(e) => setFiltros({ ...filtros, servico: e.target.value })}>
              <option value="">Todos</option>
              {Object.entries(NOMES_SERVICO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="campo">
            <span>Status</span>
            <select value={filtros.status} onChange={(e) => setFiltros({ ...filtros, status: e.target.value })}>
              <option value="">Todos</option>
              {Object.entries(NOMES_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>

        {erro && <p className="erro-campo" role="alert">{erro}</p>}
        {!lista ? <p className="discreto">Carregando…</p> : lista.length === 0 ? (
          <p className="vazio">Nenhuma execução com esses filtros.</p>
        ) : (
          <div className="tabela-rolagem">
            <table>
              <thead>
                <tr><th scope="col">Data</th><th scope="col">Serviço</th><th scope="col">Status</th><th scope="col">Arquivos</th><th scope="col">Usuário</th><th scope="col">Regras</th><th scope="col"><span className="visualmente-oculto">Abrir</span></th></tr>
              </thead>
              <tbody>
                {lista.map((e) => (
                  <tr key={e.id}>
                    <td>{formatarData(e.criado_em)}</td>
                    <td>{NOMES_SERVICO[e.servico]}</td>
                    <td><span className={`pilula pilula-${e.status.toLowerCase()}`}>{NOMES_STATUS[e.status]}</span></td>
                    <td>{e.arquivos.filter((a) => a.categoria === "entrada").map((a) => a.nome_original).join(", ")}</td>
                    <td>{e.usuario}</td>
                    <td>{e.conjunto_regras} {e.versao_regras}</td>
                    <td><button type="button" className="link-discreto" onClick={() => abrirExecucao(e.id)}>Abrir</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
