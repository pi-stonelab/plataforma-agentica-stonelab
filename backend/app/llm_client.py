"""LLMClient: único ponto de acesso ao modelo (Ollama do professor, atrás do Cloudflare Access).

O que ele garante:
- credenciais do Cloudflare só aqui, lidas do .env, nunca em logs;
- resposta em pedaços (`stream`), porque o Cloudflare desiste aos ~100 s sem resposta (HTTP 524, H14);
- prazo total por chamada (`tempo_limite`, o que sobra do turno) e novas tentativas dentro dele;
- `stop` em "Observação:", temperatura 0 e `think` desligado, para o modelo não inventar o resultado
  da ferramenta (ponto 6 do CLAUDE.md);
- no máximo N chamadas ao mesmo tempo (fila com semáforo);
- contagem de tokens e duração de cada chamada;
- modo mock, que responde sem servidor (demo e testes).

Falha do modelo levanta `ErroLLM`, que é um `ModeloIndisponivel` do motor do agente: mensagem genérica,
nunca a URL do servidor.

Uso pelo orquestrador:

    cliente = criar_cliente()
    chamar = cliente.como_chamar_modelo(ao_responder=gravar_uso)
    turno = rodar_turno(pergunta, usuario, ferramentas, chamar_modelo=chamar, ...)

Teste manual da conexão (de dentro de backend/): python -m app.llm_client
"""

import json
import logging
import re
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import httpx
from agentes.agente_atendimento.agente import PARADA_DO_MODELO, ModeloIndisponivel

PADRAO_PENSAMENTO = re.compile(r"<think>.*?</think>", flags=re.DOTALL)
OPCOES_PADRAO = {"temperature": 0, "stop": [PARADA_DO_MODELO]}

logger = logging.getLogger(__name__)


class ErroLLM(ModeloIndisponivel):
    """Falha ao falar com o modelo. `tipo` diz o motivo, sem dados sensíveis.

    É um `ModeloIndisponivel`: o motor do agente encerra o turno em `limite/modelo_indisponivel`.
    """

    TIPOS = ("configuracao", "credenciais", "indisponivel", "tempo_esgotado", "resposta_invalida")

    def __init__(self, tipo: str, mensagem: str):
        super().__init__(mensagem)
        self.tipo = tipo
        self.mensagem = mensagem


class _Repetir(Exception):
    """Falha passageira: vale tentar de novo, se ainda houver prazo."""

    def __init__(self, erro: ErroLLM):
        super().__init__(erro.mensagem)
        self.erro = erro


@dataclass(frozen=True)
class RespostaLLM:
    texto: str
    modelo: str
    tokens_entrada: int  # prompt_eval_count do Ollama
    tokens_saida: int  # eval_count do Ollama
    duracao_ms: int


def juntar_pedacos(linhas: Iterable[str], prazo: float, agora: Callable[[], float]) -> dict:
    """Junta a resposta em pedaços do Ollama (uma linha JSON por pedaço) e devolve o último pedaço
    com `response` = texto inteiro.

    Só vale a resposta que termina com `done: true`: se a conexão cai antes, o texto está cortado e o
    motor poderia agir sobre uma ação pela metade. O timeout do httpx conta cada espera, não o total,
    então o prazo total é conferido aqui a cada pedaço.
    """
    partes = []
    for linha in linhas:
        if agora() > prazo:
            raise ErroLLM("tempo_esgotado", "O modelo demorou demais para responder.")
        if not linha.strip():
            continue
        try:
            pedaco = json.loads(linha)
        except ValueError:
            raise _Repetir(ErroLLM("resposta_invalida", "O servidor não respondeu em JSON.")) from None
        if not isinstance(pedaco, dict) or "error" in pedaco:
            # O texto do erro do servidor não sai daqui (pode trazer detalhes internos).
            raise _Repetir(ErroLLM("indisponivel", "O modelo respondeu com erro."))
        texto = pedaco.get("response")
        if not isinstance(texto, str):
            raise ErroLLM("resposta_invalida", "O servidor respondeu sem o campo 'response'.")
        partes.append(texto)
        if pedaco.get("done") is True:
            return {**pedaco, "response": "".join(partes)}
    raise _Repetir(ErroLLM("indisponivel", "A resposta do modelo veio cortada."))


