from __future__ import annotations

from typing import Any


def _html(tipo: str, nome: str, categoria: str, icone: str) -> str:
    return (
        f'<div class="wf-node wf-{categoria}">'
        f'<div class="wf-node-topo"><span class="wf-node-icone">{icone}</span>'
        f'<div class="wf-node-texto"><strong>{nome}</strong>'
        f'<span>{tipo.replace("_", " ")}</span></div></div>'
        f"</div>"
    )


def _no(
    id_no: int,
    tipo: str,
    nome: str,
    config: dict[str, Any],
    pos_x: int,
    pos_y: int,
    *,
    categoria: str,
    icone: str,
    entradas: int = 1,
    saidas: int = 1,
    conexoes_entrada: list[tuple[str, str]] | None = None,
    conexoes_saida: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    inputs = {}
    for indice in range(1, entradas + 1):
        inputs[f"input_{indice}"] = {"connections": []}
    outputs = {}
    for indice in range(1, saidas + 1):
        outputs[f"output_{indice}"] = {"connections": []}
    for origem, entrada in conexoes_entrada or []:
        inputs.setdefault(entrada, {"connections": []})["connections"].append(
            {"node": str(origem), "input": "output_1"}
        )
    for destino, saida in conexoes_saida or []:
        outputs.setdefault(saida, {"connections": []})["connections"].append(
            {"node": str(destino), "input": "input_1"}
        )
    return {
        "id": id_no,
        "name": tipo,
        "data": {"tipo": tipo, "nome": nome, "config": config},
        "class": f"wf-{categoria}",
        "html": _html(tipo, nome, categoria, icone),
        "typenode": False,
        "inputs": inputs,
        "outputs": outputs,
        "pos_x": pos_x,
        "pos_y": pos_y,
    }


def grafo_novo() -> dict[str, Any]:
    return {
        "drawflow": {
            "Home": {
                "data": {
                    "1": _no(
                        1,
                        "gatilho_manual",
                        "Início manual",
                        {},
                        120,
                        220,
                        categoria="gatilho",
                        icone="▶",
                        entradas=0,
                        conexoes_saida=[("2", "output_1")],
                    ),
                    "2": _no(
                        2,
                        "log",
                        "Primeiro passo",
                        {"mensagem": "Olá, Capivara Cloud!"},
                        460,
                        220,
                        categoria="logica",
                        icone="≡",
                        conexoes_entrada=[("1", "input_1")],
                        saidas=0,
                    ),
                }
            }
        }
    }


GRAFOS_EXEMPLO = [
    {
        "nome": "Exemplo: consulta API do GitHub",
        "descricao": (
            "Gatilho manual → GET na API pública do GitHub → log com nome do "
            "repositório e quantidade de estrelas."
        ),
        "grafo": {
            "drawflow": {
                "Home": {
                    "data": {
                        "1": _no(
                            1,
                            "gatilho_manual",
                            "Início manual",
                            {},
                            120,
                            220,
                            categoria="gatilho",
                            icone="▶",
                            entradas=0,
                            conexoes_saida=[("2", "output_1")],
                        ),
                        "2": _no(
                            2,
                            "http",
                            "Buscar repositório",
                            {
                                "metodo": "GET",
                                "url": "https://api.github.com/repos/capivara-rpa/capivara",
                                "headers": '{"Accept": "application/vnd.github+json"}',
                                "corpo": "",
                                "credencial": "",
                                "timeout": 15,
                            },
                            460,
                            220,
                            categoria="acao",
                            icone="↗",
                            conexoes_entrada=[("1", "input_1")],
                            conexoes_saida=[("3", "output_1")],
                        ),
                        "3": _no(
                            3,
                            "log",
                            "Mostrar resposta",
                            {
                                "mensagem": (
                                    "Repo: {{ passos.2.json.full_name }} · "
                                    "stars: {{ passos.2.json.stargazers_count }}"
                                )
                            },
                            800,
                            220,
                            categoria="logica",
                            icone="≡",
                            conexoes_entrada=[("2", "input_1")],
                            saidas=0,
                        ),
                    }
                }
            }
        },
    },
    {
        "nome": "Exemplo: webhook com condição",
        "descricao": (
            "Recebe um webhook com { prioridade } e decide o caminho: alta "
            "prioridade ou fila normal. Ideal para testar o editor."
        ),
        "grafo": {
            "drawflow": {
                "Home": {
                    "data": {
                        "1": _no(
                            1,
                            "gatilho_webhook",
                            "Webhook",
                            {"caminho": "prioridade"},
                            120,
                            240,
                            categoria="gatilho",
                            icone="⇥",
                            entradas=0,
                            conexoes_saida=[("2", "output_1")],
                        ),
                        "2": _no(
                            2,
                            "condicao",
                            "Prioridade alta?",
                            {
                                "campo": "{{ entrada.prioridade }}",
                                "operador": "==",
                                "valor": "alta",
                            },
                            460,
                            240,
                            categoria="logica",
                            icone="◇",
                            saidas=2,
                            conexoes_entrada=[("1", "input_1")],
                            conexoes_saida=[
                                ("3", "output_1"),
                                ("4", "output_2"),
                            ],
                        ),
                        "3": _no(
                            3,
                            "log",
                            "Prioridade alta",
                            {"mensagem": "Chamar o time agora: {{ entrada.titulo }}"},
                            800,
                            150,
                            categoria="logica",
                            icone="!",
                            conexoes_entrada=[("2", "input_1")],
                            saidas=0,
                        ),
                        "4": _no(
                            4,
                            "log",
                            "Fila normal",
                            {"mensagem": "Entrou na fila: {{ entrada.titulo }}"},
                            800,
                            330,
                            categoria="logica",
                            icone="≡",
                            conexoes_entrada=[("2", "input_1")],
                            saidas=0,
                        ),
                    }
                }
            }
        },
    },
]
