from __future__ import annotations

import base64
import contextlib
import email
import hashlib
import imaplib
import json
import mimetypes
import re
import smtplib
import ssl
import time
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from openpyxl import Workbook, load_workbook

from .config import PASTA_SAIDAS
from .db import obter_credencial
from .template import json_ou_texto, obter_caminho, resolver_template, validar_url


def _campo(
    nome: str,
    rotulo: str,
    tipo: str = "text",
    *,
    placeholder: str = "",
    ajuda: str = "",
    opcoes: list[str] | None = None,
    padrao: Any = "",
    obrigatorio: bool = False,
    mostrar_se: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    campo = {
        "nome": nome,
        "rotulo": rotulo,
        "tipo": tipo,
        "placeholder": placeholder,
        "ajuda": ajuda,
        "opcoes": opcoes or [],
        "padrao": padrao,
        "obrigatorio": obrigatorio,
    }
    if mostrar_se:
        campo["mostrar_se"] = mostrar_se
    return campo


CATALOGO: list[dict[str, Any]] = [
    {
        "tipo": "gatilho_manual",
        "nome": "Início manual",
        "categoria": "Gatilhos",
        "icone": "▶",
        "cor": "#1FA463",
        "descricao": "Executa o fluxo quando você clicar em Rodar.",
        "docs": "",
        "entradas": 0,
        "saidas": 1,
        "campos": [],
    },
    {
        "tipo": "gatilho_webhook",
        "nome": "Webhook",
        "categoria": "Gatilhos",
        "icone": "⇥",
        "cor": "#1FA463",
        "descricao": "Recebe um POST em /api/webhooks/{id} com o corpo JSON.",
        "docs": "https://swagger.io/docs/specification/",
        "entradas": 0,
        "saidas": 1,
        "campos": [
            _campo(
                "caminho",
                "Apelido do webhook",
                placeholder="prioridade",
                ajuda="Usado apenas como documentação no MVP.",
            )
        ],
    },
    {
        "tipo": "http",
        "nome": "HTTP Request",
        "categoria": "Ações",
        "icone": "↗",
        "cor": "#1F5FD1",
        "descricao": "Chama qualquer API REST. O canivete suíço da Capivara Cloud.",
        "docs": "https://developer.mozilla.org/pt-BR/docs/Web/HTTP",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "http",
        "modelo_credencial": {
            "tipo": "bearer",
            "token": "seu-token",
        },
        "campos": [
            _campo(
                "metodo",
                "Método",
                "select",
                opcoes=["GET", "POST", "PUT", "PATCH", "DELETE"],
                padrao="GET",
            ),
            _campo(
                "url",
                "URL",
                placeholder="https://api.exemplo.com/v1/clientes",
                obrigatorio=True,
            ),
            _campo(
                "headers",
                "Headers (JSON)",
                "textarea",
                placeholder='{"Accept": "application/json"}',
            ),
            _campo(
                "corpo",
                "Corpo (JSON ou texto)",
                "textarea",
                placeholder='{"nome": "{{ entrada.nome }}"}',
            ),
            _campo(
                "credencial",
                "Credencial",
                "credencial",
                ajuda="Opcional: Bearer, Basic ou API key.",
            ),
            _campo("timeout", "Timeout (s)", "number", padrao=20),
        ],
    },
    {
        "tipo": "email",
        "nome": "E-mail (SMTP/IMAP)",
        "categoria": "Ações",
        "icone": "✉",
        "cor": "#9B6B43",
        "descricao": "Envia, testa, lista e lê e-mails com anexos via SMTP/IMAP.",
        "docs": "https://datatracker.ietf.org/doc/html/rfc5321",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "smtp",
        "modelo_credencial": {
            "host": "smtp.exemplo.com",
            "porta": 587,
            "usuario": "conta@exemplo.com",
            "senha": "sua-senha",
            "remetente": "Capivara Cloud <conta@exemplo.com>",
            "tls": True,
            "imap_host": "imap.exemplo.com",
            "imap_porta": 993,
            "imap_ssl": True,
        },
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=[
                    "enviar",
                    "testar_conexao",
                    "listar",
                    "ler",
                    "baixar_anexos",
                    "mover",
                    "marcar_lido",
                    "marcar_nao_lido",
                ],
                padrao="enviar",
            ),
            _campo("credencial", "Credencial SMTP/IMAP", "credencial", obrigatorio=True),
            _campo(
                "para",
                "Para",
                placeholder="cliente@exemplo.com",
                obrigatorio=True,
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "cc",
                "CC",
                placeholder="copia@exemplo.com",
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "bcc",
                "BCC",
                placeholder="copia-oculta@exemplo.com",
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "assunto",
                "Assunto",
                placeholder="Relatório diário",
                obrigatorio=True,
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "corpo",
                "Corpo",
                "textarea",
                placeholder="Olá, {{ entrada.nome }}!",
                obrigatorio=True,
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "html",
                "Enviar como HTML",
                "select",
                opcoes=["não", "sim"],
                padrao="não",
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "anexos",
                "Anexos (JSON)",
                "textarea",
                placeholder=(
                    '["relatorios/janeiro.pdf", '
                    '{"caminho": "fotos/logo.png", "nome": "logo.png"}]'
                ),
                ajuda="Aceita caminhos dentro de data/output ou objetos com base64.",
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "pasta",
                "Pasta IMAP",
                placeholder="INBOX",
                padrao="INBOX",
                mostrar_se={
                    "acao": [
                        "listar",
                        "ler",
                        "baixar_anexos",
                        "mover",
                        "marcar_lido",
                        "marcar_nao_lido",
                    ]
                },
            ),
            _campo(
                "limite",
                "Limite de mensagens",
                "number",
                padrao=10,
                mostrar_se={"acao": ["listar"]},
            ),
            _campo(
                "uid",
                "UID da mensagem",
                placeholder="123",
                obrigatorio=True,
                mostrar_se={
                    "acao": [
                        "ler",
                        "baixar_anexos",
                        "mover",
                        "marcar_lido",
                        "marcar_nao_lido",
                    ]
                },
            ),
            _campo(
                "destino",
                "Pasta de destino",
                placeholder="Arquivados",
                obrigatorio=True,
                mostrar_se={"acao": ["mover"]},
            ),
            _campo(
                "marcar_lido",
                "Marcar como lido após baixar",
                "checkbox",
                padrao=False,
                mostrar_se={"acao": ["baixar_anexos"]},
            ),
        ],
    },
    {
        "tipo": "excel",
        "nome": "Excel",
        "categoria": "Ações",
        "icone": "▦",
        "cor": "#168A52",
        "descricao": "Cria ou lê planilhas .xlsx no armazenamento local.",
        "docs": "https://openpyxl.readthedocs.io/",
        "entradas": 1,
        "saidas": 1,
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=["criar", "ler"],
                padrao="criar",
            ),
            _campo(
                "caminho",
                "Arquivo",
                placeholder="relatorios/clientes.xlsx",
                obrigatorio=True,
            ),
            _campo("aba", "Aba", placeholder="Planilha1"),
            _campo(
                "dados",
                "Dados (JSON)",
                "textarea",
                placeholder='[{"nome": "Ana", "cidade": "São Paulo"}]',
                ajuda="Para criar: lista de objetos. Para ler: deixe vazio.",
            ),
        ],
    },
    {
        "tipo": "slack",
        "nome": "Slack",
        "categoria": "Ações",
        "icone": "#",
        "cor": "#4A154B",
        "descricao": "Mensagem via Incoming Webhook ou chat.postMessage.",
        "docs": "https://api.slack.com/specs",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "slack",
        "modelo_credencial": {
            "webhook_url": "https://hooks.slack.com/services/...",
        },
        "campos": [
            _campo("credencial", "Credencial Slack", "credencial"),
            _campo("webhook_url", "Webhook URL", placeholder="https://hooks.slack.com/..."),
            _campo("canal", "Canal", placeholder="#automacoes"),
            _campo("texto", "Texto", "textarea", placeholder="Deu bom: {{ entrada.nome }}"),
        ],
    },
    {
        "tipo": "teams",
        "nome": "Microsoft Teams",
        "categoria": "Ações",
        "icone": "T",
        "cor": "#5B5FC7",
        "descricao": "Envia mensagem para um canal via Incoming Webhook.",
        "docs": "https://learn.microsoft.com/graph/api/channel-post-messages",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "teams",
        "modelo_credencial": {
            "webhook_url": "https://...webhook.office.com/webhookb2/...",
        },
        "campos": [
            _campo("credencial", "Credencial Teams", "credencial"),
            _campo("webhook_url", "Webhook URL"),
            _campo("titulo", "Título", placeholder="Capivara Cloud"),
            _campo("texto", "Texto", "textarea", placeholder="Novo pedido: {{ entrada.id }}"),
        ],
    },
    {
        "tipo": "google_sheets",
        "nome": "Google Sheets",
        "categoria": "Ações",
        "icone": "G",
        "cor": "#0F9D58",
        "descricao": "Lê ou adiciona linhas em uma planilha via API v4.",
        "docs": "https://developers.google.com/sheets/api/reference/rest",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "google",
        "modelo_credencial": {
            "service_account_json": (
                '{"type":"service_account","project_id":"...",'
                '"client_email":"...","private_key":"..."}'
            ),
        },
        "campos": [
            _campo("credencial", "Conta de serviço", "credencial", obrigatorio=True),
            _campo("spreadsheet_id", "Spreadsheet ID", obrigatorio=True),
            _campo("range", "Range", placeholder="Página1!A1", obrigatorio=True),
            _campo("acao", "Ação", "select", opcoes=["append", "read"], padrao="append"),
            _campo(
                "valores",
                "Valores (JSON)",
                "textarea",
                placeholder='[["Ana", "SP"]] ou [{"nome":"Ana","uf":"SP"}]',
            ),
        ],
    },
    {
        "tipo": "telegram",
        "nome": "Telegram",
        "categoria": "Ações",
        "icone": "➤",
        "cor": "#229ED9",
        "descricao": "Envia mensagem via Bot API.",
        "docs": "https://core.telegram.org/bots/api",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "telegram",
        "modelo_credencial": {"bot_token": "123456:ABC..."},
        "campos": [
            _campo("credencial", "Credencial Telegram", "credencial", obrigatorio=True),
            _campo("chat_id", "Chat ID", obrigatorio=True),
            _campo("texto", "Texto", "textarea", obrigatorio=True),
        ],
    },
    {
        "tipo": "discord",
        "nome": "Discord",
        "categoria": "Ações",
        "icone": "◉",
        "cor": "#5865F2",
        "descricao": "Mensagem via webhook de canal.",
        "docs": "https://discord.com/developers/docs/resources/webhook",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "discord",
        "modelo_credencial": {"webhook_url": "https://discord.com/api/webhooks/..."},
        "campos": [
            _campo("credencial", "Credencial Discord", "credencial"),
            _campo("webhook_url", "Webhook URL"),
            _campo("conteudo", "Conteúdo", "textarea", obrigatorio=True),
        ],
    },
    {
        "tipo": "notion",
        "nome": "Notion",
        "categoria": "Ações",
        "icone": "N",
        "cor": "#111111",
        "descricao": "Cria uma página em um database do Notion.",
        "docs": "https://developers.notion.com/reference",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "notion",
        "modelo_credencial": {"token": "secret_..."},
        "campos": [
            _campo("credencial", "Credencial Notion", "credencial", obrigatorio=True),
            _campo("database_id", "Database ID", obrigatorio=True),
            _campo(
                "propriedades",
                "Propriedades (JSON)",
                "textarea",
                placeholder='{"Nome": {"title": [{"text": {"content": "{{ entrada.nome }}"}}]}}',
            ),
        ],
    },
    {
        "tipo": "airtable",
        "nome": "Airtable",
        "categoria": "Ações",
        "icone": "A",
        "cor": "#FCB400",
        "descricao": "Cria um registro em uma tabela.",
        "docs": "https://airtable.com/developers/web/api/introduction",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "airtable",
        "modelo_credencial": {"token": "pat..."},
        "campos": [
            _campo("credencial", "Credencial Airtable", "credencial", obrigatorio=True),
            _campo("base_id", "Base ID", obrigatorio=True),
            _campo("tabela", "Tabela", obrigatorio=True),
            _campo("campos", "Campos (JSON)", "textarea", obrigatorio=True),
        ],
    },
    {
        "tipo": "github",
        "nome": "GitHub",
        "categoria": "Ações",
        "icone": "⌂",
        "cor": "#24292F",
        "descricao": "Abre uma issue em um repositório.",
        "docs": "https://docs.github.com/en/rest",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "github",
        "modelo_credencial": {"token": "ghp_..."},
        "campos": [
            _campo("credencial", "Credencial GitHub", "credencial", obrigatorio=True),
            _campo("repo", "Repositório", placeholder="capivara-rpa/capivara", obrigatorio=True),
            _campo("titulo", "Título", obrigatorio=True),
            _campo("corpo", "Corpo", "textarea"),
            _campo("labels", "Labels (JSON)", "textarea", placeholder='["automacao"]'),
        ],
    },
    {
        "tipo": "stripe",
        "nome": "Stripe",
        "categoria": "Ações",
        "icone": "S",
        "cor": "#635BFF",
        "descricao": "Cria um PaymentIntent.",
        "docs": "https://stripe.com/docs/api",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "stripe",
        "modelo_credencial": {"secret_key": "sk_test_..."},
        "campos": [
            _campo("credencial", "Credencial Stripe", "credencial", obrigatorio=True),
            _campo("valor", "Valor em centavos", "number", padrao=1000, obrigatorio=True),
            _campo("moeda", "Moeda", placeholder="brl", padrao="brl"),
            _campo("descricao", "Descrição"),
            _campo("email", "E-mail do cliente"),
        ],
    },
    {
        "tipo": "openai",
        "nome": "OpenAI",
        "categoria": "Ações",
        "icone": "✳",
        "cor": "#10A37F",
        "descricao": "Gera texto com Chat Completions.",
        "docs": "https://platform.openai.com/docs/api-reference",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "openai",
        "modelo_credencial": {"api_key": "sk-..."},
        "campos": [
            _campo("credencial", "Credencial OpenAI", "credencial", obrigatorio=True),
            _campo("modelo", "Modelo", placeholder="gpt-4o-mini", padrao="gpt-4o-mini"),
            _campo("system", "System prompt", "textarea"),
            _campo("prompt", "Prompt", "textarea", obrigatorio=True),
        ],
    },
    {
        "tipo": "whatsapp",
        "nome": "WhatsApp Cloud",
        "categoria": "Ações",
        "icone": "W",
        "cor": "#25D366",
        "descricao": "Envia texto pela WhatsApp Cloud API (Meta).",
        "docs": "https://developers.facebook.com/docs/whatsapp/cloud-api/reference",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "whatsapp",
        "modelo_credencial": {"token": "EAAG...", "phone_number_id": "1234567890"},
        "campos": [
            _campo("credencial", "Credencial WhatsApp", "credencial", obrigatorio=True),
            _campo("phone_number_id", "Phone Number ID"),
            _campo("para", "Para", placeholder="5511999999999", obrigatorio=True),
            _campo("texto", "Texto", "textarea", obrigatorio=True),
        ],
    },
    {
        "tipo": "condicao",
        "nome": "Condição",
        "categoria": "Lógica",
        "icone": "◇",
        "cor": "#FFD84D",
        "descricao": "Dois caminhos: verdadeiro (saída 1) ou falso (saída 2).",
        "docs": "",
        "entradas": 1,
        "saidas": 2,
        "campos": [
            _campo("campo", "Campo", placeholder="{{ entrada.prioridade }}", obrigatorio=True),
            _campo(
                "operador",
                "Operador",
                "select",
                opcoes=["==", "!=", ">", "<", ">=", "<=", "contem", "vazio", "nao_vazio"],
                padrao="==",
            ),
            _campo("valor", "Valor", placeholder="alta"),
        ],
    },
    {
        "tipo": "json",
        "nome": "JSON",
        "categoria": "Lógica",
        "icone": "{ }",
        "cor": "#1F5FD1",
        "descricao": "Extrai um caminho, faz parse ou stringify.",
        "docs": "https://www.json.org/json-pt.html",
        "entradas": 1,
        "saidas": 1,
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=["extrair", "parse", "stringify"],
                padrao="extrair",
            ),
            _campo("texto", "Entrada", "textarea", placeholder="{{ passos.2.json }}"),
            _campo("caminho", "Caminho", placeholder="data.clientes.0.nome"),
        ],
    },
    {
        "tipo": "espera",
        "nome": "Espera",
        "categoria": "Lógica",
        "icone": "◷",
        "cor": "#9B6B43",
        "descricao": "Pausa o fluxo por alguns segundos (máximo 30 no MVP).",
        "docs": "",
        "entradas": 1,
        "saidas": 1,
        "campos": [_campo("segundos", "Segundos", "number", padrao=2)],
    },
    {
        "tipo": "log",
        "nome": "Log",
        "categoria": "Lógica",
        "icone": "≡",
        "cor": "#6B6357",
        "descricao": "Registra uma mensagem no trace da execução.",
        "docs": "",
        "entradas": 1,
        "saidas": 1,
        "campos": [
            _campo(
                "mensagem",
                "Mensagem",
                "textarea",
                placeholder="Processado: {{ entrada.nome }}",
                obrigatorio=True,
            )
        ],
    },
    {
        "tipo": "fim",
        "nome": "Fim",
        "categoria": "Lógica",
        "icone": "■",
        "cor": "#6B6357",
        "descricao": "Encerra o fluxo com sucesso.",
        "docs": "",
        "entradas": 1,
        "saidas": 0,
        "campos": [],
    },
    {
        "tipo": "microsoft_graph_email",
        "nome": "Outlook — enviar e-mail",
        "categoria": "Ações",
        "icone": "✉",
        "cor": "#0078D4",
        "descricao": "Envia e-mail pelo Microsoft Graph com anexos e HTML.",
        "docs": "https://learn.microsoft.com/graph/api/user-sendmail",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "microsoft_graph",
        "modelo_credencial": {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "segredo",
            "usuario": "automacao@empresa.com",
        },
        "campos": [
            _campo("credencial", "Credencial Microsoft 365", "credencial", obrigatorio=True),
            _campo(
                "usuario",
                "Usuário remetente",
                placeholder="automacao@empresa.com",
                ajuda="Opcional: sobrescreve o usuário da credencial.",
            ),
            _campo("para", "Para", placeholder="cliente@empresa.com", obrigatorio=True),
            _campo("cc", "CC", placeholder="copia@empresa.com"),
            _campo("bcc", "BCC", placeholder="copia-oculta@empresa.com"),
            _campo("assunto", "Assunto", placeholder="Relatório diário", obrigatorio=True),
            _campo("corpo", "Corpo", "textarea", obrigatorio=True),
            _campo("html", "Enviar como HTML", "select", opcoes=["não", "sim"], padrao="não"),
            _campo(
                "anexos",
                "Anexos (JSON)",
                "textarea",
                placeholder='["relatorios/janeiro.pdf", {"base64": "...", "nome": "logo.png"}]',
                ajuda="Aceita caminhos em data/output ou objetos com base64.",
            ),
        ],
    },
    {
        "tipo": "microsoft_graph_teams",
        "nome": "Teams — mensagem em canal",
        "categoria": "Ações",
        "icone": "T",
        "cor": "#6264A7",
        "descricao": "Publica uma mensagem em um canal do Teams via Microsoft Graph.",
        "docs": "https://learn.microsoft.com/graph/api/channel-post-messages",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "microsoft_graph",
        "modelo_credencial": {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "segredo",
            "usuario": "automacao@empresa.com",
        },
        "campos": [
            _campo("credencial", "Credencial Microsoft 365", "credencial", obrigatorio=True),
            _campo("team_id", "ID do time", obrigatorio=True),
            _campo("channel_id", "ID do canal", obrigatorio=True),
            _campo("texto", "Mensagem", "textarea", obrigatorio=True),
            _campo("html", "Enviar como HTML", "select", opcoes=["não", "sim"], padrao="não"),
        ],
    },
    {
        "tipo": "microsoft_graph_calendar",
        "nome": "Outlook — criar evento",
        "categoria": "Ações",
        "icone": "◷",
        "cor": "#0078D4",
        "descricao": "Cria um evento no calendário do Outlook via Microsoft Graph.",
        "docs": "https://learn.microsoft.com/graph/api/user-post-events",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "microsoft_graph",
        "modelo_credencial": {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "segredo",
            "usuario": "automacao@empresa.com",
        },
        "campos": [
            _campo("credencial", "Credencial Microsoft 365", "credencial", obrigatorio=True),
            _campo(
                "usuario",
                "Usuário",
                placeholder="automacao@empresa.com",
                ajuda="Opcional: sobrescreve o usuário da credencial.",
            ),
            _campo("assunto", "Assunto", obrigatorio=True),
            _campo("inicio", "Início", placeholder="2026-11-20T09:00:00", obrigatorio=True),
            _campo("fim", "Fim", placeholder="2026-11-20T10:00:00", obrigatorio=True),
            _campo("timezone", "Fuso horário", padrao="America/Sao_Paulo"),
            _campo("participantes", "Participantes", placeholder="a@empresa.com, b@empresa.com"),
            _campo("local", "Local", placeholder="Sala virtual"),
            _campo("corpo", "Descrição", "textarea"),
            _campo("html", "Descrição em HTML", "select", opcoes=["não", "sim"], padrao="não"),
        ],
    },
    {
        "tipo": "microsoft_graph_excel",
        "nome": "Excel Online — ler/escrever",
        "categoria": "Ações",
        "icone": "▦",
        "cor": "#217346",
        "descricao": "Lê, escreve ou adiciona linhas em uma pasta do Excel no OneDrive.",
        "docs": "https://learn.microsoft.com/graph/api/resources/excel",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "microsoft_graph",
        "modelo_credencial": {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "segredo",
            "usuario": "automacao@empresa.com",
        },
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=["ler", "escrever", "adicionar"],
                padrao="ler",
            ),
            _campo("credencial", "Credencial Microsoft 365", "credencial", obrigatorio=True),
            _campo(
                "usuario",
                "Usuário",
                placeholder="automacao@empresa.com",
                ajuda="Opcional: sobrescreve o usuário da credencial.",
            ),
            _campo(
                "item_id",
                "Item ID",
                placeholder="01ABCDEF...",
                ajuda="Alternativa ao caminho do arquivo no OneDrive.",
            ),
            _campo(
                "caminho",
                "Arquivo no OneDrive",
                placeholder="Relatórios/clientes.xlsx",
                mostrar_se={"acao": ["ler", "escrever", "adicionar"]},
            ),
            _campo("aba", "Aba", placeholder="Sheet1"),
            _campo(
                "range",
                "Range",
                placeholder="A1:D20",
                obrigatorio=True,
                mostrar_se={"acao": ["ler", "escrever"]},
            ),
            _campo(
                "valores",
                "Valores (JSON)",
                "textarea",
                placeholder='[["Ana", "SP"], ["Bia", "RJ"]]',
                mostrar_se={"acao": ["escrever", "adicionar"]},
            ),
        ],
    },
    {
        "tipo": "microsoft_graph_onedrive",
        "nome": "OneDrive — arquivos",
        "categoria": "Ações",
        "icone": "☁",
        "cor": "#0078D4",
        "descricao": "Lista, envia e baixa arquivos do OneDrive via Microsoft Graph.",
        "docs": "https://learn.microsoft.com/graph/api/resources/onedrive",
        "entradas": 1,
        "saidas": 1,
        "credencial_tipo": "microsoft_graph",
        "modelo_credencial": {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "segredo",
            "usuario": "automacao@empresa.com",
        },
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=["listar", "enviar", "baixar"],
                padrao="listar",
            ),
            _campo("credencial", "Credencial Microsoft 365", "credencial", obrigatorio=True),
            _campo(
                "usuario",
                "Usuário",
                placeholder="automacao@empresa.com",
                ajuda="Opcional: sobrescreve o usuário da credencial.",
            ),
            _campo(
                "caminho",
                "Caminho no OneDrive",
                placeholder="Relatórios",
                ajuda="Para listar, use uma pasta; para enviar/baixar, inclua o arquivo.",
            ),
            _campo(
                "conteudo",
                "Conteúdo (texto)",
                "textarea",
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "base64",
                "Conteúdo (base64)",
                "textarea",
                mostrar_se={"acao": ["enviar"]},
            ),
            _campo(
                "arquivo",
                "Arquivo local",
                placeholder="relatorios/clientes.xlsx",
                ajuda="Caminho dentro de data/output.",
                mostrar_se={"acao": ["enviar"]},
            ),
        ],
    },
    {
        "tipo": "variavel",
        "nome": "Variável",
        "categoria": "Lógica",
        "icone": "𝑥",
        "cor": "#1F5FD1",
        "descricao": "Define, consulta ou remove variáveis do fluxo.",
        "docs": "",
        "entradas": 1,
        "saidas": 1,
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=["definir", "obter", "remover", "listar"],
                padrao="definir",
            ),
            _campo(
                "nome",
                "Nome da variável",
                placeholder="cliente",
                obrigatorio=True,
                mostrar_se={"acao": ["definir", "obter", "remover"]},
            ),
            _campo(
                "valor",
                "Valor",
                "textarea",
                placeholder="{{ entrada.nome }}",
                mostrar_se={"acao": ["definir"]},
            ),
        ],
    },
    {
        "tipo": "transformar",
        "nome": "Transformar",
        "categoria": "Lógica",
        "icone": "ƒ",
        "cor": "#1F5FD1",
        "descricao": "Texto, listas, datas, números, JSON, base64 e hash em um só bloco.",
        "docs": "https://docs.python.org/3/library/stdtypes.html",
        "entradas": 1,
        "saidas": 1,
        "campos": [
            _campo(
                "acao",
                "Ação",
                "select",
                opcoes=[
                    "texto_limpar",
                    "texto_acentos",
                    "texto_maiusculo",
                    "texto_minusculo",
                    "texto_titulo",
                    "texto_slug",
                    "texto_substituir",
                    "texto_regex",
                    "texto_dividir",
                    "texto_juntar",
                    "texto_truncar",
                    "lista_filtrar",
                    "lista_mapear",
                    "lista_ordenar",
                    "lista_agrupar",
                    "lista_somar",
                    "lista_contar",
                    "lista_distintos",
                    "lista_primeiro",
                    "lista_ultimo",
                    "data_agora",
                    "data_formatar",
                    "data_adicionar",
                    "data_diferenca",
                    "numero_arredondar",
                    "numero_formatar",
                    "json_parse",
                    "json_stringify",
                    "json_extrair",
                    "base64_codificar",
                    "base64_decodificar",
                    "hash_sha256",
                    "uuid",
                    "converter_texto",
                    "converter_numero",
                    "converter_booleano",
                ],
                padrao="texto_limpar",
            ),
            _campo(
                "entrada",
                "Entrada",
                "textarea",
                placeholder="{{ passos.2.json }}",
                ajuda="Aceita texto, JSON, listas ou o resultado de um passo anterior.",
            ),
            _campo(
                "valor",
                "Valor / parâmetro",
                placeholder="novo, alta, asc",
                mostrar_se={
                    "acao": [
                        "texto_substituir",
                        "texto_regex",
                        "lista_filtrar",
                        "lista_ordenar",
                        "data_diferenca",
                    ]
                },
            ),
            _campo(
                "valor2",
                "Substituir por",
                mostrar_se={"acao": ["texto_substituir"]},
            ),
            _campo(
                "separador",
                "Separador",
                placeholder=",",
                mostrar_se={"acao": ["texto_dividir", "texto_juntar"]},
            ),
            _campo(
                "formato",
                "Formato",
                placeholder="%d/%m/%Y",
                ajuda="Use formato de data (strftime) ou quantidade de casas.",
                mostrar_se={"acao": ["data_agora", "data_formatar", "numero_formatar"]},
            ),
            _campo(
                "caminho",
                "Caminho do campo",
                placeholder="nome",
                ajuda="Para listas de objetos e JSON.",
                mostrar_se={
                    "acao": [
                        "lista_filtrar",
                        "lista_mapear",
                        "lista_ordenar",
                        "lista_agrupar",
                        "lista_somar",
                        "lista_distintos",
                        "lista_primeiro",
                        "lista_ultimo",
                        "json_extrair",
                    ]
                },
            ),
            _campo(
                "operador",
                "Operador",
                "select",
                opcoes=["==", "!=", "contem", ">", "<", ">=", "<=", "vazio", "nao_vazio"],
                padrao="==",
                mostrar_se={"acao": ["lista_filtrar"]},
            ),
            _campo(
                "quantidade",
                "Quantidade",
                "number",
                padrao=2,
                mostrar_se={
                    "acao": [
                        "texto_truncar",
                        "data_adicionar",
                        "numero_arredondar",
                        "numero_formatar",
                    ]
                },
            ),
            _campo(
                "unidade",
                "Unidade",
                "select",
                opcoes=["dias", "horas", "minutos", "segundos"],
                padrao="dias",
                mostrar_se={"acao": ["data_adicionar"]},
            ),
            _campo(
                "ignorar_caso",
                "Ignorar maiúsculas/minúsculas",
                "checkbox",
                padrao=True,
                mostrar_se={"acao": ["texto_regex"]},
            ),
        ],
    },
]