class LLMClient:
    def __init__(
        self,
        url: str,
        modelo: str,
        *,
        cf_client_id: str | None = None,
        cf_client_secret: str | None = None,
        timeout_segundos: float = 180.0,
        tentativas: int = 3,
        max_simultaneas: int = 8,
        espera_entre_tentativas: float = 2.0,
        transporte: httpx.BaseTransport | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ):
        if not url:
            raise ErroLLM("configuracao", "Defina LLM_URL no .env (ou use LLM_MODO=mock).")
        if not modelo:
            raise ErroLLM("configuracao", "Defina LLM_MODELO no .env.")
        self.modelo = modelo
        self.timeout_segundos = timeout_segundos
        self.tentativas = max(1, tentativas)
        self.espera_entre_tentativas = espera_entre_tentativas
        self._agora = relogio
        self._vagas = threading.BoundedSemaphore(max_simultaneas)
        cabecalhos = {}
        if cf_client_id and cf_client_secret:
            cabecalhos["CF-Access-Client-Id"] = cf_client_id
            cabecalhos["CF-Access-Client-Secret"] = cf_client_secret
        self._http = httpx.Client(
            base_url=url.rstrip("/"),
            headers=cabecalhos,
            timeout=timeout_segundos,
            transport=transporte,
        )

    # ------------------------------------------------------------------ chamadas
    def gerar(
        self,
        prompt: str,
        sistema: str | None = None,
        opcoes: dict | None = None,
        tempo_limite: float | None = None,
    ) -> RespostaLLM:
        """Chama /api/generate em pedaços e devolve texto, tokens e duração.

        `tempo_limite` (segundos) é o prazo total, contando fila, tentativas e espera entre elas.
        Sem ele, vale `timeout_segundos`.
        """
        corpo = {
            "model": self.modelo,
            "prompt": prompt,
            "stream": True,
            "think": False,
            "options": {**OPCOES_PADRAO, **(opcoes or {})},
        }
        if sistema:
            corpo["system"] = sistema
        inicio = self._agora()
        prazo = inicio + self._prazo(tempo_limite)
        dados = self._com_tentativas(lambda restante: self._gerar_uma_vez(corpo, prazo, restante), prazo)
        return RespostaLLM(
            texto=PADRAO_PENSAMENTO.sub("", dados["response"]).strip(),
            modelo=dados.get("model", self.modelo),
            tokens_entrada=int(dados.get("prompt_eval_count") or 0),
            tokens_saida=int(dados.get("eval_count") or 0),
            duracao_ms=int((self._agora() - inicio) * 1000),
        )

    def listar_modelos(self) -> list[str]:
        """Nomes dos modelos instalados no servidor (/api/tags)."""
        prazo = self._agora() + self.timeout_segundos

        def listar(restante: float) -> list[str]:
            resposta = self._http.get("/api/tags", timeout=restante)
            self._conferir_status(resposta)
            try:
                return sorted(m["name"] for m in resposta.json().get("models", []))
            except (ValueError, KeyError, TypeError, AttributeError):
                raise ErroLLM("resposta_invalida", "O servidor não respondeu em JSON.") from None

        return self._com_tentativas(listar, prazo)

    def como_chamar_modelo(
        self,
        opcoes: dict | None = None,
        ao_responder: Callable[[RespostaLLM], None] | None = None,
    ) -> Callable[..., str]:
        """Função `chamar_modelo(prompt_sistema, prompt, tempo_limite=None) -> texto`, no formato que o
        `rodar_turno` espera. O motor passa em `tempo_limite` o que sobra do turno.

        `ao_responder` recebe cada RespostaLLM (para gravar tokens e latência em `uso_modelo`).
        """

        def chamar_modelo(prompt_sistema: str, prompt: str, tempo_limite: float | None = None) -> str:
            resposta = self.gerar(prompt, sistema=prompt_sistema, opcoes=opcoes, tempo_limite=tempo_limite)
            if ao_responder is not None:
                ao_responder(resposta)
            return resposta.texto

        return chamar_modelo

    # ------------------------------------------------------------------ internos
    def _prazo(self, tempo_limite: float | None) -> float:
        if tempo_limite is None or not tempo_limite > 0:
            return self.timeout_segundos
        return min(float(tempo_limite), self.timeout_segundos)

    def _gerar_uma_vez(self, corpo: dict, prazo: float, restante: float) -> dict:
        with self._http.stream("POST", "/api/generate", json=corpo, timeout=restante) as resposta:
            self._conferir_status(resposta)
            return juntar_pedacos(resposta.iter_lines(), prazo, self._agora)

    @staticmethod
    def _conferir_status(resposta: httpx.Response) -> None:
        if resposta.status_code in (401, 403):
            # Credencial errada não melhora tentando de novo.
            raise ErroLLM("credenciais", "Cloudflare Access recusou as credenciais.")
        if resposta.status_code >= 500:  # inclui o 524 do Cloudflare
            raise _Repetir(
                ErroLLM("indisponivel", f"Servidor do modelo com erro (HTTP {resposta.status_code}).")
            )
        if resposta.is_error:
            raise ErroLLM(
                "resposta_invalida", f"O servidor recusou o pedido (HTTP {resposta.status_code})."
            )

    def _com_tentativas(self, fazer: Callable[[float], object], prazo: float):
        """Roda `fazer(restante)` respeitando o limite de simultâneas, o prazo total e as tentativas."""
        esgotado = ErroLLM("tempo_esgotado", "O modelo demorou demais para responder.")
        restante = prazo - self._agora()
        if restante <= 0 or not self._vagas.acquire(timeout=restante):
            raise esgotado
        try:
            ultimo_erro = ErroLLM("indisponivel", "Servidor do modelo indisponível.")
            for tentativa in range(1, self.tentativas + 1):
                restante = prazo - self._agora()
                if restante <= 0:
                    raise esgotado
                try:
                    return fazer(restante)
                except httpx.TimeoutException:
                    ultimo_erro = esgotado
                except httpx.TransportError:
                    ultimo_erro = ErroLLM("indisponivel", "Não foi possível conectar ao modelo.")
                except _Repetir as repetir:
                    ultimo_erro = repetir.erro
                logger.warning("modelo falhou tentativa=%d tipo=%s", tentativa, ultimo_erro.tipo)
                espera = self.espera_entre_tentativas * tentativa
                if tentativa == self.tentativas or self._agora() + espera >= prazo:
                    break
                time.sleep(espera)
            raise ultimo_erro
        finally:
            self._vagas.release()


