// Criação guiada de agentes (slides 9, 11 e 12): informar o problema, definir o objetivo
// e selecionar ferramentas, em 8 etapas.
// Rotas: POST /rascunhos, GET /rascunhos/{id}, POST /rascunhos/{id}/respostas,
//        POST /rascunhos/{id}/ajustes, PATCH /rascunhos/{id}, POST /rascunhos/{id}/simulacao,
//        POST /rascunhos/{id}/aprovar, GET /ferramentas.
import { api } from "../api.js";
import { h, formatar, ROTULOS } from "../util.js";
import { icone } from "../icones.js";
import { carregando, caixaErro, trajetoria, textoUso } from "./componentes.js";

const ETAPAS = ["Descrever", "Entender", "Perguntar", "Checar permissões", "Propor", "Ajustar", "Testar", "Aprovar"];
// Em qual etapa cada visão da tela está (índice em ETAPAS)
const ETAPA_DA_VISAO = { descrever: 0, perguntas: 2, ficha: 4, testar: 6, aprovar: 7, pronto: 8 };

const EXEMPLOS = [
  "Todo dia recebo pedidos de lojistas perguntando quanto vão pagar de multa por uma fatura atrasada. Quero um agente que consulte o cliente e calcule multa e juros.",
  "Antes de ligar para um cliente, preciso ver a situação dele e as últimas transações, incluindo contestações e estornos.",
  "Toda semana monto um resumo da receita e envio por e-mail para o time financeiro.",
];

