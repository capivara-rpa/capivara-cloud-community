from __future__ import annotations


def test_health_e_config(cliente):
    resposta = cliente.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.json()["ok"] is True
    assert resposta.json()["nome"] == "Capivara Cloud"

    config = cliente.get("/api/config")
    assert config.status_code == 200
    assert config.json()["docs"] == "/docs"
    assert config.json()["conectores"] > 10


def test_catalogo_e_modelos(cliente):
    catalogo = cliente.get("/api/conectores")
    assert catalogo.status_code == 200
    tipos = {item["tipo"] for item in catalogo.json()["conectores"]}
    assert {
        "gatilho_manual",
        "gatilho_webhook",
        "http",
        "email",
        "excel",
        "condicao",
        "microsoft_graph_email",
        "microsoft_graph_excel",
        "variavel",
        "transformar",
    } <= tipos
    assert "Microsoft 365" in catalogo.json()["conjuntos"]
    assert catalogo.json()["conjuntos"][0] == "Todos"

    modelos = cliente.get("/api/credenciais/modelos")
    assert modelos.status_code == 200
    assert any(item["tipo"] == "smtp" for item in modelos.json())


def test_cria_executa_e_consulta_fluxo(cliente):
    criado = cliente.post(
        "/api/workflows",
        json={"nome": "Fluxo de teste API", "descricao": "teste", "grafo": {}},
    )
    assert criado.status_code == 201
    workflow = criado.json()
    assert workflow["id"]
    assert workflow["grafo"]["drawflow"]["Home"]["data"]

    executado = cliente.post(
        f"/api/workflows/{workflow['id']}/executar",
        json={"entrada": {}},
    )
    assert executado.status_code == 200
    execucao = executado.json()
    assert execucao["status"] == "concluido"
    assert len(execucao["passos"]) >= 2

    detalhe = cliente.get(f"/api/execucoes/{execucao['id']}")
    assert detalhe.status_code == 200
    assert detalhe.json()["workflow_id"] == workflow["id"]

    webhook = cliente.post(f"/api/webhooks/{workflow['id']}", json={"nome": "Arthur"})
    assert webhook.status_code == 200
    assert webhook.json()["gatilho"] == "webhook"


def test_credencial_e_mascarada(cliente):
    criada = cliente.post(
        "/api/credenciais",
        json={
            "nome": "smtp_teste",
            "tipo": "smtp",
            "dados": {"host": "smtp.exemplo.com", "senha": "super-secreta"},
        },
    )
    assert criada.status_code == 201
    assert criada.json()["dados"]["senha"] == "••••••••"

    listadas = cliente.get("/api/credenciais")
    assert listadas.status_code == 200
    credencial = next(item for item in listadas.json() if item["nome"] == "smtp_teste")
    assert credencial["dados"]["senha"] == "••••••••"
    assert credencial["dados"]["host"] == "smtp.exemplo.com"

    removida = cliente.delete(f"/api/credenciais/{credencial['id']}")
    assert removida.status_code == 200


def test_swagger_abre(cliente):
    assert cliente.get("/docs").status_code == 200
    assert cliente.get("/openapi.json").status_code == 200
