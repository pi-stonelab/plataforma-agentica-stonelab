// Chat: enviar solicitações, ver respostas e acompanhar a execução (slide 9).
// Rotas: GET /conversas, POST /conversas, GET /conversas/{id}, POST /conversas/{id}/mensagens,
//        POST /conversas/{id}/confirmacoes/{cid} (Sprint 3), GET /agentes (para nova conversa).
import { api, ErroApi } from "../api.js";
import { CONFIG } from "../config.js";
import { h, formatar, iniciais } from "../util.js";
import { icone } from "../icones.js";
import { carregando, caixaErro, vazio, trajetoria, itemPasso, textoUso } from "./componentes.js";
import { itemConversa } from "./painel.js";

const SUGESTOES = {
  consultar_cliente: "Qual a situação do cliente CLI-0001?",
  consultar_transacoes_cliente: "Mostre as transações do CLI-0002",
  calcular_multa_atraso: "Calcule a multa de uma fatura de R$ 1.250,00 com 15 dias de atraso",
  consultar_endereco_cep: "Qual o endereço do CEP 01310-100?",
  enviar_email: "Envie o resumo da semana por e-mail para time-financeiro@stonelab.dev",
  resumir_receita_periodo: "Qual foi a receita da última semana?",
  listar_tickets_cliente: "Liste os chamados abertos do CLI-0003",
};

export function telaChat({ usuario, parametros, ir, atualizarUsuario }) {
  const [primeiro, segundo] = parametros;

  // #/chat/novo/<agenteId>: cria a conversa e troca a URL
  if (primeiro === "novo" && segundo) {
    const elemento = h("div", { class: "conteudo" }, carregando("Abrindo conversa…"));
    api.abrirConversa(segundo)
      .then((c) => {
        history.replaceState(null, "", `#/chat/${c.id}`);
        ir(`chat/${c.id}`);
      })
      .catch((erro) => elemento.replaceChildren(caixaErro(erro), h("a", { class: "botao", href: "#/painel" }, "Voltar ao painel")));
    return { elemento };
  }

  const conversaId = primeiro || null;
  const lista = h("div", { class: "itens" }, carregando());
  const area = h("section", { class: "chat-area", "aria-label": "Conversa" });
  const elemento = h("div", { class: `chat ${conversaId ? "" : "sem-conversa"}` },
    h("aside", { class: "chat-lista", "aria-label": "Conversas" },
      h("div", { class: "cabeca" }, h("h2", {}, "Conversas"), seletorNovaConversa(ir)),
      lista,
    ),
    area,
  );

  const carregarLista = () => api.conversas()
    .then((cs) => lista.replaceChildren(
      cs.length ? h("div", { class: "lista-conversas" }, cs.map((c) => itemConversa(c, conversaId))) : h("p", { class: "texto-3", style: { padding: "8px" } }, "Nenhuma conversa ainda."),
    ))
    .catch((erro) => lista.replaceChildren(caixaErro(erro)));
  carregarLista();

  if (!conversaId) {
    area.append(vazio("chat", "Escolha uma conversa", "Ou comece uma nova escolhendo um agente acima."));
    return { elemento };
  }

  area.append(carregando("Carregando conversa…"));
  let ativo = true;
  api.conversa(conversaId)
    .then((conversa) => ativo && montarConversa(area, conversa, usuario, () => { atualizarUsuario(); carregarLista(); }))
    .catch((erro) => area.replaceChildren(h("div", { class: "conteudo" }, caixaErro(erro), h("a", { class: "botao", href: "#/chat" }, "Voltar"))));

  return { elemento, limpar: () => { ativo = false; } };
}

function seletorNovaConversa(ir) {
  const select = h("select", { class: "entrada", "aria-label": "Nova conversa com o agente", style: { padding: "8px 10px" } },
    h("option", { value: "" }, "+ Nova conversa com…"),
  );
  select.addEventListener("change", () => select.value && ir(`chat/novo/${select.value}`));
  api.agentes()
    .then((agentes) => {
      const usaveis = agentes.filter((a) => a.acoes.includes("EXECUTAR"));
      select.append(...usaveis.map((a) => h("option", { value: a.id }, a.nome)));
      if (!usaveis.length) select.disabled = true;
    })
    .catch(() => { select.disabled = true; });
  return select;
}

