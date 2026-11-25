"""Configuração lida do .env (nunca escrever valores secretos aqui)."""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    # Procura o .env na pasta atual e na raiz do repositório.
    # env_ignore_empty: linha vazia no .env (ex.: "LLM_MODELO=") vale como ausente e usa o padrão.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", env_ignore_empty=True
    )

    # Ex.: postgresql+psycopg://stonelab:<senha>@localhost:5432/stonelab
    database_url: str

    # Modelo (LLMClient). "mock" responde sem chamar o servidor (demo e testes).
    # LLM_URL e LLM_MODELO são os mesmos que o modo terminal do agente usa (agentes/terminal.py).
    llm_modo: Literal["ollama", "mock"] = "ollama"
    llm_url: str = ""
    llm_modelo: str = "qwen3.8:27b"
    # Teto de uma chamada. O motor passa o que sobra do turno em tempo_limite, que vence se for menor.
    llm_timeout_segundos: float = 300.0
    llm_tentativas: int = 3
    llm_max_simultaneas: int = 8

    # Login: segredo que assina o token (obrigatório para subir a API) e validade do token.
    jwt_segredo: SecretStr | None = None
    jwt_validade_horas: float = 8.0
    # Senha das contas da demo (python -m app.seed); --senha na linha de comando vence.
    seed_senha_demo: SecretStr | None = None

    # Cloudflare Access: SecretStr esconde o valor em prints e logs.
    cf_access_client_id: SecretStr | None = None
    cf_access_client_secret: SecretStr | None = None


configuracao = Configuracao()
