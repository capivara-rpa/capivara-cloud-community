from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db
from .config import AGENDADOR_ATIVO, FUSO, INTERVALO_AGENDADOR
from .engine import executar_workflow

logger = logging.getLogger(__name__)

DIAS_SEMANA = {
    "seg": 0,
    "ter": 1,
    "qua": 2,
    "qui": 3,
    "sex": 4,
    "sab": 5,
    "dom": 6,
}

try:
    FUSO_LOCAL = ZoneInfo(FUSO)
except (ZoneInfoNotFoundError, ValueError):
    FUSO_LOCAL = ZoneInfo("UTC")

_parar = threading.Event()
_thread: threading.Thread | None = None


def _intervalo_segundos(expressao: str) -> int:
    encontrado = re.fullmatch(r"(\d+)\s*([smhd]?)", expressao.strip().lower())
    if not encontrado:
        raise ValueError("Use intervalo como 15m, 1h, 30s ou 1d.")
    quantidade = int(encontrado.group(1))
    fator = {"s": 1, "m": 60, "h": 3600, "d": 86400}[encontrado.group(2) or "m"]
    segundos = quantidade * fator
    if segundos < 1:
        raise ValueError("O intervalo deve ser maior que zero.")
    if segundos > 86400 * 365:
        raise ValueError("O intervalo máximo é 365 dias.")
    return segundos


def _hora_diaria(expressao: str) -> time:
    encontrado = re.fullmatch(r"(\d{1,2}):([0-5]\d)", expressao.strip())
    if not encontrado or int(encontrado.group(1)) > 23:
        raise ValueError("Use um horário válido no formato HH:MM.")
    return time(int(encontrado.group(1)), int(encontrado.group(2)))


def _campo_cron(
    valor: str,
    minimo: int,
    maximo: int,
    nomes: dict[str, int] | None = None,
) -> set[int]:
    def numero(texto: str) -> int:
        if nomes and texto.lower() in nomes:
            return nomes[texto.lower()]
        try:
            return int(texto)
        except ValueError as exc:
            raise ValueError(f"Valor inválido no cron: {texto!r}") from exc

    valores: set[int] = set()
    for parte in valor.split(","):
        if parte == "*":
            valores.update(range(minimo, maximo + 1))
            continue
        passo = 1
        if parte.startswith("*/"):
            try:
                passo = int(parte[2:])
            except ValueError as exc:
                raise ValueError(f"Passo inválido no cron: {parte!r}") from exc
            if passo < 1:
                raise ValueError(f"Passo inválido no cron: {parte!r}")
            valores.update(range(minimo, maximo + 1, passo))
            continue
        if "-" in parte:
            inicio_texto, fim_texto = parte.split("-", 1)
            inicio, fim = numero(inicio_texto), numero(fim_texto)
            if inicio > fim:
                raise ValueError(f"Intervalo inválido no cron: {parte!r}")
            valores.update(range(inicio, fim + 1))
            continue
        valores.add(numero(parte))

    if any(valor < minimo or valor > maximo for valor in valores):
        raise ValueError(f"Campo do cron fora do intervalo {minimo}-{maximo}: {valor!r}")
    return valores


