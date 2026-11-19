// Agente simulado do modo mock.
//
// Não há modelo aqui: regras simples por palavra-chave imitam o protocolo do agente real
// (agentes/agente_atendimento/agente.py: LER / USAR / PERGUNTAR / FINAL, até 8 passos)
// e chamam as mesmas "ferramentas" com os mesmos dados sintéticos. Serve para a interface
// ser construída e demonstrada antes de o back-end ficar pronto.

import { CLIENTES, TRANSACOES, ENDERECOS, CLIENTE_COM_FALHA, PRECO_POR_1K_TOKENS } from "./dados.js";
import { ficha, motivoBloqueio, clienteNoEscopo } from "./permissoes.js";

const MAX_PASSOS = 8;
let contadorPedidos = 0;

const brl = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
const dataBR = (iso) => iso.split("-").reverse().join("/");
const semAcento = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// ---------- leitura de dados do texto ----------
function lerValor(texto) {
  const m = texto.match(/r\$\s*([\d.,]+)/i) || texto.match(/([\d.,]+)\s*reais/i) || texto.match(/(?:valor|fatura)[^\d]{0,15}([\d.,]+)/i);
  if (!m) return null;
  let bruto = m[1].replace(/[.,]$/, "");
  if (bruto.includes(",")) bruto = bruto.replace(/\./g, "").replace(",", ".");
  else if (/\.\d{3}$/.test(bruto)) bruto = bruto.replace(/\./g, "");
  const valor = Number(bruto);
  return Number.isFinite(valor) && valor > 0 ? valor : null;
}
const lerDias = (t) => {
  const m = t.match(/(\d+)\s*dias?/i);
  return m ? Number(m[1]) : null;
};
const lerCliente = (t) => t.match(/cli-?\s?(\d{1,4})/i)?.[1].padStart(4, "0").replace(/^/, "CLI-") ?? null;
const lerCep = (t) => {
  const m = t.match(/\b(\d{5})-?(\d{3})\b/);
  return m ? m[1] + m[2] : null;
};
const lerEmail = (t) => t.match(/[\w.+-]+@[\w-]+\.[\w.]+/)?.[0] ?? null;
const ehSim = (t) => /^(sim|s|pode|claro|ok|quero|registr|por favor|isso)/i.test(semAcento(t.trim()));

// ---------- execução das ferramentas (imita o catálogo) ----------
function executar(nome, args, u2) {
  const ok = (dados) => ({ status: "sucesso", dados, mensagem: "", tipo_erro: null });
  const erro = (tipo_erro, mensagem) => ({ status: "erro", dados: null, mensagem, tipo_erro });

  switch (nome) {
    case "consultar_cliente": {
      if (!/^CLI-\d{4}$/.test(args.id_cliente)) return erro("parametro_invalido", "O id_cliente deve ser como CLI-0001.");
      if (!clienteNoEscopo(u2, args.id_cliente)) return erro("permissao_negada", "Cliente fora da sua carteira.");
      const c = CLIENTES[args.id_cliente];
      return c ? ok(c) : erro("nao_encontrado", "Cliente não encontrado.");
    }
    case "consultar_transacoes_cliente": {
      if (!/^CLI-\d{4}$/.test(args.id_cliente)) return erro("parametro_invalido", "O id_cliente deve ser como CLI-0001.");
      if (!clienteNoEscopo(u2, args.id_cliente)) return erro("permissao_negada", "Cliente fora da sua carteira.");
      if (args.id_cliente === CLIENTE_COM_FALHA) return erro("integracao_indisponivel", "O core de pagamentos não respondeu.");
      if (!CLIENTES[args.id_cliente]) return erro("nao_encontrado", "Cliente não encontrado.");
      const todas = [...(TRANSACOES[args.id_cliente] || [])].sort((a, b) => (a.data < b.data ? 1 : -1));
      return ok({ transacoes: todas.slice(0, args.limite || 20), total: todas.length, todas });
    }
    case "calcular_multa_atraso": {
      const { valor_fatura: v, dias_atraso: d } = args;
      if (!(v > 0 && v <= 1e6)) return erro("parametro_invalido", "O valor_fatura deve ficar entre 0 e 1.000.000.");
      if (!(d >= 0 && d <= 3650)) return erro("parametro_invalido", "Os dias_atraso devem ficar entre 0 e 3650.");
      const r = (x) => Math.round(x * 100) / 100;
      const multa = d >= 1 ? r(v * 0.02) : 0;
      const juros = r((v * 0.01 * d) / 30);
      return ok({ valor_fatura: r(v), dias_atraso: d, multa, juros, valor_total: r(r(v) + multa + juros) });
    }
    case "consultar_endereco_cep": {
      const e = ENDERECOS[args.cep];
      if (!e) return erro("nao_encontrado", "CEP não encontrado.");
      const [logradouro, bairro, cidade, uf] = e;
      return ok({ cep: args.cep, logradouro, bairro, cidade, uf });
    }
    case "solicitar_ferramenta_ausente":
      contadorPedidos += 1;
      return ok({ id_pedido: `PED-${String(contadorPedidos).padStart(4, "0")}`, nome_sugerido: args.nome_sugerido });
    case "enviar_email":
      return ok({ enviado: true, destinatario: args.destinatario });
    default:
      return erro("ferramenta_inexistente", "Ferramenta inexistente.");
  }
}