CONJUNTOS = {
    "gatilho_manual": "Gatilhos",
    "gatilho_webhook": "Gatilhos",
    "http": "Web",
    "email": "E-mail",
    "excel": "Dados",
    "slack": "Comunicação",
    "teams": "Microsoft 365",
    "telegram": "Comunicação",
    "discord": "Comunicação",
    "whatsapp": "Comunicação",
    "google_sheets": "Google Workspace",
    "notion": "Integrações",
    "airtable": "Integrações",
    "github": "Integrações",
    "stripe": "Integrações",
    "openai": "Integrações",
    "condicao": "Lógica",
    "json": "Dados",
    "espera": "Lógica",
    "log": "Lógica",
    "fim": "Lógica",
    "microsoft_graph_email": "Microsoft 365",
    "microsoft_graph_teams": "Microsoft 365",
    "microsoft_graph_calendar": "Microsoft 365",
    "microsoft_graph_excel": "Microsoft 365",
    "microsoft_graph_onedrive": "Microsoft 365",
    "variavel": "Variáveis",
    "transformar": "Variáveis",
}

LOGOS = {
    "gatilho_manual": "play",
    "gatilho_webhook": "webhook",
    "http": "httpie",
    "email": "email",
    "excel": "microsoftexcel",
    "slack": "slack",
    "teams": "microsoftteams",
    "telegram": "telegram",
    "discord": "discord",
    "whatsapp": "whatsapp",
    "google_sheets": "googlesheets",
    "notion": "notion",
    "airtable": "airtable",
    "github": "github",
    "stripe": "stripe",
    "openai": "openai",
    "condicao": "condicao",
    "json": "json",
    "espera": "clock",
    "log": "log",
    "fim": "stop",
    "microsoft_graph_email": "microsoftoutlook",
    "microsoft_graph_teams": "microsoftteams",
    "microsoft_graph_calendar": "microsoftoutlook",
    "microsoft_graph_excel": "microsoftexcel",
    "microsoft_graph_onedrive": "microsoftonedrive",
    "variavel": "variavel",
    "transformar": "transformar",
}

