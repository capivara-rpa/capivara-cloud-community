from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from .config import BANCO
from .security import cifrar, decifrar, mascarar

ESQUEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    grafo TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execucoes (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_nome TEXT NOT NULL,
    status TEXT NOT NULL,
    gatilho TEXT NOT NULL,
    entrada TEXT NOT NULL DEFAULT '{}',
    inicio TEXT NOT NULL,
    fim TEXT,
    duracao_ms INTEGER,
    erro TEXT
);

CREATE TABLE IF NOT EXISTS passos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execucao_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    status TEXT NOT NULL,
    inicio TEXT NOT NULL,
    fim TEXT,
    duracao_ms INTEGER,
    entrada TEXT NOT NULL DEFAULT '{}',
    saida TEXT NOT NULL DEFAULT '{}',
    erro TEXT
);

CREATE TABLE IF NOT EXISTS credenciais (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    dados TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    tipo TEXT NOT NULL,
    expressao TEXT NOT NULL,
    entrada TEXT NOT NULL DEFAULT '{}',
    ativo INTEGER NOT NULL DEFAULT 1,
    proxima_execucao TEXT NOT NULL,
    ultima_execucao TEXT,
    ultima_execucao_id TEXT,
    ultimo_erro TEXT,
    execucoes INTEGER NOT NULL DEFAULT 0,
    erros INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execucoes_inicio ON execucoes(inicio DESC);
CREATE INDEX IF NOT EXISTS idx_passos_execucao ON passos(execucao_id, id);
CREATE INDEX IF NOT EXISTS idx_agendamentos_proxima ON agendamentos(ativo, proxima_execucao);
"""


def agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def novo_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(BANCO, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def iniciar_banco() -> None:
    with conectar() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(ESQUEMA)
    garantir_exemplos()


def _json(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


def _carregar_json(valor: str | None, padrao: Any = None) -> Any:
    if not valor:
        return padrao
    try:
        return json.loads(valor)
    except json.JSONDecodeError:
        return padrao


def _workflow_da_linha(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "descricao": linha["descricao"],
        "grafo": _carregar_json(linha["grafo"], {}),
        "ativo": bool(linha["ativo"]),
        "criado_em": linha["criado_em"],
        "atualizado_em": linha["atualizado_em"],
    }


def criar_workflow(
    nome: str,
    descricao: str,
    grafo: dict[str, Any],
    ativo: bool = True,
) -> dict[str, Any]:
    id_workflow = novo_id()
    momento = agora()
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO workflows (id, nome, descricao, grafo, ativo, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (id_workflow, nome, descricao, _json(grafo), int(ativo), momento, momento),
        )
        linha = conn.execute(
            "SELECT * FROM workflows WHERE id = ?", (id_workflow,)
        ).fetchone()
    return _workflow_da_linha(linha)


def listar_workflows() -> list[dict[str, Any]]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM workflows ORDER BY atualizado_em DESC"
        ).fetchall()
    return [_workflow_da_linha(linha) for linha in linhas]


def obter_workflow(id_workflow: str) -> dict[str, Any] | None:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT * FROM workflows WHERE id = ?", (id_workflow,)
        ).fetchone()
    return _workflow_da_linha(linha) if linha else None


def atualizar_workflow(
    id_workflow: str,
    *,
    nome: str | None = None,
    descricao: str | None = None,
    grafo: dict[str, Any] | None = None,
    ativo: bool | None = None,
) -> dict[str, Any] | None:
    atual = obter_workflow(id_workflow)
    if not atual:
        return None
    momento = agora()
    with conectar() as conn:
        conn.execute(
            """
            UPDATE workflows
               SET nome = ?, descricao = ?, grafo = ?, ativo = ?, atualizado_em = ?
             WHERE id = ?
            """,
            (
                nome if nome is not None else atual["nome"],
                descricao if descricao is not None else atual["descricao"],
                _json(grafo) if grafo is not None else _json(atual["grafo"]),
                int(ativo if ativo is not None else atual["ativo"]),
                momento,
                id_workflow,
            ),
        )
    return obter_workflow(id_workflow)


def apagar_workflow(id_workflow: str) -> bool:
    with conectar() as conn:
        cursor = conn.execute("DELETE FROM workflows WHERE id = ?", (id_workflow,))
    return cursor.rowcount > 0


def criar_execucao(
    workflow_id: str,
    workflow_nome: str,
    gatilho: str,
    entrada: dict[str, Any],
) -> dict[str, Any]:
    id_execucao = novo_id()
    momento = agora()
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO execucoes
                (id, workflow_id, workflow_nome, status, gatilho, entrada, inicio)
            VALUES (?, ?, ?, 'executando', ?, ?, ?)
            """,
            (id_execucao, workflow_id, workflow_nome, gatilho, _json(entrada), momento),
        )
    return {
        "id": id_execucao,
        "workflow_id": workflow_id,
        "workflow_nome": workflow_nome,
        "status": "executando",
        "gatilho": gatilho,
        "entrada": entrada,
        "inicio": momento,
        "fim": None,
        "duracao_ms": None,
        "erro": None,
    }