function montarConversa(area, conversa, usuario, atualizarUsuario) {
  const agente = conversa.agente;
  const mensagens = h("div", { class: "mensagens", role: "log", "aria-live": "polite", "aria-label": "Mensagens" });
  const avisoComposicao = h("div", { class: "erro-caixa", role: "alert", hidden: true });
  const campo = h("textarea", {
    class: "entrada", rows: 1, maxlength: 2000, placeholder: `Escreva para ${agente.nome}…`, "aria-label": "Mensagem",
  });
  const botao = h("button", { class: "botao primario", type: "submit", title: "Enviar (Enter)" }, icone("enviar"), h("span", { class: "sr" }, "Enviar"));
  const sugestoes = h("div", { class: "sugestoes" });
  let enviando = false;

  const rolar = () => { mensagens.scrollTop = mensagens.scrollHeight; };

  campo.addEventListener("input", () => {
    campo.style.height = "auto";
    campo.style.height = `${Math.min(campo.scrollHeight, 180)}px`;
  });
  campo.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  async function enviar(texto) {
    texto = texto.trim();
    if (!texto || enviando) return;
    enviando = true;
    avisoComposicao.hidden = true;
    botao.disabled = true;
    campo.value = "";
    campo.style.height = "auto";
    sugestoes.replaceChildren();

    mensagens.append(bolhaUsuario({ texto, criada_em: new Date().toISOString() }, usuario));
    const passosAoVivo = h("ol", { class: "passos" });
    const linhaStatus = h("div", { class: "linha" }, h("span", { class: "girando" }), "O agente está trabalhando…");
    const aoVivo = h("div", { class: "mensagem agente" },
      h("div", { class: "avatar", "aria-hidden": "true" }, icone("robo")),
      h("div", { class: "corpo" }, h("div", { class: "ao-vivo" }, linhaStatus, passosAoVivo)),
    );
    mensagens.append(aoVivo);
    rolar();

    try {
      const r = await api.enviarMensagem(conversa.id, texto, {
        aoPasso: (passo) => {
          passosAoVivo.append(itemPasso(passo, passosAoVivo.children.length));
          linhaStatus.lastChild.textContent = `Passo ${passosAoVivo.children.length} de até ${CONFIG.MAX_PASSOS}…`;
          rolar();
        },
      });
      aoVivo.replaceWith(bolhaAgente(paraMensagem(r), conversa, usuario, aoConfirmar));
      atualizarUsuario();
    } catch (erro) {
      aoVivo.remove();
      avisoComposicao.textContent = mensagemDeErro(erro);
      avisoComposicao.hidden = false;
      campo.value = texto;
    } finally {
      enviando = false;
      botao.disabled = false;
      campo.focus();
      rolar();
    }
  }

  // Chamado pelo cartão de confirmação: o resultado entra como nova mensagem do agente.
  function aoConfirmar(resposta) {
    mensagens.append(bolhaAgente(paraMensagem(resposta), conversa, usuario, aoConfirmar));
    atualizarUsuario();
    rolar();
  }

  const form = h("form", { onsubmit: (e) => { e.preventDefault(); enviar(campo.value); } }, campo, botao);

  // histórico
  for (const m of conversa.mensagens) {
    mensagens.append(m.autor === "usuario" ? bolhaUsuario(m, usuario) : bolhaAgente(m, conversa, usuario, aoConfirmar));
  }
  if (!conversa.mensagens.length) {
    mensagens.append(
      h("div", { class: "vazio" },
        h("div", { class: "agente-icone", style: { width: "56px", height: "56px" } }, icone("robo")),
        h("h2", {}, agente.nome),
        h("p", {}, agente.objetivo),
        h("p", { class: "texto-3" }, "O agente usa só as ferramentas liberadas para você. Ele pode fazer perguntas se faltar algum dado."),
      ),
    );
    const exemplos = agente.ferramentas.map((f) => SUGESTOES[f]).filter(Boolean).slice(0, 4);
    sugestoes.append(...exemplos.map((t) => h("button", { class: "chip", type: "button", onclick: () => enviar(t) }, t)));
  }

  const podeEnviar = agente.pode_executar !== false && agente.ativo !== false;
  if (!podeEnviar) {
    campo.disabled = true;
    botao.disabled = true;
    campo.placeholder = agente.ativo === false ? "Este agente foi desativado: a conversa fica só para consulta." : "Você não tem mais permissão para usar este agente.";
  }

  area.replaceChildren(
    h("header", { class: "chat-topo" },
      h("a", { class: "botao fantasma pequeno so-mobile", href: "#/chat", title: "Voltar" }, icone("voltar")),
      h("div", { class: "agente-icone", style: { width: "38px", height: "38px" } }, icone("robo")),
      h("div", { style: { minWidth: 0, flex: 1 } },
        h("h2", {}, agente.nome),
        h("div", { class: "objetivo" }, agente.objetivo),
      ),
      h("span", { class: "selo", title: agente.ferramentas.join(", ") }, icone("ferramenta"), `${agente.ferramentas.length} ferramentas`),
      agente.ativo === false ? h("span", { class: "selo aviso" }, "Desativado") : null,
    ),
    mensagens,
    h("div", { class: "compositor" }, avisoComposicao, sugestoes, form,
      h("div", { class: "texto-3" }, "Enter envia · Shift+Enter quebra linha · Não cole senhas nem dados reais."),
    ),
  );
  rolar();
  if (podeEnviar) campo.focus();
}

