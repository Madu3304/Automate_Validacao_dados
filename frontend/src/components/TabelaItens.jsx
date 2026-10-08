import { useMemo, useState } from "react";

const POR_PAGINA = 50;

/**
 * Tabela com filtros por coluna (selects), busca livre e paginação.
 * colunas: [{ chave, titulo, formatar?(valor, item), classe?(item) }]
 * filtros: [{ chave, titulo, rotulo?(valor) }]
 */
export default function TabelaItens({ legenda, colunas, itens, filtros = [], total, limite, vazio }) {
  const [selecao, setSelecao] = useState({});
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(0);

  const opcoes = useMemo(
    () => Object.fromEntries(filtros.map((f) => [f.chave, [...new Set(itens.map((i) => i[f.chave]))].sort()])),
    [itens, filtros]
  );

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return itens.filter((item) =>
      filtros.every((f) => !selecao[f.chave] || String(item[f.chave]) === selecao[f.chave]) &&
      (!termo || colunas.some((c) => String(item[c.chave] ?? "").toLowerCase().includes(termo)))
    );
  }, [itens, selecao, busca, filtros, colunas]);

  const paginas = Math.max(1, Math.ceil(filtrados.length / POR_PAGINA));
  const atual = Math.min(pagina, paginas - 1);
  const visiveis = filtrados.slice(atual * POR_PAGINA, (atual + 1) * POR_PAGINA);

  if (!itens.length) return <p className="vazio">{vazio}</p>;

  return (
    <div className="tabela-bloco">
      <div className="filtros">
        {filtros.map((f) => (
          <label className="campo" key={f.chave}>
            <span>{f.titulo}</span>
            <select
              value={selecao[f.chave] || ""}
              onChange={(e) => { setSelecao({ ...selecao, [f.chave]: e.target.value }); setPagina(0); }}
            >
              <option value="">Todos</option>
              {opcoes[f.chave].map((v) => (
                <option key={String(v)} value={String(v)}>{f.rotulo ? f.rotulo(v) : String(v)}</option>
              ))}
            </select>
          </label>
        ))}
        <label className="campo campo-busca">
          <span>Buscar</span>
          <input type="search" value={busca} placeholder="Código, valor, coluna…"
            onChange={(e) => { setBusca(e.target.value); setPagina(0); }} />
        </label>
      </div>

      <p className="contagem">
        {filtrados.length.toLocaleString("pt-BR")} de {itens.length.toLocaleString("pt-BR")} itens
        {total > itens.length && ` (a tela mostra os ${limite.toLocaleString("pt-BR")} primeiros de ${total.toLocaleString("pt-BR")}; o relatório traz todos)`}
      </p>

      <div className="tabela-rolagem">
        <table>
          <caption className="visualmente-oculto">{legenda}</caption>
          <thead>
            <tr>{colunas.map((c) => <th key={c.chave} scope="col">{c.titulo}</th>)}</tr>
          </thead>
          <tbody>
            {visiveis.map((item, i) => (
              <tr key={atual * POR_PAGINA + i}>
                {colunas.map((c) => (
                  <td key={c.chave} className={c.classe ? c.classe(item) : undefined}>
                    {c.formatar ? c.formatar(item[c.chave], item) : String(item[c.chave] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {paginas > 1 && (
        <nav className="paginacao" aria-label="Paginação">
          <button type="button" className="botao-secundario" disabled={atual === 0} onClick={() => setPagina(atual - 1)}>Anterior</button>
          <span>Página {atual + 1} de {paginas}</span>
          <button type="button" className="botao-secundario" disabled={atual >= paginas - 1} onClick={() => setPagina(atual + 1)}>Próxima</button>
        </nav>
      )}
    </div>
  );
}
