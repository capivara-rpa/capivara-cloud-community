# Governança

## Modelo

- **Produto** (`capivara-rpa/capivara-cloud`): código, releases e documentação
  oficial.
- **Comunidade** (este repositório): ideias, RFCs, exemplos e conectores.
- **Mantenedores**: cuidam da triagem, revisão e publicação no produto.

## Labels

| Label | Significado |
| --- | --- |
| `sugestao` | Ideia nova em avaliação |
| `em-avaliacao` | Em análise pelos mantenedores |
| `aceita` | Aprovada para implementação |
| `recusada` | Fora de escopo ou inviável |
| `precisa-de-mais-info` | Falta contexto |
| `rfc` | Proposta de arquitetura/processo |
| `conector` | Proposta de integração |
| `exemplo` | Workflow ou caso de uso |
| `documentacao` | Melhoria de docs |
| `boa-primeira-contribuicao` | Boa para começar |

## Critérios de aceite

Uma proposta é aceita quando:

1. Resolve um problema real e recorrente.
2. Cabe no escopo do produto (automação de APIs em português).
3. Tem API pública estável ou caminho claro de integração.
4. Não exige segredo no repositório.
5. Pode ser testada e documentada.
6. Mantém a licença MIT e a compatibilidade com Python 3.11+.

## Decisões

- Mudanças pequenas: consenso em issue/PR.
- Mudanças grandes: RFC + período de comentários + decisão dos mantenedores.
- Em caso de empate, os mantenedores decidem e registram a justificativa.
- Decisões relevantes viram documentação no repositório do produto.

## Releases

O produto usa versionamento semântico. A comunidade não publica releases; ela
propõe mudanças que entram no fluxo do produto.

## Segurança

Vulnerabilidades não devem ser abertas como issue pública. Use o canal descrito
em `SECURITY.md`.
