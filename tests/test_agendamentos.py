from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app import agendador, db

PASSADO = "2020-01-01T00:00:00+00:00"


def _fluxo_teste() -> dict:
    return db.criar_workflow(
        f"Fluxo agendado {db.novo_id()}",
        "",
        {"drawflow": {"Home": {"data": {}}}},
    )


def test_validar_expressao_e_proxima(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agendador, "FUSO_LOCAL", ZoneInfo("UTC"))

    assert agendador.validar_expressao("intervalo", " 15m ") == "15m"
    assert agendador.validar_expressao("diario", "9:05") == "09:05"
    assert agendador.validar_expressao("cron", "*/15  9-18 * * seg-sex") == (
        "*/15 9-18 * * seg-sex"
    )

    agora = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    assert agendador.proxima_execucao("intervalo", "15m", agora=agora) == (
        "2026-11-24T12:15:00+00:00"
    )
    assert agendador.proxima_execucao("diario", "09:30", agora=agora) == (
        "2026-11-25T09:30:00+00:00"
    )
    assert agendador.proxima_execucao(
        "cron", "0 13 * * *", agora=agora
    ) == "2026-11-24T13:00:00+00:00"

    with pytest.raises(ValueError):
        agendador.validar_expressao("intervalo", "todo dia")
    with pytest.raises(ValueError):
        agendador.validar_expressao("diario", "25:00")
    with pytest.raises(ValueError):
        agendador.validar_expressao("cron", "* * * *")


def test_crud_agendamento_pela_api(cliente) -> None:
    fluxo = _fluxo_teste()
    resposta = cliente.post(
        "/api/agendamentos",
        json={
            "nome": "Relatório diário",
            "workflow_id": fluxo["id"],
            "tipo": "diario",
            "expressao": "9:05",
            "entrada": {"uf": "SP"},
            "ativo": True,
        },
    )
    assert resposta.status_code == 201
    criado = resposta.json()
    assert criado["expressao"] == "09:05"
    assert criado["entrada"] == {"uf": "SP"}
    assert criado["ativo"] is True
    assert criado["proxima_execucao"]

    assert any(item["id"] == criado["id"] for item in cliente.get("/api/agendamentos").json())
    detalhe = cliente.get(f"/api/agendamentos/{criado['id']}")
    assert detalhe.status_code == 200
    assert detalhe.json()["workflow_nome"] == fluxo["nome"]

    pausado = cliente.put(f"/api/agendamentos/{criado['id']}", json={"ativo": False})
    assert pausado.status_code == 200
    assert pausado.json()["ativo"] is False
    assert pausado.json()["entrada"] == {"uf": "SP"}

    assert cliente.delete(f"/api/agendamentos/{criado['id']}").status_code == 200
    assert cliente.get(f"/api/agendamentos/{criado['id']}").status_code == 404
    assert cliente.delete(f"/api/agendamentos/{criado['id']}").status_code == 404


def test_validacao_e_fluxo_inexistente(cliente) -> None:
    base = {
        "nome": "Teste",
        "workflow_id": "fluxo-inexistente",
        "tipo": "intervalo",
        "expressao": "15m",
    }
    assert cliente.post("/api/agendamentos", json=base).status_code == 404

    fluxo = _fluxo_teste()
    base["workflow_id"] = fluxo["id"]
    base["expressao"] = "quebrado"
    assert cliente.post("/api/agendamentos", json=base).status_code == 400


def test_verificar_agendamento_vencido_executa_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fluxo = _fluxo_teste()
    agendamento = db.criar_agendamento(
        "Vencido",
        fluxo["id"],
        "intervalo",
        "15m",
        PASSADO,
        {"origem": "teste"},
    )

    def executar(item: dict) -> dict:
        assert item["entrada"] == {"origem": "teste"}
        return {"id": "exec-agendada", "status": "concluido"}

    monkeypatch.setattr(agendador, "executar_agendamento", executar)

    resultado = agendador.verificar_agendamentos()
    assert resultado["verificados"] == 1
    assert resultado["executados"] == 1
    assert resultado["erros"] == 0

    atualizado = db.obter_agendamento(agendamento["id"])
    assert atualizado is not None
    assert atualizado["proxima_execucao"] != PASSADO
    assert atualizado["ultima_execucao_id"] == "exec-agendada"
    assert atualizado["execucoes"] == 1

    segundo = agendador.verificar_agendamentos()
    assert segundo["verificados"] == 0
    assert segundo["executados"] == 0
    assert db.obter_agendamento(agendamento["id"])["execucoes"] == 1


def test_reservar_agendamento_e_atomico() -> None:
    fluxo = _fluxo_teste()
    agendamento = db.criar_agendamento(
        "Reserva", fluxo["id"], "intervalo", "1h", PASSADO
    )
    assert db.reservar_agendamento(
        agendamento["id"], PASSADO, "2099-01-01T00:00:00+00:00", db.agora()
    )
    assert not db.reservar_agendamento(
        agendamento["id"], PASSADO, "2099-01-02T00:00:00+00:00", db.agora()
    )


def test_executar_agendamento_agora(
    cliente, monkeypatch: pytest.MonkeyPatch
) -> None:
    fluxo = _fluxo_teste()
    agendamento = db.criar_agendamento(
        "Agora", fluxo["id"], "intervalo", "1h", "2099-01-01T00:00:00+00:00"
    )
    monkeypatch.setattr(
        agendador,
        "executar_agendamento",
        lambda item: {"id": "exec-agora", "status": "concluido"},
    )

    resposta = cliente.post(f"/api/agendamentos/{agendamento['id']}/executar")
    assert resposta.status_code == 200
    assert resposta.json()["id"] == "exec-agora"

    assert cliente.post("/api/agendamentos/inexistente/executar").status_code == 404


def test_conectar_fecha_conexao(monkeypatch: pytest.MonkeyPatch) -> None:
    conexoes: list[sqlite3.Connection] = []
    original = sqlite3.connect

    def fabrica(*args, **kwargs):
        conexao = original(*args, **kwargs)
        conexoes.append(conexao)
        return conexao

    monkeypatch.setattr(sqlite3, "connect", fabrica)

    for _ in range(10):
        with db.conectar() as conexao:
            assert conexao.execute("SELECT 1").fetchone()[0] == 1

    assert len(conexoes) == 10
    for conexao in conexoes:
        with pytest.raises(sqlite3.ProgrammingError):
            conexao.execute("SELECT 1")
