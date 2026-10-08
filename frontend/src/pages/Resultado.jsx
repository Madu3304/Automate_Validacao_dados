import { useEffect, useState } from "react";
import { api, formatarNumero } from "../api";
import Criticidade from "../components/Criticidade";
import TabelaItens from "../components/TabelaItens";
import Veredito from "../components/Veredito";

// Indicadores em destaque por serviço (os demais ficam no relatório).
const DESTAQUES = {
  conciliacao: ["correspondencias", "correspondencias_sem_divergencia", "ausentes_no_klassmatt", "ausentes_no_sap",
    "codigos_duplicados_sap", "codigos_duplicados_klassmatt", "diferencas_de_campo", "registros_sap", "registros_klassmatt"],
  verificacao: ["linhas_entrada", "linhas_saida", "linhas_removidas", "celulas_ajustadas", "ajustes_criticos",
    "ocorrencias_bloqueantes", "ocorrencias_aviso"],
};

// Torna visíveis quebras de linha, tabulações e caracteres invisíveis removidos pelas regras.
function mostrarInvisiveis(valor) {
  return String(valor ?? "")
    .replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u00a0\u200b-\u200d\u2060\ufeff]/g,
      (c) => `<U+${c.charCodeAt(0).toString(16).toUpperCase().padStart(4, "0")}>`);
}