def finalizar_execucao(
    id_execucao: str,
    status: str,
    erro: str | None = None,
    duracao_ms: int | None = None,
) -> None:
    with conectar() as conn:
        conn.execute(
            """
            UPDATE execucoes
               SET status = ?, fim = ?, duracao_ms = ?, erro = ?
             WHERE id = ?
            """,
            (status, agora(), duracao_ms, erro, id_execucao),
        )


def registrar_passo(
    execucao_id: str,
    *,
    node_id: str,
    node_nome: str,
    tipo: str,
    status: str,
    inicio: str,
    fim: str | None,
    duracao_ms: int | None,
    entrada: Any,
    saida: Any,
    erro: str | None = None,
) -> None:
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO passos
                (execucao_id, node_id, node_nome, tipo, status, inicio, fim,
                 duracao_ms, entrada, saida, erro)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execucao_id,
                node_id,
                node_nome,
                tipo,
                status,
                inicio,
                fim,
                duracao_ms,
                _json(entrada),
                _json(saida),
                erro,
            ),
        )


def _execucao_da_linha(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": linha["id"],
        "workflow_id": linha["workflow_id"],
        "workflow_nome": linha["workflow_nome"],
        "status": linha["status"],
        "gatilho": linha["gatilho"],
        "entrada": _carregar_json(linha["entrada"], {}),
        "inicio": linha["inicio"],
        "fim": linha["fim"],
        "duracao_ms": linha["duracao_ms"],
        "erro": linha["erro"],
    }


def listar_execucoes(limite: int = 50) -> list[dict[str, Any]]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM execucoes ORDER BY inicio DESC LIMIT ?", (limite,)
        ).fetchall()
    return [_execucao_da_linha(linha) for linha in linhas]


def obter_execucao(id_execucao: str) -> dict[str, Any] | None:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT * FROM execucoes WHERE id = ?", (id_execucao,)
        ).fetchone()
        if not linha:
            return None
        passos = conn.execute(
            "SELECT * FROM passos WHERE execucao_id = ? ORDER BY id", (id_execucao,)
        ).fetchall()
    execucao = _execucao_da_linha(linha)
    execucao["passos"] = [
        {
            "id": passo["id"],
            "node_id": passo["node_id"],
            "node_nome": passo["node_nome"],
            "tipo": passo["tipo"],
            "status": passo["status"],
            "inicio": passo["inicio"],
            "fim": passo["fim"],
            "duracao_ms": passo["duracao_ms"],
            "entrada": _carregar_json(passo["entrada"], {}),
            "saida": _carregar_json(passo["saida"], {}),
            "erro": passo["erro"],
        }
        for passo in passos
    ]
    return execucao


def criar_credencial(nome: str, tipo: str, dados: dict[str, Any]) -> dict[str, Any]:
    id_credencial = novo_id()
    momento = agora()
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO credenciais (id, nome, tipo, dados, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id_credencial, nome, tipo, cifrar(dados), momento, momento),
        )
    return {
        "id": id_credencial,
        "nome": nome,
        "tipo": tipo,
        "dados": mascarar(dados),
        "criado_em": momento,
        "atualizado_em": momento,
    }