export function telaCriacao({ usuario, parametros, ir }) {
  const estado = { rascunho: null, visao: "descrever", testado: false, catalogo: null, catalogoAberto: false };
  const etapas = h("ol", { class: "etapas", "aria-label": "Etapas da criação" });
  const principal = h("div", { style: { display: "flex", flexDirection: "column", gap: "16px", minWidth: 0 } });
  const lateral = h("aside", { style: { display: "flex", flexDirection: "column", gap: "16px" } });

  const elemento = h("div", { class: "conteudo" },
    h("header", { class: "cabecalho-tela" },
      h("div", {},
        h("h1", {}, "Criar agente"),
        h("p", { class: "sub" }, `Descreva o problema em linguagem natural. A plataforma monta o agente e confere as permissões. Ele será da área ${ROTULOS.area[usuario.area]}.`),
      ),
    ),
    etapas,
    h("div", { class: "criacao" }, principal, lateral),
  );

  function desenhar() {
    const atual = ETAPA_DA_VISAO[estado.visao];
    etapas.replaceChildren(...ETAPAS.map((nome, i) => {
      const feita = i < atual || (estado.visao === "ficha" && i === 3);
      const ehAtual = i === atual || (estado.visao === "ficha" && i === 5);
      return h("li", { class: `etapa ${feita ? "feita" : ""} ${ehAtual ? "atual" : ""}`, "aria-current": ehAtual ? "step" : null },
        h("span", { class: "num" }, feita ? icone("check") : String(i + 1)), nome);
    }));

    const visoes = { descrever: visaoDescrever, perguntas: visaoPerguntas, ficha: visaoFicha, testar: visaoTestar, aprovar: visaoAprovar, pronto: visaoPronto };
    principal.replaceChildren(visoes[estado.visao]());
    lateral.replaceChildren(...(estado.rascunho?.ficha ? [painelFicha(estado.rascunho.ficha)] : [painelComoFunciona()]));
  }

  function trocarRascunho(r, visao) {
    estado.rascunho = r;
    if (visao) estado.visao = visao;
    if (location.hash !== `#/criar/${r.id}`) history.replaceState(null, "", `#/criar/${r.id}`);
    desenhar();
  }

  // ---------- 1. Descrever ----------
  function visaoDescrever() {
    const campo = h("textarea", { class: "entrada", id: "descricao", rows: 6, maxlength: 2000, placeholder: "Ex.: Todo dia preciso calcular a multa de faturas atrasadas e…" });
    const erro = h("div", { class: "erro-caixa", role: "alert", hidden: true });
    const botao = h("button", { class: "botao primario", type: "submit" }, "Continuar", icone("brilho"));

    async function enviar(e) {
      e.preventDefault();
      erro.hidden = true;
      botao.disabled = true;
      try {
        trocarRascunho(await api.criarRascunho(campo.value), "perguntas");
      } catch (err) {
        erro.textContent = err.message;
        erro.hidden = false;
        botao.disabled = false;
      }
    }

    return h("form", { class: "cartao", onsubmit: enviar, style: { display: "flex", flexDirection: "column", gap: "14px" } },
      h("div", { class: "campo" },
        h("label", { for: "descricao" }, "Qual problema o agente deve resolver?"),
        h("p", { class: "texto-3" }, "Conte o que você faz hoje, quando isso acontece e quais dados usa. Não precisa saber nada de programação."),
        campo,
      ),
      h("div", {},
        h("p", { class: "texto-3", style: { marginBottom: "8px" } }, "Ou comece por um exemplo:"),
        h("div", { class: "sugestoes" }, EXEMPLOS.map((t) => h("button", { class: "chip", type: "button", onclick: () => { campo.value = t; campo.focus(); } }, `${t.slice(0, 64)}…`))),
      ),
      erro,
      h("div", { class: "linha" }, h("span", { class: "espaco" }), botao),
    );
  }

  // ---------- 2 e 3. Entender e Perguntar ----------
  function visaoPerguntas() {
    const r = estado.rascunho;
    const respostas = {};
    for (const p of r.perguntas) respostas[p.id] = r.respostas?.[p.id] ?? p.sugestao ?? (p.multipla ? [] : null);
    const erro = h("div", { class: "erro-caixa", role: "alert", hidden: true });
    const botao = h("button", { class: "botao primario", type: "submit" }, "Montar a ficha do agente");

    const perguntas = r.perguntas.map((p) => {
      const grupo = h("div", { class: "sugestoes", role: "group", "aria-labelledby": `p-${p.id}` });
      const desenharOpcoes = () => grupo.replaceChildren(...p.opcoes.map((o) => {
        const marcado = p.multipla ? respostas[p.id].includes(o.valor) : respostas[p.id] === o.valor;
        return h("button", {
          class: "chip", type: "button", "aria-pressed": String(marcado),
          onclick: () => {
            if (p.multipla) {
              respostas[p.id] = marcado ? respostas[p.id].filter((v) => v !== o.valor) : [...respostas[p.id], o.valor];
            } else {
              respostas[p.id] = o.valor;
            }
            desenharOpcoes();
          },
        }, marcado ? "✓ " : "", o.rotulo);
      }));
      desenharOpcoes();
      return h("div", { class: "pergunta-guiada" },
        h("h3", { id: `p-${p.id}` }, p.texto, p.multipla ? h("span", { class: "texto-3" }, " (pode marcar várias)") : null),
        grupo,
      );
    });

    async function enviar(e) {
      e.preventDefault();
      if (Array.isArray(respostas.dados) && !respostas.dados.length) {
        erro.textContent = "Escolha pelo menos um tipo de dado.";
        erro.hidden = false;
        return;
      }
      botao.disabled = true;
      try {
        trocarRascunho(await api.responderRascunho(r.id, respostas), "ficha");
      } catch (err) {
        erro.textContent = err.message;
        erro.hidden = false;
        botao.disabled = false;
      }
    }

    const ent = r.entendimento;
    return h("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } },
      h("section", { class: "cartao" },
        h("div", { class: "cartao-titulo" }, h("h2", {}, "O que eu entendi"), h("button", { class: "botao fantasma pequeno", type: "button", onclick: () => { estado.visao = "descrever"; desenhar(); } }, "Reescrever")),
        h("div", { class: "ficha" }, h("dl", {},
          h("dt", {}, "Objetivo"), h("dd", {}, ent.objetivo),
          h("dt", {}, "Quando"), h("dd", {}, ent.quando),
          h("dt", {}, "Sistemas"), h("dd", {}, ent.sistemas.length ? ent.sistemas.join(", ") : "a definir"),
          h("dt", {}, "Dados"), h("dd", {}, ent.dados.length ? ent.dados.join(", ") : "a definir"),
        )),
      ),
      h("form", { class: "cartao", onsubmit: enviar },
        h("div", { class: "cartao-titulo" }, h("h2", {}, "Algumas perguntas rápidas")),
        r.mensagem ? h("p", { class: "texto-2", style: { marginBottom: "6px" } }, r.mensagem) : null,
        perguntas,
        erro,
        h("div", { class: "linha", style: { marginTop: "12px" } }, h("span", { class: "espaco" }), botao),
      ),
    );
  }

  // ---------- 4, 5 e 6. Checar permissões, Propor e Ajustar ----------
  function visaoFicha() {
    const r = estado.rascunho;
    const f = r.ficha;
    const nome = h("input", { class: "entrada", id: "nome-agente", value: f.nome, maxlength: 80 });
    const objetivo = h("textarea", { class: "entrada", id: "objetivo-agente", rows: 2, maxlength: 300 }, f.objetivo);
    const salvarCampo = async () => {
      if (nome.value === f.nome && objetivo.value === f.objetivo) return;
      try {
        trocarRascunho(await api.editarFicha(r.id, { nome: nome.value.trim() || f.nome, objetivo: objetivo.value.trim() || f.objetivo }));
      } catch (err) {
        alert(err.message);
      }
    };
    nome.addEventListener("change", salvarCampo);
    objetivo.addEventListener("change", salvarCampo);

    const ajuste = h("input", { class: "entrada", placeholder: 'Ex.: "adicione envio de e-mails" ou "chame de Assistente de Cobrança"', "aria-label": "Pedir ajuste" });
    const botaoAjuste = h("button", { class: "botao", type: "submit" }, "Ajustar");
    const pedirAjuste = async (e) => {
      e.preventDefault();
      if (!ajuste.value.trim()) return;
      botaoAjuste.disabled = true;
      try {
        trocarRascunho(await api.ajustarRascunho(r.id, ajuste.value));
      } catch (err) {
        alert(err.message);
        botaoAjuste.disabled = false;
      }
    };

    const removerFerramenta = async (nomeF) => {
      try {
        trocarRascunho(await api.editarFicha(r.id, { ferramentas: f.ferramentas.map((x) => x.nome).filter((x) => x !== nomeF) }));
      } catch (err) {
        alert(err.message);
      }
    };

    const catalogo = estado.catalogoAberto
      ? seletorFerramentas(r, estado, trocarRascunho, () => { estado.catalogoAberto = false; desenhar(); })
      : null;
    const abrirCatalogo = () => { estado.catalogoAberto = true; desenhar(); };

    return h("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } },
      r.mensagem ? h("div", { class: "cartao", style: { padding: "12px 16px" }, role: "status" }, h("div", { class: "linha" }, icone("brilho"), r.mensagem)) : null,
      h("section", { class: "cartao", style: { display: "flex", flexDirection: "column", gap: "14px" } },
        h("div", { class: "cartao-titulo", style: { marginBottom: 0 } }, h("h2", {}, "Ficha do agente"), h("span", { class: "dica" }, "Edite à vontade")),
        h("div", { class: "campo" }, h("label", { for: "nome-agente" }, "Nome"), nome),
        h("div", { class: "campo" }, h("label", { for: "objetivo-agente" }, "Objetivo"), objetivo),
        h("div", {},
          h("h3", { style: { marginBottom: "6px" } }, "Passos"),
          h("ol", { style: { margin: 0, paddingLeft: "20px" } }, f.passos.map((p) => h("li", {}, p))),
        ),
        h("div", {},
          h("div", { class: "linha", style: { marginBottom: "4px" } },
            h("h3", {}, "Ferramentas"),
            h("span", { class: "espaco" }),
            h("button", { class: "botao pequeno", type: "button", onclick: abrirCatalogo }, icone("mais"), "Escolher ferramentas"),
          ),
          h("div", {}, f.ferramentas.map((ferr) => itemFerramenta(ferr, ferr.nome === "solicitar_ferramenta_ausente" ? null : () => removerFerramenta(ferr.nome)))),
          catalogo,
        ),
      ),
      h("section", { class: "cartao" },
        h("div", { class: "cartao-titulo" }, h("h2", {}, "Checagem de permissões"), selo(f.permissoes.ok ? "ok" : "erro", f.permissoes.ok ? "Tudo liberado" : "Há bloqueios")),
        f.permissoes.avisos.length
          ? h("ul", { class: "avisos" }, f.permissoes.avisos.map((a) => h("li", { class: a.nivel }, icone(a.nivel === "erro" ? "erro" : a.nivel === "aviso" ? "alerta" : "info"), a.texto)))
          : h("p", { class: "texto-2" }, "Nenhum aviso. Todas as ferramentas são de leitura e liberadas para você."),
      ),
      h("form", { class: "cartao", onsubmit: pedirAjuste },
        h("div", { class: "cartao-titulo" }, h("h2", {}, "Ajustar em linguagem simples")),
        h("div", { class: "linha", style: { flexWrap: "nowrap" } }, ajuste, botaoAjuste),
      ),
      h("div", { class: "linha" },
        h("button", { class: "botao fantasma", type: "button", onclick: () => { estado.visao = "perguntas"; desenhar(); } }, icone("voltar"), "Voltar às perguntas"),
        h("span", { class: "espaco" }),
        h("button", { class: "botao primario", type: "button", onclick: () => { estado.visao = "testar"; desenhar(); } }, "Testar o agente", icone("play")),
      ),
    );
  }

  // ---------- 7. Testar ----------
  function visaoTestar() {
    const r = estado.rascunho;
    const campo = h("input", { class: "entrada", placeholder: "Ex.: Calcule a multa de R$ 800,00 com 10 dias de atraso", "aria-label": "Pedido de exemplo" });
    const resultado = h("div");
    const botao = h("button", { class: "botao primario", type: "submit" }, icone("play"), "Rodar simulação");
    const sugestoes = [
      r.ficha.ferramentas.some((f) => f.nome === "calcular_multa_atraso") && "Calcule a multa de R$ 800,00 com 10 dias de atraso",
      r.ficha.ferramentas.some((f) => f.nome === "consultar_cliente") && "Qual a situação do cliente CLI-0001?",
      r.ficha.ferramentas.some((f) => f.nome === "consultar_transacoes_cliente") && "Mostre as transações do CLI-0002",
      r.ficha.ferramentas.some((f) => f.nome === "enviar_email") && "Envie o resumo da semana por e-mail para mim@stonelab.dev",
    ].filter(Boolean);

    async function rodar(e) {
      e.preventDefault();
      botao.disabled = true;
      resultado.replaceChildren(carregando("Rodando simulação…"));
      try {
        const s = await api.simularRascunho(r.id, campo.value);
        estado.testado = true;
        resultado.replaceChildren(
          h("div", { class: "mensagem agente", style: { maxWidth: "none" } },
            h("div", { class: "avatar", "aria-hidden": "true" }, icone("robo")),
            h("div", { class: "corpo" },
              h("span", { class: "etiqueta-tipo" }, icone("escudo"), "Simulação: nada foi alterado de verdade"),
              h("div", { class: "balao" }, s.resposta),
              trajetoria(s.trajetoria, { aberta: true }),
              h("div", { class: "meta" }, textoUso(s.uso)),
            ),
          ),
        );
        avancar.disabled = false;
      } catch (err) {
        resultado.replaceChildren(caixaErro(err));
      } finally {
        botao.disabled = false;
      }
    }

    const avancar = h("button", { class: "botao primario", type: "button", disabled: !estado.testado, onclick: () => { estado.visao = "aprovar"; desenhar(); } }, "Ir para aprovação");

    return h("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } },
      h("form", { class: "cartao", onsubmit: rodar, style: { display: "flex", flexDirection: "column", gap: "12px" } },
        h("div", { class: "cartao-titulo", style: { marginBottom: 0 } }, h("h2", {}, "Testar com um exemplo")),
        h("p", { class: "texto-2" }, "O agente roda com as ferramentas da ficha e as suas permissões. Ferramentas de escrita não executam na simulação."),
        sugestoes.length ? h("div", { class: "sugestoes" }, sugestoes.map((t) => h("button", { class: "chip", type: "button", onclick: () => { campo.value = t; } }, t))) : null,
        h("div", { class: "linha", style: { flexWrap: "nowrap" } }, campo, botao),
        resultado,
      ),
      h("div", { class: "linha" },
        h("button", { class: "botao fantasma", type: "button", onclick: () => { estado.visao = "ficha"; desenhar(); } }, icone("voltar"), "Voltar à ficha"),
        h("span", { class: "espaco" }),
        estado.testado ? null : h("span", { class: "texto-3" }, "Rode pelo menos um teste para aprovar."),
        avancar,
      ),
    );
  }

  // ---------- 8. Aprovar ----------
  function visaoAprovar() {
    const r = estado.rascunho;
    const f = r.ficha;
    const erro = h("div", { class: "erro-caixa", role: "alert", hidden: true });
    const botao = h("button", { class: "botao destaque", type: "button", disabled: !f.permissoes.ok }, icone("check"), "Aprovar e criar agente");
    botao.addEventListener("click", async () => {
      botao.disabled = true;
      erro.hidden = true;
      try {
        estado.agente = await api.aprovarRascunho(r.id);
        estado.visao = "pronto";
        desenhar();
      } catch (err) {
        erro.textContent = err.message;
        erro.hidden = false;
        botao.disabled = false;
      }
    });
    return h("section", { class: "cartao", style: { display: "flex", flexDirection: "column", gap: "14px" } },
      h("h2", {}, "Confirme a criação"),
      h("ul", { style: { margin: 0, paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px" } },
        h("li", {}, "O agente ", h("strong", {}, f.nome), ` será criado na área ${ROTULOS.area[f.area] ?? f.area}, com você como dono.`),
        h("li", {}, "Só você, quem você convidar, o supervisor da área e o admin poderão vê-lo. Não existe agente público."),
        h("li", {}, "Tudo roda com as permissões de quem usa o agente, conferidas de novo a cada ferramenta."),
        h("li", {}, `Custo estimado: ${formatar.moeda(f.custo_estimado_mes)} por mês (preço simulado), contando no limite de quem usa.`),
      ),
      f.permissoes.ok ? null : h("div", { class: "erro-caixa" }, "A ficha tem ferramentas bloqueadas para o seu perfil. Volte e remova-as."),
      erro,
      h("div", { class: "linha" },
        h("button", { class: "botao fantasma", type: "button", onclick: () => { estado.visao = "testar"; desenhar(); } }, icone("voltar"), "Voltar ao teste"),
        h("span", { class: "espaco" }),
        botao,
      ),
    );
  }

  function visaoPronto() {
    const a = estado.agente;
    return h("section", { class: "cartao vazio" },
      h("div", { class: "agente-icone", style: { width: "56px", height: "56px" } }, icone("check")),
      h("h2", {}, a ? `${a.nome} foi criado` : "Este rascunho já virou um agente"),
      h("p", {}, "Ele já aparece no seu Painel. Convites para outras pessoas chegam na Sprint 3."),
      h("div", { class: "linha", style: { justifyContent: "center" } },
        a ? h("button", { class: "botao primario", type: "button", onclick: () => ir(`chat/novo/${a.id}`) }, "Conversar agora") : null,
        h("a", { class: "botao", href: "#/painel" }, "Ir para o painel"),
        h("button", { class: "botao fantasma", type: "button", onclick: () => { history.replaceState(null, "", "#/criar"); estado.rascunho = null; estado.agente = null; estado.testado = false; estado.visao = "descrever"; desenhar(); } }, "Criar outro"),
      ),
    );
  }

  // ---------- início ----------
  const rascunhoId = parametros[0];
  if (rascunhoId) {
    principal.append(carregando("Carregando rascunho…"));
    api.rascunho(rascunhoId)
      .then((r) => {
        estado.testado = !!r.testado;
        trocarRascunho(r, r.etapa === "perguntas" ? "perguntas" : r.etapa === "aprovado" ? "pronto" : "ficha");
      })
      .catch((err) => principal.replaceChildren(caixaErro(err), h("a", { class: "botao", href: "#/criar" }, "Começar de novo")));
  } else {
    desenhar();
  }

  return { elemento };
}

// ---------- peças ----------
function selo(tom, texto) {
  return h("span", { class: `selo ${tom}` }, texto);
}

function seloStatusFerramenta(f) {
  if (!f.liberada) return selo("erro", "Bloqueada");
  if (f.status !== "ativa") return selo("aviso", f.status === "planejada" ? "Em breve" : "Inativa");
  return null;
}

function itemFerramenta(f, remover) {
  return h("div", { class: "ferramenta-item" },
    h("span", { class: "agente-icone", style: { width: "30px", height: "30px", borderRadius: "8px" } }, icone(f.acesso === "escrita" ? "raio" : "ferramenta")),
    h("div", { style: { flex: 1, minWidth: 0 } },
      h("div", { class: "linha", style: { gap: "6px" } },
        h("span", { class: "nome" }, f.nome),
        h("span", { class: "selo" }, ROTULOS.acesso[f.acesso] ?? f.acesso),
        h("span", { class: "selo" }, ROTULOS.sensibilidade[f.sensibilidade] ?? f.sensibilidade),
        seloStatusFerramenta(f),
      ),
      h("div", { class: "desc" }, f.descricao),
    ),
    remover ? h("button", { class: "botao fantasma pequeno", type: "button", title: `Remover ${f.nome}`, onclick: remover }, icone("x"), h("span", { class: "sr" }, "Remover")) : null,
  );
}

function seletorFerramentas(r, estado, trocarRascunho, fechar) {
  const caixa = h("div", { class: "cartao", style: { marginTop: "12px", boxShadow: "none", background: "var(--superficie-2)" } }, carregando("Carregando catálogo…"));
  const filtro = { area: "todas", soAtivas: true };

  const desenhar = () => {
    const escolhidas = new Set(r.ficha.ferramentas.map((f) => f.nome));
    const areas = [...new Set(estado.catalogo.map((f) => f.area))];
    const visiveis = estado.catalogo.filter((f) =>
      f.nome !== "solicitar_ferramenta_ausente" &&
      (filtro.area === "todas" || f.area === filtro.area) &&
      (!filtro.soAtivas || f.status === "ativa"),
    );
    caixa.replaceChildren(
      h("div", { class: "cartao-titulo" },
        h("h3", {}, "Catálogo de ferramentas"),
        h("button", { class: "botao fantasma pequeno", type: "button", onclick: fechar }, "Fechar"),
      ),
      h("div", { class: "catalogo-filtro" },
        h("select", { class: "entrada", "aria-label": "Área", style: { width: "auto", padding: "6px 10px" }, onchange: (e) => { filtro.area = e.target.value; desenhar(); } },
          h("option", { value: "todas" }, "Todas as áreas"),
          areas.map((a) => h("option", { value: a, selected: filtro.area === a }, ROTULOS.areaFerramenta[a] ?? a)),
        ),
        h("label", { class: "linha", style: { gap: "6px" } },
          h("input", { type: "checkbox", checked: filtro.soAtivas, onchange: (e) => { filtro.soAtivas = e.target.checked; desenhar(); } }),
          "Só as ativas",
        ),
        h("span", { class: "texto-3" }, `${visiveis.length} de ${estado.catalogo.length}`),
      ),
      h("div", { class: "catalogo" }, visiveis.map((f) => {
        const caixaMarcar = h("input", {
          type: "checkbox", checked: escolhidas.has(f.nome), disabled: !f.liberada, "aria-label": f.nome,
          onchange: async (e) => {
            const nomes = [...escolhidas];
            const nova = e.target.checked ? [...nomes, f.nome] : nomes.filter((n) => n !== f.nome);
            try {
              const atualizado = await api.editarFicha(r.id, { ferramentas: nova });
              r = atualizado;
              trocarRascunho(atualizado);
            } catch (err) {
              alert(err.message);
            }
          },
        });
        return h("label", { class: "ferramenta-item", style: { cursor: f.liberada ? "pointer" : "not-allowed" } },
          caixaMarcar,
          h("div", { style: { flex: 1, minWidth: 0 } },
            h("div", { class: "linha", style: { gap: "6px" } },
              h("span", { class: "nome" }, f.nome),
              h("span", { class: "selo" }, ROTULOS.acesso[f.acesso] ?? f.acesso),
              seloStatusFerramenta(f),
            ),
            h("div", { class: "desc" }, f.liberada ? f.descricao : `${f.descricao} (${f.motivo})`),
          ),
        );
      })),
    );
  };

  if (estado.catalogo) desenhar();
  else {
    api.ferramentas()
      .then((lista) => { estado.catalogo = lista; desenhar(); })
      .catch((err) => caixa.replaceChildren(caixaErro(err)));
  }
  return caixa;
}

function painelFicha(f) {
  return h("section", { class: "cartao", style: { position: "sticky", top: "20px", display: "flex", flexDirection: "column", gap: "12px" } },
    h("div", { class: "linha" },
      h("div", { class: "agente-icone" }, icone("robo")),
      h("div", { style: { minWidth: 0 } }, h("h3", {}, f.nome), h("span", { class: "texto-3" }, ROTULOS.area[f.area] ?? f.area)),
    ),
    h("div", { class: "linha", style: { gap: "6px" } },
      selo(f.risco === "alto" ? "erro" : f.risco === "medio" ? "aviso" : "ok", ROTULOS.risco[f.risco] ?? f.risco),
      selo(f.permissoes.ok ? "ok" : "erro", f.permissoes.ok ? "Permissões ok" : "Bloqueios"),
    ),
    h("div", { class: "numeros-ficha", style: { gridTemplateColumns: "1fr 1fr" } },
      h("div", {}, h("div", { class: "valor" }, formatar.moeda(f.custo_estimado_mes)), h("div", { class: "rotulo" }, "custo estimado/mês")),
      h("div", {}, h("div", { class: "valor" }, `${f.economia_horas_mes} h`), h("div", { class: "rotulo" }, "economia estimada/mês")),
    ),
    h("p", { class: "texto-3" }, `${f.ferramentas.length} ferramentas · ~${f.usos_mes_estimados} usos por mês. Valores ilustrativos (preço simulado por token).`),
    h("details", {},
      h("summary", { class: "texto-2", style: { cursor: "pointer" } }, "O que a plataforma faz sozinha"),
      h("ul", { class: "texto-2", style: { paddingLeft: "18px", margin: "8px 0 0", fontSize: "0.88rem" } },
        h("li", {}, "Ciclo de raciocínio: pensar, agir, conferir, repetir (até 8 passos)"),
        h("li", {}, "Travas de segurança sempre ativas"),
        h("li", {}, "Gestão: custo, saúde e histórico"),
      ),
    ),
  );
}

function painelComoFunciona() {
  return h("section", { class: "cartao", style: { display: "flex", flexDirection: "column", gap: "10px" } },
    h("h3", {}, "Como funciona"),
    h("ol", { class: "texto-2", style: { margin: 0, paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "0.9rem" } },
      h("li", {}, h("strong", {}, "Descrever:"), " você conta o problema."),
      h("li", {}, h("strong", {}, "Entender:"), " a IA identifica objetivo, quando acontece, sistemas e dados."),
      h("li", {}, h("strong", {}, "Perguntar:"), " poucas perguntas, com opções para clicar."),
      h("li", {}, h("strong", {}, "Checar permissões:"), " só entram ferramentas liberadas para você."),
      h("li", {}, h("strong", {}, "Propor:"), " ficha com nome, passos, ferramentas, risco, custo e economia."),
      h("li", {}, h("strong", {}, "Ajustar:"), " peça mudanças em linguagem simples."),
      h("li", {}, h("strong", {}, "Testar:"), " simulação com um exemplo, sem mexer em nada."),
      h("li", {}, h("strong", {}, "Aprovar:"), " você confirma e o agente é criado."),
    ),
  );
}
