// Painel inicial: acesso aos agentes e às principais informações da plataforma (slide 9).
// Rotas: GET /agentes, GET /conversas, GET /me (já carregado), GET /monitoramento/alertas.
import { api } from "../api.js";
import { h, formatar, ROTULOS } from "../util.js";
import { icone } from "../icones.js";
import { carregando, caixaErro, vazio, medidorGasto } from "./componentes.js";

export function telaPainel({ usuario, ir }) {
  const ehGestor = usuario.perfil === "GestorDeAcessos";
  const primeiroNome = usuario.nome.split(" ")[0];

  const indicadores = h("div", { class: "grade colunas-4" });
  const listaAgentes = h("div", {}, carregando("Carregando agentes…"));
  const recentes = h("div", {}, carregando());
  const filtro = { area: "todas", busca: "" };
  let agentes = [];

  const elemento = h("div", { class: "conteudo" },
    h("header", { class: "cabecalho-tela" },
      h("div", {},
        h("h1", {}, `Olá, ${primeiroNome}`),
        h("p", { class: "sub" }, ehGestor
          ? "Seu perfil administra os acessos da plataforma e não usa agentes."
          : "Seus agentes, conversas recentes e o uso do mês."),
      ),
      ehGestor ? null : h("a", { class: "botao destaque", href: "#/criar" }, icone("mais"), "Criar agente"),
    ),
    ehGestor ? painelGestor() : [
      indicadores,
      h("section", { class: "cartao" },
        h("div", { class: "cartao-titulo" },
          h("h2", {}, "Seus agentes"),
          h("div", { class: "linha" },
            h("input", {
              class: "entrada", type: "search", placeholder: "Buscar agente", "aria-label": "Buscar agente",
              style: { width: "200px", padding: "7px 10px" },
              oninput: (e) => { filtro.busca = e.target.value.toLowerCase(); desenharAgentes(); },
            }),
            h("select", {
              class: "entrada", "aria-label": "Filtrar por área", style: { width: "auto", padding: "7px 10px" },
              onchange: (e) => { filtro.area = e.target.value; desenharAgentes(); },
            },
              h("option", { value: "todas" }, "Todas as áreas"),
              Object.entries(ROTULOS.area).map(([valor, rotulo]) => h("option", { value: valor }, rotulo)),
            ),
          ),
        ),
        listaAgentes,
      ),
      h("section", { class: "cartao" },
        h("div", { class: "cartao-titulo" }, h("h2", {}, "Conversas recentes"), h("a", { href: "#/chat", class: "texto-3" }, "Ver todas")),
        recentes,
      ),
    ],
  );

  function desenharAgentes() {
    const visiveis = agentes.filter((a) =>
      (filtro.area === "todas" || a.area === filtro.area) &&
      (!filtro.busca || `${a.nome} ${a.objetivo}`.toLowerCase().includes(filtro.busca)),
    );
    if (!agentes.length) {
      listaAgentes.replaceChildren(vazio("robo", "Nenhum agente por aqui ainda",
        "Você vê os agentes que criou, os da sua área (supervisores) e aqueles para os quais foi convidado.",
        h("a", { class: "botao primario", href: "#/criar" }, "Criar meu primeiro agente")));
      return;
    }
    if (!visiveis.length) {
      listaAgentes.replaceChildren(vazio("lupa", "Nenhum agente encontrado", "Tente outro filtro."));
      return;
    }
    listaAgentes.replaceChildren(h("div", { class: "agentes" }, visiveis.map((a) => cartaoAgente(a, ir))));
  }

  async function carregar() {
    if (ehGestor) return;
    const uso = usuario.uso_mes;
    try {
      const [listaA, listaC, alertas] = await Promise.all([
        api.agentes(),
        api.conversas(),
        api.alertas().catch(() => []),
      ]);
      agentes = listaA;
      desenharAgentes();

      const fracao = uso?.limite ? uso.gasto / uso.limite : 0;
      indicadores.replaceChildren(
        cartaoIndicador("Agentes disponíveis", formatar.numero(listaA.filter((a) => a.ativo).length), `${listaA.filter((a) => a.relacao === "dono").length} criados por você`),
        cartaoIndicador("Conversas", formatar.numero(listaC.length), listaC[0] ? `última ${formatar.relativo(listaC[0].atualizada_em)}` : "nenhuma ainda"),
        h("div", { class: "cartao indicador" },
          h("span", { class: "rotulo" }, "Gasto do mês"),
          h("span", { class: "valor" }, uso?.limite ? formatar.moeda(uso.gasto) : "—"),
          uso?.limite ? medidorGasto(uso.gasto, uso.limite) : null,
          h("span", { class: "detalhe" }, uso?.limite ? `${formatar.pct(fracao)} de ${formatar.moeda(uso.limite)} · preço simulado` : "sem limite definido"),
        ),
        cartaoIndicador("Alertas", formatar.numero(alertas.length), alertas.length ? h("a", { href: "#/monitoramento" }, "Ver no Monitoramento") : "tudo funcionando", alertas.some((a) => a.nivel === "erro") ? "erro" : alertas.length ? "aviso" : null),
      );

      recentes.replaceChildren(
        listaC.length
          ? h("div", { class: "lista-conversas" }, listaC.slice(0, 5).map(itemConversa))
          : vazio("chat", "Nenhuma conversa ainda", "Escolha um agente acima e clique em Conversar."),
      );
    } catch (erro) {
      listaAgentes.replaceChildren(caixaErro(erro, carregar));
      recentes.replaceChildren();
    }
  }

  carregar();
  return { elemento };
}

