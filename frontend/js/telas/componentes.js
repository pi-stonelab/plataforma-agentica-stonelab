// Peças reaproveitadas entre telas.
import { h, formatar } from "../util.js";
import { icone } from "../icones.js";

export function carregando(texto = "Carregando…") {
  return h("div", { class: "carregando", role: "status" }, h("span", { class: "girando" }), texto);
}

export function caixaErro(erro, tentarDeNovo) {
  return h("div", { class: "erro-caixa", role: "alert" },
    erro?.message || String(erro),
    tentarDeNovo ? h("div", { style: { marginTop: "8px" } }, h("button", { class: "botao pequeno", type: "button", onclick: tentarDeNovo }, "Tentar de novo")) : null,
  );
}

export function vazio(nomeIcone, titulo, texto, acao = null) {
  return h("div", { class: "vazio" }, icone(nomeIcone), h("h3", {}, titulo), texto ? h("p", {}, texto) : null, acao);
}

/** Medidor de gasto: barra, marca em 80% e cor por faixa. */
export function medidorGasto(gasto, limite) {
  const fracao = limite ? gasto / limite : 0;
  const classe = fracao >= 1 ? "erro" : fracao >= 0.8 ? "aviso" : "";
  return h("div", {
    class: `medidor ${classe}`,
    role: "meter",
    "aria-valuemin": 0,
    "aria-valuemax": limite,
    "aria-valuenow": gasto,
    "aria-label": `Gasto do mês: ${formatar.moeda(gasto)} de ${formatar.moeda(limite)}`,
  },
    h("div", { class: "preenchido", style: { width: `${Math.min(fracao, 1) * 100}%` } }),
    h("div", { class: "marca-80", title: "Aviso em 80%" }),
  );
}

// ---------- Trajetória do agente (o "rastro" da KAN-60) ----------
const ICONE_ACAO = { LER: "livro", USAR: "ferramenta", PERGUNTAR: "pergunta", FINAL: "check", CONFIRMAR: "cadeado", BLOQUEIO: "escudo" };
const ROTULO_ACAO = { LER: "Leu", USAR: "Usou ferramenta", PERGUNTAR: "Perguntou", FINAL: "Respondeu", CONFIRMAR: "Pediu confirmação", BLOQUEIO: "Barrou o pedido", INVALIDO: "Formato inválido" };

/**
 * Aceita os dois formatos de passo:
 *  - objeto {passo, acao, alvo, resumo, status, tipo_erro, pensamento} (proposto no CONTRATO_API.md)
 *  - texto "Passo 3: USAR -> 'consultar_cliente' executada: sucesso" (o que agente.py devolve hoje)
 */
export function normalizarPasso(passo, indice = 0) {
  if (passo && typeof passo === "object") return passo;
  const texto = String(passo ?? "");
  const m = texto.match(/^Passo\s+(\d+):\s*(\w+)\s*->\s*(.*)$/i);
  const resumo = m ? m[3] : texto;
  const status = /permissao_negada|bloqueado|não liberado/i.test(resumo) ? "bloqueado" : /erro|inválid|invalido|indisponivel/i.test(resumo) ? "erro" : "ok";
  return { passo: m ? Number(m[1]) : indice + 1, acao: m ? m[2].toUpperCase() : "INVALIDO", alvo: "", resumo, status, tipo_erro: null };
}

export function itemPasso(bruto, indice) {
  const p = normalizarPasso(bruto, indice);
  const classe = p.status === "bloqueado" ? "bloqueado" : p.status === "erro" ? "erro" : "";
  const nomeIcone = p.status === "bloqueado" ? "cadeado" : p.status === "erro" ? "alerta" : ICONE_ACAO[p.acao] || "info";
  return h("li", { class: `passo ${classe}` },
    h("span", { class: "ponto" }, icone(nomeIcone)),
    h("div", {},
      h("div", { class: "linha", style: { gap: "6px" } },
        h("span", { class: "acao" }, `${p.passo}. ${ROTULO_ACAO[p.acao] || p.acao}`),
        p.alvo ? h("span", { class: "alvo" }, p.alvo) : null,
      ),
      h("div", {}, p.resumo),
      p.pensamento ? h("div", { class: "pensamento" }, p.pensamento) : null,
    ),
  );
}

export function trajetoria(passos, { aberta = false } = {}) {
  if (!passos?.length) return null;
  const usos = passos.map(normalizarPasso).filter((p) => p.acao === "USAR").length;
  return h("details", { class: "trajetoria", open: aberta },
    h("summary", {}, `Como cheguei nessa resposta · ${passos.length} ${passos.length === 1 ? "passo" : "passos"}${usos ? ` · ${usos} ${usos === 1 ? "ferramenta" : "ferramentas"}` : ""}`),
    h("ol", { class: "passos" }, passos.map(itemPasso)),
  );
}

export function textoUso(uso) {
  if (!uso) return null;
  const tokens = (uso.tokens_entrada || 0) + (uso.tokens_saida || 0);
  return `${formatar.numero(tokens)} tokens · ${formatar.ms(uso.latencia_ms || 0)} · ${formatar.moeda(uso.custo || 0)} (simulado)`;
}
