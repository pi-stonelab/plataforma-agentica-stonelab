// Sessão do usuário: guarda o token JWT e o perfil vindo de GET /me.
//
// O token fica no sessionStorage (some ao fechar a aba). O perfil NUNCA é enviado pelo front:
// o back-end tira perfil, área e carteira do token + banco.

const CHAVE = "stonelab.token";
let tokenEmMemoria = null;
let usuarioAtual = null;

export const sessao = {
  get token() {
    try {
      return sessionStorage.getItem(CHAVE) ?? tokenEmMemoria;
    } catch {
      return tokenEmMemoria;
    }
  },
  set token(valor) {
    tokenEmMemoria = valor;
    try {
      if (valor) sessionStorage.setItem(CHAVE, valor);
      else sessionStorage.removeItem(CHAVE);
    } catch {
      // sem armazenamento: fica só em memória
    }
  },
  get usuario() {
    return usuarioAtual;
  },
  set usuario(valor) {
    usuarioAtual = valor;
  },
  sair() {
    this.token = null;
    usuarioAtual = null;
  },
};
