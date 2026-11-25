"""Login: senha com bcrypt, token JWT e a dependência que devolve o acesso de quem chamou.

O token leva só `sub` (id neutro), `iat` e `exp` (ponto 12 do CLAUDE.md). Perfil, área, nível e
carteira nunca viram claim: são lidos do banco e do diretório a cada pedido (`montar_acesso`).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import configuracao
from app.db import obter_sessao
from app.permissoes import Acesso, AcessoRecusado, DiretorioIndisponivel, montar_acesso

ALGORITMO = "HS256"
LIMITE_BCRYPT = 72  # bytes: o bcrypt não aceita senha maior
MENSAGEM_LOGIN = "E-mail ou senha inválidos."
MENSAGEM_SESSAO = "Sessão inválida ou expirada. Entre de novo."
MENSAGEM_DIRETORIO = "O diretório de funcionários está fora do ar. Tente de novo em instantes."

# Hash de uma senha qualquer: o login com e-mail inexistente também roda o bcrypt, para o tempo de
# resposta não revelar quais e-mails existem.
_HASH_FALSO = bcrypt.hashpw(b"senha-que-nao-existe", bcrypt.gensalt()).decode()

_bearer = HTTPBearer(auto_error=False)


def gerar_hash(senha: str) -> str:
    dados = senha.encode()
    if not dados or len(dados) > LIMITE_BCRYPT:
        raise ValueError(f"A senha precisa ter de 1 a {LIMITE_BCRYPT} bytes.")
    return bcrypt.hashpw(dados, bcrypt.gensalt()).decode()


def senha_confere(senha: str, senha_hash: str) -> bool:
    dados = senha.encode()
    if len(dados) > LIMITE_BCRYPT:
        bcrypt.checkpw(b"x", _HASH_FALSO.encode())  # mesmo custo, resposta igual
        return False
    try:
        return bcrypt.checkpw(dados, senha_hash.encode())
    except ValueError:  # hash corrompido no banco
        return False


def normalizar_email(email: str) -> str:
    return email.strip().lower()


TAMANHO_MINIMO_DO_SEGREDO = 32  # HS256 pede chave de pelo menos 32 bytes (RFC 7518, 3.2)


def segredo_do_token() -> str:
    segredo = configuracao.jwt_segredo.get_secret_value() if configuracao.jwt_segredo else ""
    if len(segredo.encode()) < TAMANHO_MINIMO_DO_SEGREDO:
        raise RuntimeError(
            f"Defina JWT_SEGREDO no .env com pelo menos {TAMANHO_MINIMO_DO_SEGREDO} caracteres."
        )
    return segredo


def criar_token(id_usuario: str, agora: datetime | None = None) -> str:
    agora = agora or datetime.now(UTC)
    validade = timedelta(hours=configuracao.jwt_validade_horas)
    carga = {"sub": id_usuario, "iat": agora, "exp": agora + validade}
    return jwt.encode(carga, segredo_do_token(), algorithm=ALGORITMO)


def ler_token(token: str) -> str:
    """O `sub` de um token válido. Assinatura errada, expirado ou sem campos: AcessoRecusado."""
    try:
        carga = jwt.decode(
            token, segredo_do_token(), algorithms=[ALGORITMO], options={"require": ["sub", "exp"]}
        )
    except jwt.PyJWTError:
        raise AcessoRecusado from None
    sub = carga.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AcessoRecusado
    return sub


def autenticar(sessao: Session, email: str, senha: str) -> Acesso:
    """Confere e-mail e senha e a porta 1 inteira. Qualquer falha: AcessoRecusado (mensagem única)."""
    conta = sessao.scalar(select(models.Usuario).where(models.Usuario.email == normalizar_email(email)))
    if conta is None:
        senha_confere(senha, _HASH_FALSO)
        raise AcessoRecusado
    if not senha_confere(senha, conta.senha_hash):
        raise AcessoRecusado
    return montar_acesso(sessao, conta.id)  # desligado, afastado ou perfil inválido não entram


def nao_autorizado(mensagem: str = MENSAGEM_SESSAO) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=mensagem, headers={"WWW-Authenticate": "Bearer"}
    )


def diretorio_fora() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=MENSAGEM_DIRETORIO)


def acesso_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    sessao: Annotated[Session, Depends(obter_sessao)],
) -> Acesso:
    """Dependência das rotas logadas: token → banco → diretório, a cada pedido."""
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise nao_autorizado()
    try:
        return montar_acesso(sessao, ler_token(credenciais.credentials))
    except AcessoRecusado:
        raise nao_autorizado() from None
    except DiretorioIndisponivel:
        raise diretorio_fora() from None


AcessoAtual = Annotated[Acesso, Depends(acesso_atual)]
