# Capivara Cloud — Escopo do MVP

## Visão

O Capivara Cloud é uma plataforma de automação API-first, em português, para
pessoas que precisam conectar sistemas sem escrever um projeto inteiro. A
experiência é parecida com Zapier, Power Automate e n8n: um canvas visual,
blocos de gatilho/ação e execução observável.

O produto é separado do Capivara / RPA Brasil. A Lagoa orquestra robôs
em máquinas; o Cloud orquestra chamadas de API, dados e notificações.

## Público

- Analistas de operações que vivem colando dados entre planilhas e sistemas.
- Pessoas de produto que precisam integrar ferramentas sem depender de sprint.
- Devs que querem um ponto de partida open source, em português, para automação.
- Comunidade Capivara que já usa a Lagoa e quer integrar sistemas web.

## MVP (agora)

1. Editor visual com Drawflow.
2. Workflow com gatilho manual e webhook.
3. Conectores iniciais: e-mail, Excel, Slack, Teams, Google Sheets, HTTP,
   Telegram, Discord, Notion, Airtable, GitHub, Stripe, OpenAI, WhatsApp.
4. Blocos de lógica: condição, JSON, espera, log e fim.
5. Credenciais cifradas com Fernet e mascaradas na API.
6. Histórico de execuções com trace por passo.
7. Swagger/OpenAPI público.
 8. UI local com tema claro/escuro e identidade Capivara.
 9. Agendamentos recorrentes (intervalo, horário diário e cron) com pausa e
    execução imediata.


## Fora do MVP

- Autenticação de usuários e multiusuário.
- Times, organizações e RBAC.
- Execução distribuída e filas.
- Marketplace de conectores.
- Cobrança.
- Editor de código dentro do navegador.
- Alta disponibilidade e banco externo.

## Princípios

- **Português primeiro**: nomes, mensagens e documentação em PT-BR.
- **API-first**: tudo que a UI faz tem uma rota HTTP equivalente.
- **Observável**: toda execução deixa trace; toda falha é legível.
- **Seguro por padrão**: credencial cifrada, segredo mascarado, SSRF bloqueado.
- **Simples de rodar**: um `pip install`, um SQLite e um servidor local.
- **Sem lock-in**: grafo em JSON, dados em SQLite, conectores em Python.

## Métricas de sucesso do MVP

- Criar e executar um fluxo em menos de 2 minutos.
- Inspecionar uma falha sem abrir o código.
- Instalar e subir localmente em menos de 5 minutos.
- Integrar um webhook externo com uma linha de `curl`.
- Entender o catálogo de conectores sem ler código.

## Roadmap depois do MVP

1. Login local e sessão.
2. Execução assíncrona e fila.
3. Retentativas e relatório de erros dos agendamentos.
4. Mais conectores (Google Drive, Gmail, Postgres, S3, CRM).
5. Versionamento de workflow.
6. Importar/exportar JSON.
7. Marketplace da comunidade.
8. Deploy em Docker e hospedagem gerenciada.