// ---------- intenção do pedido ----------
const INTENCOES = [
  { ferramenta: "enviar_email", teste: /(envi|mand|dispar).{0,40}e-?mail/ },
  { ferramenta: "listar_faturas_em_atraso", teste: /(list|quais|mostr).{0,25}faturas?/ },
  { ferramenta: "calcular_multa_atraso", teste: /multa|juros|atraso/ },
  { ferramenta: "consultar_endereco_cep", teste: /\bcep\b|endereco/ },
  { ferramenta: "consultar_transacoes_cliente", teste: /transac|vendas|extrato|movimenta|contestac|estorn/ },
  { ferramenta: "listar_tickets_cliente", teste: /chamado|ticket/ },
  { ferramenta: "resumir_receita_periodo", teste: /receita|faturamento|relatorio/ },
  { ferramenta: "consultar_cliente", teste: /cliente|lojista|cadastro|situacao|cli-?\d/ },
];

const GUARDRAILS = [
  {
    teste: /(ignor|desconsider|esquec).{0,40}(instruc|regra|orienta)|prompt do sistema|system prompt|modo desenvolvedor|revel.{0,30}(senha|credencia|token|segredo)/,
    regra: "Entrada: instrução para mudar as regras do agente",
    resposta: "Não posso seguir esse pedido: ele tenta mudar as minhas regras de funcionamento. Se precisar de algo dentro do meu objetivo, é só pedir.",
  },
  {
    teste: /(alter|troc|mud|atualiz).{0,30}(conta bancaria|dados bancarios|conta de (deposito|recebimento)|chave pix)/,
    regra: "Entrada: pedido de troca de conta bancária (risco de golpe)",
    resposta: "Troca de conta bancária não pode ser feita pelo agente. Esse é um padrão conhecido de golpe: oriente o lojista a fazer a alteração pelo app, com a verificação de identidade.",
  },
];

// ---------- o turno do agente ----------
/**
 * Roda um turno. Devolve { resposta, tipo, trajetoria, confirmacao, pendente, execucoes, uso }.
 * - pendente: estado guardado quando o agente PERGUNTA (o próximo turno continua dali).
 * - simulacao: true na etapa "Testar" da criação guiada; ferramentas de escrita não executam.
 */
