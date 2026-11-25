# Conectores do Capivara Cloud

O catálogo vivo está em `GET /api/conectores` e no Swagger. Cada conector tem
`tipo`, `categoria`, `conjunto`, `logo`, `campos`, `credencial_tipo` (quando
existe) e `docs`. A resposta também traz `conjuntos` para montar os filtros da
paleta.

Campos condicionais usam `mostrar_se`: um mapa `campo -> valores` que só exibe o
campo quando o valor atual do campo bate com a lista (por exemplo, `Para` só
aparece quando `acao` é `enviar`).

## Gatilhos

| Tipo | Nome | Como dispara |
| --- | --- | --- |
| `gatilho_manual` | Início manual | Botão **Rodar** no editor |
| `gatilho_webhook` | Webhook | `POST /api/webhooks/{id}` com JSON |

## Ações

| Tipo | Nome | Credencial | Observações |
| --- | --- | --- | --- |
| `http` | HTTP Request | `http` (opcional) | GET/POST/PUT/PATCH/DELETE, headers, corpo, Bearer/Basic/API key |
| `email` | E-mail (SMTP/IMAP) | `smtp` | Envia (HTML/anexos), testa, lista, lê, baixa anexos, move e marca lido/não lido |
| `excel` | Excel | — | Cria/lê `.xlsx` em `data/output` |
| `slack` | Slack | `slack` (opcional) | Webhook ou Bot token + canal |
| `teams` | Microsoft Teams | `teams` | Webhook do Teams |
| `google_sheets` | Google Sheets | `google_sheets` | OAuth refresh token |
| `telegram` | Telegram | `telegram` | Bot token + chat_id |
| `discord` | Discord | — | Webhook do Discord |
| `notion` | Notion | `notion` | Cria página em database |
| `airtable` | Airtable | `airtable` | Cria registro |
| `github` | GitHub | `github` | Cria issue |
| `stripe` | Stripe | `stripe` | Cria PaymentIntent |
| `openai` | OpenAI | `openai` | Chat Completions |
| `whatsapp` | WhatsApp Cloud | `whatsapp` | Mensagem de texto |

### Microsoft 365 (Microsoft Graph)

| Tipo | Nome | O que faz |
| --- | --- | --- |
| `microsoft_graph_email` | Outlook — enviar e-mail | `sendMail` com HTML, CC/BCC e anexos |
| `microsoft_graph_teams` | Teams — mensagem em canal | Publica mensagem em `team_id`/`channel_id` |
| `microsoft_graph_calendar` | Outlook — criar evento | Cria evento com início/fim, fuso e participantes |
| `microsoft_graph_excel` | Excel Online — ler/escrever | Lê range, escreve range ou adiciona linhas |
| `microsoft_graph_onedrive` | OneDrive — arquivos | Lista, envia (texto/base64/arquivo local) e baixa |

Os cinco usam a credencial `microsoft_graph` e o fluxo client credentials
(`tenant_id` + `client_id` + `client_secret`). O campo `usuario` da credencial
(ou do nó) define o `/users/{usuario}`; sem ele o Graph usa `/me` quando o token
for delegado.

## Lógica

| Tipo | Nome | O que faz |
| --- | --- | --- |
| `condicao` | Condição | Compara dois valores e escolhe `output_1`/`output_2` |
| `json` | JSON | Lê, monta ou transforma JSON |
| `espera` | Espera | Aguarda N segundos |
| `log` | Log | Registra uma mensagem no trace |
| `fim` | Fim | Encerra o fluxo |
| `variavel` | Variável | Define, consulta, remove ou lista variáveis em `contexto["vars"]` |
| `transformar` | Transformar | Texto, listas, datas, números, JSON, base64, SHA-256, UUID e conversões |

### Ações do bloco `email`

| Ação | Campos principais | Saída |
| --- | --- | --- |
| `enviar` | `para`, `assunto`, `corpo`, `html`, `anexos`, `cc`, `bcc` | `enviado`, `para`, `anexos` |
| `testar_conexao` | — | `smtp.ok` e `imap.ok` |
| `listar` | `pasta`, `limite` | `mensagens` (uid, assunto, de, data, lido) |
| `ler` | `uid`, `pasta` | `resumo`, `texto`, `html`, `anexos` (metadados) |
| `baixar_anexos` | `uid`, `pasta`, `marcar_lido` | arquivos gravados em `data/output/downloads` |
| `mover` | `uid`, `pasta`, `destino` | `movido` |
| `marcar_lido` / `marcar_nao_lido` | `uid`, `pasta` | `lido` |

