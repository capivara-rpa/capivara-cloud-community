from __future__ import annotations

from app import db
from app.engine import executar_workflow
from app.exemplos import GRAFOS_EXEMPLO, grafo_novo


def test_executa_fluxo_manual_com_log():
    workflow = db.criar_workflow("Teste manual", "", grafo_novo())
    execucao = executar_workflow(workflow, entrada={}, gatilho="manual")

    assert execucao["status"] == "concluido"
    assert execucao["erro"] is None
    assert len(execucao["passos"]) == 2
    assert execucao["passos"][0]["tipo"] == "gatilho_manual"
    assert execucao["passos"][1]["tipo"] == "log"
    assert execucao["passos"][1]["saida"]["mensagem"] == "Olá, Capivara Cloud!"


def test_condicao_escolhe_caminho_verdadeiro():
    workflow = db.criar_workflow(
        "Teste condicao alta",
        "",
        GRAFOS_EXEMPLO[1]["grafo"],
    )
    execucao = executar_workflow(
        workflow,
        entrada={"prioridade": "alta", "titulo": "Servidor caiu"},
        gatilho="webhook",
    )

    nomes = [passo["node_nome"] for passo in execucao["passos"]]
    assert execucao["status"] == "concluido"
    assert "Prioridade alta" in nomes
    assert "Fila normal" not in nomes


def test_condicao_escolhe_caminho_falso():
    workflow = db.criar_workflow(
        "Teste condicao normal",
        "",
        GRAFOS_EXEMPLO[1]["grafo"],
    )
    execucao = executar_workflow(
        workflow,
        entrada={"prioridade": "baixa", "titulo": "Pedido novo"},
        gatilho="webhook",
    )

    nomes = [passo["node_nome"] for passo in execucao["passos"]]
    assert execucao["status"] == "concluido"
    assert "Fila normal" in nomes
    assert "Prioridade alta" not in nomes
