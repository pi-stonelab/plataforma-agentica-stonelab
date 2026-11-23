"""Base dos conectores: como a plataforma fala com cada sistema que as ferramentas usam.

Um conector por integração, com o mesmo nome usado em `integracoes` nas fichas. Ele lê a configuração do
ambiente (.env) na hora de cada uso, diz o modo (`real`, `simulado` ou `desligado`), protege cada chamada com
o disjuntor e responde a saúde sem nenhum segredo.

Falha de rede vira `ConnectionError` ou `TimeoutError`, que a `Ferramenta.executar` responde como
`integracao_indisponivel` sem repassar o texto. O log leva só a integração, o serviço, a etapa e o tipo do erro.

Conector novo (bloco E): uma subclasse com `nome`, `rotulo`, `tipo`, `variaveis` e, se tiver, `variavel_modo` e
`servicos`; `conferir_configuracao(ambiente)` levanta `ConfiguracaoInvalida` com o nome da variável errada;
`testar(ambiente)` faz uma chamada de verdade sem dado de lojista; cada chamada de rede passa por
`chamar(etapa, funcao, servico=...)`. Depois, `registro.registrar(...)` e o import em `integracoes/__init__.py`.
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

MODOS = ("real", "simulado", "desligado")
TIPOS = ("interno", "externo")
SAUDES = ("ok", "pausada", "indisponivel", "desligada")
FALHAS_PARA_PAUSAR = 3
SEGUNDOS_DE_PAUSA = 60
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

    def falha(self):
        """Conta uma falha de rede. Devolve True se esta falha abriu (ou reabriu) a pausa."""
        with self._trava:
            self._falhas_seguidas += 1
            self._testando = False
            if self._falhas_seguidas >= FALHAS_PARA_PAUSAR:
                self._pausado_ate = self._relogio() + SEGUNDOS_DE_PAUSA
                return True
            return False

    def neutro(self):
        """A chamada terminou sem dizer nada sobre a integração (erro do nosso lado): só solta o teste."""
        with self._trava:
            self._testando = False

    @property
    def pausado(self):
        with self._trava:
            return self._pausado_ate is not None and self._relogio() < self._pausado_ate

    @property
    def falhou_por_ultimo(self):
        with self._trava:
            return self._falhas_seguidas > 0


class Conector:
    nome = ""  # o mesmo de `integracoes` nas fichas
    rotulo = ""  # como a interface mostra
    tipo = "externo"
    variavel_modo = ""  # ex.: APIS_PUBLICAS_MODO; vazio quando o conector decide o modo pela configuração
    modo_padrao = "real"
    variaveis = ()  # nomes das variáveis do .env que o conector lê (nunca os valores)
    servicos = ("",)  # cada serviço tem o próprio disjuntor: uma API fora do ar não pausa a outra

    def __init__(self, relogio=time.monotonic):
        self._relogio = relogio
        self._disjuntores = {servico: Disjuntor(relogio) for servico in self.servicos}

    def modo(self, ambiente=os.environ):
        if not self.variavel_modo:
            return self.modo_padrao
        valor = ambiente.get(self.variavel_modo, "").strip().lower() or self.modo_padrao
        if valor not in MODOS:
            logger.warning("modo de integracao invalido: integracao=%s variavel=%s", self.nome, self.variavel_modo)
            return "desligado"  # valor estranho: falha fechada
        return valor

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
        """True se a integração foi derrubada de propósito (falha simulada). Os conectores internos usam."""
        return False

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

    def saude(self, ambiente=os.environ):
        """`desligada`, `pausada`, `indisponivel` ou `ok`, sem fazer chamada nenhuma."""
        if not self.configurado(ambiente):
            return "desligada" if self.modo(ambiente) == "desligado" else "indisponivel"
        if self.fora_do_ar():
            return "indisponivel"
        if any(d.pausado for d in self._disjuntores.values()):
            return "pausada"
        if any(d.falhou_por_ultimo for d in self._disjuntores.values()):
            return "indisponivel"
        return "ok"

    def testar(self, ambiente=os.environ):
        """Chamada de verdade, sem dado de lojista, para quem configura conferir. Devolve uma frase curta."""
        raise IntegracaoDesligada("teste não implementado para esta integração")

    def reiniciar(self):
        """Zera os disjuntores (testes e reinício da demo)."""
        self._disjuntores = {servico: Disjuntor(self._relogio) for servico in self.servicos}
