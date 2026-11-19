// Back-end simulado. Responde as mesmas rotas de frontend/CONTRATO_API.md, com os mesmos
// formatos e códigos de erro. O estado fica no navegador (localStorage) para sobreviver ao F5.
//
// Quando o back-end real estiver pronto, este arquivo deixa de ser usado (abra com ?mock=0).

import { ErroApi } from "../api.js";
import { esperar } from "../util.js";
import { USUARIOS, AGENTES, SENHA_DEMO, LIMITE_MES, GASTO_INICIAL, ALERTAS_INICIAIS, PRECO_POR_1K_TOKENS, CLIENTE_COM_FALHA } from "./dados.js";
import { pode, acoesPermitidas, relacao, usuarioCamada2, catalogoPara } from "./permissoes.js";
import { turno, confirmar } from "./motor.js";
import { novoRascunho, aplicarRespostas, aplicarAjuste, editarFicha } from "./onboarding.js";

const CHAVE_DB = "stonelab.mock.db.v1";
const DIA_MS = 86400000;
// Datas no fuso local (não UTC), para "hoje" bater com o relógio de quem usa.
const diaLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const hoje = () => diaLocal(new Date());
const agora = () => new Date().toISOString();
const novoId = (prefixo) => `${prefixo}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

// ---------- histórico de uso (gerado, determinístico) ----------
// Quem usa cada agente no dia a dia (para os gráficos do Monitoramento).
const USO_PADRAO = [
  ["ag-atendimento", "u-bruno"],
  ["ag-atendimento", "u-carla"],
  ["ag-chamados", "u-carla"],
  ["ag-cobranca", "u-diego"],
  ["ag-relatorio", "u-fernanda"],
  ["ag-relatorio", "u-diego"],
  ["ag-conciliacao", "u-ana"],
  ["ag-atendimento", "u-ana"],
];

function aleatorio(semente) {
  let s = semente;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

function gerarHistorico() {
  const sorteio = aleatorio(20261112);
  const linhas = [];
  for (let d = 29; d >= 0; d--) {
    const data = new Date(Date.now() - d * DIA_MS);
    const dia = diaLocal(data);
    const fimDeSemana = [0, 6].includes(data.getDay());
    for (const [agente_id, usuario] of USO_PADRAO) {
      if (agente_id === "ag-conciliacao" && d < 18) continue; // deprecado há 18 dias
      const execucoes = Math.round((fimDeSemana ? 1 : 4) + sorteio() * (fimDeSemana ? 2 : 9));
      const falhando = agente_id === "ag-chamados" || (agente_id === "ag-cobranca" && d === 0);
      const erros = Math.floor(sorteio() * (falhando ? 3 : 1.4));
      const chamadas = Math.round(execucoes * (4 + sorteio() * 2));
      const tokens_entrada = chamadas * Math.round(1100 + sorteio() * 500);
      const tokens_saida = chamadas * Math.round(60 + sorteio() * 60);
      linhas.push({
        dia, agente_id, usuario, execucoes, erros: Math.min(erros, execucoes), chamadas,
        tokens_entrada, tokens_saida,
        latencia_ms_total: chamadas * Math.round(700 + sorteio() * 900),
        custo: 0,
      });
    }
  }
  // Ajusta o custo para que o gasto do mês de cada pessoa bata com GASTO_INICIAL.
  const mes = hoje().slice(0, 7);
  for (const [usuario, alvo] of Object.entries(GASTO_INICIAL)) {
    const doMes = linhas.filter((l) => l.usuario === usuario && l.dia.startsWith(mes));
    const tokens = doMes.reduce((s, l) => s + l.tokens_entrada + l.tokens_saida, 0);
    const fator = tokens ? alvo / tokens : 0;
    for (const l of linhas.filter((x) => x.usuario === usuario)) {
      l.custo = (l.tokens_entrada + l.tokens_saida) * fator;
    }
  }
  return linhas;
}

// ---------- banco em memória + localStorage ----------
let db = null;

function salvar() {
  try {
    localStorage.setItem(CHAVE_DB, JSON.stringify({ ...db, historico: undefined }));
  } catch {
    // sem armazenamento: o estado vale só até recarregar
  }
}

function carregar() {
  if (db) return db;
  let guardado = null;
  try {
    guardado = JSON.parse(localStorage.getItem(CHAVE_DB) || "null");
  } catch {
    guardado = null;
  }
  db = guardado || {
    agentes: structuredClone(AGENTES),
    conversas: [],
    rascunhos: [],
    uso: [],
    alertas: structuredClone(ALERTAS_INICIAIS),
  };
  db.historico = gerarHistorico();
  if (!guardado) semearConversas();
  salvar();
  return db;
}

export function reiniciarMock() {
  try {
    localStorage.removeItem(CHAVE_DB);
  } catch {
    // nada a fazer
  }
  db = null;
}

function semearConversas() {
  const exemplos = [
    ["u-carla", "ag-atendimento", ["Qual a situação do cliente CLI-0002?"], 26],
    ["u-carla", "ag-atendimento", ["Calcule a multa de uma fatura de R$ 1.250,00 com 15 dias de atraso"], 3],
    ["u-bruno", "ag-atendimento", ["Me mostre as transações do CLI-0001"], 5],
    ["u-diego", "ag-cobranca", ["Quero a multa de uma fatura", "R$ 980,00 e 40 dias"], 20],
    ["u-ana", "ag-atendimento", ["Qual o endereço do CEP 20040-020?"], 30],
  ];
  for (const [usuarioId, agenteId, textos, horasAtras] of exemplos) {
    const usuario = USUARIOS.find((u) => u.id === usuarioId);
    const agente = db.agentes.find((a) => a.id === agenteId);
    const inicio = Date.now() - horasAtras * 3600000;
    const conversa = { id: novoId("cv"), usuario: usuarioId, agente_id: agenteId, criada_em: new Date(inicio).toISOString(), atualizada_em: null, titulo: textos[0].slice(0, 60), mensagens: [], pendente: null };
    let pendente = null;
    textos.forEach((texto, i) => {
      const quando = new Date(inicio + i * 60000).toISOString();
      conversa.mensagens.push({ id: novoId("m"), autor: "usuario", texto, criada_em: quando });
      const r = turno({ texto, usuario, u2: usuarioCamada2(usuario), ferramentasDoAgente: agente.ferramentas, pendente });
      pendente = r.pendente;
      conversa.mensagens.push({ id: novoId("m"), autor: "agente", texto: r.resposta, tipo: r.tipo, trajetoria: r.trajetoria, uso: r.uso, confirmacao: r.confirmacao, criada_em: new Date(inicio + i * 60000 + 9000).toISOString() });
    });
    conversa.pendente = pendente;
    conversa.atualizada_em = conversa.mensagens.at(-1).criada_em;
    db.conversas.push(conversa);
  }
}

// ---------- autenticação ----------
function usuarioDoToken(token) {
  const id = typeof token === "string" && token.startsWith("mock.") ? token.slice(5) : null;
  const usuario = USUARIOS.find((u) => u.id === id);
  if (!usuario) throw new ErroApi(401, "Sua sessão expirou. Entre novamente.");
  return usuario;
}

// ---------- montagem das respostas ----------
function gastoMes(usuarioId) {
  const mes = hoje().slice(0, 7);
  const linhas = [...db.historico, ...db.uso].filter((l) => l.usuario === usuarioId && l.dia.startsWith(mes));
  return Math.round(linhas.reduce((s, l) => s + l.custo, 0) * 100) / 100;
}

function me(usuario) {
  return {
    id: usuario.id,
    nome: usuario.nome,
    email: usuario.email,
    perfil: usuario.perfil,
    area: usuario.area,
    areas_extras: usuario.areas_extras,
    carteira: usuario.carteira,
    uso_mes: { gasto: gastoMes(usuario.id), limite: LIMITE_MES[usuario.perfil] },
  };
}

const nomeDe = (id) => USUARIOS.find((u) => u.id === id)?.nome ?? "—";

function agenteParaApi(agente, usuario) {
  return {
    id: agente.id,
    nome: agente.nome,
    objetivo: agente.objetivo,
    area: agente.area,
    dono: { id: agente.dono, nome: nomeDe(agente.dono) },
    ferramentas: agente.ferramentas,
    ativo: agente.ativo,
    criado_em: agente.criado_em,
    relacao: relacao(usuario, agente),
    acoes: acoesPermitidas(usuario, agente),
  };
}

function buscarAgente(id, usuario, acao = "VER") {
  const agente = db.agentes.find((a) => a.id === id);
  // Agente que a pessoa não vê é tratado como inexistente (não vaza que ele existe).
  if (!agente || !pode(usuario, "VER", agente)) throw new ErroApi(404, "Agente não encontrado.");
  if (!pode(usuario, acao, agente)) {
    throw new ErroApi(403, agente.ativo ? "Você não tem permissão para usar este agente." : "Este agente foi desativado e só pode ser consultado.");
  }
  return agente;
}

function buscarConversa(id, usuario) {
  const conversa = db.conversas.find((c) => c.id === id && c.usuario === usuario.id);
  if (!conversa) throw new ErroApi(404, "Conversa não encontrada.");
  return conversa;
}

function conversaParaApi(conversa, usuario) {
  const agente = db.agentes.find((a) => a.id === conversa.agente_id);
  return {
    id: conversa.id,
    agente: { id: agente.id, nome: agente.nome, objetivo: agente.objetivo, ferramentas: agente.ferramentas, ativo: agente.ativo, pode_executar: pode(usuario, "EXECUTAR", agente) },
    criada_em: conversa.criada_em,
    mensagens: conversa.mensagens,
  };
}

function resumoConversa(conversa) {
  const agente = db.agentes.find((a) => a.id === conversa.agente_id);
  return {
    id: conversa.id,
    agente: { id: agente.id, nome: agente.nome },
    titulo: conversa.titulo || "Nova conversa",
    criada_em: conversa.criada_em,
    atualizada_em: conversa.atualizada_em || conversa.criada_em,
  };
}

function registrarUso(usuario, agenteId, r) {
  const erros = r.execucoes.filter((e) => e.tipo_erro && e.tipo_erro !== "permissao_negada").length ? 1 : 0;
  db.uso.push({
    dia: hoje(), agente_id: agenteId, usuario: usuario.id, execucoes: 1, erros,
    chamadas: r.uso.chamadas_modelo, tokens_entrada: r.uso.tokens_entrada, tokens_saida: r.uso.tokens_saida,
    latencia_ms_total: r.uso.latencia_ms, custo: ((r.uso.tokens_entrada + r.uso.tokens_saida) / 1000) * PRECO_POR_1K_TOKENS,
  });
  // Falha controlada vira alerta para o dono (slide 32 e 41).
  const falha = r.execucoes.find((e) => e.tipo_erro === "integracao_indisponivel");
  if (falha) {
    const existente = db.alertas.find((a) => a.agente_id === agenteId && a.falha.startsWith("integracao_indisponivel"));
    if (existente) {
      existente.ocorrencias += 1;
      existente.quando = agora();
    } else {
      db.alertas.unshift({
        id: novoId("al"), nivel: "erro", agente_id: agenteId,
        falha: `integracao_indisponivel em ${falha.ferramenta} (core de pagamentos fora do ar)`,
        etapa: `Passo ${r.trajetoria.findIndex((p) => p.tipo_erro === "integracao_indisponivel") + 1}: USAR ${falha.ferramenta}`,
        quando: agora(), ocorrencias: 1,
        o_que_fazer: "Aguardar o core voltar. O agente avisou o usuário e seguiu com o restante do pedido.",
      });
    }
  }
}

function conferirLimite(usuario) {
  const limite = LIMITE_MES[usuario.perfil];
  if (usuario.perfil !== "AdminGlobal" && limite && gastoMes(usuario.id) >= limite) {
    throw new ErroApi(402, "Você atingiu o limite de gasto do mês. Peça aprovação ao seu gestor para continuar.", "limite_atingido");
  }
}

// ---------- monitoramento ----------
function escopoMonitoramento(usuario) {
  if (usuario.perfil === "GestorDeAcessos") throw new ErroApi(403, "Seu perfil não acompanha uso de agentes.");
  if (usuario.perfil === "AdminGlobal") return { escopo: "plataforma", rotulo: "Toda a plataforma", filtro: () => true };
  if (usuario.perfil === "Supervisor") {
    const areas = [usuario.area, ...usuario.areas_extras];
    const ids = db.agentes.filter((a) => areas.includes(a.area)).map((a) => a.id);
    return { escopo: "area", rotulo: "Agentes da sua área", filtro: (l) => ids.includes(l.agente_id) };
  }
  return { escopo: "pessoal", rotulo: "Seu uso", filtro: (l) => l.usuario === usuario.id };
}

function linhasDoPeriodo(usuario, dias) {
  const desde = diaLocal(new Date(Date.now() - (dias - 1) * DIA_MS));
  const escopo = escopoMonitoramento(usuario);
  return { escopo, linhas: [...db.historico, ...db.uso].filter((l) => l.dia >= desde && escopo.filtro(l)) };
}

function somar(linhas) {
  const t = { execucoes: 0, erros: 0, chamadas: 0, tokens_entrada: 0, tokens_saida: 0, latencia: 0, custo: 0 };
  for (const l of linhas) {
    t.execucoes += l.execucoes;
    t.erros += l.erros;
    t.chamadas += l.chamadas;
    t.tokens_entrada += l.tokens_entrada;
    t.tokens_saida += l.tokens_saida;
    t.latencia += l.latencia_ms_total;
    t.custo += l.custo;
  }
  return t;
}

const centavos = (v) => Math.round(v * 100) / 100;

function monitoramento(rota, usuario, dias) {
  const { escopo, linhas } = linhasDoPeriodo(usuario, dias);
  if (rota === "resumo") {
    const t = somar(linhas);
    return {
      escopo: escopo.escopo,
      rotulo_escopo: escopo.rotulo,
      dias,
      gasto_mes: gastoMes(usuario.id),
      limite_mes: LIMITE_MES[usuario.perfil],
      custo_periodo: centavos(t.custo),
      execucoes: t.execucoes,
      erros: t.erros,
      taxa_erro: t.execucoes ? t.erros / t.execucoes : 0,
      chamadas_modelo: t.chamadas,
      tokens_entrada: t.tokens_entrada,
      tokens_saida: t.tokens_saida,
      latencia_media_ms: t.chamadas ? Math.round(t.latencia / t.chamadas) : 0,
    };
  }
  if (rota === "uso-diario") {
    const porDia = new Map();
    for (let d = dias - 1; d >= 0; d--) porDia.set(diaLocal(new Date(Date.now() - d * DIA_MS)), []);
    for (const l of linhas) porDia.get(l.dia)?.push(l);
    return [...porDia.entries()].map(([dia, ls]) => {
      const t = somar(ls);
      return { dia, custo: centavos(t.custo), execucoes: t.execucoes, erros: t.erros, tokens: t.tokens_entrada + t.tokens_saida };
    });
  }
  if (rota === "agentes") {
    const ids = [...new Set(linhas.map((l) => l.agente_id))];
    return ids
      .map((id) => {
        const agente = db.agentes.find((a) => a.id === id);
        const ls = linhas.filter((l) => l.agente_id === id);
        const t = somar(ls);
        const taxaErro = t.execucoes ? t.erros / t.execucoes : 0;
        return {
          agente_id: id,
          nome: agente?.nome ?? id,
          area: agente?.area,
          ativo: agente?.ativo ?? false,
          execucoes: t.execucoes,
          taxa_sucesso: 1 - taxaErro,
          latencia_media_ms: t.chamadas ? Math.round(t.latencia / t.chamadas) : 0,
          tokens: t.tokens_entrada + t.tokens_saida,
          custo: centavos(t.custo),
          ultimo_uso: ls.map((l) => l.dia).sort().at(-1),
          saude: !agente?.ativo ? "inativo" : taxaErro > 0.15 ? "critico" : taxaErro > 0.06 ? "atencao" : "saudavel",
        };
      })
      .sort((a, b) => b.execucoes - a.execucoes);
  }
  throw new ErroApi(404, "Rota não encontrada.");
}

function alertas(usuario) {
  const escopo = escopoMonitoramento(usuario);
  const visiveis = db.alertas.filter((a) => {
    const agente = db.agentes.find((x) => x.id === a.agente_id);
    if (!agente) return false;
    if (escopo.escopo === "plataforma") return true;
    if (escopo.escopo === "area") return [usuario.area, ...usuario.areas_extras].includes(agente.area);
    return agente.dono === usuario.id;
  });
  const lista = visiveis.map((a) => ({ ...a, agente: { id: a.agente_id, nome: db.agentes.find((x) => x.id === a.agente_id)?.nome } }));
  const limite = LIMITE_MES[usuario.perfil];
  const gasto = gastoMes(usuario.id);
  if (limite && gasto / limite >= 0.8) {
    lista.unshift({
      id: "al-limite",
      nivel: gasto >= limite ? "erro" : "aviso",
      agente: null,
      falha: `Gasto do mês em ${Math.round((gasto / limite) * 100)}% do seu limite`,
      etapa: "Limite de gasto",
      quando: agora(),
      ocorrencias: 1,
      o_que_fazer: "Ao chegar em 100%, novas mensagens precisam de aprovação do seu gestor.",
    });
  }
  return lista;
}

// ---------- roteador ----------
const ROTAS = [];
const rota = (metodo, padrao, funcao) => ROTAS.push({ metodo, padrao: new RegExp(`^${padrao.replace(/:(\w+)/g, "(?<$1>[^/]+)")}$`), funcao });

rota("GET", "/health", () => ({ status: "ok", modo: "mock" }));

rota("POST", "/auth/login", ({ corpo }) => {
  const usuario = USUARIOS.find((u) => u.email.toLowerCase() === String(corpo?.email || "").trim().toLowerCase());
  if (!usuario || corpo?.senha !== SENHA_DEMO) throw new ErroApi(401, "E-mail ou senha inválidos.");
  return { token: `mock.${usuario.id}`, tipo: "bearer" };
});

rota("GET", "/me", ({ usuario }) => me(usuario));

rota("GET", "/agentes", ({ usuario }) =>
  db.agentes.filter((a) => pode(usuario, "VER", a)).map((a) => agenteParaApi(a, usuario)),
);

rota("GET", "/agentes/:id", ({ usuario, p }) => agenteParaApi(buscarAgente(p.id, usuario), usuario));

rota("GET", "/ferramentas", ({ usuario }) => {
  if (usuario.perfil === "GestorDeAcessos") throw new ErroApi(403, "Seu perfil não usa ferramentas.");
  return catalogoPara(usuario);
});

rota("GET", "/conversas", ({ usuario }) =>
  db.conversas
    .filter((c) => c.usuario === usuario.id)
    .map(resumoConversa)
    .sort((a, b) => (a.atualizada_em < b.atualizada_em ? 1 : -1)),
);

rota("POST", "/conversas", ({ usuario, corpo }) => {
  const agente = buscarAgente(corpo?.agente_id, usuario, "EXECUTAR");
  const conversa = { id: novoId("cv"), usuario: usuario.id, agente_id: agente.id, criada_em: agora(), atualizada_em: null, titulo: null, mensagens: [], pendente: null };
  db.conversas.push(conversa);
  salvar();
  return conversaParaApi(conversa, usuario);
});

rota("GET", "/conversas/:id", ({ usuario, p }) => conversaParaApi(buscarConversa(p.id, usuario), usuario));

rota("POST", "/conversas/:id/confirmacoes/:cid", ({ usuario, p, corpo }) => {
  const conversa = buscarConversa(p.id, usuario);
  const agente = buscarAgente(conversa.agente_id, usuario, "EXECUTAR");
  const msg = conversa.mensagens.find((m) => m.confirmacao?.id === p.cid);
  if (!msg) throw new ErroApi(404, "Confirmação não encontrada.");
  if (msg.confirmacao.situacao !== "pendente") throw new ErroApi(409, "Esta ação já foi confirmada ou cancelada.");
  const aprovar = corpo?.aprovar === true;
  msg.confirmacao.situacao = aprovar ? "aprovada" : "cancelada";
  const r = confirmar({ confirmacao: msg.confirmacao, aprovar, u2: usuarioCamada2(usuario) });
  const resposta = { id: novoId("m"), autor: "agente", texto: r.resposta, tipo: r.tipo, trajetoria: r.trajetoria, uso: r.uso, confirmacao: null, criada_em: agora() };
  conversa.mensagens.push(resposta);
  conversa.atualizada_em = resposta.criada_em;
  registrarUso(usuario, agente.id, r);
  salvar();
  return { id: resposta.id, resposta: r.resposta, tipo: r.tipo, trajetoria: r.trajetoria, uso: r.uso, confirmacao: null, criada_em: resposta.criada_em };
});

// ----- criação guiada -----
function buscarRascunho(id, usuario) {
  const r = db.rascunhos.find((x) => x.id === id && x.usuario === usuario.id);
  if (!r) throw new ErroApi(404, "Rascunho não encontrado.");
  return r;
}
const rascunhoParaApi = (r) => {
  const { usuario: _usuario, ...resto } = r;
  return resto;
};
function trocarRascunho(antigo, novo) {
  db.rascunhos[db.rascunhos.indexOf(antigo)] = novo;
  salvar();
  return rascunhoParaApi(novo);
}

rota("POST", "/rascunhos", ({ usuario, corpo }) => {
  if (usuario.perfil === "GestorDeAcessos") throw new ErroApi(403, "Seu perfil não cria agentes.");
  const descricao = String(corpo?.descricao || "").trim();
  if (descricao.length < 15) throw new ErroApi(422, "Descreva o problema com um pouco mais de detalhe (pelo menos 15 caracteres).", "validacao");
  const r = { id: novoId("rs"), usuario: usuario.id, criado_em: agora(), ...novoRascunho(descricao, usuario) };
  db.rascunhos.push(r);
  salvar();
  return rascunhoParaApi(r);
});

rota("GET", "/rascunhos/:id", ({ usuario, p }) => rascunhoParaApi(buscarRascunho(p.id, usuario)));

rota("POST", "/rascunhos/:id/respostas", ({ usuario, p, corpo }) => {
  const r = buscarRascunho(p.id, usuario);
  return trocarRascunho(r, aplicarRespostas(r, corpo?.respostas || {}, usuarioCamada2(usuario)));
});

rota("POST", "/rascunhos/:id/ajustes", ({ usuario, p, corpo }) => {
  const r = buscarRascunho(p.id, usuario);
  if (!r.ficha) throw new ErroApi(409, "Responda as perguntas antes de ajustar.");
  return trocarRascunho(r, aplicarAjuste(r, String(corpo?.texto || ""), usuarioCamada2(usuario)));
});

rota("PATCH", "/rascunhos/:id", ({ usuario, p, corpo }) => {
  const r = buscarRascunho(p.id, usuario);
  if (!r.ficha) throw new ErroApi(409, "Responda as perguntas antes de editar a ficha.");
  return trocarRascunho(r, editarFicha(r, corpo?.ficha || {}, usuarioCamada2(usuario)));
});

rota("POST", "/rascunhos/:id/simulacao", ({ usuario, p, corpo }) => {
  const r = buscarRascunho(p.id, usuario);
  if (!r.ficha) throw new ErroApi(409, "Monte a ficha antes de testar.");
  const exemplo = String(corpo?.exemplo || "").trim();
  if (!exemplo) throw new ErroApi(422, "Escreva um pedido de exemplo.", "validacao");
  const t = turno({ texto: exemplo, usuario, u2: usuarioCamada2(usuario), ferramentasDoAgente: r.ficha.ferramentas.map((f) => f.nome), simulacao: true });
  r.testado = true;
  salvar();
  return { resposta: t.resposta, tipo: t.tipo, trajetoria: t.trajetoria, uso: t.uso, simulacao: true };
});

rota("POST", "/rascunhos/:id/aprovar", ({ usuario, p }) => {
  const r = buscarRascunho(p.id, usuario);
  if (!r.ficha) throw new ErroApi(409, "Monte a ficha antes de aprovar.");
  if (!r.ficha.permissoes.ok) throw new ErroApi(403, "A ficha tem ferramentas que não são liberadas para você. Remova-as antes de aprovar.");
  const agente = {
    id: novoId("ag"),
    nome: r.ficha.nome,
    objetivo: r.ficha.objetivo,
    area: usuario.area,
    dono: usuario.id,
    convidados: [],
    ferramentas: r.ficha.ferramentas.map((f) => f.nome),
    ativo: true,
    criado_em: agora(),
  };
  db.agentes.push(agente);
  r.etapa = "aprovado";
  r.agente_id = agente.id;
  salvar();
  return agenteParaApi(agente, usuario);
});

// ----- monitoramento -----
const diasDe = (q) => Math.min(Math.max(Number(q.get("dias")) || 30, 1), 30);
rota("GET", "/monitoramento/resumo", ({ usuario, q }) => monitoramento("resumo", usuario, diasDe(q)));
rota("GET", "/monitoramento/uso-diario", ({ usuario, q }) => monitoramento("uso-diario", usuario, diasDe(q)));
rota("GET", "/monitoramento/agentes", ({ usuario, q }) => monitoramento("agentes", usuario, diasDe(q)));
rota("GET", "/monitoramento/alertas", ({ usuario }) => alertas(usuario));

const ROTAS_PUBLICAS = ["/health", "/auth/login"];

/** Ponto de entrada usado por api.js em modo mock. */
export async function atender(metodo, caminhoCompleto, corpo, token) {
  carregar();
  await esperar(120 + Math.random() * 200);
  const [caminho, busca = ""] = caminhoCompleto.split("?");
  for (const r of ROTAS) {
    const m = r.metodo === metodo && caminho.match(r.padrao);
    if (!m) continue;
    const usuario = ROTAS_PUBLICAS.includes(caminho) ? null : usuarioDoToken(token);
    // structuredClone: a tela nunca altera o "banco" por referência
    return structuredClone(r.funcao({ usuario, corpo, p: m.groups || {}, q: new URLSearchParams(busca) }));
  }
  throw new ErroApi(404, "Rota não encontrada.");
}

/** POST /conversas/{id}/mensagens com um passo por vez (imita o SSE da Sprint 3). */
export async function enviarMensagemComPassos(conversaId, texto, token, aoPasso) {
  carregar();
  const usuario = usuarioDoToken(token);
  const conversa = buscarConversa(conversaId, usuario);
  const agente = buscarAgente(conversa.agente_id, usuario, "EXECUTAR");
  const limpo = String(texto || "").trim();
  if (!limpo) throw new ErroApi(422, "Escreva uma mensagem.", "validacao");
  if (limpo.length > 2000) throw new ErroApi(422, "Mensagem muito longa (máximo 2.000 caracteres).", "validacao");
  conferirLimite(usuario);

  conversa.mensagens.push({ id: novoId("m"), autor: "usuario", texto: limpo, criada_em: agora() });
  conversa.titulo ||= limpo.slice(0, 60);
  salvar();

  const r = turno({ texto: limpo, usuario, u2: usuarioCamada2(usuario), ferramentasDoAgente: agente.ferramentas, pendente: conversa.pendente });
  for (const passo of r.trajetoria) {
    await esperar(passo.acao === "USAR" ? 750 : 380);
    aoPasso?.(structuredClone(passo));
  }
  await esperar(200);

  const resposta = { id: novoId("m"), autor: "agente", texto: r.resposta, tipo: r.tipo, trajetoria: r.trajetoria, uso: r.uso, confirmacao: r.confirmacao, criada_em: agora() };
  conversa.mensagens.push(resposta);
  conversa.pendente = r.pendente;
  conversa.atualizada_em = resposta.criada_em;
  registrarUso(usuario, agente.id, r);
  salvar();
  return structuredClone({ id: resposta.id, resposta: r.resposta, tipo: r.tipo, trajetoria: r.trajetoria, uso: r.uso, confirmacao: r.confirmacao, criada_em: resposta.criada_em });
}

export const CENARIOS_DEMO = { CLIENTE_COM_FALHA };
