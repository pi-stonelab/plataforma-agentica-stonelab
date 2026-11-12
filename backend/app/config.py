"""Configuração lida do .env (nunca escrever valores secretos aqui)."""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    # Procura o .env na pasta atual e na raiz do repositório.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Ex.: postgresql+psycopg://stonelab:<senha>@localhost:5432/stonelab
    database_url: str

    # Modelo (LLMClient). "mock" responde sem chamar o servidor (demo e testes).
    llm_modo: Literal["ollama", "mock"] = "ollama"
    ollama_host: str = ""
    ollama_modelo: str = "qwen3.8:27b"
    ollama_timeout_segundos: float = 180.0
    ollama_tentativas: int = 3
    ollama_max_simultaneas: int = 8
    # Cloudflare Access: SecretStr esconde o valor em prints e logs.
    cf_access_client_id: SecretStr | None = None
    cf_access_client_secret: SecretStr | None = None


configuracao = Configuracao()