def _campos_cron(expressao: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    partes = expressao.split()
    if len(partes) != 5:
        raise ValueError("Cron deve ter 5 campos: minuto hora dia mês dia-da-semana.")
    minutos = _campo_cron(partes[0], 0, 59)
    horas = _campo_cron(partes[1], 0, 23)
    dias = _campo_cron(partes[2], 1, 31)
    meses = _campo_cron(partes[3], 1, 12)
    semana = _campo_cron(partes[4], 0, 7, DIAS_SEMANA)
    semana = {0 if dia == 7 else dia for dia in semana}
    return minutos, horas, dias, meses, semana


def validar_expressao(tipo: str, expressao: str) -> str:
    """Valida a expressão e devolve a forma normalizada."""
    valor = expressao.strip()
    if not valor:
        raise ValueError("Informe a expressão do agendamento.")
    if tipo == "intervalo":
        _intervalo_segundos(valor)
        return valor
    if tipo == "diario":
        _hora_diaria(valor)
        return _hora_diaria(valor).strftime("%H:%M")
    if tipo == "cron":
        _campos_cron(valor)
        return " ".join(valor.split())
    raise ValueError("Tipo de agendamento inválido.")


def _proxima_cron(
    momento: datetime,
    campos: tuple[set[int], set[int], set[int], set[int], set[int]],
) -> datetime:
    minutos, horas, dias, meses, semana = campos
    horarios = sorted(hora * 60 + minuto for hora in horas for minuto in minutos)
    for deslocamento in range(367):
        dia = (momento.date() + timedelta(days=deslocamento))
        if dia.month not in meses or dia.day not in dias or dia.weekday() not in semana:
            continue
        for total in horarios:
            candidato = datetime.combine(
                dia,
                time(total // 60, total % 60),
                tzinfo=FUSO_LOCAL,
            )
            if candidato > momento:
                return candidato
    raise ValueError("Nenhuma data futura encontrada para este cron.")


def proxima_execucao(
    tipo: str,
    expressao: str,
    *,
    agora: datetime | None = None,
) -> str:
    """Calcula a próxima execução e devolve em ISO UTC."""
    momento = agora or datetime.now(UTC)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    if tipo == "intervalo":
        proximo = momento + timedelta(seconds=_intervalo_segundos(expressao))
    else:
        local = momento.astimezone(FUSO_LOCAL)
        if tipo == "diario":
            alvo = datetime.combine(
                local.date(), _hora_diaria(expressao), tzinfo=FUSO_LOCAL
            )
            proximo = alvo if alvo > local else alvo + timedelta(days=1)
        elif tipo == "cron":
            proximo = _proxima_cron(local, _campos_cron(expressao))
        else:
            raise ValueError("Tipo de agendamento inválido.")
    return proximo.astimezone(UTC).isoformat(timespec="seconds")


def executar_agendamento(agendamento: dict[str, Any]) -> dict[str, Any]:
    workflow = db.obter_workflow(agendamento["workflow_id"])
    if not workflow:
        raise ValueError("O fluxo deste agendamento não existe mais.")
    return executar_workflow(
        workflow,
        entrada=agendamento.get("entrada") or {},
        gatilho="agendado",
    )


def verificar_agendamentos() -> dict[str, int]:
    """Dispara agendamentos vencidos, protegendo contra dupla execução."""
    contadores = {"verificados": 0, "executados": 0, "erros": 0}
    devidos = db.listar_agendamentos_devidos(db.agora())
    for agendamento in devidos:
        try:
            proximo = proxima_execucao(agendamento["tipo"], agendamento["expressao"])
        except ValueError as exc:
            db.registrar_resultado_agendamento(
                agendamento["id"], sucesso=False, erro=str(exc)
            )
            contadores["erros"] += 1
            continue

        if not db.reservar_agendamento(
            agendamento["id"],
            agendamento["proxima_execucao"],
            proximo,
            db.agora(),
        ):
            continue
        contadores["verificados"] += 1

        try:
            execucao = executar_agendamento(agendamento)
        except Exception as exc:
            db.registrar_resultado_agendamento(
                agendamento["id"], sucesso=False, erro=str(exc)
            )
            contadores["erros"] += 1
            continue

        erro = execucao.get("erro") if execucao.get("status") == "erro" else None
        db.registrar_resultado_agendamento(
            agendamento["id"],
            sucesso=not erro,
            erro=erro,
            execucao_id=execucao.get("id"),
        )
        if erro:
            contadores["erros"] += 1
        else:
            contadores["executados"] += 1
    return contadores


def _loop() -> None:
    while not _parar.wait(INTERVALO_AGENDADOR):
        try:
            verificar_agendamentos()
        except Exception:
            logger.exception("[agendador] falha ao verificar agendamentos")


def iniciar_agendador() -> None:
    global _parar, _thread
    if not AGENDADOR_ATIVO or (_thread and _thread.is_alive()):
        return
    _parar = threading.Event()
    _thread = threading.Thread(target=_loop, name="capivara-agendador", daemon=True)
    _thread.start()
    logger.info("[agendador] iniciado (a cada %ss, fuso %s)", INTERVALO_AGENDADOR, FUSO)


def parar_agendador() -> None:
    global _thread
    _parar.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=5)
    _thread = None
