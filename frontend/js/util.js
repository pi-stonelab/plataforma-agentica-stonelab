// Utilidades de DOM e formatação.
//
// Regra de segurança: texto vindo da API (resposta do agente, nomes, mensagens) entra SEMPRE
// como texto (textContent), nunca como HTML. Por isso não usamos innerHTML com dados.

/**
 * Cria um elemento. Ex.: h("button", { class: "botao", onclick: fn }, "Salvar")
 * Atributos começando com "on" viram eventos; null/false/undefined são ignorados.
 */
export function h(tag, atributos = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos || {})) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (chave.startsWith("on") && typeof valor === "function") {
      el.addEventListener(chave.slice(2).toLowerCase(), valor);
    } else if (chave === "class") {
      el.className = valor;
    } else if (chave === "style" && typeof valor === "object") {
      Object.assign(el.style, valor);
    } else if (chave === "dataset") {
      Object.assign(el.dataset, valor);
    } else if (valor === true) {
      el.setAttribute(chave, "");
    } else {
      el.setAttribute(chave, String(valor));
    }
  }
  anexar(el, filhos);
  return el;
}

function anexar(el, filhos) {
  for (const filho of filhos.flat(Infinity)) {
    if (filho === null || filho === undefined || filho === false) continue;
    el.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
}

/** SVG simples e fixo (ícones). Só para markup escrito aqui no código, nunca dados da API. */
export function svg(markup, classe = "icone") {
  const span = document.createElement("span");
  span.className = classe;
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = markup;
  return span;
}

export function limpar(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const numero = new Intl.NumberFormat("pt-BR");

export const formatar = {
  moeda: (v) => moeda.format(Number(v) || 0),
  numero: (v) => numero.format(Number(v) || 0),
  pct: (v, casas = 0) => `${(Number(v) * 100).toFixed(casas).replace(".", ",")}%`,
  ms: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1).replace(".", ",")} s` : `${Math.round(v)} ms`),
  dataHora(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  },
  dia(iso) {
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  },
  relativo(iso) {
    if (!iso) return "";
    const seg = (Date.now() - new Date(iso).getTime()) / 1000;
    if (seg < 60) return "agora";
    if (seg < 3600) return `há ${Math.floor(seg / 60)} min`;
    if (seg < 86400) return `há ${Math.floor(seg / 3600)} h`;
    const dias = Math.floor(seg / 86400);
    return dias === 1 ? "ontem" : `há ${dias} dias`;
  },
};

// Nomes legíveis para os valores da API
export const ROTULOS = {
  perfil: {
    AdminGlobal: "Admin global",
    Supervisor: "Supervisor",
    Colaborador: "Colaborador",
    GestorDeAcessos: "Gestor de acessos",
  },
  area: {
    Financeiro: "Financeiro",
    AtendimentoCliente: "Atendimento ao cliente",
  },
  relacao: {
    admin: "Admin",
    supervisor: "Da sua área",
    dono: "Criado por você",
    convidado: "Convidado",
  },
  areaFerramenta: {
    atendimento: "Atendimento",
    financeiro: "Financeiro",
    dados_e_indicadores: "Dados e indicadores",
    documentos_e_agenda: "Documentos e agenda",
    comunicacao: "Comunicação",
    chamados_internos: "Chamados internos",
    consultas_publicas: "Consultas públicas",
    plataforma: "Plataforma",
  },
  acesso: { leitura: "Leitura", escrita: "Escrita", calculo: "Cálculo" },
  sensibilidade: { publica: "Pública", interna: "Interna", pessoal: "Pessoal", sigilosa: "Sigilosa" },
  risco: { baixo: "Risco baixo", medio: "Risco médio", alto: "Risco alto" },
};

export function iniciais(nome = "") {
  const partes = nome.trim().split(/\s+/);
  return ((partes[0]?.[0] || "") + (partes.length > 1 ? partes.at(-1)[0] : "")).toUpperCase();
}

export function esperar(ms) {
  return new Promise((resolver) => setTimeout(resolver, ms));
}
