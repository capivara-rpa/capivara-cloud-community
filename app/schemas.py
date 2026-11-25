from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    descricao: str = ""
    grafo: dict[str, Any] = Field(default_factory=dict)
    ativo: bool = True


class WorkflowAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = None
    grafo: dict[str, Any] | None = None
    ativo: bool | None = None


class ExecucaoEntrada(BaseModel):
    entrada: dict[str, Any] = Field(default_factory=dict)


class CredencialEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=80)
    tipo: str = Field(min_length=1, max_length=40)
    dados: dict[str, Any] = Field(default_factory=dict)


class AgendamentoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    workflow_id: str = Field(min_length=1, max_length=80)
    tipo: Literal["intervalo", "diario", "cron"] = "intervalo"
    expressao: str = Field(min_length=1, max_length=120)
    entrada: dict[str, Any] = Field(default_factory=dict)
    ativo: bool = True


class AgendamentoAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: Literal["intervalo", "diario", "cron"] | None = None
    expressao: str | None = Field(default=None, min_length=1, max_length=120)
    entrada: dict[str, Any] | None = None
    ativo: bool | None = None
