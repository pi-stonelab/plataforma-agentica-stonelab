// Cópia, em JS, das regras de permissão do back-end. Só serve ao modo mock.
// No produto real quem decide é o back-end (seguranca/permissoes.py e ferramentas/governanca.py).

import { CATALOGO } from "./ferramentas.js";
import { ATIVAS_SO_NO_MOCK } from "./dados.js";

export const ACOES = ["VER", "EXECUTAR", "EDITAR", "CONVIDAR", "DEPRECAR"];

// ---------- Camada 1: acesso ao agente (seguranca/permissoes.py) ----------
function podeNoAgenteAtivo(usuario, acao, agente) {
  switch (usuario.perfil) {
    case "AdminGlobal":
      return true;
    case "Supervisor": {
      const areas = [usuario.area, ...(usuario.areas_extras || [])];
      if (areas.includes(agente.area) || agente.dono === usuario.id) return true;
      return agente.convidados.includes(usuario.id) && (acao === "VER" || acao === "EXECUTAR");
    }
    case "Colaborador":
      if (agente.dono === usuario.id) return true;
      return agente.convidados.includes(usuario.id) && (acao === "VER" || acao === "EXECUTAR");
    default: // GestorDeAcessos e desconhecidos: falha fechado
      return false;
  }
}

export function pode(usuario, acao, agente) {
  // agente deprecado só aceita VER (commit 827290c)
  if (!agente.ativo && acao !== "VER") return false;
  return podeNoAgenteAtivo(usuario, acao, agente);
}

export function acoesPermitidas(usuario, agente) {
  return ACOES.filter((acao) => pode(usuario, acao, agente));
}

export function relacao(usuario, agente) {
  if (agente.dono === usuario.id) return "dono";
  if (usuario.perfil === "AdminGlobal") return "admin";
  if (usuario.perfil === "Supervisor" && [usuario.area, ...(usuario.areas_extras || [])].includes(agente.area)) return "supervisor";
  return "convidado";
}

// ---------- Correspondência entre camadas (proposta do CLAUDE.md, a confirmar) ----------
const AREA_CAMADA2 = { Financeiro: "financeiro", AtendimentoCliente: "atendimento" };

export function usuarioCamada2(usuario) {
  if (usuario.perfil === "GestorDeAcessos") return null;
  return {
    id_usuario: usuario.id,
    nivel: usuario.perfil === "Colaborador" ? "N1" : "N2",
    area: AREA_CAMADA2[usuario.area],
    carteira: usuario.carteira || [],
  };
}

// ---------- Camada 2: acesso à ferramenta (ferramentas/governanca.py) ----------
const NIVEIS = ["N1", "N2"];
const POR_NOME = Object.fromEntries(CATALOGO.map((f) => [f.nome, f]));

export function ficha(nome) {
  const f = POR_NOME[nome];
  if (!f) return null;
  return ATIVAS_SO_NO_MOCK.includes(nome) ? { ...f, status: "ativa" } : f;
}

/** null se pode usar; senão, frase curta com o motivo (igual a governanca.motivo_bloqueio). */
export function motivoBloqueio(f, u2) {
  if (!u2) return "Seu perfil não usa ferramentas.";
  if (NIVEIS.indexOf(u2.nivel) < NIVEIS.indexOf(f.nivel_minimo)) return "Nível insuficiente.";
  if (!f.areas_permitidas.includes("todas") && !f.areas_permitidas.includes(u2.area)) return "Área não permitida.";
  return null;
}

export function clienteNoEscopo(u2, idCliente) {
  if (!u2) return false;
  if (u2.nivel === "N2") return true;
  return u2.carteira.includes(idCliente);
}

/** Catálogo como o GET /ferramentas devolveria: cada ficha com liberada/motivo. */
export function catalogoPara(usuario) {
  const u2 = usuarioCamada2(usuario);
  return CATALOGO.map((original) => {
    const f = ficha(original.nome);
    const motivo = motivoBloqueio(f, u2);
    return {
      nome: f.nome,
      area: f.area,
      descricao: f.descricao,
      acesso: f.acesso,
      sensibilidade: f.sensibilidade,
      status: f.status,
      integracoes: f.integracoes,
      liberada: motivo === null,
      motivo,
    };
  });
}