export function turno({ texto, usuario, u2, ferramentasDoAgente, pendente = null, simulacao = false }) {
  const trajetoria = [];
  const execucoes = [];
  const norm = semAcento(texto);
  const passo = (acao, alvo, resumo, extra = {}) => {
    trajetoria.push({ passo: trajetoria.length + 1, acao, alvo, resumo, status: "ok", tipo_erro: null, ...extra });
  };
  const fim = (resposta, tipo = "final", extra = {}) => {
    passo(tipo === "pergunta" ? "PERGUNTAR" : tipo === "bloqueio" ? "BLOQUEIO" : tipo === "confirmacao" ? "CONFIRMAR" : "FINAL",
      "", tipo === "pergunta" ? "pergunta enviada ao funcionário" : tipo === "confirmacao" ? "aguardando confirmação do funcionário" : tipo === "bloqueio" ? "pedido barrado" : "resposta final entregue",
      extra.passoExtra || {});
    return { resposta, tipo, trajetoria: trajetoria.slice(0, MAX_PASSOS), confirmacao: extra.confirmacao || null, pendente: extra.pendente || null, execucoes, uso: calcularUso(trajetoria.length) };
  };

  // Travas de entrada (Frente 6): sempre ativas, antes do modelo.
  for (const g of GUARDRAILS) {
    if (g.teste.test(norm)) {
      return fim(g.resposta, "bloqueio", { passoExtra: { status: "bloqueado", tipo_erro: "guardrail", pensamento: g.regra } });
    }
  }

  // Lê o índice e a ficha da ferramenta; devolve a ficha liberada ou um motivo.
  const prepararFerramenta = (nome) => {
    passo("LER", "", "índice lido", { pensamento: "Vou ver quais áreas de ferramentas estão disponíveis." });
    const f = ficha(nome);
    if (!f || !ferramentasDoAgente.includes(nome)) return { problema: "ausente" };
    passo("LER", f.area, `'${f.area}' lido`, { pensamento: `A área ${f.area} parece ter o que preciso.` });
    if (f.status !== "ativa") {
      trajetoria.at(-1).resumo = `'${nome}' ainda está ${f.status}`;
      return { problema: "inativa", f };
    }
    const motivo = motivoBloqueio(f, u2);
    if (motivo) {
      passo("LER", `${f.area}/${nome}`, "caminho não encontrado ou não liberado", { status: "bloqueado", tipo_erro: "permissao_negada" });
      return { problema: "permissao", f, motivo };
    }
    passo("LER", `${f.area}/${nome}`, `'${f.area}/${nome}' lido`, { pensamento: "Vou conferir os parâmetros antes de usar." });
    return { f };
  };

  const usar = (nome, args) => {
    const r = simulacao && ficha(nome)?.acesso === "escrita"
      ? { status: "simulado", dados: null, mensagem: "Simulação: nada foi executado.", tipo_erro: null }
      : executar(nome, args, u2);
    passo("USAR", nome, `'${nome}' executada: ${r.tipo_erro || r.status}`, {
      argumentos: args,
      status: r.tipo_erro ? (r.tipo_erro === "permissao_negada" ? "bloqueado" : "erro") : "ok",
      tipo_erro: r.tipo_erro,
    });
    execucoes.push({ ferramenta: nome, status: r.status, tipo_erro: r.tipo_erro });
    return r;
  };

  const oferecerPedido = (nomeSugerido, descricao, motivo) =>
    fim(
      `${motivo}\n\nQuer que eu registre um pedido de ferramenta nova (${nomeSugerido}) para o time de Ferramentas?`,
      "pergunta",
      { pendente: { tipo: "oferta_pedido", nome_sugerido: nomeSugerido, descricao } },
    );

  // ----- continuação de uma pergunta anterior -----
  let intencao = null;
  let dados = {};
  if (pendente?.tipo === "oferta_pedido") {
    if (!ehSim(texto)) return fim("Tudo bem, não registrei nenhum pedido. Posso ajudar com outra coisa?");
    const p = prepararFerramenta("solicitar_ferramenta_ausente");
    if (p.problema) return fim("Não consegui registrar o pedido: a ferramenta de pedidos não está liberada para este agente.");
    const r = usar("solicitar_ferramenta_ausente", { nome_sugerido: pendente.nome_sugerido, descricao: pendente.descricao });
    return fim(`Pedido registrado com o código ${r.dados?.id_pedido ?? "(indisponível)"}.`);
  }
  const novaIntencao = INTENCOES.find((i) => i.teste.test(norm))?.ferramenta ?? null;
  // Continua a pergunta anterior só se a resposta trouxe o dado pedido; senão, é um pedido novo.
  const trouxeDado = { calcular_multa_atraso: lerValor(texto) ?? lerDias(texto), consultar_endereco_cep: lerCep(texto) }[pendente?.ferramenta] ?? lerCliente(texto);
  if (pendente?.tipo === "dados" && (trouxeDado != null || !novaIntencao) && (trouxeDado != null || texto.trim().length < 25)) {
    intencao = pendente.ferramenta;
    dados = { ...pendente.dados };
  } else {
    intencao = novaIntencao;
  }
  dados.id_cliente = lerCliente(texto) || dados.id_cliente;
  dados.valor_fatura = lerValor(texto) ?? dados.valor_fatura;
  dados.dias_atraso = lerDias(texto) ?? dados.dias_atraso;
  dados.cep = lerCep(texto) || dados.cep;
  dados.destinatario = lerEmail(texto) || dados.destinatario;

  if (!intencao) {
    passo("LER", "", "índice lido", { pensamento: "Vou ver se alguma ferramenta serve a esse pedido." });
    const resumo = texto.trim().slice(0, 120);
    return oferecerPedido(
      "ferramenta_sob_medida",
      resumo,
      "Não encontrei uma ferramenta que faça isso. As que tenho servem para consultar clientes e transações, calcular multa por atraso e buscar endereço por CEP.",
    );
  }

  const perguntarDados = (pergunta) => fim(pergunta, "pergunta", { pendente: { tipo: "dados", ferramenta: intencao, dados } });

  // Pede o que falta antes de ler as ferramentas (regra 4 do agente: nunca chutar).
  if (intencao === "calcular_multa_atraso" && (dados.valor_fatura == null || dados.dias_atraso == null)) {
    const falta = [dados.valor_fatura == null && "do valor da fatura", dados.dias_atraso == null && "de quantos dias de atraso"].filter(Boolean).join(" e ");
    return perguntarDados(`Para calcular, preciso ${falta}. Pode me informar?`);
  }
  if (["consultar_cliente", "consultar_transacoes_cliente"].includes(intencao) && !dados.id_cliente) {
    return perguntarDados("Qual é o código do cliente? Ele tem o formato CLI-0001.");
  }
  if (intencao === "consultar_endereco_cep" && !dados.cep) {
    return perguntarDados("Qual é o CEP? Pode ser com ou sem hífen, como 01310-100.");
  }

  const p = prepararFerramenta(intencao);
  if (p.problema === "ausente" || p.problema === "inativa") {
    const motivo = p.problema === "inativa"
      ? `A ferramenta ${intencao} existe no catálogo, mas ainda está ${p.f.status}. Por isso não consigo fazer isso agora.`
      : "Este agente não tem uma ferramenta para isso.";
    return oferecerPedido(intencao, texto.trim().slice(0, 120), motivo);
  }
  if (p.problema === "permissao") {
    return fim("Não tenho acesso a isso com as suas permissões.", "final", { passoExtra: { status: "bloqueado" } });
  }

  // ----- usa a ferramenta e responde -----
  switch (intencao) {
    case "consultar_cliente": {
      const r = usar(intencao, { id_cliente: dados.id_cliente });
      if (r.tipo_erro === "permissao_negada") return fim(`Não tenho acesso ao cliente ${dados.id_cliente}: ele não está na sua carteira.`);
      if (r.tipo_erro) return fim(`Não encontrei o cliente ${dados.id_cliente}. Confira o código e tente de novo.`);
      const c = r.dados;
      return fim(
        `${c.nome_fantasia} (${c.id_cliente})\n• Segmento: ${c.segmento}\n• Cidade: ${c.cidade}/${c.uf}\n• Situação: ${c.situacao}\n• Cliente desde: ${dataBR(c.cliente_desde)}`,
      );
    }
    case "consultar_transacoes_cliente": {
      const r = usar(intencao, { id_cliente: dados.id_cliente, limite: 20 });
      if (r.tipo_erro === "permissao_negada") return fim(`Não tenho acesso às transações do ${dados.id_cliente}: ele não está na sua carteira.`);
      if (r.tipo_erro === "integracao_indisponivel") {
        return fim(`O sistema de pagamentos não respondeu agora, então não consegui trazer as transações do ${dados.id_cliente}. O responsável já foi avisado pelo Monitoramento. Tente de novo em alguns minutos.`, "final", { passoExtra: { status: "erro" } });
      }
      if (r.tipo_erro) return fim(`Não encontrei o cliente ${dados.id_cliente}.`);
      const { todas, total } = r.dados;
      if (!total) return fim(`O cliente ${dados.id_cliente} não tem transações registradas.`);
      const contestadas = todas.filter((t) => t.situacao === "contestada").length;
      const estornadas = todas.filter((t) => t.situacao === "estornada").length;
      const linhas = todas.slice(0, 5).map((t) => `• ${dataBR(t.data)} · ${t.tipo} · ${brl(t.valor)} · ${t.situacao}`);
      return fim(
        `O ${dados.id_cliente} (${CLIENTES[dados.id_cliente].nome_fantasia}) tem ${total} transações. As 5 mais recentes:\n${linhas.join("\n")}\n\nNo total: ${contestadas} contestadas e ${estornadas} estornadas.`,
      );
    }
    case "calcular_multa_atraso": {
      const r = usar(intencao, { valor_fatura: dados.valor_fatura, dias_atraso: dados.dias_atraso });
      if (r.tipo_erro) return perguntarDados(`${r.mensagem} Pode corrigir o valor?`);
      const d = r.dados;
      return fim(
        `Para uma fatura de ${brl(d.valor_fatura)} com ${d.dias_atraso} dias de atraso:\n• Multa (2%): ${brl(d.multa)}\n• Juros (1% ao mês, proporcional): ${brl(d.juros)}\n• Total a pagar: ${brl(d.valor_total)}`,
      );
    }
    case "consultar_endereco_cep": {
      const r = usar(intencao, { cep: dados.cep });
      if (r.tipo_erro) return fim(`Não encontrei o CEP ${dados.cep.replace(/(\d{5})(\d{3})/, "$1-$2")} na base.`);
      const e = r.dados;
      return fim(`${e.logradouro}, ${e.bairro}, ${e.cidade}/${e.uf} (CEP ${e.cep.replace(/(\d{5})(\d{3})/, "$1-$2")}).`);
    }
    case "enviar_email": {
      const destinatario = dados.destinatario || "time-financeiro@stonelab.dev";
      const args = {
        destinatario,
        assunto: "Resumo semanal de receita",
        corpo: "Olá, time.\n\nSegue o resumo da semana: receita estável, 3 contestações abertas e nenhuma falha de liquidação.\n\nAbraços,",
      };
      if (simulacao) {
        usar(intencao, args);
        return fim(`Simulação: eu prepararia um e-mail para ${destinatario} e pediria sua confirmação. Nada foi enviado.`);
      }
      const confirmacao = {
        id: `cf-${Date.now().toString(36)}`,
        ferramenta: "enviar_email",
        titulo: "Enviar e-mail",
        campos: [
          { rotulo: "Para", valor: args.destinatario },
          { rotulo: "Assunto", valor: args.assunto },
          { rotulo: "Mensagem", valor: args.corpo },
        ],
        argumentos: args,
        situacao: "pendente",
      };
      return fim("Preparei o e-mail abaixo. Revise e confirme para eu enviar.", "confirmacao", { confirmacao });
    }
    default:
      return fim("Não consegui concluir. Tente reformular o pedido.");
  }
}

