// Criação guiada simulada (slide 11: Descrever, Entender, Perguntar, Checar permissões,
// Propor, Ajustar, Testar, Aprovar). No back-end real, as etapas Entender/Perguntar/Propor/Ajustar
// são feitas pelo modelo; aqui são regras por palavra-chave.

import { ficha as fichaFerramenta, motivoBloqueio } from "./permissoes.js";
import { PRECO_POR_1K_TOKENS } from "./dados.js";

const semAcento = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export const MAPA_DADOS = [
  { chave: "clientes", rotulo: "Cadastro de clientes", teste: /cliente|lojista|cadastro/, ferramentas: ["consultar_cliente", "buscar_clientes"], sistema: "CRM simulado" },
  { chave: "transacoes", rotulo: "Transações e vendas", teste: /transac|venda|extrato|concilia|recebiv/, ferramentas: ["consultar_transacoes_cliente"], sistema: "SQL simulado" },
  { chave: "faturas", rotulo: "Faturas, multas e cobrança", teste: /fatura|cobranc|multa|juros|atraso|inadimpl/, ferramentas: ["calcular_multa_atraso", "listar_faturas_em_atraso"], sistema: "SQL simulado" },
  { chave: "chamados", rotulo: "Chamados e histórico de contato", teste: /chamado|ticket|reclama|contato/, ferramentas: ["listar_tickets_cliente", "consultar_ticket", "consultar_historico_contato"], sistema: "CRM simulado" },
  { chave: "indicadores", rotulo: "Indicadores e relatórios", teste: /relatorio|receita|indicador|nps|contestac|volume/, ferramentas: ["resumir_receita_periodo", "consultar_taxa_contestacao_mensal", "resumir_volume_tickets"], sistema: "BigQuery" },
  { chave: "email", rotulo: "Envio de e-mails", teste: /e-?mail|enviar|avisar|notific/, ferramentas: ["enviar_email"], sistema: "Google Workspace / Microsoft 365" },
  { chave: "enderecos", rotulo: "Endereços por CEP", teste: /\bcep\b|endereco/, ferramentas: ["consultar_endereco_cep"], sistema: "APIs públicas" },
];

const FREQUENCIAS = [
  { valor: "sob_demanda", rotulo: "Sob demanda", teste: null },
  { valor: "diaria", rotulo: "Todo dia", teste: /diari|todo dia|todos os dias/ },
  { valor: "semanal", rotulo: "Toda semana", teste: /seman/ },
  { valor: "mensal", rotulo: "Todo mês", teste: /mensal|todo mes|fechamento/ },
];

const VOLUME = { ate_5: 16, de_5_a_20: 50, mais_20: 110 };
const MINUTOS_POUPADOS_POR_USO = 15;
const TOKENS_POR_USO = 5500;
const RISCO_ORDEM = ["baixo", "medio", "alto"];

export function novoRascunho(descricao, usuario) {
  const norm = semAcento(descricao);
  const detectados = MAPA_DADOS.filter((m) => m.teste.test(norm));
  const frequencia = FREQUENCIAS.find((f) => f.teste?.test(norm));
  const objetivo = descricao.trim().split(/(?<=[.!?])\s/)[0].slice(0, 160);

  const perguntas = [];
  if (!frequencia) {
    perguntas.push({
      id: "frequencia",
      texto: "Quando essa tarefa acontece?",
      multipla: false,
      opcoes: FREQUENCIAS.map(({ valor, rotulo }) => ({ valor, rotulo })),
      sugestao: "sob_demanda",
    });
  }
  perguntas.push(
    {
      id: "dados",
      texto: "Quais dados o agente precisa consultar?",
      multipla: true,
      opcoes: MAPA_DADOS.filter((m) => m.chave !== "email").map(({ chave, rotulo }) => ({ valor: chave, rotulo })),
      sugestao: detectados.filter((d) => d.chave !== "email").map((d) => d.chave),
    },
    {
      id: "acao",
      texto: "O agente deve só consultar ou também preparar ações?",
      multipla: false,
      opcoes: [
        { valor: "consultar", rotulo: "Só consultar e responder" },
        { valor: "agir", rotulo: "Preparar ações (como e-mails) para eu aprovar" },
      ],
      sugestao: detectados.some((d) => d.chave === "email") ? "agir" : "consultar",
    },
    {
      id: "volume",
      texto: "Quantas vezes por mês, mais ou menos, alguém faz essa tarefa hoje?",
      multipla: false,
      opcoes: [
        { valor: "ate_5", rotulo: "Poucas (até 20)" },
        { valor: "de_5_a_20", rotulo: "Várias (20 a 80)" },
        { valor: "mais_20", rotulo: "Muitas (mais de 80)" },
      ],
      sugestao: "de_5_a_20",
    },
  );

  return {
    etapa: "perguntas",
    descricao,
    area: usuario.area,
    entendimento: {
      objetivo,
      quando: frequencia?.rotulo ?? "A confirmar",
      sistemas: [...new Set(detectados.map((d) => d.sistema))],
      dados: detectados.map((d) => d.rotulo),
    },
    perguntas,
    respostas: {},
    ficha: null,
    mensagem: detectados.length
      ? "Entendi o pedido. Faltam alguns detalhes: escolha as opções abaixo."
      : "Não identifiquei os dados envolvidos. Escolha abaixo o que o agente precisa consultar.",
  };
}