CONJUNTOS_ORDEM = [
    "Todos",
    "Gatilhos",
    "Microsoft 365",
    "E-mail",
    "Comunicação",
    "Google Workspace",
    "Dados",
    "Integrações",
    "Web",
    "Lógica",
    "Variáveis",
]

for _item in CATALOGO:
    _item.setdefault("conjunto", CONJUNTOS.get(_item["tipo"], _item.get("categoria", "Ações")))
    _item.setdefault("logo", f"/static/img/logos/{LOGOS.get(_item['tipo'], 'generico')}.svg")

CATALOGO_POR_TIPO = {item["tipo"]: item for item in CATALOGO}


def _credencial(nome: str | None) -> dict[str, Any]:
    if not nome:
        return {}
    registro = obter_credencial(nome, mascarar_dados=False)
    if not registro:
        raise ValueError(f"Credencial '{nome}' não encontrada.")
    return registro.get("dados", {})


def _timeout(config: dict[str, Any]) -> float:
    try:
        return max(1.0, min(float(config.get("timeout") or 20), 60.0))
    except (TypeError, ValueError):
        return 20.0


def _http(config: dict[str, Any]) -> dict[str, Any]:
    url = str(config.get("url") or "").strip()
    if not url:
        raise ValueError("Informe a URL da requisição.")
    validar_url(url)
    metodo = str(config.get("metodo") or "GET").upper()
    headers = json_ou_texto(config.get("headers"), {}) or {}
    if not isinstance(headers, dict):
        raise ValueError("Headers precisam ser um objeto JSON.")
    corpo = json_ou_texto(config.get("corpo"), None)
    cred = _credencial(config.get("credencial"))
    auth = None
    if cred:
        tipo = str(cred.get("tipo") or "bearer").lower()
        if tipo == "basic":
            auth = (str(cred.get("usuario", "")), str(cred.get("senha", "")))
        elif tipo == "api_key":
            headers[str(cred.get("nome") or "X-API-Key")] = str(cred.get("valor", ""))
        elif cred.get("token"):
            headers.setdefault("Authorization", f"Bearer {cred['token']}")
    kwargs: dict[str, Any] = {
        "method": metodo,
        "url": url,
        "headers": headers,
        "timeout": _timeout(config),
        "follow_redirects": True,
    }
    if auth:
        kwargs["auth"] = auth
    if corpo not in (None, "") and metodo not in {"GET", "HEAD"}:
        if isinstance(corpo, (dict, list)):
            kwargs["json"] = corpo
        else:
            kwargs["content"] = str(corpo)
    with httpx.Client() as cliente:
        resposta = cliente.request(**kwargs)
    texto = resposta.text[:20000]
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    if resposta.status_code >= 400:
        raise ValueError(f"HTTP {resposta.status_code}: {texto[:800]}")
    return {
        "status": resposta.status_code,
        "content_type": resposta.headers.get("content-type", ""),
        "json": dados,
        "texto": texto,
    }


