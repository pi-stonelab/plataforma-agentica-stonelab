"""Base dos conectores: como a plataforma fala com cada sistema que as ferramentas usam.

Um conector por integração, com o mesmo nome usado em `integracoes` nas fichas. Ele lê a configuração do
ambiente (.env) na hora de cada uso, diz o modo (`real`, `simulado` ou `desligado`), protege cada chamada com
o disjuntor e responde a saúde sem nenhum segredo.

Falha de rede vira `ConnectionError` ou `TimeoutError`, que a `Ferramenta.executar` responde como
`integracao_indisponivel` sem repassar o texto. O log leva só a integração, o serviço, a etapa e o tipo do erro.

Conector novo (bloco E): uma subclasse com `nome`, `rotulo`, `tipo`, `variaveis`, `credencial` e, se tiver,
`variavel_modo`, `servicos` e `mensagem_desligada`; `conferir_configuracao(ambiente)` levanta
`ConfiguracaoInvalida` com o nome da variável errada; `testar(ambiente)` faz uma chamada de verdade sem dado de
lojista; cada chamada de rede passa por `chamar(etapa, funcao, servico=...)` e monta a URL com
`cliente_http.montar_url`; destino escolhido pelo modelo (canal, chat, projeto) passa por `exigir_destino`.
Depois, `registro.registrar(...)` e o import em `integracoes/__init__.py`.

Saúde (`saude`), sem fazer chamada nenhuma:
- `desligada`: modo `desligado` no .env (ou integração ainda planejada).
- `configuracao_invalida`: modo `real` com uma variável errada ou faltando.
- `indisponivel`: falha simulada ligada (`mock.falhas`) ou a última chamada de algum serviço falhou há menos de
  `SEGUNDOS_DE_FALHA_RECENTE`. Falha antiga, sem chamada depois, não acusa: evita alerta falso horas depois.
- `pausada`: o disjuntor de algum serviço está aberto.
- `sem_chamadas`: modo `real`, configurado, ninguém chamou ainda desde que a plataforma subiu.
- `ok`: o resto. A saúde do conector é a pior entre os serviços; `saude_por_servico` dá o detalhe.
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

MODOS = ("real", "simulado", "desligado")
TIPOS = ("interno", "externo")
CREDENCIAIS = ("plataforma", "pessoa")
# Da pior para a melhor: a saúde do conector é a pior entre os seus serviços.
SAUDES = ("desligada", "configuracao_invalida", "indisponivel", "pausada", "sem_chamadas", "ok")
FALHAS_PARA_PAUSAR = 3
SEGUNDOS_DE_PAUSA = 60
SEGUNDOS_DE_FALHA_RECENTE = 300  # depois disso, uma falha antiga sem chamada nova não acusa mais
FALHAS_DE_REDE = (ConnectionError, TimeoutError, OSError)


class ConfiguracaoInvalida(ConnectionError):
    """Uma variável do .env está errada. A mensagem diz qual, nunca o valor."""

    def __init__(self, variavel):
        super().__init__(f"{variavel} inválida no .env.")
        self.variavel = variavel


class IntegracaoPausada(ConnectionError):
    """O disjuntor está aberto: a integração falhou seguidas vezes e descansa antes de tentar de novo."""


class IntegracaoDesligada(ConnectionError):
    """A integração está desligada no .env (ou não configurada)."""


class DestinoNaoPermitido(ValueError):
    """O destino pedido (canal, chat, projeto) não está na lista permitida do .env."""


class Disjuntor:
    """Depois de `FALHAS_PARA_PAUSAR` falhas seguidas, recusa as chamadas por `SEGUNDOS_DE_PAUSA`.

    Passada a pausa, deixa UMA chamada testar a integração: deu certo, volta ao normal; falhou, pausa de novo.
    Enquanto essa chamada de teste roda, as outras continuam recusadas.
    """

    def __init__(self, relogio=time.monotonic):
        self._relogio = relogio
        self._trava = threading.Lock()
        self._falhas_seguidas = 0
        self._pausado_ate = None
        self._testando = False
        self._ultima_falha_em = None
        self._ja_chamado = False

    def liberar(self):
        """Chamada antes de cada uso. Levanta `IntegracaoPausada` se a chamada não pode seguir."""
        with self._trava:
            if self._pausado_ate is None:
                return
            if self._relogio() < self._pausado_ate or self._testando:
                raise IntegracaoPausada("integração pausada")
            self._testando = True

    def sucesso(self):
        with self._trava:
            self._falhas_seguidas = 0
            self._pausado_ate = None
            self._testando = False
            self._ja_chamado = True

    def falha(self):
        """Conta uma falha de rede. Devolve True se esta falha abriu (ou reabriu) a pausa."""
        with self._trava:
            self._falhas_seguidas += 1
            self._testando = False
            self._ja_chamado = True
            self._ultima_falha_em = self._relogio()
            if self._falhas_seguidas >= FALHAS_PARA_PAUSAR:
                self._pausado_ate = self._relogio() + SEGUNDOS_DE_PAUSA
                return True
            return False

    def neutro(self):
        """A chamada terminou sem dizer nada sobre a integração (erro do nosso lado ou pedido recusado)."""
        with self._trava:
            self._testando = False
            self._ja_chamado = True

    @property
    def pausado(self):
        with self._trava:
            return self._pausado_ate is not None and self._relogio() < self._pausado_ate

    @property
    def falhou_ha_pouco(self):
        """A última chamada falhou e foi há menos de `SEGUNDOS_DE_FALHA_RECENTE`."""
        with self._trava:
            if self._falhas_seguidas == 0 or self._ultima_falha_em is None:
                return False
            return self._relogio() - self._ultima_falha_em < SEGUNDOS_DE_FALHA_RECENTE

    @property
    def ja_chamado(self):
        with self._trava:
            return self._ja_chamado


class Conector:
    nome = ""  # o mesmo de `integracoes` nas fichas
    rotulo = ""  # como a interface mostra
    tipo = "externo"
    variavel_modo = ""  # ex.: APIS_PUBLICAS_MODO; vazio quando o conector decide o modo pela configuração
    modo_padrao = "real"
    variaveis = ()  # nomes das variáveis do .env que o conector lê (nunca os valores)
    servicos = ("",)  # cada serviço tem o próprio disjuntor: uma API fora do ar não pausa a outra
    # `plataforma`: uma credencial do .env para todos. `pessoa`: cada funcionário liga a própria conta (OAuth).
    # [A FAZER (Marcelo e Isabel, back-end, Sprint 3): guardar e renovar o token OAuth de cada pessoa e
    # entregar ao conector junto com o `Usuario`; a tela de conectores (front) dispara o login de cada uma]
    credencial = "plataforma"
    mensagem_desligada = ""  # o que o agente ouve quando a integração está desligada; vazio usa a padrão
    como_ligar = ""  # o que fazer no .env para ligar (só o terminal mostra)
    dicas = {}  # variável do .env -> como corrigir (só o terminal mostra, nunca com o valor)

    def __init__(self, relogio=time.monotonic):
        self._relogio = relogio
        self._disjuntores = {servico: Disjuntor(relogio) for servico in self.servicos}
        self._modo_invalido_avisado = False

    def _valor_do_modo(self, ambiente):
        return ambiente.get(self.variavel_modo, "").strip().lower() if self.variavel_modo else ""

    def modo(self, ambiente=os.environ):
        if not self.variavel_modo:
            return self.modo_padrao
        valor = self._valor_do_modo(ambiente) or self.modo_padrao
        if valor not in MODOS:
            if not self._modo_invalido_avisado:  # um aviso só, não um por chamada
                self._modo_invalido_avisado = True
                logger.warning("modo de integracao invalido: integracao=%s variavel=%s", self.nome, self.variavel_modo)
            return "desligado"  # valor estranho: falha fechada
        return valor

    def problema_de_configuracao(self, ambiente=os.environ):
        """O que está errado no .env, para quem configura (terminal), sem nenhum valor; None se nada."""
        valor = self._valor_do_modo(ambiente)
        if valor and valor not in MODOS:
            return f"{self.variavel_modo} com um valor que não existe. Use real, simulado ou desligado."
        modo = self.modo(ambiente)
        if modo == "desligado":
            return f"Desligada. Para ligar, {self.como_ligar}." if self.como_ligar else "Desligada."
        if modo == "real":
            try:
                self.conferir_configuracao(ambiente)
            except ConfiguracaoInvalida as erro:
                return self.dicas.get(erro.variavel, str(erro))
            except ConnectionError as erro:  # a configuração do SMTP tem a própria exceção, com a mesma frase
                return str(erro)
        return None

    def conferir_configuracao(self, ambiente=os.environ):
        """Levanta `ConfiguracaoInvalida` se o modo real não tem o que precisa. A subclasse completa."""

    def configurado(self, ambiente=os.environ):
        modo = self.modo(ambiente)
        if modo == "desligado":
            return False
        if modo == "simulado":
            return True
        try:
            self.conferir_configuracao(ambiente)
        except ConnectionError:
            return False
        return True

    def exigir_ligado(self, ambiente=os.environ):
        """O modo de uso agora (`real` ou `simulado`). Desligada ou mal configurada: `ConnectionError`."""
        modo = self.modo(ambiente)
        if modo == "desligado":
            raise IntegracaoDesligada("integração desligada")
        if modo == "real":
            self.conferir_configuracao(ambiente)
        return modo

    def fora_do_ar(self):
        """True se a integração foi derrubada de propósito (falha simulada, `mock.falhas`)."""
        return False

    def aviso_desligada(self):
        """Frase para o agente quando a integração está desligada ou mal configurada (nunca fala do .env)."""
        frase = self.mensagem_desligada or f"A integração {self.rotulo} não está ligada nesta plataforma."
        return f"{frase} Avise o usuário e não tente de novo."

    def exigir_destino(self, valor, lista_permitida):
        """Devolve `valor` se ele está na lista permitida do .env; senão `DestinoNaoPermitido`.

        O modelo nunca escolhe destino livre (canal, chat, projeto): só o que quem configura liberou.
        """
        permitidos = {item.strip() for item in lista_permitida if item and item.strip()}
        if not isinstance(valor, str) or valor.strip() not in permitidos:
            raise DestinoNaoPermitido("destino fora da lista permitida")
        return valor.strip()

    def chamar(self, etapa, funcao, servico=""):
        """Roda `funcao()` protegida pelo disjuntor do `servico`. Falha de rede conta e vai ao log sem conteúdo."""
        disjuntor = self._disjuntores[servico]
        disjuntor.liberar()
        try:
            resultado = funcao()
        except FALHAS_DE_REDE as erro:
            abriu = disjuntor.falha()
            logger.warning(
                "integracao falhou: integracao=%s servico=%s etapa=%s tipo=%s",
                self.nome, servico or "-", etapa, type(erro).__name__,
            )
            if abriu:
                logger.warning(
                    "integracao pausada: integracao=%s servico=%s segundos=%d",
                    self.nome, servico or "-", SEGUNDOS_DE_PAUSA,
                )
            raise
        except BaseException:
            disjuntor.neutro()
            raise
        disjuntor.sucesso()
        return resultado

    def _saude_do_servico(self, disjuntor, modo):
        if disjuntor.pausado:
            return "pausada"
        if disjuntor.falhou_ha_pouco:
            return "indisponivel"
        if modo == "real" and not disjuntor.ja_chamado:
            return "sem_chamadas"
        return "ok"

    def saude_por_servico(self, ambiente=os.environ):
        """{serviço: saúde}, com as mesmas regras de `saude` (ver o topo do arquivo)."""
        modo = self.modo(ambiente)
        if modo == "desligado":
            return {servico: "desligada" for servico in self.servicos}
        if not self.configurado(ambiente):
            return {servico: "configuracao_invalida" for servico in self.servicos}
        if self.fora_do_ar():
            return {servico: "indisponivel" for servico in self.servicos}
        return {servico: self._saude_do_servico(d, modo) for servico, d in self._disjuntores.items()}

    def saude(self, ambiente=os.environ):
        """A pior saúde entre os serviços, sem fazer chamada nenhuma."""
        return min(self.saude_por_servico(ambiente).values(), key=SAUDES.index)

    def testar(self, ambiente=os.environ):
        """Chamada de verdade, sem dado de lojista, para quem configura conferir. Devolve uma frase curta."""
        raise IntegracaoDesligada("teste não implementado para esta integração")

    def reiniciar(self):
        """Zera os disjuntores (testes e reinício da demo)."""
        self._disjuntores = {servico: Disjuntor(self._relogio) for servico in self.servicos}
