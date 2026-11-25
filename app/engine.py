from __future__ import annotations

import time
from typing import Any

from . import db
from .connectors import CATALOGO_POR_TIPO, executar
from .security import mascarar


class ErroWorkflow(Exception):
    pass


def _dados_do_grafo(grafo: dict[str, Any]) -> dict[str, Any]:
    try:
        return grafo["drawflow"]["Home"]["data"]
    except (KeyError, TypeError):
        return {}


def _parsear(grafo: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    dados = _dados_do_grafo(grafo)
    nos: dict[str, dict[str, Any]] = {}
    arestas: list[dict[str, str]] = []
    for id_no, bruto in dados.items():
        id_texto = str(id_no)
        dados_no = bruto.get("data") or {}
        tipo = str(dados_no.get("tipo") or bruto.get("name") or "")
        if not tipo:
            continue
        nome_padrao = CATALOGO_POR_TIPO.get(tipo, {}).get("nome")
        nos[id_texto] = {
            "id": id_texto,
            "tipo": tipo,
            "nome": str(dados_no.get("nome") or nome_padrao or tipo),
            "config": dados_no.get("config") or {},
        }
        for nome_saida, saida in (bruto.get("outputs") or {}).items():
            for conexao in saida.get("connections") or []:
                arestas.append(
                    {
                        "source": id_texto,
                        "target": str(conexao.get("node")),
                        "source_output": str(nome_saida),
                    }
                )
    return nos, arestas


def _no_inicial(nos: dict[str, dict[str, Any]], arestas: list[dict[str, str]]) -> str | None:
    for id_no, no in nos.items():
        if no["tipo"].startswith("gatilho_"):
            return id_no
    destinos = {aresta["target"] for aresta in arestas}
    candidatos = [id_no for id_no in nos if id_no not in destinos]
    if candidatos:
        return candidatos[0]
    return next(iter(nos), None)


def _proximo(
    no: dict[str, Any],
    arestas: list[dict[str, str]],
    saida: dict[str, Any],
) -> dict[str, str] | None:
    candidatas = [aresta for aresta in arestas if aresta["source"] == no["id"]]
    if not candidatas:
        return None
    if no["tipo"] == "condicao":
        verdadeiro = bool(saida.get("resultado"))
        aceitas = {"output_1", "true"} if verdadeiro else {"output_2", "false"}
        for aresta in candidatas:
            if aresta["source_output"] in aceitas:
                return aresta
        return None
    return candidatas[0]


def executar_workflow(
    workflow: dict[str, Any],
    entrada: dict[str, Any] | None = None,
    gatilho: str = "manual",
) -> dict[str, Any]:
    entrada = entrada or {}
    nos, arestas = _parsear(workflow.get("grafo") or {})
    if not nos:
        raise ErroWorkflow("O fluxo está vazio. Adicione um nó de gatilho e uma ação.")

    atual = _no_inicial(nos, arestas)
    execucao = db.criar_execucao(
        workflow["id"], workflow["nome"], gatilho, entrada
    )
    contexto: dict[str, Any] = {
        "entrada": entrada,
        "gatilho": {"tipo": gatilho, "body": entrada},
        "passos": {},
        "ultimo": None,
        "vars": {},
    }
    inicio_execucao = time.perf_counter()
    status = "concluido"
    erro: str | None = None
    quantidade = 0

    while atual and quantidade < 100:
        no = nos.get(atual)
        if not no:
            status = "erro"
            erro = f"Nó não encontrado: {atual}"
            break
        inicio = db.agora()
        relogio = time.perf_counter()
        try:
            saida = executar(no["tipo"], no["config"], contexto)
            duracao = int((time.perf_counter() - relogio) * 1000)
            contexto["passos"][atual] = saida
            contexto["ultimo"] = saida
            db.registrar_passo(
                execucao["id"],
                node_id=atual,
                node_nome=no["nome"],
                tipo=no["tipo"],
                status="concluido",
                inicio=inicio,
                fim=db.agora(),
                duracao_ms=duracao,
                entrada={"config": mascarar(no["config"])},
                saida=saida,
            )
        except Exception as exc:  # noqa: BLE001 - o erro vira trace do usuário
            duracao = int((time.perf_counter() - relogio) * 1000)
            status = "erro"
            erro = str(exc)
            db.registrar_passo(
                execucao["id"],
                node_id=atual,
                node_nome=no["nome"],
                tipo=no["tipo"],
                status="erro",
                inicio=inicio,
                fim=db.agora(),
                duracao_ms=duracao,
                entrada={"config": mascarar(no["config"])},
                saida={},
                erro=erro,
            )
            break

        quantidade += 1
        if no["tipo"] == "fim" or saida.get("fim"):
            break
        proximo = _proximo(no, arestas, saida)
        if not proximo:
            break
        atual = proximo["target"]

    if quantidade >= 100 and status == "concluido":
        status = "erro"
        erro = "Limite de 100 passos atingido. Verifique se o fluxo tem um ciclo."

    duracao_total = int((time.perf_counter() - inicio_execucao) * 1000)
    db.finalizar_execucao(execucao["id"], status, erro, duracao_total)
    return db.obter_execucao(execucao["id"]) or execucao
