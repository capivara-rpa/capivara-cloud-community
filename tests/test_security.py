from __future__ import annotations

from app.security import cifrar, decifrar, mascarar


def test_cifra_e_decifra():
    dados = {"host": "smtp.exemplo.com", "senha": "super-secreta"}
    token = cifrar(dados)
    assert token != str(dados)
    assert decifrar(token) == dados


def test_mascara_segredos_aninhados():
    dados = {
        "host": "smtp.exemplo.com",
        "senha": "123",
        "headers": {"Authorization": "Bearer abc"},
        "config": {"token": "xyz", "canal": "#geral"},
    }
    mascarado = mascarar(dados)
    assert mascarado["host"] == "smtp.exemplo.com"
    assert mascarado["senha"] == "••••••••"
    assert mascarado["headers"] == "••••••••"
    assert mascarado["config"]["token"] == "••••••••"
    assert mascarado["config"]["canal"] == "#geral"
