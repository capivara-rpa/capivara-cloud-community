from __future__ import annotations

import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import CHAVE_ARQUIVO

SEGREDOS = {
    "senha",
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "client_secret",
    "private_key",
    "access_token",
    "refresh_token",
    "webhook_url",
    "authorization",
    "headers",
}


def _chave() -> bytes:
    chave_env = os.getenv("CAPIVARA_CLOUD_KEY")
    if chave_env:
        return chave_env.encode()
    if CHAVE_ARQUIVO.exists():
        return CHAVE_ARQUIVO.read_bytes().strip()
    chave = Fernet.generate_key()
    CHAVE_ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    CHAVE_ARQUIVO.write_bytes(chave)
    os.chmod(CHAVE_ARQUIVO, 0o600)
    return chave


def _fernet() -> Fernet:
    return Fernet(_chave())


def cifrar(dados: dict[str, Any]) -> str:
    bruto = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode()
    return _fernet().encrypt(bruto).decode()


def decifrar(token: str) -> dict[str, Any]:
    try:
        bruto = _fernet().decrypt(token.encode())
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Credencial ilegível. Verifique a chave local.") from exc
    return json.loads(bruto.decode())


def mascarar(dados: dict[str, Any]) -> dict[str, Any]:
    mascarado: dict[str, Any] = {}
    for chave, valor in dados.items():
        if chave.lower() in SEGREDOS and valor:
            mascarado[chave] = "••••••••"
        elif isinstance(valor, dict):
            mascarado[chave] = mascarar(valor)
        else:
            mascarado[chave] = valor
    return mascarado
