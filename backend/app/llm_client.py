"""LLMClient: único ponto de acesso ao modelo (Ollama do professor, atrás do Cloudflare Access).

O que ele garante:
- credenciais do Cloudflare só aqui, lidas do .env, nunca em logs;
- tempo limite e novas tentativas quando o servidor falha;
- no máximo N chamadas ao mesmo tempo (fila com semáforo);
- contagem de tokens e duração de cada chamada;
- modo mock, que responde sem servidor (demo e testes).

Uso pelo orquestrador (o agente da frente 3 recebe uma função `prompt -> texto`):

    cliente = criar_cliente()
    chamar = cliente.como_chamar_modelo(sistema=agente.SISTEMA, opcoes={...})
    resposta, trajetoria = agente.agente(pergunta, usuario, chamar_modelo=chamar)

Teste manual da conexão (de dentro de backend/): python -m app.llm_client
"""

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

PADRAO_PENSAMENTO = re.compile(r"<think>.*?</think>", flags=re.DOTALL)


class ErroLLM(Exception):
    """Falha ao falar com o modelo. `tipo` diz o motivo, sem dados sensíveis."""

    TIPOS = ("configuracao", "credenciais", "indisponivel", "tempo_esgotado", "resposta_invalida")

    def __init__(self, tipo: str, mensagem: str):
        super().__init__(mensagem)
        self.tipo = tipo
        self.mensagem = mensagem


@dataclass(frozen=True)
class RespostaLLM:
    texto: str
    modelo: str
    tokens_entrada: int  # prompt_eval_count do Ollama
    tokens_saida: int  # eval_count do Ollama
    duracao_ms: int


class LLMClient:
    def __init__(
        self,
        host: str,
        modelo: str,
        *,
        cf_client_id: str | None = None,
        cf_client_secret: str | None = None,
        timeout_segundos: float = 180.0,
        tentativas: int = 3,
        max_simultaneas: int = 8,
        espera_entre_tentativas: float = 2.0,
        transporte: httpx.BaseTransport | None = None,
    ):
        if not host:
            raise ErroLLM("configuracao", "Defina OLLAMA_HOST no .env (ou use LLM_MODO=mock).")
        self.modelo = modelo
        self.tentativas = max(1, tentativas)
        self.espera_entre_tentativas = espera_entre_tentativas
        self._vagas = threading.BoundedSemaphore(max_simultaneas)
        cabecalhos = {}
        if cf_client_id and cf_client_secret:
            cabecalhos["CF-Access-Client-Id"] = cf_client_id
            cabecalhos["CF-Access-Client-Secret"] = cf_client_secret
        self._http = httpx.Client(
            base_url=host.rstrip("/"),
            headers=cabecalhos,
            timeout=timeout_segundos,
            transport=transporte,
        )

    # ------------------------------------------------------------------ chamadas
    def gerar(
        self, prompt: str, sistema: str | None = None, opcoes: dict | None = None
    ) -> RespostaLLM:
        """Chama /api/generate (sem streaming) e devolve texto, tokens e duração."""
        corpo = {
            "model": self.modelo,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": opcoes or {},
        }
        if sistema:
            corpo["system"] = sistema
        inicio = time.monotonic()
        dados = self._post("/api/generate", corpo)
        try:
            texto = PADRAO_PENSAMENTO.sub("", dados["response"]).strip()
        except (KeyError, TypeError):
            raise ErroLLM(
                "resposta_invalida", "O servidor respondeu sem o campo 'response'."
            ) from None
        return RespostaLLM(
            texto=texto,
            modelo=dados.get("model", self.modelo),
            tokens_entrada=int(dados.get("prompt_eval_count") or 0),
            tokens_saida=int(dados.get("eval_count") or 0),
            duracao_ms=int((time.monotonic() - inicio) * 1000),
        )

    def listar_modelos(self) -> list[str]:
        """Nomes dos modelos instalados no servidor (/api/tags)."""
        resposta = self._enviar(lambda: self._http.get("/api/tags"))
        return sorted(m["name"] for m in resposta.json().get("models", []))

    def como_chamar_modelo(
        self,
        sistema: str | None = None,
        opcoes: dict | None = None,
        ao_responder: Callable[[RespostaLLM], None] | None = None,
    ) -> Callable[[str], str]:
        """Função `prompt -> texto` no formato que o agente espera em `chamar_modelo`.

        `ao_responder` recebe cada RespostaLLM (ex.: para gravar tokens em uso_modelo).
        """

        def chamar_modelo(prompt: str) -> str:
            resposta = self.gerar(prompt, sistema=sistema, opcoes=opcoes)
            if ao_responder is not None:
                ao_responder(resposta)
            return resposta.texto

        return chamar_modelo

    # ------------------------------------------------------------------ internos
    def _post(self, caminho: str, corpo: dict) -> dict:
        resposta = self._enviar(lambda: self._http.post(caminho, json=corpo))
        try:
            return resposta.json()
        except ValueError:
            raise ErroLLM("resposta_invalida", "O servidor não respondeu em JSON.") from None

    def _enviar(self, requisicao: Callable[[], httpx.Response]) -> httpx.Response:
        """Faz a requisição respeitando o limite de simultâneas e com novas tentativas."""
        ultimo_erro = ErroLLM("indisponivel", "Servidor do modelo indisponível.")
        with self._vagas:
            for tentativa in range(1, self.tentativas + 1):
                try:
                    resposta = requisicao()
                except httpx.TimeoutException:
                    ultimo_erro = ErroLLM(
                        "tempo_esgotado", "O modelo demorou demais para responder."
                    )
                except httpx.TransportError:
                    ultimo_erro = ErroLLM("indisponivel", "Não foi possível conectar ao modelo.")
                else:
                    if resposta.status_code in (401, 403):
                        # Credencial errada não melhora tentando de novo.
                        raise ErroLLM("credenciais", "Cloudflare Access recusou as credenciais.")
                    if resposta.status_code < 500:
                        if resposta.is_error:
                            raise ErroLLM(
                                "resposta_invalida",
                                f"O servidor recusou o pedido (HTTP {resposta.status_code}).",
                            )
                        return resposta
                    ultimo_erro = ErroLLM(
                        "indisponivel",
                        f"Servidor do modelo com erro (HTTP {resposta.status_code}).",
                    )
                if tentativa < self.tentativas:
                    time.sleep(self.espera_entre_tentativas * tentativa)
        raise ultimo_erro


