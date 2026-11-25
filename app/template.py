from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlparse

from .config import PERMITIR_REDE_LOCAL

PADRAO = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def obter_caminho(contexto: Any, caminho: str) -> Any:
    atual = contexto
    for parte in caminho.strip().split("."):
        if isinstance(atual, dict):
            atual = atual.get(parte)
        elif isinstance(atual, list) and parte.isdigit():
            indice = int(parte)
            atual = atual[indice] if indice < len(atual) else None
        else:
            return None
    return atual


def resolver_template(valor: Any, contexto: dict[str, Any]) -> Any:
    if isinstance(valor, str):
        completo = PADRAO.fullmatch(valor.strip())
        if completo:
            resultado = obter_caminho(contexto, completo.group(1))
            if resultado is None:
                raise ValueError(f"Variável não encontrada: {completo.group(1)}")
            return resultado

        def substituir(match: re.Match[str]) -> str:
            resultado = obter_caminho(contexto, match.group(1))
            if resultado is None:
                raise ValueError(f"Variável não encontrada: {match.group(1)}")
            if isinstance(resultado, (dict, list)):
                return json.dumps(resultado, ensure_ascii=False)
            return str(resultado)

        return PADRAO.sub(substituir, valor)
    if isinstance(valor, dict):
        return {chave: resolver_template(item, contexto) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [resolver_template(item, contexto) for item in valor]
    return valor


def json_ou_texto(valor: Any, padrao: Any = None) -> Any:
    if valor is None or valor == "":
        return padrao
    if isinstance(valor, (dict, list)):
        return valor
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except json.JSONDecodeError:
            return valor
    return valor


def validar_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("A URL precisa começar com http:// ou https://")
    if not parsed.hostname:
        raise ValueError("A URL não tem um host válido.")
    if PERMITIR_REDE_LOCAL:
        return
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ValueError(
            "URL local bloqueada. Use CAPIVARA_CLOUD_PERMITIR_REDE_LOCAL=true "
            "para permitir em desenvolvimento."
        )
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise ValueError("IP privado bloqueado por segurança (SSRF).")
