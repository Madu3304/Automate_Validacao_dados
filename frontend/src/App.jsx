import { useEffect, useState } from "react";
import { api, definirUsuario } from "./api";
import Conciliacao from "./pages/Conciliacao";
import Historico from "./pages/Historico";
import Inicio from "./pages/Inicio";
import Resultado from "./pages/Resultado";
import Verificacao from "./pages/Verificacao";

const MENU = [
  { id: "inicio", rotulo: "Início" },
  { id: "conciliacao", rotulo: "Conciliar SAP x Klassmatt" },
  { id: "verificacao", rotulo: "Verificar e ajustar planilha" },
  { id: "historico", rotulo: "Histórico" },
];

function lerUsuario() {
  try { return localStorage.getItem("gdm-usuario") || ""; } catch { return ""; }
}

export default function App() {
  const [tela, setTela] = useState({ nome: "inicio" });
  const [catalogo, setCatalogo] = useState(null);
  const [erroCatalogo, setErroCatalogo] = useState("");
  const [usuario, setUsuario] = useState(lerUsuario);

  useEffect(() => {
    api.servicos().then(setCatalogo).catch((e) => setErroCatalogo(e.message));
  }, []);

  useEffect(() => {
    definirUsuario(usuario);
    try { localStorage.setItem("gdm-usuario", usuario); } catch { /* armazenamento indisponível */ }
  }, [usuario]);

  const ir = (nome) => { setTela({ nome }); window.scrollTo(0, 0); };
  const abrirExecucao = (id, dados) => { setTela({ nome: "execucao", id, dados }); window.scrollTo(0, 0); };
  const ativo = tela.nome === "execucao" ? tela.dados?.servico || "historico" : tela.nome;

  let conteudo;
  if (erroCatalogo) {
    conteudo = (
      <div className="erro-campo" role="alert">
        <p><strong>A API não respondeu.</strong> {erroCatalogo}</p>
        <p>Inicie o backend com <code>uvicorn app.main:app --port 8000</code> e recarregue a página.</p>
      </div>
    );
  } else if (!catalogo) {
    conteudo = <p className="discreto">Carregando serviços…</p>;
  } else if (tela.nome === "conciliacao") {
    conteudo = <Conciliacao catalogo={catalogo} abrirExecucao={abrirExecucao} />;
  } else if (tela.nome === "verificacao") {
    conteudo = <Verificacao catalogo={catalogo} abrirExecucao={abrirExecucao} />;
  } else if (tela.nome === "historico") {
    conteudo = <Historico abrirExecucao={abrirExecucao} />;
  } else if (tela.nome === "execucao") {
    conteudo = <Resultado key={tela.id} id={tela.id} inicial={tela.dados} catalogo={catalogo} ir={ir} />;
  } else {
    conteudo = <Inicio ir={ir} abrirExecucao={abrirExecucao} />;
  }

  return (
    <div className="app">
      <aside className="trilho">
        <div className="marca-produto">
          <span className="marca-produto-nome">Dados Mestres</span>
          <span className="marca-produto-sub">SAP x Klassmatt</span>
        </div>
        <nav aria-label="Principal">
          <ul>
            {MENU.map((m) => (
              <li key={m.id}>
                <button type="button" className="item-menu" aria-current={ativo === m.id ? "page" : undefined} onClick={() => ir(m.id)}>
                  {m.rotulo}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <label className="campo campo-usuario">
          <span>Seu nome (registrado no histórico)</span>
          <input value={usuario} maxLength={80} onChange={(e) => setUsuario(e.target.value)} placeholder="Ex.: Ana Souza" />
        </label>
      </aside>
      <main className="conteudo" id="conteudo">{conteudo}</main>
    </div>
  );
}