export default function Resultado({ id, inicial, catalogo, ir }) {
  const [execucao, setExecucao] = useState(inicial || null);
  const [erro, setErro] = useState("");
  const [aba, setAba] = useState("ocorrencias");

  useEffect(() => {
    if (inicial?.id === id) return;
    setExecucao(null);
    api.execucao(id).then(setExecucao).catch((e) => setErro(e.message));
  }, [id, inicial]);

  if (erro) return <p className="erro-campo" role="alert">{erro}</p>;
  if (!execucao) return <p className="discreto">Carregando execução…</p>;

  const { rotulos } = catalogo;
  const totais = execucao.resumo?.totais || {};
  const entradas = execucao.arquivos.filter((a) => a.categoria === "entrada");
  const saidas = execucao.arquivos.filter((a) => a.categoria === "saida");
  const rotuloTipo = (t) => rotulos.tipos[t] || t;

  return (
    <>
      <Veredito execucao={execucao} />

      {execucao.resumo?.requer_revisao && (
        <p className="alerta-revisao" role="note">
          Esta cópia tem ajustes críticos. Revise as linhas marcadas como críticas na lista de alterações antes de usar a planilha.
        </p>
      )}

      {Object.keys(totais).length > 0 && (
        <section className="secao">
          <h2>Indicadores</h2>
          <dl className="indicadores">
            {DESTAQUES[execucao.servico].filter((k) => k in totais).map((k) => (
              <div key={k} className={`indicador${totais[k] > 0 && /ausentes|duplicados|diferencas|bloqueantes|criticos/.test(k) ? " indicador-atencao" : ""}`}>
                <dt>{rotulos.totais[k] || k}</dt>
                <dd>{formatarNumero(totais[k])}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section className="secao">
        <h2>Arquivos</h2>
        <ul className="arquivos">
          {saidas.map((a) => (
            <li key={a.nome}>
              <a className="botao-secundario" href={api.urlArquivo(execucao.id, a.nome)} download>Baixar {a.rotulo.toLowerCase()}</a>
            </li>
          ))}
          {entradas.map((a) => (
            <li key={a.nome}>
              <a className="link-discreto" href={api.urlArquivo(execucao.id, a.nome)} download>
                {a.rotulo}: {a.nome_original}
              </a>
              <span className={`integridade ${a.integro ? "integro" : "violado"}`}>
                {a.integro ? "inalterado" : "alterado ou indisponível"}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {execucao.servico === "conciliacao" && execucao.itens?.divergencias && (
        <section className="secao">
          <h2>Divergências</h2>
          <TabelaItens
            legenda="Divergências da conciliação"
            itens={execucao.itens.divergencias}
            total={execucao.itens_totais.divergencias}
            limite={execucao.limite_itens}
            vazio="Nenhuma divergência. As duas bases estão conciliadas."
            filtros={[
              { chave: "criticidade", titulo: "Criticidade", rotulo: (v) => (v === "bloqueante" ? "Bloqueante" : "Aviso") },
              { chave: "tipo", titulo: "Tipo", rotulo: rotuloTipo },
              { chave: "campo", titulo: "Campo", rotulo: (v) => v || "(sem campo)" },
            ]}
            colunas={[
              { chave: "criticidade", titulo: "Criticidade", formatar: (v) => <Criticidade valor={v} /> },
              { chave: "tipo", titulo: "Tipo", formatar: rotuloTipo },
              { chave: "chave", titulo: "Código", classe: () => "numerico" },
              { chave: "campo", titulo: "Campo" },
              { chave: "valor_sap", titulo: "Valor no SAP" },
              { chave: "valor_klassmatt", titulo: "Valor no Klassmatt" },
              { chave: "linha_sap", titulo: "Linha SAP", classe: () => "numerico" },
              { chave: "linha_klassmatt", titulo: "Linha Klassmatt", classe: () => "numerico" },
              { chave: "mensagem", titulo: "Detalhe", classe: () => "texto-longo" },
            ]}
          />
        </section>
      )}

      {execucao.servico === "verificacao" && execucao.itens?.ocorrencias && (
        <section className="secao">
          <div className="abas" role="tablist">
            <button type="button" role="tab" aria-selected={aba === "ocorrencias"} onClick={() => setAba("ocorrencias")}>
              Ocorrências ({formatarNumero(execucao.itens_totais.ocorrencias)})
            </button>
            <button type="button" role="tab" aria-selected={aba === "alteracoes"} onClick={() => setAba("alteracoes")}>
              Alterações ({formatarNumero(execucao.itens_totais.alteracoes)})
            </button>
          </div>

          {aba === "ocorrencias" ? (
            <TabelaItens
              key="ocorrencias"
              legenda="Ocorrências que as regras apontam e não corrigem"
              itens={execucao.itens.ocorrencias}
              total={execucao.itens_totais.ocorrencias}
              limite={execucao.limite_itens}
              vazio="Nenhuma ocorrência. A planilha atende todas as regras verificadas."
              filtros={[
                { chave: "severidade", titulo: "Severidade", rotulo: (v) => (v === "bloqueante" ? "Bloqueante" : "Aviso") },
                { chave: "tipo", titulo: "Tipo", rotulo: rotuloTipo },
                { chave: "coluna", titulo: "Coluna" },
              ]}
              colunas={[
                { chave: "severidade", titulo: "Severidade", formatar: (v) => <Criticidade valor={v} /> },
                { chave: "linha", titulo: "Linha", classe: () => "numerico" },
                { chave: "coluna", titulo: "Coluna" },
                { chave: "tipo", titulo: "Tipo", formatar: rotuloTipo },
                { chave: "valor", titulo: "Valor" },
                { chave: "mensagem", titulo: "Detalhe", classe: () => "texto-longo" },
              ]}
            />
          ) : (
            <TabelaItens
              key="alteracoes"
              legenda="Alterações aplicadas na cópia tratada"
              itens={execucao.itens.alteracoes}
              total={execucao.itens_totais.alteracoes}
              limite={execucao.limite_itens}
              vazio="Nenhuma alteração foi necessária."
              filtros={[
                { chave: "regra", titulo: "Regra" },
                { chave: "coluna", titulo: "Coluna" },
                { chave: "critico", titulo: "Crítico", rotulo: (v) => (v ? "Sim" : "Não") },
              ]}
              colunas={[
                { chave: "linha", titulo: "Linha", classe: () => "numerico" },
                { chave: "coluna", titulo: "Coluna" },
                { chave: "valor_original", titulo: "Antes", formatar: (v) => <code className="valor">{mostrarInvisiveis(v) || "(vazio)"}</code> },
                { chave: "valor_ajustado", titulo: "Depois", formatar: (v) => <code className="valor">{v}</code> },
                { chave: "descricao_regra", titulo: "Regra" },
                { chave: "critico", titulo: "Crítico", formatar: (v, item) => (v ? <span className="marca marca-bloqueante" title={item.observacao}>Revisar</span> : "") },
              ]}
            />
          )}
        </section>
      )}

      {execucao.resumo?.parametros && (
        <details className="secao parametros">
          <summary>Parâmetros desta execução</summary>
          <Parametros servico={execucao.servico} p={execucao.resumo.parametros} />
        </details>
      )}

      <div className="acoes">
        <button type="button" className="botao-secundario" onClick={() => ir(execucao.servico)}>Nova execução</button>
        <button type="button" className="link-discreto" onClick={() => ir("historico")}>Ver histórico</button>
      </div>
    </>
  );
}

function Parametros({ servico, p }) {
  if (servico === "conciliacao") {
    return (
      <dl className="lista-parametros">
        <dt>Coluna do código</dt><dd>SAP: {p.coluna_chave_sap} (aba {p.aba_sap || "única"}). Klassmatt: {p.coluna_chave_klassmatt} (aba {p.aba_klassmatt || "única"}).</dd>
        <dt>Normalização</dt><dd>{p.normalizacao_chave}</dd>
        <dt>Campos comparados</dt>
        <dd>{p.campos_comparados.length ? p.campos_comparados.map((c) => `${c.campo} (${c.coluna_sap} x ${c.coluna_klassmatt}, ${c.criticidade})`).join("; ") : "Nenhum"}</dd>
        {p.campos_ignorados.length > 0 && (<><dt>Campos não comparados</dt><dd>{p.campos_ignorados.map((c) => `${c.campo}: ${c.motivo.toLowerCase()}`).join("; ")}</dd></>)}
      </dl>
    );
  }
  return (
    <dl className="lista-parametros">
      <dt>Conjunto</dt><dd>{p.conjunto_nome}, versão {p.versao_regras}</dd>
      <dt>Ajustes críticos</dt><dd>{p.ajustes_criticos_autorizados ? "Autorizados" : "Não autorizados"}</dd>
      <dt>Regras aplicadas</dt><dd>{p.regras_aplicadas.map((r) => `${r.descricao} (${r.colunas.join(", ")})`).join("; ") || "Nenhuma"}</dd>
      {p.regras_ignoradas.length > 0 && (<><dt>Regras não aplicadas</dt><dd>{p.regras_ignoradas.map((r) => `${r.descricao}: ${r.motivo.toLowerCase()}`).join("; ")}</dd></>)}
    </dl>
  );
}
