# Capivara Cloud — Arquitetura

## Visão geral

```text
Navegador (Drawflow)
        │  JSON do grafo
        ▼
FastAPI (app/main.py)
        │
        ├── SQLite (app/db.py) ── workflows, execuções, passos, credenciais, agendamentos
        ├── Motor (app/engine.py) ── percorre o grafo e chama conectores
        ├── Agendador (app/agendador.py) ── thread que dispara fluxos vencidos
        ├── Conectores (app/connectors.py)
        ├── Cofre (app/security.py) ── Fernet + máscara
        └── Template (app/template.py) ── {{ variáveis }}, JSON, URL
```

## Formato do grafo

O grafo é o export nativo do Drawflow:

```json
{
  "drawflow": {
    "Home": {
      "data": {
        "1": {
          "id": 1,
          "name": "gatilho_manual",
          "data": {
            "tipo": "gatilho_manual",
            "nome": "Início manual",
            "config": {}
          },
          "inputs": {},
          "outputs": {
            "output_1": {
              "connections": [{ "node": "2", "output": "input_1" }]
            }
          }
        }
      }
    }
  }
}
```

O motor lê `drawflow.Home.data`, monta as arestas a partir de `outputs` e
começa pelo primeiro nó de gatilho. Sem gatilho, começa pelo primeiro nó sem
entrada. Cada nó carrega `data.tipo` e `data.config`.

## Execução

1. `POST /api/workflows/{id}/executar` ou `POST /api/webhooks/{id}`.
2. `engine.executar_workflow()` cria uma linha em `execucoes`.
3. O motor percorre os nós, chamando `connectors.executar(tipo, config, contexto)`.
4. Cada passo é gravado em `passos` com entrada, saída, duração e erro.
5. `condicao` escolhe `output_1` (verdadeiro) ou `output_2` (falso).
6. O motor para em `fim`, em nó sem saída ou após 100 passos (proteção de ciclo).
7. A execução termina como `concluido` ou `erro`.

## Contexto de template

Dentro de qualquer `config`, o valor `{{ caminho }}` é resolvido:

- `{{ entrada.nome }}` — corpo do webhook ou entrada manual.
- `{{ passos.2.json.id }}` — saída de um nó anterior (pelo id do nó).
- `{{ ultimo.texto }}` — saída do passo anterior.
- `{{ gatilho.tipo }}` — `manual` ou `webhook`.

Se a variável não existir, a execução falha com mensagem clara.

## Credenciais

- `POST /api/credenciais` cifra o JSON com Fernet e grava em `credenciais`.
- A listagem devolve os valores mascarados.
- O motor busca a credencial pelo nome no momento do passo.
- `security.SEGREDOS` define quais chaves são mascaradas no trace.
- A chave vem de `CAPIVARA_CLOUD_KEY` ou de `data/cloud.key` (0600).

## Segurança

- SSRF: `template.validar_url()` bloqueia `localhost`, `127.0.0.1`, `10.x`,
  `172.16-31.x`, `192.168.x`, `169.254.x` e nomes privados por padrão.
- Para desenvolvimento, `CAPIVARA_CLOUD_PERMITIR_REDE_LOCAL=true`.
- O trace mascara `headers`, `token`, `senha`, `secret` e chaves equivalentes.
- O MVP não tem login; não exponha a porta na internet sem autenticação/TLS.

## Decisões

- **SQLite** para zero configuração e portabilidade do MVP.
- **Drawflow** por ser vanilla, leve e não exigir build de frontend.
- **FastAPI** por Swagger automático, Pydantic e boa DX.
- **Fernet** por ser simétrico, auditado e simples de operar localmente.
- **Sem React** para manter o projeto fácil de entender e contribuir.