def listar_credenciais() -> list[dict[str, Any]]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM credenciais ORDER BY nome COLLATE NOCASE"
        ).fetchall()
    saida: list[dict[str, Any]] = []
    for linha in linhas:
        try:
            dados = decifrar(linha["dados"])
        except ValueError:
            dados = {}
        saida.append(
            {
                "id": linha["id"],
                "nome": linha["nome"],
                "tipo": linha["tipo"],
                "dados": mascarar(dados),
                "criado_em": linha["criado_em"],
                "atualizado_em": linha["atualizado_em"],
            }
        )
    return saida


def obter_credencial(nome: str, *, mascarar_dados: bool = True) -> dict[str, Any] | None:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT * FROM credenciais WHERE nome = ?", (nome,)
        ).fetchone()
    if not linha:
        return None
    try:
        dados = decifrar(linha["dados"])
    except ValueError:
        dados = {}
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "tipo": linha["tipo"],
        "dados": mascarar(dados) if mascarar_dados else dados,
        "criado_em": linha["criado_em"],
        "atualizado_em": linha["atualizado_em"],
    }


def apagar_credencial(id_credencial: str) -> bool:
    with conectar() as conn:
        cursor = conn.execute(
            "DELETE FROM credenciais WHERE id = ?", (id_credencial,)
        )
    return cursor.rowcount > 0


_AGENDAMENTO_SELECT = """
SELECT a.*, COALESCE(w.nome, '') AS workflow_nome
  FROM agendamentos a
  LEFT JOIN workflows w ON w.id = a.workflow_id
"""


def _agendamento_da_linha(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "workflow_id": linha["workflow_id"],
        "workflow_nome": linha["workflow_nome"],
        "tipo": linha["tipo"],
        "expressao": linha["expressao"],
        "entrada": _carregar_json(linha["entrada"], {}),
        "ativo": bool(linha["ativo"]),
        "proxima_execucao": linha["proxima_execucao"],
        "ultima_execucao": linha["ultima_execucao"],
        "ultima_execucao_id": linha["ultima_execucao_id"],
        "ultimo_erro": linha["ultimo_erro"],
        "execucoes": linha["execucoes"],
        "erros": linha["erros"],
        "criado_em": linha["criado_em"],
        "atualizado_em": linha["atualizado_em"],
    }


def criar_agendamento(
    nome: str,
    workflow_id: str,
    tipo: str,
    expressao: str,
    proxima_execucao: str,
    entrada: dict[str, Any] | None = None,
    ativo: bool = True,
) -> dict[str, Any]:
    id_agendamento = novo_id()
    momento = agora()
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO agendamentos
                (id, nome, workflow_id, tipo, expressao, entrada, ativo,
                 proxima_execucao, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_agendamento,
                nome,
                workflow_id,
                tipo,
                expressao,
                _json(entrada or {}),
                int(ativo),
                proxima_execucao,
                momento,
                momento,
            ),
        )
    return obter_agendamento(id_agendamento)


def listar_agendamentos() -> list[dict[str, Any]]:
    with conectar() as conn:
        linhas = conn.execute(
            f"{_AGENDAMENTO_SELECT} ORDER BY a.proxima_execucao"
        ).fetchall()
    return [_agendamento_da_linha(linha) for linha in linhas]


def obter_agendamento(id_agendamento: str) -> dict[str, Any] | None:
    with conectar() as conn:
        linha = conn.execute(
            f"{_AGENDAMENTO_SELECT} WHERE a.id = ?", (id_agendamento,)
        ).fetchone()
    return _agendamento_da_linha(linha) if linha else None


def atualizar_agendamento(
    id_agendamento: str,
    *,
    nome: str | None = None,
    tipo: str | None = None,
    expressao: str | None = None,
    entrada: dict[str, Any] | None = None,
    ativo: bool | None = None,
    proxima_execucao: str | None = None,
) -> dict[str, Any] | None:
    atual = obter_agendamento(id_agendamento)
    if not atual:
        return None
    with conectar() as conn:
        conn.execute(
            """
            UPDATE agendamentos
               SET nome = ?, tipo = ?, expressao = ?, entrada = ?, ativo = ?,
                   proxima_execucao = ?, atualizado_em = ?
             WHERE id = ?
            """,
            (
                nome if nome is not None else atual["nome"],
                tipo if tipo is not None else atual["tipo"],
                expressao if expressao is not None else atual["expressao"],
                _json(entrada) if entrada is not None else _json(atual["entrada"]),
                int(ativo if ativo is not None else atual["ativo"]),
                proxima_execucao or atual["proxima_execucao"],
                agora(),
                id_agendamento,
            ),
        )
    return obter_agendamento(id_agendamento)