function cartaoIndicador(rotulo, valor, detalhe, tom = null) {
  return h("div", { class: "cartao indicador" },
    h("span", { class: "rotulo" }, rotulo),
    h("span", { class: "valor", style: tom ? { color: `var(--${tom})` } : null }, valor),
    h("span", { class: "detalhe" }, detalhe),
  );
}

export function itemConversa(c, atual = null) {
  return h("a", { class: "item-conversa", href: `#/chat/${c.id}`, "aria-current": c.id === atual ? "page" : null },
    h("span", { class: "agente-icone", style: { width: "34px", height: "34px", borderRadius: "10px" } }, icone("chat")),
    h("span", { style: { minWidth: 0, flex: 1 } },
      h("div", { class: "titulo" }, c.titulo || "Nova conversa"),
      h("div", { class: "texto-3" }, `${c.agente.nome} · ${formatar.relativo(c.atualizada_em)}`),
    ),
  );
}

function cartaoAgente(a, ir) {
  const podeExecutar = a.acoes.includes("EXECUTAR");
  const usaveis = a.ferramentas.length;
  return h("article", { class: `cartao cartao-agente ${a.ativo ? "" : "inativo"}` },
    h("div", { class: "topo" },
      h("div", { class: "agente-icone" }, icone("robo")),
      h("div", { style: { minWidth: 0 } },
        h("h3", {}, a.nome),
        h("div", { class: "linha", style: { gap: "6px", marginTop: "4px" } },
          h("span", { class: "selo" }, ROTULOS.area[a.area] ?? a.area),
          h("span", { class: `selo ${a.relacao === "dono" ? "ok" : "info"}` }, ROTULOS.relacao[a.relacao] ?? a.relacao),
          a.ativo ? null : h("span", { class: "selo aviso" }, "Desativado"),
        ),
      ),
    ),
    h("p", { class: "objetivo" }, a.objetivo),
    h("div", { class: "rodape" },
      h("span", { class: "texto-3", title: a.ferramentas.join(", ") }, icone("ferramenta"), ` ${usaveis} ${usaveis === 1 ? "ferramenta" : "ferramentas"} · dono: ${a.dono.nome}`),
      h("span", { class: "espaco" }),
      podeExecutar
        ? h("button", { class: "botao primario pequeno", type: "button", onclick: () => ir(`chat/novo/${a.id}`) }, "Conversar")
        : h("span", { class: "texto-3" }, "Só consulta"),
    ),
  );
}

function painelGestor() {
  return h("section", { class: "cartao" },
    vazio("usuarios", "Gestão de acessos",
      "Seu perfil atribui e remove perfis de outras pessoas (nunca o próprio). A tela de gestão de perfis chega na Sprint 3.",
    ),
  );
}
