// Cliente da API. É o ÚNICO arquivo que fala com o back-end.
// Cada função aqui corresponde a uma rota descrita em frontend/CONTRATO_API.md.
//
// Em modo mock (CONFIG.MOCK), as mesmas chamadas vão para js/mock/servidor.js,
// que responde no mesmo formato. Assim, trocar para o back-end real não muda as telas.

import { CONFIG } from "./config.js";
import { sessao } from "./sessao.js";

export class ErroApi extends Error {
  constructor(status, mensagem, codigo = null) {
    super(mensagem);
    this.status = status;
    this.codigo = codigo;
  }
}

// Avisado quando o token expira (401): o app volta para o login.
let aoExpirar = () => {};
export function quandoSessaoExpirar(funcao) {
  aoExpirar = funcao;
}

let servidorMock = null;
async function mock() {
  if (!servidorMock) servidorMock = await import("./mock/servidor.js");
  return servidorMock;
}

/** Converte o corpo de erro do FastAPI ({detail: ...}) em mensagem legível. */
function lerErro(status, corpo) {
  const detalhe = corpo?.detail;
  if (typeof detalhe === "string") return new ErroApi(status, detalhe);
  if (detalhe && typeof detalhe === "object" && !Array.isArray(detalhe)) {
    return new ErroApi(status, detalhe.mensagem || "Erro na requisição.", detalhe.codigo || null);
  }
  if (Array.isArray(detalhe)) {
    // erro de validação do pydantic (422)
    return new ErroApi(status, detalhe.map((d) => d.msg).join("; ") || "Dados inválidos.", "validacao");
  }
  const padrao = {
    400: "Requisição inválida.",
    401: "Sua sessão expirou. Entre novamente.",
    403: "Você não tem permissão para isso.",
    404: "Não encontrado.",
    429: "Muitas requisições. Tente de novo em instantes.",
    500: "Erro interno no servidor.",
    502: "O modelo não respondeu. Tente de novo.",
    503: "Serviço indisponível no momento.",
  };
  return new ErroApi(status, padrao[status] || `Erro ${status}.`);
}

async function requisitar(metodo, caminho, corpo) {
  const token = sessao.token;
  if (CONFIG.MOCK) {
    try {
      return await (await mock()).atender(metodo, caminho, corpo, token);
    } catch (erro) {
      if (erro instanceof ErroApi && erro.status === 401 && caminho !== "/auth/login") aoExpirar();
      throw erro;
    }
  }

  let resposta;
  try {
    resposta = await fetch(CONFIG.API_URL + caminho, {
      method: metodo,
      headers: {
        Accept: "application/json",
        ...(corpo !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
    });
  } catch {
    throw new ErroApi(0, "Não foi possível falar com o back-end. Ele está rodando?", "rede");
  }

  const texto = await resposta.text();
  let dados = null;
  try {
    dados = texto ? JSON.parse(texto) : null;
  } catch {
    dados = null;
  }
  if (!resposta.ok) {
    if (resposta.status === 401 && caminho !== "/auth/login") aoExpirar();
    throw lerErro(resposta.status, dados);
  }
  return dados;
}

const get = (caminho) => requisitar("GET", caminho);
const post = (caminho, corpo = {}) => requisitar("POST", caminho, corpo);
const patch = (caminho, corpo = {}) => requisitar("PATCH", caminho, corpo);
const qs = (params) => {
  const p = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
  const s = p.toString();
  return s ? `?${s}` : "";
};

// ---------- SSE (Sprint 3) ----------
// POST com Accept: text/event-stream. Eventos: "passo" (um item da trajetória) e "mensagem" (a resposta final).
async function enviarComSSE(conversaId, texto, aoPasso) {
  const resposta = await fetch(`${CONFIG.API_URL}/conversas/${conversaId}/mensagens`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      Authorization: `Bearer ${sessao.token}`,
    },
    body: JSON.stringify({ texto }),
  });
  if (!resposta.ok) {
    if (resposta.status === 401) aoExpirar();
    let corpo = null;
    try {
      corpo = await resposta.json();
    } catch {
      corpo = null;
    }
    throw lerErro(resposta.status, corpo);
  }
  const leitor = resposta.body.getReader();
  const decodificador = new TextDecoder();
  let buffer = "";
  let final = null;
  for (;;) {
    const { value, done } = await leitor.read();
    if (done) break;
    buffer += decodificador.decode(value, { stream: true });
    let fim;
    while ((fim = buffer.indexOf("\n\n")) >= 0) {
      const bloco = buffer.slice(0, fim);
      buffer = buffer.slice(fim + 2);
      let evento = "message";
      let dados = "";
      for (const linha of bloco.split("\n")) {
        if (linha.startsWith("event:")) evento = linha.slice(6).trim();
        else if (linha.startsWith("data:")) dados += linha.slice(5).trim();
      }
      if (!dados) continue;
      const json = JSON.parse(dados);
      if (evento === "passo") aoPasso?.(json);
      else if (evento === "mensagem") final = json;
      else if (evento === "erro") throw new ErroApi(json.status || 500, json.mensagem || "Erro no agente.", json.codigo);
    }
  }
  if (!final) throw new ErroApi(500, "A resposta do agente veio incompleta.");
  return final;
}