class LLMClientMock:
    """Responde sem servidor, seguindo o protocolo do agente (LER / FINAL).

    1ª chamada de um turno: lê o índice de ferramentas.
    Depois disso: entrega uma resposta final avisando que é modo de demonstração.
    """

    modelo = "mock"

    def gerar(
        self,
        prompt: str,
        sistema: str | None = None,
        opcoes: dict | None = None,
        tempo_limite: float | None = None,
    ) -> RespostaLLM:
        if PARADA_DO_MODELO not in prompt:
            texto = "PENSAMENTO: Vou ver quais ferramentas tenho.\nLER: "
        else:
            texto = (
                "PENSAMENTO: Estou em modo de demonstração.\n"
                "FINAL: [modo mock] O modelo está desligado; esta é uma resposta de teste."
            )
        return RespostaLLM(
            texto=texto,
            modelo=self.modelo,
            tokens_entrada=len(prompt.split()),
            tokens_saida=len(texto.split()),
            duracao_ms=0,
        )

    def listar_modelos(self) -> list[str]:
        return [self.modelo]

    como_chamar_modelo = LLMClient.como_chamar_modelo


def criar_cliente(config=None) -> LLMClient | LLMClientMock:
    """Monta o cliente a partir do .env."""
    if config is None:
        from app.config import configuracao as config
    if config.llm_modo == "mock":
        return LLMClientMock()

    def segredo(valor):
        return valor.get_secret_value() if valor is not None else None

    return LLMClient(
        url=config.llm_url,
        modelo=config.llm_modelo,
        cf_client_id=segredo(config.cf_access_client_id),
        cf_client_secret=segredo(config.cf_access_client_secret),
        timeout_segundos=config.llm_timeout_segundos,
        tentativas=config.llm_tentativas,
        max_simultaneas=config.llm_max_simultaneas,
    )


if __name__ == "__main__":
    # Teste manual: lista os modelos e faz uma pergunta curta. Nunca imprime credenciais.
    try:
        cliente = criar_cliente()
        modelos = cliente.listar_modelos()
        print("Modelos no servidor:", ", ".join(modelos) or "(nenhum)")
        if cliente.modelo not in modelos:
            print(f"Atenção: '{cliente.modelo}' não está na lista. Confira LLM_MODELO.")
        resposta = cliente.gerar("Responda só com a palavra: pronto")
        print(
            f"Resposta: {resposta.texto!r} | tokens {resposta.tokens_entrada}+"
            f"{resposta.tokens_saida} | {resposta.duracao_ms} ms"
        )
    except ErroLLM as erro:
        print(f"Falhou ({erro.tipo}): {erro.mensagem}")
