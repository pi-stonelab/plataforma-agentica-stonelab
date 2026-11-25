// Tela de login. POST /auth/login → {token}; depois o app chama GET /me.
import { api } from "../api.js";
import { CONFIG } from "../config.js";
import { sessao } from "../sessao.js";
import { h, iniciais, ROTULOS } from "../util.js";
import { icone } from "../icones.js";

export function telaLogin({ aoEntrar }) {
  const erro = h("div", { class: "erro-caixa", role: "alert", hidden: true });
  const email = h("input", { class: "entrada", id: "email", type: "email", autocomplete: "username", required: true, placeholder: "voce@stonelab.test" });
  const senha = h("input", { class: "entrada", id: "senha", type: "password", autocomplete: "current-password", required: true });
  const botao = h("button", { class: "botao primario", type: "submit" }, "Entrar");

  async function entrar(evento) {
    evento.preventDefault();
    erro.hidden = true;
    botao.disabled = true;
    botao.textContent = "Entrando…";
    try {
      const { token } = await api.login(email.value.trim(), senha.value);
      sessao.token = token;
      sessao.usuario = null;
      aoEntrar();
    } catch (e) {
      erro.textContent = e.message;
      erro.hidden = false;
      botao.disabled = false;
      botao.textContent = "Entrar";
    }
  }

  const contasDemo = CONFIG.MOCK ? contasDeDemonstracao(email, senha) : null;

  return h("div", { class: "login" },
    h("section", { class: "login-marca" },
      h("div", {},
        h("div", { class: "logo-texto" }, "stone", h("span", { style: { color: "var(--marca)" } }, "lab")),
        h("h2", {}, "Agentes de IA com governança, para Atendimento e Financeiro."),
        h("p", {}, "Crie e use agentes sem programar. O acesso é conferido pelo seu perfil, e cada ação fica registrada."),
      ),
      h("ul", {},
        h("li", {}, icone("escudo"), h("span", {}, "Modelo local: os dados não saem da Stone.")),
        h("li", {}, icone("cadeado"), h("span", {}, "Permissão conferida duas vezes: no pedido e na ferramenta.")),
        h("li", {}, icone("moeda"), h("span", {}, "Limite de gasto por pessoa, com aviso em 80%.")),
      ),
      h("p", { class: "texto-3", style: { color: "#a8cdb0" } }, "Projeto BIA1102 · PUC-Rio · somente dados sintéticos"),
    ),
    h("section", { class: "login-forma" },
      h("form", { class: "login-caixa", onsubmit: entrar },
        h("div", {}, h("h1", {}, "Entrar"), h("p", { class: "texto-2" }, "Use seu e-mail corporativo.")),
        erro,
        h("div", { class: "campo" }, h("label", { for: "email" }, "E-mail"), email),
        h("div", { class: "campo" }, h("label", { for: "senha" }, "Senha"), senha),
        botao,
        contasDemo,
      ),
    ),
  );
}

function contasDeDemonstracao(email, senha) {
  const lista = h("div", { class: "contas-demo" }, h("p", { class: "texto-3" }, "Carregando contas de demonstração…"));
  import("../mock/dados.js").then(({ USUARIOS, SENHA_DEMO }) => {
    lista.replaceChildren(
      h("p", { class: "texto-3" }, `Modo demonstração. Clique em uma conta (senha: ${SENHA_DEMO}):`),
      ...USUARIOS.map((u) =>
        h("button", {
          type: "button",
          class: "conta-demo",
          onclick: () => {
            email.value = u.email;
            senha.value = SENHA_DEMO;
            email.form.requestSubmit();
          },
        },
          h("span", { class: "avatar", "aria-hidden": "true" }, iniciais(u.nome)),
          h("span", {},
            h("strong", {}, u.nome), h("br"),
            h("span", { class: "texto-3" }, `${ROTULOS.perfil[u.perfil]} · ${ROTULOS.area[u.area]}`),
          ),
        ),
      ),
    );
  });
  return lista;
}