def apagar_agendamento(id_agendamento: str) -> bool:
    with conectar() as conn:
        cursor = conn.execute(
            "DELETE FROM agendamentos WHERE id = ?", (id_agendamento,)
        )
    return cursor.rowcount > 0


def listar_agendamentos_devidos(momento: str, limite: int = 50) -> list[dict[str, Any]]:
    with conectar() as conn:
        linhas = conn.execute(
            f"{_AGENDAMENTO_SELECT} "
            "WHERE a.ativo = 1 AND a.proxima_execucao <= ? "
            "ORDER BY a.proxima_execucao LIMIT ?",
            (momento, limite),
        ).fetchall()
    return [_agendamento_da_linha(linha) for linha in linhas]


def reservar_agendamento(
    id_agendamento: str,
    proxima_anterior: str,
    proxima_seguinte: str,
    executado_em: str,
) -> bool:
    with conectar() as conn:
        cursor = conn.execute(
            """
            UPDATE agendamentos
               SET proxima_execucao = ?, ultima_execucao = ?, ultimo_erro = NULL
             WHERE id = ? AND proxima_execucao = ? AND ativo = 1
            """,
            (proxima_seguinte, executado_em, id_agendamento, proxima_anterior),
        )
    return cursor.rowcount > 0


def registrar_resultado_agendamento(
    id_agendamento: str,
    *,
    sucesso: bool,
    erro: str | None = None,
    execucao_id: str | None = None,
) -> None:
    with conectar() as conn:
        conn.execute(
            """
            UPDATE agendamentos
               SET ultimo_erro = ?, execucoes = execucoes + 1,
                   erros = erros + ?, ultima_execucao_id = COALESCE(?, ultima_execucao_id),
                   atualizado_em = ?
             WHERE id = ?
            """,
            (
                None if sucesso else (erro or "Erro desconhecido."),
                int(not sucesso),
                execucao_id,
                agora(),
                id_agendamento,
            ),
        )


def estatisticas() -> dict[str, Any]:
    with conectar() as conn:
        workflows = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        execucoes = conn.execute("SELECT COUNT(*) FROM execucoes").fetchone()[0]
        concluidas = conn.execute(
            "SELECT COUNT(*) FROM execucoes WHERE status = 'concluido'"
        ).fetchone()[0]
        erros = conn.execute(
            "SELECT COUNT(*) FROM execucoes WHERE status = 'erro'"
        ).fetchone()[0]
        credenciais = conn.execute("SELECT COUNT(*) FROM credenciais").fetchone()[0]
        agendamentos = conn.execute("SELECT COUNT(*) FROM agendamentos").fetchone()[0]
        agendamentos_ativos = conn.execute(
            "SELECT COUNT(*) FROM agendamentos WHERE ativo = 1"
        ).fetchone()[0]
        ultimas = conn.execute(
            "SELECT * FROM execucoes ORDER BY inicio DESC LIMIT 6"
        ).fetchall()
    return {
        "workflows": workflows,
        "execucoes": execucoes,
        "concluidas": concluidas,
        "erros": erros,
        "credenciais": credenciais,
        "agendamentos": agendamentos,
        "agendamentos_ativos": agendamentos_ativos,
        "taxa_sucesso": round((concluidas / execucoes) * 100, 1) if execucoes else 0.0,
        "ultimas": [_execucao_da_linha(linha) for linha in ultimas],
    }


def garantir_exemplos() -> None:
    from .exemplos import GRAFOS_EXEMPLO

    with conectar() as conn:
        total = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    if total:
        return
    for exemplo in GRAFOS_EXEMPLO:
        criar_workflow(
            nome=exemplo["nome"],
            descricao=exemplo["descricao"],
            grafo=exemplo["grafo"],
            ativo=True,
        )