### Ações do bloco `transformar`

- Texto: `texto_limpar`, `texto_acentos`, `texto_maiusculo`, `texto_minusculo`,
  `texto_titulo`, `texto_slug`, `texto_substituir`, `texto_regex`,
  `texto_dividir`, `texto_juntar`, `texto_truncar`.
- Listas: `lista_filtrar`, `lista_mapear`, `lista_ordenar`, `lista_agrupar`,
  `lista_somar`, `lista_contar`, `lista_distintos`, `lista_primeiro`,
  `lista_ultimo`.
- Datas: `data_agora`, `data_formatar`, `data_adicionar`, `data_diferenca`.
- Números: `numero_arredondar`, `numero_formatar`.
- JSON/dados: `json_parse`, `json_stringify`, `json_extrair`.
- Segurança/utilidades: `base64_codificar`, `base64_decodificar`,
  `hash_sha256`, `uuid`.
- Conversões: `converter_texto`, `converter_numero`, `converter_booleano`.

Use `{{ vars.nome }}` para consumir uma variável em qualquer campo de outro nó.

## Modelos de credencial

Os modelos prontos aparecem em `GET /api/credenciais/modelos` e no formulário de
credenciais. Exemplos:

### HTTP

```json
{
  "tipo": "bearer",
  "token": "seu-token"
}
```

Tipos aceitos: `bearer`, `basic` (`usuario`/`senha`) e `api_key`
(`nome`/`valor`).

### SMTP/IMAP

```json
{
  "host": "smtp.exemplo.com",
  "porta": 587,
  "usuario": "conta@exemplo.com",
  "senha": "sua-senha",
  "remetente": "Capivara Cloud <conta@exemplo.com>",
  "tls": true,
  "imap_host": "imap.exemplo.com",
  "imap_porta": 993,
  "imap_ssl": true
}
```

`imap_host`/`imap_porta`/`imap_ssl` são opcionais para envio, mas necessários
para `listar`, `ler`, `baixar_anexos`, `mover` e marcar lido.

### Microsoft Graph

```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000000",
  "client_id": "00000000-0000-0000-0000-000000000000",
  "client_secret": "segredo",
  "usuario": "automacao@empresa.com"
}
```

### Google Sheets

```json
{
  "client_id": "....apps.googleusercontent.com",
  "client_secret": "....",
  "refresh_token": "...."
}
```

### Slack

```json
{
  "webhook_url": "https://hooks.slack.com/services/...",
  "bot_token": "",
  "canal": "#geral"
}
```

### Telegram

```json
{
  "bot_token": "123:ABC",
  "chat_id": "123456"
}
```

### Notion

```json
{
  "token": "secret_...",
  "database_id": "...."
}
```

### Airtable

```json
{
  "token": "pat...",
  "base_id": "app...",
  "tabela": "Clientes"
}
```

### GitHub

```json
{
  "token": "ghp_...",
  "repo": "capivara-rpa/capivara-cloud"
}
```

### Stripe

```json
{
  "secret_key": "sk_test_..."
}
```

### OpenAI

```json
{
  "api_key": "sk-...",
  "modelo": "gpt-4o-mini"
}
```

### WhatsApp Cloud

```json
{
  "token": "EAAG...",
  "phone_number_id": "123456789"
}
```

## Adicionar um conector

1. Adicione uma entrada em `CATALOGO` (`app/connectors.py`) com `tipo`,
   `categoria`, `campos` e, se precisar, `credencial_tipo`/`modelo_credencial`.
2. Implemente `_seu_conector(config)` retornando um `dict` com a saída do passo.
3. Registre o handler no `executar()` (`app/connectors.py`).
4. Adicione um teste em `tests/test_connectors.py`.
5. Atualize esta página e, se fizer sentido, proponha no repositório da
   comunidade.

## Convenções

- Use `_credencial(config.get("credencial"))` para buscar segredos.
- Use `resolver_template` no `config` antes de chamar o handler.
- Use `validar_url` em qualquer URL configurável.
- Levante `ValueError` com mensagem em português para erro de negócio.
- Devolva dados serializáveis em JSON.
- Nunca grave segredo no retorno do passo.