class LLMClientMock:
    """Responde sem servidor, seguindo o protocolo do agente (LER / FINAL).

    1ª chamada de um atendimento: lê o índice de ferramentas.
    Depois disso: entrega uma resposta final avisando que é modo de demonstração.
    """

    modelo = "mock"

    def gerar(
        self, prompt: str, sistema: str | None = None, opcoes: dict | None = None
    ) -> RespostaLLM:
        if "Observação:" not in prompt:
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
        host=config.ollama_host,
        modelo=config.ollama_modelo,
        cf_client_id=segredo(config.cf_access_client_id),
        cf_client_secret=segredo(config.cf_access_client_secret),
        timeout_segundos=config.ollama_timeout_segundos,
        tentativas=config.ollama_tentativas,
        max_simultaneas=config.ollama_max_simultaneas,
    )


if __name__ == "__main__":
    # Teste manual: lista os modelos e faz uma pergunta curta. Nunca imprime credenciais.
    try:
        cliente = criar_cliente()
        modelos = cliente.listar_modelos()
        print("Modelos no servidor:", ", ".join(modelos) or "(nenhum)")
        if cliente.modelo not in modelos:
            print(f"Atenção: '{cliente.modelo}' não está na lista. Confira OLLAMA_MODELO.")
        resposta = cliente.gerar("Responda só com a palavra: pronto")
        print(
            f"Resposta: {resposta.texto!r} | tokens {resposta.tokens_entrada}+"
            f"{resposta.tokens_saida} | {resposta.duracao_ms} ms"
        )
    except ErroLLM as erro:
        print(f"Falhou ({erro.tipo}): {erro.mensagem}")
