from __future__ import annotations

import pytest

from app.connectors import executar


def test_log_retorna_mensagem():
    saida = executar("log", {"mensagem": "Olá, Capivara!"}, {})
    assert saida["mensagem"] == "Olá, Capivara!"


def test_condicao_verdadeira_e_falsa():
    assert executar("condicao", {"campo": "a", "operador": "==", "valor": "a"}, {})[
        "resultado"
    ] is True
    assert executar("condicao", {"campo": "a", "operador": "!=", "valor": "a"}, {})[
        "resultado"
    ] is False


def test_json_faz_parse_e_extrai_caminho():
    lido = executar("json", {"acao": "parse", "texto": '{"a": 1, "b": 2}'}, {})
    assert lido["resultado"] == {"a": 1, "b": 2}

    extraido = executar(
        "json",
        {"acao": "extrair", "texto": '{"cliente": {"nome": "Arthur"}}', "caminho": "cliente.nome"},
        {},
    )
    assert extraido["resultado"] == "Arthur"


def test_http_bloqueia_localhost_por_padrao():
    with pytest.raises(ValueError, match="local|privad|permitid"):
        executar("http", {"url": "http://127.0.0.1:8787/api/health"}, {})


def test_variavel_define_consulta_remove_e_lista():
    contexto = {}
    definido = executar(
        "variavel",
        {"acao": "definir", "nome": "cliente", "valor": "Ana"},
        contexto,
    )
    assert definido["valor"] == "Ana"
    assert contexto["vars"]["cliente"] == "Ana"

    obtido = executar("variavel", {"acao": "obter", "nome": "cliente"}, contexto)
    assert obtido["valor"] == "Ana"

    listado = executar("variavel", {"acao": "listar"}, contexto)
    assert listado["variaveis"] == {"cliente": "Ana"}

    removido = executar("variavel", {"acao": "remover", "nome": "cliente"}, contexto)
    assert removido["removido"] is True
    assert contexto["vars"] == {}


def test_transformar_texto_lista_data_numero_json_base64_e_hash():
    assert executar("transformar", {"acao": "texto_slug", "entrada": "São Paulo!"}, {})[
        "resultado"
    ] == "sao-paulo"
    assert executar(
        "transformar",
        {"acao": "texto_substituir", "entrada": "Oi mundo", "valor": "mundo", "valor2": "Capivara"},
        {},
    )["resultado"] == "Oi Capivara"

    filtrados = executar(
        "transformar",
        {
            "acao": "lista_filtrar",
            "entrada": [{"uf": "SP"}, {"uf": "RJ"}],
            "caminho": "uf",
            "operador": "==",
            "valor": "SP",
        },
        {},
    )
    assert filtrados["resultado"] == [{"uf": "SP"}]

    assert executar(
        "transformar",
        {"acao": "lista_somar", "entrada": [1, 2, 3.5]},
        {},
    )["resultado"] == 6.5
    assert executar(
        "transformar",
        {"acao": "lista_contar", "entrada": "[1, 2, 3]"},
        {},
    )["resultado"] == 3
    assert executar(
        "transformar",
        {"acao": "data_formatar", "entrada": "2026-11-17", "formato": "%d/%m/%Y"},
        {},
    )["resultado"] == "17/11/2026"
    assert executar(
        "transformar",
        {"acao": "numero_formatar", "entrada": 1234.5, "quantidade": 2},
        {},
    )["resultado"] == "1.234,50"
    assert executar(
        "transformar",
        {"acao": "json_parse", "entrada": '{"a": 1}'},
        {},
    )["resultado"] == {"a": 1}
    assert executar(
        "transformar",
        {
            "acao": "json_extrair",
            "entrada": '{"cliente": {"nome": "Ana"}}',
            "caminho": "cliente.nome",
        },
        {},
    )["resultado"] == "Ana"
    assert executar(
        "transformar",
        {"acao": "base64_codificar", "entrada": "Capivara"},
        {},
    )["resultado"] == "Q2FwaXZhcmE="
    assert executar(
        "transformar",
        {"acao": "base64_decodificar", "entrada": "Q2FwaXZhcmE="},
        {},
    )["resultado"] == "Capivara"
    assert len(
        executar("transformar", {"acao": "hash_sha256", "entrada": "Capivara"}, {})[
            "resultado"
        ]
    ) == 64


def test_catalogo_tem_conjuntos_logos_e_campos_condicionais():
    from app.connectors import CATALOGO

    por_tipo = {item["tipo"]: item for item in CATALOGO}
    assert len(CATALOGO) == 28
    assert por_tipo["microsoft_graph_excel"]["conjunto"] == "Microsoft 365"
    assert por_tipo["microsoft_graph_excel"]["logo"].endswith("microsoftexcel.svg")
    assert por_tipo["email"]["logo"].endswith("email.svg")
    assert por_tipo["variavel"]["conjunto"] == "Variáveis"

    acao = next(campo for campo in por_tipo["email"]["campos"] if campo["nome"] == "acao")
    assert "listar" in acao["opcoes"]
    para = next(campo for campo in por_tipo["email"]["campos"] if campo["nome"] == "para")
    assert para["mostrar_se"] == {"acao": ["enviar"]}
    pasta = next(campo for campo in por_tipo["email"]["campos"] if campo["nome"] == "pasta")
    assert "listar" in pasta["mostrar_se"]["acao"]


def test_microsoft_graph_exige_credencial():
    with pytest.raises(ValueError, match="credencial Microsoft 365"):
        executar("microsoft_graph_email", {"para": "a@b.com"}, {})
    with pytest.raises(ValueError, match="credencial Microsoft 365"):
        executar("microsoft_graph_excel", {"acao": "ler"}, {})


def test_microsoft_graph_email_monta_payload(monkeypatch):
    import httpx

    from app import connectors, db

    db.criar_credencial(
        "graph_teste",
        "microsoft_graph",
        {
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "segredo",
            "usuario": "automacao@empresa.com",
        },
    )
    chamadas = {}

    def post_falso(url, **kwargs):
        chamadas["token"] = (url, kwargs)
        return httpx.Response(200, json={"access_token": "token-teste"})

    def request_falso(metodo, url, **kwargs):
        chamadas["pedido"] = (metodo, url, kwargs)
        return httpx.Response(202, json={})

    monkeypatch.setattr(connectors.httpx, "post", post_falso)
    monkeypatch.setattr(connectors.httpx, "request", request_falso)

    saida = executar(
        "microsoft_graph_email",
        {
            "credencial": "graph_teste",
            "para": "cliente@empresa.com",
            "assunto": "Relatório",
            "corpo": "<b>Oi</b>",
            "html": "sim",
        },
        {},
    )
    assert saida["enviado"] is True
    assert chamadas["token"][0].endswith("/tenant/oauth2/v2.0/token")
    metodo, url, kwargs = chamadas["pedido"]
    assert metodo == "POST"
    assert url.endswith("/users/automacao@empresa.com/sendMail")
    assert kwargs["headers"]["Authorization"] == "Bearer token-teste"
    mensagem = kwargs["json"]["message"]
    assert mensagem["subject"] == "Relatório"
    assert mensagem["body"] == {"contentType": "HTML", "content": "<b>Oi</b>"}
    assert mensagem["toRecipients"][0]["emailAddress"]["address"] == "cliente@empresa.com"