def _como_lista(valor: Any) -> list[Any]:
    if valor is None or valor == "":
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.startswith("["):
            try:
                dados = json.loads(texto)
                if isinstance(dados, list):
                    return dados
            except json.JSONDecodeError:
                pass
        return [parte.strip() for parte in re.split(r"[;,]", texto) if parte.strip()]
    return [valor]


def _enderecos(valor: Any) -> list[str]:
    return [str(item).strip() for item in _como_lista(valor) if str(item).strip()]


def _booleano(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in {"1", "true", "sim", "yes", "s"}


def _nome_seguro(nome: str) -> str:
    limpo = Path(str(nome or "anexo")).name
    limpo = re.sub(r"[^A-Za-z0-9._-]+", "_", limpo).strip("._")
    return limpo or "anexo"


def _anexo_bytes(item: Any) -> tuple[str, str, bytes]:
    if isinstance(item, str):
        texto = item.strip()
        if texto.startswith("data:"):
            cabecalho, _, dados = texto.partition(",")
            mime = cabecalho[5:].split(";")[0] or "application/octet-stream"
            return "anexo", mime, base64.b64decode(dados)
        caminho = _caminho_seguro(texto)
        if not caminho.exists() or not caminho.is_file():
            raise ValueError(f"Anexo não encontrado: {texto}")
        mime = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
        return caminho.name, mime, caminho.read_bytes()
    if isinstance(item, dict):
        nome = str(item.get("nome") or "anexo")
        if item.get("base64"):
            mime = str(
                item.get("mime")
                or mimetypes.guess_type(nome)[0]
                or "application/octet-stream"
            )
            return nome, mime, base64.b64decode(str(item["base64"]))
        caminho_bruto = item.get("caminho") or item.get("arquivo")
        if caminho_bruto:
            caminho = _caminho_seguro(str(caminho_bruto))
            if not caminho.exists() or not caminho.is_file():
                raise ValueError(f"Anexo não encontrado: {caminho_bruto}")
            mime = str(
                item.get("mime")
                or mimetypes.guess_type(caminho.name)[0]
                or "application/octet-stream"
            )
            return str(item.get("nome") or caminho.name), mime, caminho.read_bytes()
    raise ValueError(
        "Anexo inválido. Use caminho em data/output ou objeto com base64."
    )


def _email_credencial(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    if not cred:
        raise ValueError("Selecione uma credencial de e-mail.")
    return cred


def _smtp_conectar(cred: dict[str, Any]) -> smtplib.SMTP:
    host = str(cred.get("host") or "")
    porta = int(cred.get("porta") or 587)
    usuario = str(cred.get("usuario") or "")
    senha = str(cred.get("senha") or "")
    if not host or not usuario:
        raise ValueError("Credencial de e-mail precisa de host e usuário.")
    contexto = ssl.create_default_context()
    if porta == 465 or cred.get("ssl"):
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, porta, context=contexto, timeout=20)
    else:
        smtp = smtplib.SMTP(host, porta, timeout=20)
        if cred.get("tls", True):
            smtp.starttls(context=contexto)
    smtp.login(usuario, senha)
    return smtp


def _email_enviar(config: dict[str, Any]) -> dict[str, Any]:
    cred = _email_credencial(config)
    usuario = str(cred.get("usuario") or "")
    remetente = str(cred.get("remetente") or usuario)
    para = _enderecos(config.get("para"))
    if not para:
        raise ValueError("Informe ao menos um destinatário.")
    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = ", ".join(para)
    if _enderecos(config.get("cc")):
        mensagem["Cc"] = ", ".join(_enderecos(config.get("cc")))
    if _enderecos(config.get("bcc")):
        mensagem["Bcc"] = ", ".join(_enderecos(config.get("bcc")))
    mensagem["Subject"] = str(config.get("assunto") or "")
    corpo = str(config.get("corpo") or "")
    if _booleano(config.get("html")):
        mensagem.set_content("Seu cliente de e-mail não suporta HTML.")
        mensagem.add_alternative(corpo, subtype="html")
    else:
        mensagem.set_content(corpo)
    anexos = []
    for item in _como_lista(config.get("anexos")):
        nome, mime, dados = _anexo_bytes(item)
        maintype, _, subtype = mime.partition("/")
        mensagem.add_attachment(
            dados,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=nome,
        )
        anexos.append(nome)
    with _smtp_conectar(cred) as smtp:
        smtp.send_message(mensagem)
    return {
        "enviado": True,
        "para": para,
        "assunto": mensagem["Subject"],
        "anexos": anexos,
    }


def _email_testar(config: dict[str, Any]) -> dict[str, Any]:
    cred = _email_credencial(config)
    resultado: dict[str, Any] = {"smtp": {"ok": False}, "imap": {"ok": False}}
    try:
        with _smtp_conectar(cred) as smtp:
            codigo, mensagem = smtp.noop()
        resultado["smtp"] = {"ok": codigo == 250, "codigo": codigo, "resposta": str(mensagem)}
    except Exception as exc:  # noqa: BLE001 - o teste precisa reportar o erro
        resultado["smtp"] = {"ok": False, "erro": str(exc)}
    try:
        imap = _imap_conectar(cred)
        try:
            status, _ = imap.noop()
            resultado["imap"] = {"ok": status == "OK"}
        finally:
            imap.logout()
    except Exception as exc:  # noqa: BLE001 - o teste precisa reportar o erro
        resultado["imap"] = {"ok": False, "erro": str(exc)}
    return resultado


def _imap_conectar(cred: dict[str, Any]) -> imaplib.IMAP4:
    host = str(cred.get("imap_host") or cred.get("host") or "")
    usuario = str(cred.get("usuario") or "")
    senha = str(cred.get("senha") or "")
    if not host or not usuario:
        raise ValueError("Credencial de e-mail precisa de imap_host, usuário e senha.")
    porta = int(cred.get("imap_porta") or 993)
    try:
        if _booleano(cred.get("imap_ssl", True)):
            imap: imaplib.IMAP4 = imaplib.IMAP4_SSL(host, porta, timeout=20)
        else:
            imap = imaplib.IMAP4(host, porta, timeout=20)
            imap.starttls()
        imap.login(usuario, senha)
    except Exception as exc:
        raise ValueError(f"Falha ao conectar no IMAP: {exc}") from exc
    return imap


def _imap_pasta(imap: imaplib.IMAP4, pasta: Any, readonly: bool = True) -> str:
    nome = str(pasta or "INBOX")
    status, _ = imap.select(nome, readonly=readonly)
    if status != "OK":
        raise ValueError(f"Não foi possível abrir a pasta IMAP '{nome}'.")
    return nome


def _imap_uids(imap: imaplib.IMAP4, limite: int) -> list[int]:
    status, dados = imap.uid("search", None, "ALL")
    if status != "OK":
        raise ValueError("Falha ao pesquisar mensagens no IMAP.")
    uids = sorted(
        {int(parte) for parte in (dados[0] or b"").split() if parte.isdigit()},
        reverse=True,
    )
    return uids[:limite]


def _imap_mensagem(imap: imaplib.IMAP4, uid: Any) -> email.message.Message:
    status, dados = imap.uid("fetch", str(uid), "(RFC822)")
    if status != "OK":
        raise ValueError(f"Mensagem UID {uid} não encontrada.")
    bruto = None
    for item in dados or []:
        if isinstance(item, tuple) and len(item) > 1:
            bruto = item[1]
            break
    if not bruto:
        raise ValueError(f"Mensagem UID {uid} sem conteúdo.")
    return email.message_from_bytes(bruto, policy=policy.default)


def _cabecalho(msg: email.message.Message, nome: str) -> str:
    valor = msg.get(nome, "")
    try:
        return str(make_header(decode_header(str(valor))))
    except Exception:  # noqa: BLE001 - cabeçalho malformado não deve quebrar o fluxo
        return str(valor)


def _corpo_email(msg: email.message.Message) -> dict[str, str]:
    textos: list[str] = []
    htmls: list[str] = []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        disposicao = str(parte.get("Content-Disposition") or "").lower()
        if "attachment" in disposicao:
            continue
        tipo = parte.get_content_type()
        try:
            conteudo = parte.get_content()
        except Exception:  # noqa: BLE001 - fallback para payload bruto
            bruto = parte.get_payload(decode=True) or b""
            conteudo = bruto.decode(parte.get_content_charset() or "utf-8", errors="replace")
        if tipo == "text/plain":
            textos.append(str(conteudo))
        elif tipo == "text/html":
            htmls.append(str(conteudo))
    return {"texto": "\n".join(textos).strip(), "html": "\n".join(htmls).strip()}


def _anexos_email(msg: email.message.Message) -> list[dict[str, Any]]:
    anexos: list[dict[str, Any]] = []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        nome = parte.get_filename()
        if not nome:
            continue
        try:
            nome = str(make_header(decode_header(nome)))
        except Exception:  # noqa: BLE001 - nome malformado não deve quebrar o fluxo
            nome = str(nome)
        dados = parte.get_payload(decode=True) or b""
        anexos.append(
            {
                "nome": _nome_seguro(nome),
                "mime": parte.get_content_type(),
                "tamanho": len(dados),
                "dados": dados,
            }
        )
    return anexos


def _email_resumo(msg: email.message.Message, uid: int, tamanho: int, flags: str) -> dict[str, Any]:
    data = _cabecalho(msg, "Date")
    with contextlib.suppress(TypeError, ValueError):
        data = parsedate_to_datetime(data).isoformat(timespec="seconds")
    return {
        "uid": uid,
        "assunto": _cabecalho(msg, "Subject"),
        "de": _cabecalho(msg, "From"),
        "para": _cabecalho(msg, "To"),
        "data": data,
        "lido": "\\Seen" in flags,
        "tamanho": tamanho,
    }


def _email_listar(config: dict[str, Any]) -> dict[str, Any]:
    cred = _email_credencial(config)
    limite = max(1, min(int(config.get("limite") or 10), 50))
    imap = _imap_conectar(cred)
    try:
        pasta = _imap_pasta(imap, config.get("pasta"), readonly=True)
        mensagens = []
        for uid in _imap_uids(imap, limite):
            status, dados = imap.uid("fetch", str(uid), "(FLAGS)")
            flags = ""
            if status == "OK":
                flags = b" ".join(item for item in dados if isinstance(item, bytes)).decode(
                    errors="ignore"
                )
            msg = _imap_mensagem(imap, uid)
            tamanho = len(msg.as_bytes())
            mensagens.append(_email_resumo(msg, uid, tamanho, flags))
        return {"pasta": pasta, "total": len(mensagens), "mensagens": mensagens}
    finally:
        imap.logout()


def _email_ler(config: dict[str, Any]) -> dict[str, Any]:
    cred = _email_credencial(config)
    uid = str(config.get("uid") or "").strip()
    if not uid:
        raise ValueError("Informe o UID da mensagem.")
    imap = _imap_conectar(cred)
    try:
        pasta = _imap_pasta(imap, config.get("pasta"), readonly=True)
        msg = _imap_mensagem(imap, uid)
        corpo = _corpo_email(msg)
        anexos = [
            {chave: valor for chave, valor in anexo.items() if chave != "dados"}
            for anexo in _anexos_email(msg)
        ]
        resumo = _email_resumo(msg, int(uid), len(msg.as_bytes()), "")
        return {
            "pasta": pasta,
            **resumo,
            "cc": _cabecalho(msg, "Cc"),
            "texto": corpo["texto"],
            "html": corpo["html"],
            "anexos": anexos,
        }
    finally:
        imap.logout()


def _email_baixar_anexos(config: dict[str, Any]) -> dict[str, Any]:
    cred = _email_credencial(config)
    uid = str(config.get("uid") or "").strip()
    if not uid:
        raise ValueError("Informe o UID da mensagem.")
    imap = _imap_conectar(cred)
    try:
        _imap_pasta(imap, config.get("pasta"), readonly=False)
        msg = _imap_mensagem(imap, uid)
        pasta_destino = str(config.get("destino") or f"anexos/{uid}").strip()
        salvos = []
        for anexo in _anexos_email(msg):
            destino = _caminho_seguro(f"{pasta_destino}/{anexo['nome']}")
            destino.write_bytes(anexo["dados"])
            salvos.append(str(destino.relative_to(PASTA_SAIDAS.resolve())))
        if _booleano(config.get("marcar_lido")):
            imap.uid("store", uid, "+FLAGS", "(\\Seen)")
        return {"uid": int(uid), "salvos": salvos, "total": len(salvos)}
    finally:
        imap.logout()


def _email_mover(config: dict[str, Any]) -> dict[str, Any]:
    cred = _email_credencial(config)
    uid = str(config.get("uid") or "").strip()
    destino = str(config.get("destino") or "").strip()
    if not uid or not destino:
        raise ValueError("Informe o UID e a pasta de destino.")
    imap = _imap_conectar(cred)
    try:
        _imap_pasta(imap, config.get("pasta"), readonly=False)
        status, _ = imap.uid("copy", uid, destino)
        if status != "OK":
            raise ValueError(f"Não foi possível copiar a mensagem para '{destino}'.")
        imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
        imap.expunge()
        return {"uid": int(uid), "movido_para": destino}
    finally:
        imap.logout()


def _email_marcar(config: dict[str, Any], lido: bool = True) -> dict[str, Any]:
    cred = _email_credencial(config)
    uid = str(config.get("uid") or "").strip()
    if not uid:
        raise ValueError("Informe o UID da mensagem.")
    imap = _imap_conectar(cred)
    try:
        _imap_pasta(imap, config.get("pasta"), readonly=False)
        sinal = "+FLAGS" if lido else "-FLAGS"
        status, _ = imap.uid("store", uid, sinal, "(\\Seen)")
        if status != "OK":
            raise ValueError("Não foi possível alterar o status da mensagem.")
        return {"uid": int(uid), "lido": lido}
    finally:
        imap.logout()


def _email(config: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "enviar").lower()
    if acao == "enviar":
        return _email_enviar(config)
    if acao == "testar_conexao":
        return _email_testar(config)
    if acao == "listar":
        return _email_listar(config)
    if acao == "ler":
        return _email_ler(config)
    if acao == "baixar_anexos":
        return _email_baixar_anexos(config)
    if acao == "mover":
        return _email_mover(config)
    if acao == "marcar_lido":
        return _email_marcar(config, lido=True)
    if acao == "marcar_nao_lido":
        return _email_marcar(config, lido=False)
    raise ValueError(f"Ação de e-mail desconhecida: {acao}")


def _caminho_seguro(caminho: str) -> Path:
    relativo = Path(str(caminho or "").strip())
    if not relativo.name:
        raise ValueError("Informe o arquivo Excel.")
    destino = (PASTA_SAIDAS / relativo).resolve()
    if PASTA_SAIDAS.resolve() not in destino.parents and destino != PASTA_SAIDAS.resolve():
        raise ValueError("O arquivo precisa ficar dentro de data/output.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    return destino


def _excel(config: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "criar").lower()
    destino = _caminho_seguro(str(config.get("caminho") or "planilha.xlsx"))
    if acao == "ler":
        if not destino.exists():
            raise ValueError(f"Arquivo não encontrado: {destino.name}")
        livro = load_workbook(destino, data_only=True)
        aba = str(config.get("aba") or "").strip()
        planilha = livro[aba] if aba and aba in livro.sheetnames else livro.active
        linhas = list(planilha.iter_rows(values_only=True))
        if not linhas:
            return {"arquivo": destino.name, "linhas": []}
        cabecalho = [str(valor or "") for valor in linhas[0]]
        dados = [
            {cabecalho[i]: linha[i] for i in range(len(cabecalho))}
            for linha in linhas[1:]
        ]
        return {"arquivo": destino.name, "aba": planilha.title, "linhas": dados}
    dados = json_ou_texto(config.get("dados"), [])
    if not isinstance(dados, list):
        raise ValueError("Os dados do Excel precisam ser uma lista de objetos.")
    livro = Workbook()
    planilha = livro.active
    if str(config.get("aba") or "").strip():
        planilha.title = str(config["aba"]).strip()[:31]
    if dados and isinstance(dados[0], dict):
        cabecalho = list(dados[0].keys())
        planilha.append(cabecalho)
        for item in dados:
            planilha.append([item.get(coluna) for coluna in cabecalho])
    else:
        for linha in dados:
            planilha.append(linha if isinstance(linha, list) else [linha])
    livro.save(destino)
    return {"arquivo": destino.name, "aba": planilha.title, "linhas": len(dados)}


def _slack(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    webhook = str(config.get("webhook_url") or cred.get("webhook_url") or "").strip()
    texto = str(config.get("texto") or "")
    if webhook:
        validar_url(webhook)
        resposta = httpx.post(webhook, json={"text": texto}, timeout=20)
        resposta.raise_for_status()
        return {"enviado": True, "via": "webhook", "status": resposta.status_code}
    token = str(cred.get("bot_token") or cred.get("token") or "")
    if not token:
        raise ValueError("Informe webhook_url ou uma credencial com bot_token.")
    resposta = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": str(config.get("canal") or ""), "text": texto},
        timeout=20,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    if not dados.get("ok"):
        raise ValueError(f"Slack recusou: {dados.get('error', 'erro desconhecido')}")
    return {"enviado": True, "via": "api", "ts": dados.get("ts")}


def _teams(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    webhook = str(config.get("webhook_url") or cred.get("webhook_url") or "").strip()
    if not webhook:
        raise ValueError("Informe o webhook do Teams.")
    validar_url(webhook)
    titulo = str(config.get("titulo") or "Capivara Cloud")
    texto = str(config.get("texto") or "")
    resposta = httpx.post(
        webhook,
        json={"text": f"**{titulo}**\n\n{texto}"},
        timeout=20,
    )
    resposta.raise_for_status()
    return {"enviado": True, "status": resposta.status_code}


def _google_sheets(config: dict[str, Any]) -> dict[str, Any]:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    cred = _credencial(config.get("credencial"))
    bruto = cred.get("service_account_json") or cred.get("json") or cred
    info = json.loads(bruto) if isinstance(bruto, str) else bruto
    if not isinstance(info, dict) or not info.get("client_email"):
        raise ValueError("Credencial Google precisa do JSON da conta de serviço.")
    credenciais = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    credenciais.refresh(Request())
    headers = {"Authorization": f"Bearer {credenciais.token}"}
    spreadsheet = str(config.get("spreadsheet_id") or "")
    range_ = str(config.get("range") or "")
    if not spreadsheet or not range_:
        raise ValueError("Informe spreadsheet_id e range.")
    valores = quote(range_, safe="")
    base = (
        "https://sheets.googleapis.com/v4/spreadsheets/"
        f"{spreadsheet}/values/{valores}"
    )
    acao = str(config.get("acao") or "append").lower()
    if acao == "read":
        resposta = httpx.get(base, headers=headers, timeout=30)
        resposta.raise_for_status()
        return {"valores": resposta.json().get("values", [])}
    valores = json_ou_texto(config.get("valores"), [])
    if isinstance(valores, list) and valores and isinstance(valores[0], dict):
        cabecalho = list(valores[0].keys())
        valores = [cabecalho] + [[item.get(coluna) for coluna in cabecalho] for item in valores]
    resposta = httpx.post(
        f"{base}:append",
        headers=headers,
        params={"valueInputOption": "USER_ENTERED"},
        json={"values": valores},
        timeout=30,
    )
    resposta.raise_for_status()
    return resposta.json()


def _telegram(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    token = str(cred.get("bot_token") or cred.get("token") or "")
    if not token:
        raise ValueError("Credencial Telegram sem bot_token.")
    resposta = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": str(config.get("chat_id") or ""), "text": str(config.get("texto") or "")},
        timeout=20,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    if not dados.get("ok"):
        raise ValueError("Telegram recusou a mensagem.")
    return {"enviado": True, "message_id": dados.get("result", {}).get("message_id")}


def _discord(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    webhook = str(config.get("webhook_url") or cred.get("webhook_url") or "").strip()
    if not webhook:
        raise ValueError("Informe o webhook do Discord.")
    validar_url(webhook)
    resposta = httpx.post(
        webhook,
        json={"content": str(config.get("conteudo") or "")},
        timeout=20,
    )
    resposta.raise_for_status()
    return {"enviado": True, "status": resposta.status_code}


def _notion(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    token = str(cred.get("token") or cred.get("api_key") or "")
    if not token:
        raise ValueError("Credencial Notion sem token.")
    propriedades = json_ou_texto(config.get("propriedades"), {})
    resposta = httpx.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "parent": {"database_id": str(config.get("database_id") or "")},
            "properties": propriedades,
        },
        timeout=30,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    return {"id": dados.get("id"), "url": dados.get("url")}


def _airtable(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    token = str(cred.get("token") or cred.get("api_key") or "")
    base_id = str(config.get("base_id") or "")
    tabela = str(config.get("tabela") or "")
    if not token or not base_id or not tabela:
        raise ValueError("Informe credencial, base_id e tabela do Airtable.")
    resposta = httpx.post(
        f"https://api.airtable.com/v0/{base_id}/{quote(tabela, safe='')}",
        headers={"Authorization": f"Bearer {token}"},
        json={"fields": json_ou_texto(config.get("campos"), {})},
        timeout=30,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    return {"id": dados.get("id"), "createdTime": dados.get("createdTime")}


def _github(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    token = str(cred.get("token") or cred.get("api_key") or "")
    repo = str(config.get("repo") or "")
    if not token or not repo:
        raise ValueError("Informe credencial e repositório do GitHub.")
    resposta = httpx.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "title": str(config.get("titulo") or ""),
            "body": str(config.get("corpo") or ""),
            "labels": json_ou_texto(config.get("labels"), []),
        },
        timeout=30,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    return {"numero": dados.get("number"), "url": dados.get("html_url")}


def _stripe(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    chave = str(cred.get("secret_key") or cred.get("token") or "")
    if not chave:
        raise ValueError("Credencial Stripe sem secret_key.")
    dados = {
        "amount": int(config.get("valor") or 0),
        "currency": str(config.get("moeda") or "brl"),
        "automatic_payment_methods[enabled]": "true",
    }
    if config.get("descricao"):
        dados["description"] = str(config["descricao"])
    if config.get("email"):
        dados["receipt_email"] = str(config["email"])
    resposta = httpx.post(
        "https://api.stripe.com/v1/payment_intents",
        auth=(chave, ""),
        data=dados,
        timeout=30,
    )
    resposta.raise_for_status()
    retorno = resposta.json()
    return {
        "id": retorno.get("id"),
        "status": retorno.get("status"),
        "valor": retorno.get("amount"),
    }


def _openai(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    chave = str(cred.get("api_key") or cred.get("token") or "")
    if not chave:
        raise ValueError("Credencial OpenAI sem api_key.")
    mensagens = []
    if config.get("system"):
        mensagens.append({"role": "system", "content": str(config["system"])})
    mensagens.append({"role": "user", "content": str(config.get("prompt") or "")})
    resposta = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {chave}"},
        json={"model": str(config.get("modelo") or "gpt-4o-mini"), "messages": mensagens},
        timeout=60,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    return {
        "texto": dados["choices"][0]["message"]["content"],
        "modelo": dados.get("model"),
        "tokens": dados.get("usage", {}).get("total_tokens"),
    }


def _whatsapp(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    token = str(cred.get("token") or cred.get("access_token") or "")
    phone_id = str(config.get("phone_number_id") or cred.get("phone_number_id") or "")
    if not token or not phone_id:
        raise ValueError("Informe token e phone_number_id do WhatsApp.")
    resposta = httpx.post(
        f"https://graph.facebook.com/v20.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "to": str(config.get("para") or ""),
            "type": "text",
            "text": {"body": str(config.get("texto") or "")},
        },
        timeout=30,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    mensagens = dados.get("messages", [])
    return {"enviado": True, "id": mensagens[0].get("id") if mensagens else None}


def _condicao(config: dict[str, Any]) -> dict[str, Any]:
    campo = config.get("campo")
    valor = config.get("valor")
    operador = str(config.get("operador") or "==").lower()
    if operador == "vazio":
        resultado = campo in (None, "", [], {})
    elif operador == "nao_vazio":
        resultado = campo not in (None, "", [], {})
    elif operador == "contem":
        resultado = str(valor).lower() in str(campo).lower()
    else:
        try:
            esquerda = float(campo)  # type: ignore[arg-type]
            direita = float(valor)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            esquerda, direita = str(campo), str(valor)
        resultado = {
            "==": esquerda == direita,
            "!=": esquerda != direita,
            ">": esquerda > direita,
            "<": esquerda < direita,
            ">=": esquerda >= direita,
            "<=": esquerda <= direita,
        }.get(operador, False)
    return {"resultado": bool(resultado), "campo": campo, "valor": valor, "operador": operador}


def _json(config: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "extrair").lower()
    texto = config.get("texto")
    if acao == "parse":
        return {"resultado": json_ou_texto(texto, texto)}
    if acao == "stringify":
        return {"resultado": json.dumps(texto, ensure_ascii=False)}
    caminho = str(config.get("caminho") or "")
    atual = json_ou_texto(texto, texto)
    for parte in caminho.split("."):
        if not parte:
            continue
        if isinstance(atual, dict):
            atual = atual.get(parte)
        elif isinstance(atual, list) and parte.isdigit():
            atual = atual[int(parte)] if int(parte) < len(atual) else None
        else:
            atual = None
    return {"resultado": atual}


GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_LOGIN = "https://login.microsoftonline.com"


def _graph_credencial(config: dict[str, Any]) -> dict[str, Any]:
    cred = _credencial(config.get("credencial"))
    if not cred:
        raise ValueError("Selecione uma credencial Microsoft 365.")
    return cred


def _graph_token(cred: dict[str, Any]) -> str:
    token = str(cred.get("access_token") or cred.get("token") or "")
    if token:
        return token
    tenant = str(cred.get("tenant_id") or cred.get("tenant") or "")
    client_id = str(cred.get("client_id") or "")
    client_secret = str(cred.get("client_secret") or cred.get("secret") or "")
    if not tenant or not client_id or not client_secret:
        raise ValueError(
            "Credencial Microsoft 365 precisa de tenant_id, client_id e client_secret."
        )
    resposta = httpx.post(
        f"{GRAPH_LOGIN}/{tenant}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    if resposta.status_code >= 400:
        raise ValueError(f"Falha ao autenticar no Microsoft Graph: {resposta.text[:800]}")
    dados = resposta.json()
    token = str(dados.get("access_token") or "")
    if not token:
        raise ValueError("Microsoft Graph não devolveu access_token.")
    return token


def _graph_usuario(config: dict[str, Any], cred: dict[str, Any]) -> str:
    usuario = str(config.get("usuario") or cred.get("usuario") or "").strip()
    if usuario:
        return f"/users/{quote(usuario, safe='@.')}"
    return "/me"


def _graph_pedido(
    metodo: str,
    caminho: str,
    token: str,
    **kwargs: Any,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(kwargs.pop("headers", {}))
    url = caminho if caminho.startswith("http") else f"{GRAPH}{caminho}"
    resposta = httpx.request(
        metodo,
        url,
        headers=headers,
        timeout=kwargs.pop("timeout", 30),
        **kwargs,
    )
    if resposta.status_code >= 400:
        raise ValueError(f"Microsoft Graph {resposta.status_code}: {resposta.text[:800]}")
    return resposta


def _destinatarios(valor: Any) -> list[dict[str, Any]]:
    return [{"emailAddress": {"address": endereco}} for endereco in _enderecos(valor)]


def _graph_email(config: dict[str, Any]) -> dict[str, Any]:
    cred = _graph_credencial(config)
    token = _graph_token(cred)
    base = _graph_usuario(config, cred)
    para = _enderecos(config.get("para"))
    if not para:
        raise ValueError("Informe ao menos um destinatário.")
    corpo = str(config.get("corpo") or "")
    mensagem: dict[str, Any] = {
        "subject": str(config.get("assunto") or ""),
        "body": {
            "contentType": "HTML" if _booleano(config.get("html")) else "Text",
            "content": corpo,
        },
        "toRecipients": _destinatarios(para),
    }
    if _enderecos(config.get("cc")):
        mensagem["ccRecipients"] = _destinatarios(config.get("cc"))
    if _enderecos(config.get("bcc")):
        mensagem["bccRecipients"] = _destinatarios(config.get("bcc"))
    anexos = []
    for item in _como_lista(config.get("anexos")):
        nome, mime, dados = _anexo_bytes(item)
        anexos.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": nome,
                "contentType": mime,
                "contentBytes": base64.b64encode(dados).decode("ascii"),
            }
        )
    if anexos:
        mensagem["attachments"] = anexos
    resposta = _graph_pedido(
        "POST",
        f"{base}/sendMail",
        token,
        json={"message": mensagem, "saveToSentItems": True},
    )
    return {
        "enviado": True,
        "para": para,
        "anexos": [anexo["name"] for anexo in anexos],
        "status": resposta.status_code,
    }


def _graph_teams(config: dict[str, Any]) -> dict[str, Any]:
    cred = _graph_credencial(config)
    token = _graph_token(cred)
    team_id = str(config.get("team_id") or "").strip()
    channel_id = str(config.get("channel_id") or "").strip()
    if not team_id or not channel_id:
        raise ValueError("Informe team_id e channel_id.")
    resposta = _graph_pedido(
        "POST",
        f"/teams/{quote(team_id, safe='')}/channels/{quote(channel_id, safe='')}/messages",
        token,
        json={
            "body": {
                "contentType": "html" if _booleano(config.get("html")) else "text",
                "content": str(config.get("texto") or ""),
            }
        },
    )
    dados = resposta.json()
    return {"id": dados.get("id"), "webUrl": dados.get("webUrl")}


def _data_hora_graph(valor: Any, timezone: str) -> dict[str, str]:
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError("Informe data e hora no formato ISO.")
    return {"dateTime": texto, "timeZone": timezone}


def _graph_calendar(config: dict[str, Any]) -> dict[str, Any]:
    cred = _graph_credencial(config)
    token = _graph_token(cred)
    base = _graph_usuario(config, cred)
    timezone = str(config.get("timezone") or "America/Sao_Paulo")
    evento: dict[str, Any] = {
        "subject": str(config.get("assunto") or ""),
        "start": _data_hora_graph(config.get("inicio"), timezone),
        "end": _data_hora_graph(config.get("fim"), timezone),
    }
    if config.get("corpo"):
        evento["body"] = {
            "contentType": "HTML" if _booleano(config.get("html")) else "Text",
            "content": str(config.get("corpo")),
        }
    if config.get("local"):
        evento["location"] = {"displayName": str(config.get("local"))}
    participantes = _enderecos(config.get("participantes"))
    if participantes:
        evento["attendees"] = [
            {"emailAddress": {"address": endereco}, "type": "required"}
            for endereco in participantes
        ]
    resposta = _graph_pedido("POST", f"{base}/events", token, json=evento)
    dados = resposta.json()
    return {"id": dados.get("id"), "webLink": dados.get("webLink")}


def _graph_workbook(config: dict[str, Any], cred: dict[str, Any]) -> str:
    base = _graph_usuario(config, cred)
    item_id = str(config.get("item_id") or "").strip()
    caminho = str(config.get("caminho") or "").strip()
    if item_id:
        return f"{base}/drive/items/{quote(item_id, safe='')}/workbook"
    if caminho:
        return f"{base}/drive/root:/{quote(caminho, safe='/')}:/workbook"
    raise ValueError("Informe item_id ou o caminho do arquivo Excel no OneDrive.")


def _graph_worksheet(config: dict[str, Any], token: str, workbook: str) -> str:
    aba = str(config.get("aba") or "").strip()
    if aba:
        return f"{workbook}/worksheets/{quote(aba, safe='')}"
    resposta = _graph_pedido(
        "GET",
        f"{workbook}/worksheets",
        token,
        params={"$select": "id,name"},
    )
    abas = resposta.json().get("value") or []
    if not abas:
        raise ValueError("A pasta do Excel não tem abas.")
    nome = str(abas[0].get("name") or abas[0].get("id") or "")
    return f"{workbook}/worksheets/{quote(nome, safe='')}"


def _graph_valores(valor: Any) -> list[list[Any]]:
    dados = json_ou_texto(valor, [])
    if not isinstance(dados, list):
        raise ValueError("Os valores precisam ser uma lista.")
    if dados and isinstance(dados[0], dict):
        cabecalho = list(dados[0].keys())
        return [cabecalho] + [
            [item.get(coluna) for coluna in cabecalho] for item in dados
        ]
    return [linha if isinstance(linha, list) else [linha] for linha in dados]


def _proxima_linha(address: Any) -> int:
    final = str(address or "").split("!")[-1].split(":")[-1]
    numeros = re.findall(r"\d+", final)
    return int(numeros[-1]) + 1 if numeros else 1


def _graph_excel(config: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "ler").lower()
    cred = _graph_credencial(config)
    token = _graph_token(cred)
    workbook = _graph_workbook(config, cred)
    worksheet = _graph_worksheet(config, token, workbook)
    if acao == "ler":
        range_ = str(config.get("range") or "").strip()
        if not range_:
            raise ValueError("Informe o range para ler o Excel.")
        resposta = _graph_pedido(
            "GET",
            f"{worksheet}/range(address='{quote(range_, safe='')}')",
            token,
        )
        dados = resposta.json()
        return {"address": dados.get("address"), "valores": dados.get("values", [])}
    valores = _graph_valores(config.get("valores"))
    if not valores:
        raise ValueError("Informe os valores para escrever no Excel.")
    if acao == "escrever":
        range_ = str(config.get("range") or "").strip()
        if not range_:
            raise ValueError("Informe o range para escrever no Excel.")
        resposta = _graph_pedido(
            "PATCH",
            f"{worksheet}/range(address='{quote(range_, safe='')}')",
            token,
            json={"values": valores},
        )
        dados = resposta.json()
        return {"address": dados.get("address"), "linhas": len(valores)}
    if acao == "adicionar":
        usado = _graph_pedido(
            "GET",
            f"{worksheet}/usedRange",
            token,
            params={"$select": "address,values"},
        )
        dados = usado.json()
        linha = _proxima_linha(dados.get("address"))
        range_ = f"A{linha}"
        resposta = _graph_pedido(
            "PATCH",
            f"{worksheet}/range(address='{quote(range_, safe='')}')",
            token,
            json={"values": valores},
        )
        return {"address": resposta.json().get("address"), "linhas": len(valores)}
    raise ValueError(f"Ação de Excel Online desconhecida: {acao}")


def _conteudo_bytes(config: dict[str, Any]) -> bytes:
    if config.get("base64"):
        return base64.b64decode(str(config.get("base64")))
    if config.get("arquivo"):
        caminho = _caminho_seguro(str(config.get("arquivo")))
        if not caminho.exists() or not caminho.is_file():
            raise ValueError(f"Arquivo não encontrado: {config.get('arquivo')}")
        return caminho.read_bytes()
    return str(config.get("conteudo") or "").encode("utf-8")


def _graph_onedrive(config: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "listar").lower()
    cred = _graph_credencial(config)
    token = _graph_token(cred)
    base = _graph_usuario(config, cred)
    caminho = str(config.get("caminho") or "").strip().strip("/")
    if acao == "listar":
        alvo = (
            f"{base}/drive/root:/{quote(caminho, safe='/')}:/children"
            if caminho
            else f"{base}/drive/root/children"
        )
        resposta = _graph_pedido("GET", alvo, token)
        itens = []
        for item in resposta.json().get("value", []):
            itens.append(
                {
                    "id": item.get("id"),
                    "nome": item.get("name"),
                    "tamanho": item.get("size"),
                    "pasta": "folder" in item,
                    "webUrl": item.get("webUrl"),
                }
            )
        return {"caminho": caminho or "/", "itens": itens}
    if not caminho:
        raise ValueError("Informe o caminho do arquivo no OneDrive.")
    if acao == "enviar":
        dados = _conteudo_bytes(config)
        resposta = _graph_pedido(
            "PUT",
            f"{base}/drive/root:/{quote(caminho, safe='/')}:/content",
            token,
            content=dados,
            headers={"Content-Type": "application/octet-stream"},
        )
        item = resposta.json()
        return {
            "id": item.get("id"),
            "nome": item.get("name"),
            "webUrl": item.get("webUrl"),
            "tamanho": len(dados),
        }
    if acao == "baixar":
        resposta = _graph_pedido(
            "GET",
            f"{base}/drive/root:/{quote(caminho, safe='/')}:/content",
            token,
        )
        destino = _caminho_seguro(f"downloads/{_nome_seguro(Path(caminho).name)}")
        destino.write_bytes(resposta.content)
        return {
            "arquivo": str(destino.relative_to(PASTA_SAIDAS.resolve())),
            "tamanho": len(resposta.content),
        }
    raise ValueError(f"Ação do OneDrive desconhecida: {acao}")


def _microsoft(config: dict[str, Any], tipo: str) -> dict[str, Any]:
    if tipo == "microsoft_graph_email":
        return _graph_email(config)
    if tipo == "microsoft_graph_teams":
        return _graph_teams(config)
    if tipo == "microsoft_graph_calendar":
        return _graph_calendar(config)
    if tipo == "microsoft_graph_excel":
        return _graph_excel(config)
    if tipo == "microsoft_graph_onedrive":
        return _graph_onedrive(config)
    raise ValueError(f"Conector Microsoft desconhecido: {tipo}")


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def _sem_acentos(texto: str) -> str:
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )


def _slug(texto: str) -> str:
    limpo = _sem_acentos(texto).lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", limpo)
    return limpo.strip("-")


def _lista(valor: Any) -> list[Any]:
    dados = json_ou_texto(valor, valor)
    if isinstance(dados, list):
        return dados
    if isinstance(dados, str):
        if not dados.strip():
            return []
        return [parte.strip() for parte in dados.split(",") if parte.strip()]
    return [dados]


def _valor_caminho(item: Any, caminho: str) -> Any:
    return obter_caminho(item, caminho) if caminho else item


def _data(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        return valor
    texto = _texto(valor).strip()
    if not texto:
        raise ValueError("Informe uma data.")
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        pass
    for formato in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {texto}")


def _formatar_numero(valor: Any, casas: Any = 2) -> str:
    casas = max(0, min(int(casas or 0), 6))
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _transformar(config: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "").lower()
    entrada = config.get("entrada")
    if acao == "texto_limpar":
        resultado = " ".join(_texto(entrada).split())
    elif acao == "texto_acentos":
        resultado = _sem_acentos(_texto(entrada))
    elif acao == "texto_maiusculo":
        resultado = _texto(entrada).upper()
    elif acao == "texto_minusculo":
        resultado = _texto(entrada).lower()
    elif acao == "texto_titulo":
        resultado = _texto(entrada).title()
    elif acao == "texto_slug":
        resultado = _slug(_texto(entrada))
    elif acao == "texto_substituir":
        resultado = _texto(entrada).replace(
            _texto(config.get("valor")),
            _texto(config.get("valor2")),
        )
    elif acao == "texto_regex":
        padrao = _texto(config.get("valor"))
        if not padrao:
            raise ValueError("Informe a expressão regular em 'Valor / parâmetro'.")
        flags = re.IGNORECASE if _booleano(config.get("ignorar_caso", True)) else 0
        achados = re.findall(padrao, _texto(entrada), flags)
        return {
            "acao": acao,
            "resultado": achados[0] if achados else None,
            "achados": achados,
        }
    elif acao == "texto_dividir":
        separador = _texto(config.get("separador")) or ","
        resultado = [parte.strip() for parte in _texto(entrada).split(separador)]
    elif acao == "texto_juntar":
        separador = _texto(config.get("separador")) or ","
        resultado = separador.join(_texto(item) for item in _lista(entrada))
    elif acao == "texto_truncar":
        limite = max(0, int(config.get("quantidade") or 0))
        resultado = _texto(entrada)[:limite]
    elif acao.startswith("lista_"):
        itens = _lista(entrada)
        caminho = str(config.get("caminho") or "")
        if acao == "lista_filtrar":
            operador = str(config.get("operador") or "==")
            alvo = config.get("valor")
            resultado = [
                item
                for item in itens
                if _condicao(
                    {"campo": _valor_caminho(item, caminho), "operador": operador, "valor": alvo}
                )["resultado"]
            ]
        elif acao == "lista_mapear":
            resultado = [_valor_caminho(item, caminho) for item in itens]
        elif acao == "lista_ordenar":
            reverso = str(config.get("valor") or "asc").lower() in {"desc", "decrescente"}
            resultado = sorted(
                itens,
                key=lambda item: _valor_caminho(item, caminho),
                reverse=reverso,
            )
        elif acao == "lista_agrupar":
            resultado = {}
            for item in itens:
                chave = _texto(_valor_caminho(item, caminho))
                resultado[chave] = resultado.get(chave, 0) + 1
        elif acao == "lista_somar":
            resultado = sum(
                float(_valor_caminho(item, caminho) or 0) for item in itens
            )
        elif acao == "lista_contar":
            resultado = len(itens)
        elif acao == "lista_distintos":
            vistos = set()
            resultado = []
            for item in itens:
                valor = _valor_caminho(item, caminho)
                chave = json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)
                if chave not in vistos:
                    vistos.add(chave)
                    resultado.append(valor)
        elif acao == "lista_primeiro":
            resultado = itens[0] if itens else None
        elif acao == "lista_ultimo":
            resultado = itens[-1] if itens else None
        else:
            raise ValueError(f"Ação de lista desconhecida: {acao}")
    elif acao == "data_agora":
        agora = datetime.now(UTC)
        formato = _texto(config.get("formato"))
        resultado = agora.strftime(formato) if formato else agora.isoformat(timespec="seconds")
    elif acao == "data_formatar":
        formato = _texto(config.get("formato")) or "%d/%m/%Y"
        resultado = _data(entrada).strftime(formato)
    elif acao == "data_adicionar":
        unidade = str(config.get("unidade") or "dias")
        chave = {
            "dias": "days",
            "horas": "hours",
            "minutos": "minutes",
            "segundos": "seconds",
        }.get(unidade, "days")
        quantidade = float(config.get("quantidade") or 0)
        nova = _data(entrada) + timedelta(**{chave: quantidade})
        formato = _texto(config.get("formato"))
        resultado = nova.strftime(formato) if formato else nova.isoformat(timespec="seconds")
    elif acao == "data_diferenca":
        dias = (_data(config.get("valor")) - _data(entrada)).total_seconds() / 86400
        resultado = int(dias) if dias.is_integer() else round(dias, 2)
    elif acao == "numero_arredondar":
        resultado = round(float(entrada), int(config.get("quantidade") or 0))
    elif acao == "numero_formatar":
        resultado = _formatar_numero(entrada, config.get("quantidade") or 2)
    elif acao == "json_parse":
        resultado = (
            entrada
            if isinstance(entrada, (dict, list))
            else json.loads(_texto(entrada))
        )
    elif acao == "json_stringify":
        resultado = json.dumps(entrada, ensure_ascii=False)
    elif acao == "json_extrair":
        resultado = obter_caminho(
            json_ou_texto(entrada, entrada),
            str(config.get("caminho") or ""),
        )
    elif acao == "base64_codificar":
        resultado = base64.b64encode(_texto(entrada).encode("utf-8")).decode("ascii")
    elif acao == "base64_decodificar":
        resultado = base64.b64decode(_texto(entrada)).decode("utf-8", errors="replace")
    elif acao == "hash_sha256":
        resultado = hashlib.sha256(_texto(entrada).encode("utf-8")).hexdigest()
    elif acao == "uuid":
        resultado = str(uuid.uuid4())
    elif acao == "converter_texto":
        resultado = _texto(entrada)
    elif acao == "converter_numero":
        numero = float(_texto(entrada).replace(",", "."))
        resultado = int(numero) if numero.is_integer() else numero
    elif acao == "converter_booleano":
        resultado = _booleano(entrada)
    else:
        raise ValueError(f"Ação de transformação desconhecida: {acao}")
    return {"acao": acao, "resultado": resultado}


def _variavel(config: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
    acao = str(config.get("acao") or "definir").lower()
    variaveis = contexto.setdefault("vars", {})
    nome = str(config.get("nome") or "").strip()
    if acao == "listar":
        return {"variaveis": dict(variaveis)}
    if not nome:
        raise ValueError("Informe o nome da variável.")
    if acao == "definir":
        valor = config.get("valor")
        variaveis[nome] = valor
        return {"nome": nome, "valor": valor}
    if acao == "obter":
        return {"nome": nome, "valor": variaveis.get(nome)}
    if acao == "remover":
        return {"nome": nome, "removido": variaveis.pop(nome, None) is not None}
    raise ValueError(f"Ação de variável desconhecida: {acao}")


def executar(tipo: str, config: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
    config = resolver_template(config, contexto)
    if tipo in {"gatilho_manual", "gatilho_webhook"}:
        return {"gatilho": tipo, "entrada": contexto.get("entrada", {})}
    if tipo == "http":
        return _http(config)
    if tipo == "email":
        return _email(config)
    if tipo == "excel":
        return _excel(config)
    if tipo == "slack":
        return _slack(config)
    if tipo == "teams":
        return _teams(config)
    if tipo == "google_sheets":
        return _google_sheets(config)
    if tipo == "telegram":
        return _telegram(config)
    if tipo == "discord":
        return _discord(config)
    if tipo == "notion":
        return _notion(config)
    if tipo == "airtable":
        return _airtable(config)
    if tipo == "github":
        return _github(config)
    if tipo == "stripe":
        return _stripe(config)
    if tipo == "openai":
        return _openai(config)
    if tipo == "whatsapp":
        return _whatsapp(config)
    if tipo.startswith("microsoft_graph_"):
        return _microsoft(config, tipo)
    if tipo == "variavel":
        return _variavel(config, contexto)
    if tipo == "transformar":
        return _transformar(config)
    if tipo == "condicao":
        return _condicao(config)
    if tipo == "json":
        return _json(config)
    if tipo == "espera":
        segundos = max(0, min(float(config.get("segundos") or 0), 30))
        time.sleep(segundos)
        return {"segundos": segundos}
    if tipo == "log":
        return {"mensagem": str(config.get("mensagem") or "")}
    if tipo == "fim":
        return {"fim": True}
    raise ValueError(f"Tipo de nó desconhecido: {tipo}")
