# Capivara Cloud

Automação de APIs em português, com workflows visuais, conectores prontos,
credenciais cifradas e execução observável.

> Produto separado do **Capivara / RPA Brasil**. A Lagoa continua sendo
> o orquestrador de robôs; o Cloud é a plataforma API-first estilo Zapier,
> Power Automate e n8n.

> **Espaço da comunidade:** este é um **snapshot funcional** do Cloud oficial,
> mantido para testar ideias, RFCs, exemplos e conectores propostos pela
> comunidade. O código estável fica em
> [`capivara-rpa/capivara-cloud`](https://github.com/capivara-rpa/capivara-cloud).

## Como usar este snapshot

- O código do produto está presente aqui para rodar, testar e propor mudanças.
- Use [`CONTRIBUTING.md`](CONTRIBUTING.md), [`GOVERNANCA.md`](GOVERNANCA.md),
  [`ideias/`](ideias/) e [`conectores/`](conectores/) para avaliar propostas.
- Para produção, prefira o repositório oficial do Cloud.
- A sincronização com o produto preserva `ideias/`, `conectores/` e os documentos
  de governança deste repositório.

## O que já funciona

- Editor visual com **Drawflow**: arraste blocos, conecte e configure.
- Workflows com **gatilho manual** e **webhook** (`POST /api/webhooks/{id}`).
- Execução com **trace por passo** (entrada, saída, duração e erro).
- Credenciais **cifradas com Fernet**; a API só devolve valores mascarados.
- Catálogo com **28 conectores**: e-mail SMTP/IMAP (envio, leitura e anexos),
  Microsoft 365 via Graph (Outlook, Teams, Calendar, Excel Online e OneDrive),
  Excel local, Slack, Teams, Google Sheets, HTTP, Telegram, Discord, Notion,
  Airtable, GitHub, Stripe, OpenAI, WhatsApp, variáveis, transformações,
  condição, JSON, espera, log e fim.
- Paleta com filtros por conjunto e **logos reais** das tecnologias.
- **Swagger** em `/docs`, ReDoc em `/redoc` e OpenAPI em `/openapi.json`.
- Bloqueio de SSRF para URLs locais/privadas (liberável em desenvolvimento).
- Tema claro/escuro e identidade visual Capivara.

## Rodar localmente

Requisitos: Python 3.11+.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m app.main
```

Abra <http://127.0.0.1:8787/>. O Swagger fica em
<http://127.0.0.1:8787/docs>.

Também dá para usar o wrapper:

```bash
./scripts/run.sh
```

No Windows:

```bat
scripts\run.bat
```

## Estrutura

```text
app/
  main.py        FastAPI, rotas e Swagger
  engine.py      motor de execução do grafo
  agendador.py   execuções recorrentes (intervalo/diário/cron)
  connectors.py  catálogo + handlers dos conectores
  db.py          SQLite (workflows, execuções, passos, credenciais, agendamentos)
  security.py    Fernet, máscara de segredos
  template.py    resolução de {{ variáveis }}, JSON e validação de URL
  exemplos.py    workflows de exemplo
  schemas.py     modelos Pydantic
  static/        UI (HTML/CSS/JS + Drawflow vendorizado)
data/            banco, chave e saídas (gitignored)
docs/            escopo, arquitetura e conectores
tests/           pytest
```

## Endpoints principais

| Método | Caminho | Descrição |
| --- | --- | --- |
| GET | `/api/health` | Saúde da API |
| GET | `/api/config` | Versão e metadados |
| GET | `/api/conectores` | Catálogo de conectores |
| GET | `/api/workflows` | Lista fluxos |
| POST | `/api/workflows` | Cria fluxo |
| GET | `/api/workflows/{id}` | Detalha fluxo |
| PUT | `/api/workflows/{id}` | Atualiza grafo |
| DELETE | `/api/workflows/{id}` | Remove fluxo |
| POST | `/api/workflows/{id}/executar` | Executa manualmente |
| POST | `/api/webhooks/{id}` | Dispara por webhook |
| GET | `/api/agendamentos` | Lista agendamentos |
| POST | `/api/agendamentos` | Cria agendamento recorrente |
| POST | `/api/agendamentos/verificar` | Verifica agendamentos vencidos agora |
| GET | `/api/agendamentos/{id}` | Detalha agendamento |
| PUT | `/api/agendamentos/{id}` | Atualiza, pausa ou ativa |
| DELETE | `/api/agendamentos/{id}` | Remove agendamento |
| POST | `/api/agendamentos/{id}/executar` | Executa agora |
| GET | `/api/execucoes` | Histórico |
| GET | `/api/execucoes/{id}` | Trace completo |
| GET | `/api/credenciais` | Lista mascarada |
| POST | `/api/credenciais` | Cria credencial cifrada |
| DELETE | `/api/credenciais/{id}` | Remove credencial |

Exemplo de webhook:

```bash
curl -X POST http://127.0.0.1:8787/api/webhooks/SEU_ID \
  -H "Content-Type: application/json" \
  -d '{"nome":"Arthur","email":"arthur@exemplo.com"}'
```

## Agendamentos

O menu **Agendamentos** cria execuções recorrentes sem dependência externa.
São três tipos: `intervalo` (`15m`, `1h`, `30s`, `1d`), `diario`
(`09:30`) e `cron` (5 campos, aceitando `*/15`, `9-18`, listas e
`seg-sex`). Cada agendamento pode ser pausado, reativado, executado agora
e mostra a próxima execução e o último erro. A verificação roda em uma
thread do próprio servidor a cada `CAPIVARA_CLOUD_INTERVALO_AGENDADOR`
segundos; o botão **Verificar agora** força uma checagem imediata.

## Variáveis de ambiente

| Variável | Default | Para que serve |
| --- | --- | --- |
| `CAPIVARA_CLOUD_DATA` | `./data` | Pasta de dados |
| `CAPIVARA_CLOUD_BANCO` | `data/cloud.db` | Banco SQLite |
| `CAPIVARA_CLOUD_CHAVE` | `data/cloud.key` | Arquivo da chave Fernet |
| `CAPIVARA_CLOUD_KEY` | vazio | Chave Fernet inline |
| `CAPIVARA_CLOUD_HOST` | `127.0.0.1` | Host do servidor |
| `CAPIVARA_CLOUD_PORTA` | `8787` | Porta do servidor |
| `CAPIVARA_CLOUD_PERMITIR_REDE_LOCAL` | `false` | Libera HTTP para localhost/rede privada |
| `CAPIVARA_CLOUD_AGENDADOR` | `true` | Liga a thread de agendamentos |
| `CAPIVARA_CLOUD_INTERVALO_AGENDADOR` | `60` | Intervalo mínimo de verificação (segundos) |
| `CAPIVARA_CLOUD_FUSO` | `America/Sao_Paulo` | Fuso para `diario` e `cron` |

## Segurança

- Credenciais são cifradas antes de ir para o SQLite.
- A listagem devolve apenas valores mascarados.
- Segredos conhecidos (`senha`, `token`, `headers`, etc.) são mascarados no trace.
- URLs privadas/localhost são bloqueadas por padrão para reduzir SSRF.
- Para produção, coloque atrás de HTTPS, autenticação e uma chave gerenciada
  (KMS/keyring), não no arquivo local.

## Qualidade

```bash
ruff check app tests
pytest
python -m compileall app
```

## Status

MVP local em desenvolvimento. O foco é validar o editor visual, o motor de
execução, os conectores iniciais e a experiência de API pública antes de
adicionar autenticação, multiusuário e execução distribuída.

## Comunidade

Sugestões, RFCs e exemplos: <https://github.com/capivara-rpa/capivara-cloud-community>.

## Licença

MIT.
