// Monitoramento: custos, desempenho, status e alertas (slides 9, 40 e 41).
// Rotas: GET /monitoramento/resumo, /uso-diario, /agentes, /alertas (todas com ?dias=).
// O back-end decide o escopo: Colaborador vê o próprio uso, Supervisor a área, Admin tudo.
import { api } from "../api.js";
import { h, formatar, ROTULOS } from "../util.js";
import { icone } from "../icones.js";
import { carregando, caixaErro, vazio, medidorGasto } from "./componentes.js";

const NS = "http://www.w3.org/2000/svg";
const s = (tag, atributos = {}, ...filhos) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, String(v));
  for (const f of filhos) el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  return el;
};

export function telaMonitoramento() {
  const estado = { dias: 30, metrica: "custo" };
  const corpo = h("div", { style: { display: "flex", flexDirection: "column", gap: "20px" } }, carregando("Carregando métricas…"));
  const subtitulo = h("p", { class: "sub" }, "Custos, desempenho, status e alertas dos agentes.");
  const periodo = alternador([["7", "7 dias"], ["30", "30 dias"]], String(estado.dias), (v) => { estado.dias = Number(v); carregar(); });

  const elemento = h("div", { class: "conteudo" },
    h("header", { class: "cabecalho-tela" }, h("div", {}, h("h1", {}, "Monitoramento"), subtitulo), periodo),
    corpo,
  );

  let dica = null;
  async function carregar() {
    dica?.remove();
    corpo.replaceChildren(carregando("Carregando métricas…"));
    try {
      const [resumo, diario, agentes, alertas] = await Promise.all([
        api.resumoUso(estado.dias), api.usoDiario(estado.dias), api.usoPorAgente(estado.dias), api.alertas(),
      ]);
      subtitulo.textContent = `${resumo.rotulo_escopo} · últimos ${resumo.dias} dias. Custos com preço simulado por token (o modelo é local).`;
      const graficoLugar = h("div");
      const desenharGrafico = () => graficoLugar.replaceChildren(grafico(diario, estado.metrica, (d) => { dica = d; }));
      desenharGrafico();

      corpo.replaceChildren(
        indicadores(resumo),
        h("div", { class: "grade colunas-2", style: { gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)" } },
          h("section", { class: "cartao" },
            h("div", { class: "cartao-titulo" },
              h("h2", {}, estado.metrica === "custo" ? "Custo por dia" : "Execuções por dia"),
              alternador([["custo", "Custo"], ["execucoes", "Execuções"]], estado.metrica, (v) => { estado.metrica = v; carregar(); }),
            ),
            graficoLugar,
            tabelaDiaria(diario),
          ),
          h("section", { class: "cartao" },
            h("div", { class: "cartao-titulo" }, h("h2", {}, "Alertas"), h("span", { class: "dica" }, `${alertas.length} ${alertas.length === 1 ? "ativo" : "ativos"}`)),
            alertas.length ? h("div", {}, alertas.map(itemAlerta)) : vazio("check", "Nenhum alerta", "Tudo funcionando."),
          ),
        ),
        h("section", { class: "cartao" },
          h("div", { class: "cartao-titulo" }, h("h2", {}, "Desempenho por agente")),
          agentes.length ? tabelaAgentes(agentes) : vazio("robo", "Sem uso no período", null),
        ),
      );
    } catch (erro) {
      corpo.replaceChildren(caixaErro(erro, carregar));
    }
  }

  carregar();
  return { elemento, limpar: () => dica?.remove() };
}

function alternador(opcoes, atual, aoMudar) {
  const caixa = h("div", { class: "alternador", role: "group" });
  for (const [valor, rotulo] of opcoes) {
    caixa.append(h("button", {
      type: "button", "aria-pressed": String(valor === atual),
      onclick: (ev) => {
        for (const b of caixa.children) b.setAttribute("aria-pressed", String(b === ev.currentTarget));
        aoMudar(valor);
      },
    }, rotulo));
  }
  return caixa;
}

function indicadores(r) {
  const fracao = r.limite_mes ? r.gasto_mes / r.limite_mes : 0;
  const tile = (rotulo, valor, detalhe, extra = null) =>
    h("div", { class: "cartao indicador" }, h("span", { class: "rotulo" }, rotulo), h("span", { class: "valor" }, valor), extra, h("span", { class: "detalhe" }, detalhe));
  return h("div", { class: "grade colunas-4" },
    tile("Seu gasto no mês", formatar.moeda(r.gasto_mes),
      r.limite_mes ? `${formatar.pct(fracao)} de ${formatar.moeda(r.limite_mes)} · aviso em 80%` : "sem limite",
      r.limite_mes ? medidorGasto(r.gasto_mes, r.limite_mes) : null),
    tile("Execuções", formatar.numero(r.execucoes), `${formatar.moeda(r.custo_periodo)} no período`),
    tile("Taxa de erro", formatar.pct(r.taxa_erro, 1), `${formatar.numero(r.erros)} execuções com falha`),
    tile("Latência média", formatar.ms(r.latencia_media_ms), `${formatar.numero(r.chamadas_modelo)} chamadas · ${formatar.numero(r.tokens_entrada + r.tokens_saida)} tokens`),
  );
}

// ---------- Gráfico de barras (uma série, um eixo) ----------
function grafico(dados, metrica, guardarDica) {
  const L = 720;
  const A = 230;
  const m = { topo: 12, dir: 8, base: 26, esq: 52 };
  const larguraUtil = L - m.esq - m.dir;
  const alturaUtil = A - m.topo - m.base;
  const valores = dados.map((d) => (metrica === "custo" ? d.custo : d.execucoes));
  const max = niceMax(Math.max(...valores, 0));
  const passo = larguraUtil / dados.length;
  const larguraBarra = Math.max(Math.min(passo - 2, 28), 2);
  const formatarValor = metrica === "custo" ? (v) => formatar.moeda(v) : (v) => formatar.numero(v);

  const dica = h("div", { class: "grafico-dica", role: "tooltip", hidden: true });
  document.body.append(dica);
  guardarDica(dica);

  const raizSvg = s("svg", { viewBox: `0 0 ${L} ${A}`, role: "img", "aria-label": `${metrica === "custo" ? "Custo" : "Execuções"} por dia nos últimos ${dados.length} dias` });
  for (let i = 0; i <= 4; i++) {
    const v = (max / 4) * i;
    const y = m.topo + alturaUtil - (v / max) * alturaUtil;
    raizSvg.append(
      s("line", { class: "grade-linha", x1: m.esq, x2: L - m.dir, y1: y, y2: y }),
      s("text", { class: "eixo-texto", x: m.esq - 8, y: y + 4, "text-anchor": "end" }, metrica === "custo" ? formatar.moeda(v).replace(/,00$/, "") : formatar.numero(Math.round(v))),
    );
  }
  const cadaQuantos = dados.length > 10 ? 5 : 1;
  dados.forEach((d, i) => {
    const v = valores[i];
    const x = m.esq + i * passo + (passo - larguraBarra) / 2;
    const alt = max ? (v / max) * alturaUtil : 0;
    const y = m.topo + alturaUtil - alt;
    const r = Math.min(4, larguraBarra / 2, alt);
    const barra = s("path", {
      class: "barra",
      d: alt > 0
        ? `M${x},${y + alt} V${y + r} Q${x},${y} ${x + r},${y} H${x + larguraBarra - r} Q${x + larguraBarra},${y} ${x + larguraBarra},${y + r} V${y + alt} Z`
        : `M${x},${y} H${x + larguraBarra}`,
    });
    // área de clique maior que a barra
    const alvo = s("rect", { x: m.esq + i * passo, y: m.topo, width: passo, height: alturaUtil, fill: "transparent", tabindex: 0, "aria-label": `${formatar.dia(d.dia)}: ${formatarValor(v)}` });
    const mostrar = (ev) => {
      barra.classList.add("ativa");
      dica.replaceChildren(h("strong", {}, formatar.dia(d.dia)), ` · ${formatarValor(v)} · ${formatar.numero(d.execucoes)} execuções${d.erros ? ` · ${d.erros} com erro` : ""}`);
      dica.hidden = false;
      const caixa = ev.type === "focus" ? alvo.getBoundingClientRect() : { left: ev.clientX, top: ev.clientY };
      dica.style.left = `${Math.min(caixa.left + 12, innerWidth - dica.offsetWidth - 8)}px`;
      dica.style.top = `${caixa.top - 40}px`;
    };
    const esconder = () => { barra.classList.remove("ativa"); dica.hidden = true; };
    alvo.addEventListener("mousemove", mostrar);
    alvo.addEventListener("focus", mostrar);
    alvo.addEventListener("mouseleave", esconder);
    alvo.addEventListener("blur", esconder);
    raizSvg.append(barra, alvo);
    if ((dados.length - 1 - i) % cadaQuantos === 0) {
      raizSvg.append(s("text", { class: "eixo-texto", x: x + larguraBarra / 2, y: A - 8, "text-anchor": "middle" }, formatar.dia(d.dia)));
    }
  });
  return h("div", { class: "grafico" }, raizSvg);
}

function niceMax(v) {
  if (v <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(v));
  const n = v / exp;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * exp;
}

function tabelaDiaria(dados) {
  return h("details", { style: { marginTop: "10px" } },
    h("summary", { class: "texto-3", style: { cursor: "pointer" } }, "Ver como tabela"),
    h("div", { class: "tabela-rolagem", style: { maxHeight: "240px", overflowY: "auto", marginTop: "8px" } },
      h("table", { class: "tabela" },
        h("thead", {}, h("tr", {}, h("th", {}, "Dia"), h("th", { class: "num" }, "Execuções"), h("th", { class: "num" }, "Erros"), h("th", { class: "num" }, "Tokens"), h("th", { class: "num" }, "Custo"))),
        h("tbody", {}, [...dados].reverse().map((d) => h("tr", {},
          h("td", {}, formatar.dia(d.dia)), h("td", { class: "num" }, formatar.numero(d.execucoes)), h("td", { class: "num" }, formatar.numero(d.erros)),
          h("td", { class: "num" }, formatar.numero(d.tokens)), h("td", { class: "num" }, formatar.moeda(d.custo)),
        ))),
      ),
    ),
  );
}

const SAUDE = {
  saudavel: ["ok", "check", "Saudável"],
  atencao: ["aviso", "alerta", "Atenção"],
  critico: ["erro", "erro", "Crítico"],
  inativo: ["", "info", "Desativado"],
};

function tabelaAgentes(agentes) {
  return h("div", { class: "tabela-rolagem" },
    h("table", { class: "tabela" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Agente"), h("th", {}, "Status"), h("th", { class: "num" }, "Execuções"), h("th", { class: "num" }, "Sucesso"),
        h("th", { class: "num" }, "Latência média"), h("th", { class: "num" }, "Tokens"), h("th", { class: "num" }, "Custo"), h("th", {}, "Último uso"),
      )),
      h("tbody", {}, agentes.map((a) => {
        const [tom, ic, rotulo] = SAUDE[a.saude] || SAUDE.saudavel;
        return h("tr", {},
          h("td", {}, h("strong", {}, a.nome), h("div", { class: "texto-3" }, ROTULOS.area[a.area] ?? a.area ?? "")),
          h("td", {}, h("span", { class: `selo ${tom}` }, icone(ic), rotulo)),
          h("td", { class: "num" }, formatar.numero(a.execucoes)),
          h("td", { class: "num" }, formatar.pct(a.taxa_sucesso, 1)),
          h("td", { class: "num" }, formatar.ms(a.latencia_media_ms)),
          h("td", { class: "num" }, formatar.numero(a.tokens)),
          h("td", { class: "num" }, formatar.moeda(a.custo)),
          h("td", {}, a.ultimo_uso ? formatar.dia(a.ultimo_uso) : "—"),
        );
      })),
    ),
  );
}

function itemAlerta(a) {
  const nivel = ["erro", "aviso", "info"].includes(a.nivel) ? a.nivel : "info";
  return h("article", { class: `alerta ${nivel}` },
    h("span", { class: "ponto" }, icone(nivel === "erro" ? "erro" : nivel === "aviso" ? "alerta" : "info")),
    h("div", { style: { minWidth: 0 } },
      h("div", { class: "linha", style: { gap: "6px" } },
        h("strong", {}, a.agente?.nome ?? "Sua conta"),
        a.ocorrencias > 1 ? h("span", { class: "selo" }, `${a.ocorrencias}x`) : null,
        h("span", { class: "texto-3" }, formatar.relativo(a.quando)),
      ),
      h("div", {}, a.falha),
      h("div", { class: "texto-3" }, `Etapa: ${a.etapa}`),
      h("div", { class: "o-que-fazer" }, h("strong", {}, "O que fazer: "), a.o_que_fazer),
    ),
  );
}
