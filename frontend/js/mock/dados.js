// Dados sintéticos do modo mock. Nada aqui é real.
//
// Clientes, transações e endereços reproduzem ferramentas/dados_sinteticos.py (mesmas fórmulas),
// para que a demo no mock e a demo com o back-end real mostrem os mesmos números.

export const SENHA_DEMO = "stone123";

// ---------- Usuários (um por perfil, nas duas áreas) ----------
// carteira: clientes que um Colaborador (N1 na camada 2) pode consultar.
export const USUARIOS = [
  { id: "u-ana", nome: "Ana Ribeiro", email: "ana@stonelab.test", perfil: "AdminGlobal", area: "Financeiro", areas_extras: [], carteira: [] },
  { id: "u-bruno", nome: "Bruno Martins", email: "bruno@stonelab.test", perfil: "Supervisor", area: "AtendimentoCliente", areas_extras: [], carteira: [] },
  { id: "u-fernanda", nome: "Fernanda Costa", email: "fernanda@stonelab.test", perfil: "Supervisor", area: "Financeiro", areas_extras: [], carteira: [] },
  { id: "u-carla", nome: "Carla Souza", email: "carla@stonelab.test", perfil: "Colaborador", area: "AtendimentoCliente", areas_extras: [], carteira: ["CLI-0001", "CLI-0002", "CLI-0003"] },
  { id: "u-diego", nome: "Diego Alves", email: "diego@stonelab.test", perfil: "Colaborador", area: "Financeiro", areas_extras: [], carteira: ["CLI-0004", "CLI-0005", "CLI-0007"] },
  { id: "u-gabriela", nome: "Gabriela Lima", email: "gabriela@stonelab.test", perfil: "GestorDeAcessos", area: "AtendimentoCliente", areas_extras: [], carteira: [] },
];

// Limite mensal simulado por pessoa (regra da PO, a confirmar): aviso em 80%.
export const LIMITE_MES = { AdminGlobal: 50, Supervisor: 40, Colaborador: 20, GestorDeAcessos: 0 };
// Preço simulado: o modelo é local (custo real zero).
export const PRECO_POR_1K_TOKENS = 0.01;
// Gasto já acumulado no mês antes da demo (para mostrar o aviso de 80% com a Carla).
export const GASTO_INICIAL = { "u-ana": 12.4, "u-bruno": 9.85, "u-fernanda": 15.1, "u-carla": 16.42, "u-diego": 6.3, "u-gabriela": 0 };

// ---------- Agentes ----------
const ATIVAS = [
  "consultar_cliente",
  "consultar_transacoes_cliente",
  "calcular_multa_atraso",
  "consultar_endereco_cep",
  "solicitar_ferramenta_ausente",
];

export const AGENTES = [
  {
    id: "ag-atendimento",
    nome: "Assistente de Atendimento",
    objetivo: "Tira dúvidas sobre clientes, transações, multas e endereços durante o atendimento.",
    area: "AtendimentoCliente",
    dono: "u-bruno",
    convidados: ["u-carla"],
    ferramentas: ATIVAS,
    ativo: true,
    criado_em: "2026-10-28T14:00:00-03:00",
  },
  {
    id: "ag-cobranca",
    nome: "Cobrança e Multas",
    objetivo: "Calcula multa e juros de faturas em atraso e consulta o histórico do lojista.",
    area: "Financeiro",
    dono: "u-diego",
    convidados: [],
    ferramentas: ["consultar_cliente", "consultar_transacoes_cliente", "calcular_multa_atraso", "listar_faturas_em_atraso", "solicitar_ferramenta_ausente"],
    ativo: true,
    criado_em: "2026-11-03T10:20:00-03:00",
  },
  {
    id: "ag-chamados",
    nome: "Resumo de Chamados",
    objetivo: "Resume os chamados abertos de um cliente antes do contato.",
    area: "AtendimentoCliente",
    dono: "u-carla",
    convidados: [],
    ferramentas: ["consultar_cliente", "listar_tickets_cliente", "consultar_ticket", "solicitar_ferramenta_ausente"],
    ativo: true,
    criado_em: "2026-11-06T16:45:00-03:00",
  },
  {
    id: "ag-relatorio",
    nome: "Relatório Semanal Financeiro",
    objetivo: "Monta o resumo semanal de receita e envia por e-mail ao time.",
    area: "Financeiro",
    dono: "u-fernanda",
    convidados: ["u-diego"],
    ferramentas: ["resumir_receita_periodo", "consultar_transacoes_cliente", "enviar_email", "solicitar_ferramenta_ausente"],
    ativo: true,
    criado_em: "2026-11-05T09:00:00-03:00",
  },
  {
    id: "ag-conciliacao",
    nome: "Conciliação de Transações (v1)",
    objetivo: "Versão antiga da conciliação. Substituída pelo Relatório Semanal.",
    area: "Financeiro",
    dono: "u-ana",
    convidados: [],
    ferramentas: ["consultar_transacoes_cliente"],
    ativo: false,
    criado_em: "2026-10-15T11:00:00-03:00",
  },
];

