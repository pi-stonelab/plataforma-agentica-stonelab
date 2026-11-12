"""Configuração lida do .env (nunca escrever valores secretos aqui)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    # Procura o .env na pasta atual e na raiz do repositório.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Ex.: postgresql+psycopg://stonelab:<senha>@localhost:5432/stonelab
    database_url: str


configuracao = Configuracao()
