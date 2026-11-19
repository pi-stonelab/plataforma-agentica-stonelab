// Configuração do front. Duas formas de rodar:
//
// 1. Modo mock (padrão): tudo funciona sem back-end, com dados sintéticos em js/mock/.
// 2. Back-end real: abra com ?mock=0 (e, se o back-end estiver em outra origem, ?api=http://localhost:8000).
//
// A escolha fica guardada no navegador. ?mock=1 volta ao modo mock.

const params = new URLSearchParams(location.search);

function lerGuardado(chave) {
  try {
    return localStorage.getItem(chave);
  } catch {
    return null;
  }
}

function guardar(chave, valor) {
  try {
    localStorage.setItem(chave, valor);
  } catch {
    // navegador sem armazenamento: a escolha vale só para esta aba
  }
}

if (params.has("mock")) guardar("stonelab.mock", params.get("mock") === "0" ? "0" : "1");
if (params.has("api")) guardar("stonelab.api", params.get("api"));
if (params.has("sse")) guardar("stonelab.sse", params.get("sse") === "1" ? "1" : "0");

export const CONFIG = {
  // true: usa o back-end simulado em js/mock/servidor.js
  MOCK: (lerGuardado("stonelab.mock") ?? "1") !== "0",
  // "" = mesma origem (front servido pelo próprio FastAPI)
  API_URL: (lerGuardado("stonelab.api") ?? "").replace(/\/$/, ""),
  // Sprint 3: resposta do chat por SSE, um evento por passo do agente
  SSE: lerGuardado("stonelab.sse") === "1",
  // limite de passos do agente (agentes/agente_atendimento/agente.py: MAX_PASSOS)
  MAX_PASSOS: 8,
  // aviso de gasto (regra da PO: aviso em 80%)
  AVISO_GASTO: 0.8,
};