// Ferramentas planejadas que o mock liga só para demonstrar a confirmação em duas etapas (Sprint 3).
export const ATIVAS_SO_NO_MOCK = ["enviar_email"];

// ---------- Clientes e transações (cópia de ferramentas/dados_sinteticos.py) ----------
const NOMES_FANTASIA = [
  "Padaria Trigo Dourado",
  "Mercearia Horizonte",
  "Papelaria Folha Azul",
  "Oficina Roda Viva",
  "Floricultura Jardim Claro",
  "Farmácia Bem Perto",
  "Livraria Capítulo Dois",
  "Barbearia Navalha Fina",
];
const SEGMENTOS = ["alimentação", "varejo", "serviços"];
const CIDADES = [["São Paulo", "SP"], ["Rio de Janeiro", "RJ"], ["Belo Horizonte", "MG"]];
const TIPOS_TRANSACAO = ["credito", "debito", "pix"];
const SITUACOES_TRANSACAO = ["aprovada", "aprovada", "aprovada", "estornada", "aprovada", "contestada"];
const QUANTIDADE_TRANSACOES = { "CLI-0001": 60, "CLI-0002": 12, "CLI-0003": 25, "CLI-0004": 8 };

export const ENDERECOS = {
  "01310100": ["Avenida Paulista", "Bela Vista", "São Paulo", "SP"],
  "20040020": ["Rua da Quitanda", "Centro", "Rio de Janeiro", "RJ"],
  "30130010": ["Avenida Afonso Pena", "Centro", "Belo Horizonte", "MG"],
};

const id = (n) => `CLI-${String(n).padStart(4, "0")}`;

export const CLIENTES = Object.fromEntries(
  NOMES_FANTASIA.map((nome, i) => {
    const n = i + 1;
    const [cidade, uf] = CIDADES[n % CIDADES.length];
    return [
      id(n),
      {
        id_cliente: id(n),
        nome_fantasia: nome,
        segmento: SEGMENTOS[n % SEGMENTOS.length],
        cidade,
        uf,
        situacao: n % 4 === 0 ? "inadimplente" : "ativo",
        cliente_desde: `${2019 + (n % 6)}-0${1 + (n % 9)}-15`,
      },
    ];
  }),
);

function montarTransacoes(n, quantidade) {
  const primeiroDia = Date.UTC(2026, 0, 3);
  return Array.from({ length: quantidade }, (_, i) => ({
    id_transacao: `TRX-${String(n).padStart(4, "0")}${String(i).padStart(3, "0")}`,
    data: new Date(primeiroDia + (5 * i + n) * 86400000).toISOString().slice(0, 10),
    valor: Math.round((40 + ((i * 37 + n * 11) % 460) + (i % 4) * 0.25) * 100) / 100,
    tipo: TIPOS_TRANSACAO[(i + n) % TIPOS_TRANSACAO.length],
    situacao: SITUACOES_TRANSACAO[(i + n) % SITUACOES_TRANSACAO.length],
  }));
}

export const TRANSACOES = Object.fromEntries(
  Object.entries(QUANTIDADE_TRANSACOES).map(([cli, qtd]) => [cli, montarTransacoes(Number(cli.slice(-4)), qtd)]),
);

// Cenário "falha controlada" (slide 32): o core de pagamentos cai para este cliente.
export const CLIENTE_COM_FALHA = "CLI-0007";

// ---------- Alertas já existentes (slide 41: agente, falha, etapa, horário, o que fazer) ----------
export const ALERTAS_INICIAIS = [
  {
    id: "al-1",
    nivel: "erro",
    agente_id: "ag-cobranca",
    falha: "integracao_indisponivel em consultar_transacoes_cliente (core de pagamentos fora do ar)",
    etapa: "Passo 4: USAR consultar_transacoes_cliente",
    quando: "2026-11-12T09:41:00-03:00",
    ocorrencias: 3,
    o_que_fazer: "Aguardar o core voltar. O agente avisou o usuário e seguiu com o restante do pedido.",
  },
  {
    id: "al-2",
    nivel: "aviso",
    agente_id: "ag-chamados",
    falha: "Limite de 8 passos atingido sem resposta final",
    etapa: "Passo 8",
    quando: "2026-11-11T17:05:00-03:00",
    ocorrencias: 2,
    o_que_fazer: "Revisar o objetivo do agente: as ferramentas de chamados ainda estão planejadas.",
  },
  {
    id: "al-3",
    nivel: "aviso",
    agente_id: "ag-atendimento",
    falha: "Resposta fora do formato do protocolo (LER/USAR/PERGUNTAR/FINAL)",
    etapa: "Passo 2",
    quando: "2026-11-10T11:12:00-03:00",
    ocorrencias: 1,
    o_que_fazer: "Nada a fazer: o agente corrigiu no passo seguinte. Acompanhar se repetir.",
  },
];