/** Converte a resposta do POST (campo "resposta") no formato do histórico (campo "texto"). */
function paraMensagem(r) {
  return { id: r.id, autor: "agente", texto: r.resposta ?? r.texto, tipo: r.tipo, trajetoria: r.trajetoria, uso: r.uso, confirmacao: r.confirmacao, criada_em: r.criada_em };
}

function mensagemDeErro(erro) {
  if (!(erro instanceof ErroApi)) return "Algo deu errado ao enviar. Tente de novo.";
  if (erro.codigo === "limite_atingido") return erro.message;
  if (erro.status === 403) return `${erro.message} Se precisar usar este agente, peça um convite ao dono.`;
  if (erro.status === 504 || erro.status === 502) return "O modelo demorou demais para responder. Tente de novo em instantes.";
  return erro.message;
}

function bolhaUsuario(m, usuario) {
  return h("div", { class: "mensagem usuario" },
    h("div", { class: "avatar", "aria-hidden": "true" }, iniciais(usuario.nome)),
    h("div", { class: "corpo" },
      h("div", { class: "balao" }, m.texto),
      h("div", { class: "meta", style: { justifyContent: "flex-end" } }, formatar.dataHora(m.criada_em)),
    ),
  );
}

const ETIQUETAS = {
  pergunta: ["pergunta", "O agente precisa de uma informação"],
  bloqueio: ["escudo", "Pedido barrado pelas travas de segurança"],
  confirmacao: ["cadeado", "Ação de escrita: precisa da sua confirmação"],
};

function bolhaAgente(m, conversa, usuario, aoConfirmar) {
  const tipo = m.tipo || "final";
  const etiqueta = ETIQUETAS[tipo];
  return h("div", { class: `mensagem agente tipo-${tipo}` },
    h("div", { class: "avatar", "aria-hidden": "true" }, icone("robo")),
    h("div", { class: "corpo" },
      etiqueta ? h("span", { class: `etiqueta-tipo ${tipo}` }, icone(etiqueta[0]), etiqueta[1]) : null,
      h("div", { class: "balao" }, m.texto),
      m.confirmacao ? cartaoConfirmacao(m.confirmacao, conversa, aoConfirmar) : null,
      trajetoria(m.trajetoria),
      h("div", { class: "meta" }, formatar.dataHora(m.criada_em), m.uso ? h("span", { title: "Tokens, latência e custo simulado desta resposta" }, `· ${textoUso(m.uso)}`) : null),
    ),
  );
}

function cartaoConfirmacao(c, conversa, aoConfirmar) {
  const situacao = h("div", { class: "linha" });
  const erro = h("div", { class: "erro-caixa", hidden: true });

  async function decidir(aprovar) {
    for (const b of situacao.querySelectorAll("button")) b.disabled = true;
    erro.hidden = true;
    try {
      const r = await api.confirmarAcao(conversa.id, c.id, aprovar);
      c.situacao = aprovar ? "aprovada" : "cancelada";
      desenhar();
      aoConfirmar(r);
    } catch (e) {
      erro.textContent = e.message;
      erro.hidden = false;
      for (const b of situacao.querySelectorAll("button")) b.disabled = false;
    }
  }

  function desenhar() {
    if (c.situacao === "pendente") {
      situacao.replaceChildren(
        h("button", { class: "botao primario pequeno", type: "button", onclick: () => decidir(true) }, icone("check"), "Confirmar e executar"),
        h("button", { class: "botao pequeno", type: "button", onclick: () => decidir(false) }, "Cancelar"),
      );
    } else {
      situacao.replaceChildren(
        h("span", { class: `selo ${c.situacao === "aprovada" ? "ok" : ""}` }, c.situacao === "aprovada" ? "Confirmado por você" : "Cancelado"),
      );
    }
  }
  desenhar();

  return h("div", { class: "cartao-confirmacao" },
    h("strong", {}, c.titulo || c.ferramenta),
    h("dl", {}, (c.campos || []).flatMap((campo) => [h("dt", {}, campo.rotulo), h("dd", {}, campo.valor)])),
    erro,
    situacao,
  );
}