function detalharFerramenta(nome, u2) {
  const f = fichaFerramenta(nome);
  if (!f) return null;
  const motivo = motivoBloqueio(f, u2);
  return {
    nome: f.nome,
    area: f.area,
    descricao: f.descricao,
    acesso: f.acesso,
    sensibilidade: f.sensibilidade,
    status: f.status,
    liberada: motivo === null,
    motivo,
  };
}

/** Recalcula risco, custo, economia e avisos de permissão (etapa 4: Checar permissões). */
function completarFicha(ficha, u2, usosMes) {
  const detalhes = [...new Set(ficha.ferramentas.map((f) => (typeof f === "string" ? f : f.nome)))]
    .map((nome) => detalharFerramenta(nome, u2))
    .filter(Boolean);
  const escrita = detalhes.filter((f) => f.acesso === "escrita" && f.nome !== "solicitar_ferramenta_ausente");
  const sensiveis = detalhes.filter((f) => f.sensibilidade === "sigilosa" || f.sensibilidade === "pessoal");
  const risco = RISCO_ORDEM[Math.max(escrita.length ? 2 : 0, sensiveis.length ? 1 : 0)];

  const avisos = [];
  for (const f of detalhes) {
    if (!f.liberada) avisos.push({ nivel: "erro", texto: `${f.nome} não está liberada para o seu perfil (${f.motivo}).` });
    else if (f.status !== "ativa") avisos.push({ nivel: "aviso", texto: `${f.nome} ainda está ${f.status}: o agente só poderá usá-la depois de ativada.` });
  }
  for (const f of escrita) avisos.push({ nivel: "info", texto: `${f.nome} é de escrita: cada uso pede a sua confirmação antes de executar.` });
  if (sensiveis.length) avisos.push({ nivel: "info", texto: "Usa dados pessoais ou sigilosos: CPF, cartão e dados bancários são mascarados antes de chegar ao modelo." });

  return {
    ...ficha,
    ferramentas: detalhes,
    risco,
    usos_mes_estimados: usosMes,
    custo_estimado_mes: Math.round(((usosMes * TOKENS_POR_USO) / 1000) * PRECO_POR_1K_TOKENS * 100) / 100,
    economia_horas_mes: Math.round((usosMes * MINUTOS_POUPADOS_POR_USO) / 60),
    permissoes: { ok: detalhes.every((f) => f.liberada), avisos },
  };
}

function nomeSugerido(chaves, area) {
  if (chaves.includes("chamados")) return "Resumo de Chamados";
  if (chaves.includes("faturas")) return "Assistente de Cobrança";
  if (chaves.includes("indicadores")) return "Relatório de Indicadores";
  if (chaves.includes("transacoes")) return "Consulta de Transações";
  if (chaves.includes("clientes")) return "Consulta de Clientes";
  return area === "Financeiro" ? "Assistente Financeiro" : "Assistente de Atendimento";
}

