# Exemplos de workflow

Os exemplos abaixo já são semeados no primeiro start do banco:

- **Olá, Capivara Cloud** — gatilho manual → log → fim.
- **Webhook → JSON → log** — recebe um POST e registra o corpo.

## Criar um fluxo por API

```bash
curl -X POST http://127.0.0.1:8787/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"nome":"Meu fluxo","descricao":"teste","grafo":{}}'
```

## Rodar manualmente

```bash
curl -X POST http://127.0.0.1:8787/api/workflows/SEU_ID/executar \
  -H "Content-Type: application/json" \
  -d '{"entrada":{"nome":"Arthur"}}'
```

## Disparar por webhook

```bash
curl -X POST http://127.0.0.1:8787/api/webhooks/SEU_ID \
  -H "Content-Type: application/json" \
  -d '{"nome":"Arthur","email":"arthur@exemplo.com"}'
```

## Exportar e importar

No editor, o botão **Salvar** grava o export do Drawflow em `workflows.grafo`.
O mesmo JSON pode ser versionado e reaplicado via `PUT /api/workflows/{id}`.
