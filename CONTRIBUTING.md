# Como contribuir

Obrigado por ajudar o Capivara Cloud. Este repositório é um **snapshot funcional**
do produto, usado para rodar, testar e reunir ideias, RFCs, exemplos e conectores
antes de virarem código na versão estável.

## Fluxo

1. **Sugestão** — abra uma issue com o template `Sugestão`.
2. **Triagem** — a comunidade e os mantenedores avaliam impacto e escopo.
3. **RFC** — para mudanças grandes, copie `ideias/TEMPLATE.md` e abra um PR.
4. **Aceite** — a proposta recebe a label `aceita`.
5. **Implementação** — o código vai para o repositório do produto.
6. **Release** — a mudança aparece no próximo release.

## O que entra aqui

- Ideias de conectores e integrações.
- Exemplos de workflows e casos de uso.
- Melhorias de documentação.
- Feedback de usabilidade do editor.
- RFCs de arquitetura, segurança e API.

## O que não entra aqui

- Forks divergentes do produto (o código aqui é sincronizado; mudanças aceitas vão para `capivara-rpa/capivara-cloud`).
- Segredos, tokens, senhas ou dados de clientes.
- Conteúdo ofensivo, spam ou propaganda.
- Mudanças que quebrem a licença MIT.

## Padrões

- Escreva em português claro.
- Explique o problema antes da solução.
- Inclua exemplos de entrada e saída quando possível.
- Para conectores, informe API, autenticação e limites de uso.
- Para exemplos, inclua o JSON do workflow e como testar.

## Testes

Quando a contribuição virar código no produto, ela precisa passar em:

```bash
ruff check app tests
pytest
python -m compileall app
```

## Revisão

- Um mantenedor revisa e pode pedir ajustes.
- PRs pequenos são revisados mais rápido.
- Propostas sem informação suficiente recebem `precisa-de-mais-info`.
- Propostas fora do escopo recebem `recusada` com justificativa.

## Código de conduta

Ao participar, você concorda com o `CODE_OF_CONDUCT.md`.
