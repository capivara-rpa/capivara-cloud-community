# Conectores

Propostas de integrações para o Capivara Cloud. O catálogo oficial fica no
produto (`app/connectors.py`); aqui reunimos ideias, exemplos e detalhes de API
antes da implementação.

## Estrutura sugerida

```text
conectores/
  nome-do-servico/
    README.md        # problema, API, autenticação, ações
    exemplo.json     # workflow de exemplo (opcional)
```

## O que documentar

- Nome do serviço e link da API.
- Tipo de autenticação e campos da credencial.
- Ações desejadas (criar, listar, atualizar, apagar).
- Paginação, rate limit e limites.
- Exemplo de requisição e resposta.
- Erros comuns e como tratar.
- Se precisa de webhook.

## Regras

- Não inclua tokens, senhas ou dados reais.
- Use exemplos fictícios.
- Respeite os termos de uso do serviço.
- Se a API for privada, explique como obter acesso.
- Propostas sem documentação suficiente recebem `precisa-de-mais-info`.
