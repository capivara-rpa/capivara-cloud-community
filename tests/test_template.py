from __future__ import annotations

import pytest

from app.template import json_ou_texto, resolver_template, validar_url


def test_resolve_variavel_simples_e_texto():
    contexto = {"entrada": {"nome": "Arthur"}, "passos": {"2": {"json": {"id": 7}}}}
    assert resolver_template("{{ entrada.nome }}", contexto) == "Arthur"
    assert resolver_template("Olá, {{ entrada.nome }}!", contexto) == "Olá, Arthur!"
    assert resolver_template("{{ passos.2.json.id }}", contexto) == 7


def test_resolve_dict_e_lista():
    contexto = {"entrada": {"nome": "Ana"}}
    config = {"para": "{{ entrada.nome }}@exemplo.com", "lista": ["{{ entrada.nome }}"]}
    assert resolver_template(config, contexto) == {
        "para": "Ana@exemplo.com",
        "lista": ["Ana"],
    }


def test_variavel_ausente_gera_erro_claro():
    with pytest.raises(ValueError, match="Variável não encontrada: entrada.idade"):
        resolver_template("{{ entrada.idade }}", {"entrada": {}})


def test_json_ou_texto():
    assert json_ou_texto('{"a": 1}') == {"a": 1}
    assert json_ou_texto("texto puro") == "texto puro"
    assert json_ou_texto(None, {}) == {}


def test_validar_url_publica_e_privada():
    validar_url("https://api.github.com/repos/capivara-rpa/capivara")
    with pytest.raises(ValueError, match="local"):
        validar_url("http://localhost:8787/")
    with pytest.raises(ValueError, match="privado"):
        validar_url("http://192.168.0.10/")