export const api = {
  // ----- Sprint 2 (KAN-60) -----
  saude: () => get("/health"),
  login: (email, senha) => post("/auth/login", { email, senha }),
  me: () => get("/me"),
  agentes: () => get("/agentes"),
  agente: (id) => get(`/agentes/${id}`),
  conversas: () => get("/conversas"),
  abrirConversa: (agenteId) => post("/conversas", { agente_id: agenteId }),
  conversa: (id) => get(`/conversas/${id}`),

  /**
   * Envia uma mensagem e devolve a resposta do agente.
   * aoPasso(passo) é chamado a cada passo quando há streaming (SSE ou mock);
   * sem streaming, a trajetória chega inteira no final.
   */
  async enviarMensagem(conversaId, texto, { aoPasso } = {}) {
    if (CONFIG.MOCK) {
      return (await mock()).enviarMensagemComPassos(conversaId, texto, sessao.token, aoPasso);
    }
    if (CONFIG.SSE) return enviarComSSE(conversaId, texto, aoPasso);
    return post(`/conversas/${conversaId}/mensagens`, { texto });
  },

  // ----- Sprint 3 -----
  confirmarAcao: (conversaId, confirmacaoId, aprovar) =>
    post(`/conversas/${conversaId}/confirmacoes/${confirmacaoId}`, { aprovar }),

  ferramentas: () => get("/ferramentas"),

  // Criação guiada (onboarding em 8 etapas)
  criarRascunho: (descricao) => post("/rascunhos", { descricao }),
  rascunho: (id) => get(`/rascunhos/${id}`),
  responderRascunho: (id, respostas) => post(`/rascunhos/${id}/respostas`, { respostas }),
  ajustarRascunho: (id, texto) => post(`/rascunhos/${id}/ajustes`, { texto }),
  editarFicha: (id, ficha) => patch(`/rascunhos/${id}`, { ficha }),
  simularRascunho: (id, exemplo) => post(`/rascunhos/${id}/simulacao`, { exemplo }),
  aprovarRascunho: (id) => post(`/rascunhos/${id}/aprovar`),

  // Monitoramento
  resumoUso: (dias = 30) => get(`/monitoramento/resumo${qs({ dias })}`),
  usoDiario: (dias = 30) => get(`/monitoramento/uso-diario${qs({ dias })}`),
  usoPorAgente: (dias = 30) => get(`/monitoramento/agentes${qs({ dias })}`),
  alertas: () => get("/monitoramento/alertas"),
};