export function aplicarRespostas(rascunho, respostas, u2) {
  const todas = { ...rascunho.respostas, ...respostas };
  let chaves = Array.isArray(todas.dados) ? todas.dados : [];
  if (todas.acao === "agir") chaves = [...chaves, "email"];
  const blocos = MAPA_DADOS.filter((m) => chaves.includes(m.chave));
  let ferramentas = blocos.flatMap((b) => b.ferramentas);
  if (todas.acao !== "agir") ferramentas = ferramentas.filter((n) => fichaFerramenta(n)?.acesso !== "escrita");
  ferramentas.push("solicitar_ferramenta_ausente");

  const passos = ["Entender o pedido do funcionário e perguntar o que faltar"];
  for (const b of blocos) {
    if (b.chave === "email") passos.push("Preparar o e-mail e pedir confirmação antes de enviar");
    else if (b.chave === "faturas") passos.push("Calcular multa e juros da fatura em atraso");
    else passos.push(`Consultar ${b.rotulo.toLowerCase()}`);
  }
  passos.push("Responder com um resumo claro, sem inventar dados");

  const usos = VOLUME[todas.volume] ?? VOLUME.de_5_a_20;
  const ficha = completarFicha(
    {
      nome: nomeSugerido(chaves, rascunho.area),
      objetivo: rascunho.entendimento.objetivo,
      area: rascunho.area,
      passos,
      ferramentas,
    },
    u2,
    usos,
  );
  return { ...rascunho, respostas: todas, etapa: "proposta", ficha, mensagem: "Montei a ficha do agente. Revise, ajuste se quiser e teste antes de aprovar." };
}

/** Etapa 6: ajuste em linguagem simples. */
export function aplicarAjuste(rascunho, texto, u2) {
  const norm = semAcento(texto);
  const ficha = { ...rascunho.ficha, ferramentas: rascunho.ficha.ferramentas.map((f) => f.nome), passos: [...rascunho.ficha.passos] };
  const mudancas = [];

  const nome = texto.match(/(?:chame|chamar|renomei[ae]|nome)\s*(?:o agente\s*)?(?:de|para|como|:)\s*["“']?([^"”'\n.]{3,60})/i);
  if (nome) {
    ficha.nome = nome[1].trim();
    mudancas.push(`nome alterado para "${ficha.nome}"`);
  }

  const remover = /(remov|tir|sem |exclu|nao precisa)/.test(norm);
  const adicionar = /(adicion|inclu|coloc|tambem|acrescent|quero que)/.test(norm);
  const alvoBlocos = MAPA_DADOS.filter((m) => m.teste.test(norm));
  const alvoNomes = ficha.ferramentas.concat(MAPA_DADOS.flatMap((m) => m.ferramentas)).filter((n) => norm.includes(n));
  const alvos = [...new Set([...alvoBlocos.flatMap((b) => b.ferramentas), ...alvoNomes])];

  if (/so consult|sem escrita|nao (pode )?envi/.test(norm)) {
    const antes = ficha.ferramentas.length;
    ficha.ferramentas = ficha.ferramentas.filter((n) => n === "solicitar_ferramenta_ausente" || fichaFerramenta(n)?.acesso !== "escrita");
    ficha.passos = ficha.passos.filter((p) => !/e-mail/.test(p));
    if (ficha.ferramentas.length !== antes) mudancas.push("ferramentas de escrita removidas");
  } else if (alvos.length && remover) {
    ficha.ferramentas = ficha.ferramentas.filter((n) => !alvos.includes(n) || n === "solicitar_ferramenta_ausente");
    mudancas.push(`removidas: ${alvos.join(", ")}`);
  } else if (alvos.length && (adicionar || !nome)) {
    const novas = alvos.filter((n) => !ficha.ferramentas.includes(n));
    ficha.ferramentas.push(...novas);
    if (novas.length) mudancas.push(`adicionadas: ${novas.join(", ")}`);
  }

  const atualizada = completarFicha(ficha, u2, rascunho.ficha.usos_mes_estimados);
  return {
    ...rascunho,
    etapa: "proposta",
    ficha: atualizada,
    mensagem: mudancas.length
      ? `Feito: ${mudancas.join("; ")}.`
      : 'Não entendi o ajuste. Tente algo como "adicione envio de e-mails", "remova transações" ou "chame de Assistente de Cobrança".',
  };
}

/** Edição direta da ficha (nome, objetivo, lista de ferramentas). */
export function editarFicha(rascunho, parcial, u2) {
  const ficha = {
    ...rascunho.ficha,
    ...(parcial.nome !== undefined ? { nome: String(parcial.nome).slice(0, 80) } : {}),
    ...(parcial.objetivo !== undefined ? { objetivo: String(parcial.objetivo).slice(0, 300) } : {}),
    ferramentas: parcial.ferramentas ?? rascunho.ficha.ferramentas.map((f) => f.nome),
  };
  return { ...rascunho, ficha: completarFicha(ficha, u2, rascunho.ficha.usos_mes_estimados), mensagem: null };
}