/** Resultado da confirmação de uma ação de escrita (Sprint 3). */
export function confirmar({ confirmacao, aprovar, u2 }) {
  const trajetoria = [];
  const execucoes = [];
  if (!aprovar) {
    trajetoria.push({ passo: 1, acao: "FINAL", alvo: "", resumo: "envio cancelado pelo funcionário", status: "ok", tipo_erro: null });
    return { resposta: "Envio cancelado. Nada foi enviado.", tipo: "final", trajetoria, execucoes, uso: calcularUso(1) };
  }
  const r = executar(confirmacao.ferramenta, confirmacao.argumentos, u2);
  execucoes.push({ ferramenta: confirmacao.ferramenta, status: r.status, tipo_erro: r.tipo_erro });
  trajetoria.push({ passo: 1, acao: "USAR", alvo: confirmacao.ferramenta, resumo: `'${confirmacao.ferramenta}' executada: ${r.tipo_erro || r.status}`, status: r.tipo_erro ? "erro" : "ok", tipo_erro: r.tipo_erro });
  trajetoria.push({ passo: 2, acao: "FINAL", alvo: "", resumo: "resposta final entregue", status: "ok", tipo_erro: null });
  return {
    resposta: r.tipo_erro ? `Não consegui enviar: ${r.mensagem}` : `E-mail enviado para ${confirmacao.argumentos.destinatario}.`,
    tipo: "final",
    trajetoria,
    execucoes,
    uso: calcularUso(2),
  };
}

export function calcularUso(chamadas) {
  let entrada = 0;
  let saida = 0;
  let latencia = 0;
  for (let i = 1; i <= chamadas; i++) {
    entrada += 850 + 320 * i + Math.floor(Math.random() * 120);
    saida += 45 + Math.floor(Math.random() * 90);
    latencia += 450 + Math.floor(Math.random() * 900);
  }
  const custo = Math.round(((entrada + saida) / 1000) * PRECO_POR_1K_TOKENS * 10000) / 10000;
  return { chamadas_modelo: chamadas, tokens_entrada: entrada, tokens_saida: saida, latencia_ms: latencia, custo };
}
