// Ponto de entrada: rotas por hash, barra lateral e sessão.
//
// Rotas:
//   #/login                     tela de login
//   #/painel                    Painel inicial (agentes e resumo)
//   #/chat                      lista de conversas
//   #/chat/<conversaId>         uma conversa
//   #/chat/novo/<agenteId>      abre conversa nova com o agente
//   #/criar                     criação guiada de agentes
//   #/criar/<rascunhoId>        continua um rascunho
//   #/monitoramento             custos, desempenho e alertas

import { api, quandoSessaoExpirar, ErroApi } from "./api.js";
import { CONFIG } from "./config.js";
import { sessao } from "./sessao.js";
import { h, limpar, iniciais, ROTULOS, formatar } from "./util.js";
import { icone, logoMarca } from "./icones.js";
import { telaLogin } from "./telas/login.js";
import { telaPainel } from "./telas/painel.js";
import { telaChat } from "./telas/chat.js";
import { telaCriacao } from "./telas/criacao.js";
import { telaMonitoramento } from "./telas/monitoramento.js";

const raiz = document.getElementById("app");
let limparTelaAnterior = null;

const NAVEGACAO = [
  { rota: "painel", rotulo: "Painel", icone: "painel" },
  { rota: "chat", rotulo: "Chat", icone: "chat" },
  { rota: "criar", rotulo: "Criar agente", icone: "criar", esconder: (u) => u.perfil === "GestorDeAcessos" },
  { rota: "monitoramento", rotulo: "Monitoramento", icone: "monitor", esconder: (u) => u.perfil === "GestorDeAcessos" },
];

const TELAS = { painel: telaPainel, chat: telaChat, criar: telaCriacao, monitoramento: telaMonitoramento };

export function ir(rota) {
  if (location.hash === `#/${rota}`) roteador();
  else location.hash = `#/${rota}`;
}

/** Atualiza o perfil (ex.: gasto do mês depois de uma mensagem) e a faixa de aviso. */
export async function atualizarUsuario() {
  try {
    sessao.usuario = await api.me();
    desenharFaixaGasto();
  } catch {
    // a tela atual mostra o próprio erro
  }
}

function desenharFaixaGasto() {
  const lugar = document.getElementById("faixa-gasto");
  if (!lugar) return;
  limpar(lugar);
  const uso = sessao.usuario?.uso_mes;
  if (!uso?.limite) return;
  const fracao = uso.gasto / uso.limite;
  if (fracao < CONFIG.AVISO_GASTO) return;
  const estourou = fracao >= 1;
  lugar.append(
    h("div", { class: `faixa ${estourou ? "erro" : "aviso"}`, role: "status" },
      icone("alerta"),
      h("span", {},
        estourou
          ? `Você atingiu o limite de gasto do mês (${formatar.moeda(uso.gasto)} de ${formatar.moeda(uso.limite)}). Novas mensagens precisam de aprovação do seu gestor.`
          : `Você já usou ${formatar.pct(fracao)} do seu limite do mês (${formatar.moeda(uso.gasto)} de ${formatar.moeda(uso.limite)}). Ao chegar em 100%, novas mensagens precisam de aprovação do gestor.`,
      ),
    ),
  );
}

function barraLateral(usuario, rotaAtual) {
  const nav = h("nav", { class: "nav", "aria-label": "Principal" },
    NAVEGACAO.filter((n) => !n.esconder?.(usuario)).map((n) =>
      h("a", { href: `#/${n.rota}`, "aria-current": rotaAtual === n.rota ? "page" : null }, icone(n.icone), n.rotulo),
    ),
  );

  const seloMock = CONFIG.MOCK
    ? h("div", { class: "selo-mock" },
        "Modo demonstração: dados simulados no navegador. ",
        h("button", {
          type: "button",
          onclick: async () => {
            if (!confirm("Apagar conversas e agentes criados na demonstração?")) return;
            (await import("./mock/servidor.js")).reiniciarMock();
            location.reload();
          },
        }, "Reiniciar demo"),
      )
    : null;

  return h("aside", { class: "lateral" },
    h("a", { class: "logo", href: "#/painel" },
      logoMarca(),
      h("span", {}, h("span", { class: "logo-texto" }, "stone", h("span", {}, "lab")), h("span", { class: "logo-sub" }, "Plataforma agêntica")),
    ),
    nav,
    h("div", { class: "lateral-rodape" },
      seloMock,
      h("div", { class: "cartao-usuario" },
        h("div", { class: "avatar", "aria-hidden": "true" }, iniciais(usuario.nome)),
        h("div", { class: "textos" },
          h("div", { class: "nome" }, usuario.nome),
          h("div", { class: "perfil" }, `${ROTULOS.perfil[usuario.perfil] ?? usuario.perfil} · ${ROTULOS.area[usuario.area] ?? usuario.area}`),
        ),
      ),
      h("button", { class: "botao-sair", type: "button", onclick: sair, title: "Sair" }, icone("sair"), h("span", { class: "sr" }, "Sair")),
    ),
  );
}

function sair() {
  sessao.sair();
  ir("login");
}

async function roteador() {
  limparTelaAnterior?.();
  limparTelaAnterior = null;

  const [rota = "painel", ...resto] = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);

  if (!sessao.token) {
    limpar(raiz).append(telaLogin({ aoEntrar: () => ir("painel") }));
    if (rota !== "login") history.replaceState(null, "", "#/login");
    return;
  }
  if (rota === "login") return ir("painel");

  if (!sessao.usuario) {
    limpar(raiz).append(h("div", { class: "carregando" }, h("span", { class: "girando" }), "Carregando seu perfil…"));
    try {
      sessao.usuario = await api.me();
    } catch (erro) {
      if (erro instanceof ErroApi && erro.status === 401) return;
      limpar(raiz).append(
        h("div", { class: "conteudo" }, h("div", { class: "erro-caixa" }, erro.message), h("button", { class: "botao", onclick: () => roteador() }, "Tentar de novo")),
      );
      return;
    }
  }

  const usuario = sessao.usuario;
  const item = NAVEGACAO.find((n) => n.rota === rota);
  if (!TELAS[rota] || item?.esconder?.(usuario)) return ir("painel");

  const principal = h("main", { class: "principal", id: "principal" });
  limpar(raiz).append(h("div", { class: "estrutura" }, barraLateral(usuario, rota), principal));
  principal.append(h("div", { id: "faixa-gasto" }));
  desenharFaixaGasto();

  const tela = TELAS[rota]({ usuario, parametros: resto, ir, atualizarUsuario });
  principal.append(tela.elemento ?? tela);
  limparTelaAnterior = tela.limpar ?? null;
  document.title = `${item?.rotulo ?? "Stonelab"} · Stonelab`;
}

quandoSessaoExpirar(() => {
  sessao.sair();
  ir("login");
});
window.addEventListener("hashchange", roteador);
roteador();
