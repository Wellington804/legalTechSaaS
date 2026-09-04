# Painel Diário — Research

## Overview

Evoluir a página inicial do LexFlow para orientar advogados autônomos e pequenos escritórios à próxima ação em até 30 segundos, usando somente dados persistidos e autorizados.

O design validado completo está em [`../design-painel-diario.md`](../design-painel-diario.md).

## Problem Statement

O painel atual já consulta o núcleo real de `workspace`, mas depende de várias requisições, ordena parte das tarefas no navegador e calcula alguns totais carregando coleções completas. Há também código legado sem consumidor com métricas simuladas e fallback local. O próximo ciclo deve melhorar a rotina diária e remover esses riscos sem criar outra infraestrutura.

## User Stories / Use Cases

- Como advogado, quero identificar a prioridade atual e abrir seu contexto imediatamente.
- Como advogado, quero concluir ou reagendar uma tarefa sem navegar até a agenda.
- Como advogado, quero cadastrar uma próxima ação para um processo sem planejamento.
- Como usuário com acesso restrito, não devo ver nem alterar dados de outros tenants ou casos.
- Como responsável financeiro, quero ver lançamentos em rascunho sem que o sistema os chame incorretamente de vencidos.

## Technical Research

### Approach Options

1. Estender a visão do módulo `workspace`, com agregações e ordenação no PostgreSQL.
2. Compor múltiplos endpoints no frontend.
3. Criar uma projeção materializada alimentada por eventos.

### Recommended Approach

A opção 1 foi aceita. Ela reutiliza o monólito modular, autorização, auditoria e concorrência existentes. Consultas `EXISTS`/`NOT EXISTS` e agregações substituem carregamento integral de coleções. A documentação SQLAlchemy 2.0 confirma o uso de `SelectBase.exists()` dentro de um `SELECT` externo.

### Required Technologies

- FastAPI e SQLAlchemy assíncrono já instalados.
- PostgreSQL como fonte de verdade.
- Next.js 16 e React no Client Component interativo já existente.
- Nenhuma dependência ou serviço novo.

### Data Requirements

- Tarefas abertas, datas, tipo, revisão e processo.
- Processos ativos autorizados sem tarefa aberta.
- Publicações não reconhecidas.
- Entregas de comunicação `failed` ou `unknown` ligadas ao caso.
- Falhas persistidas de upload/processamento documental.
- Lançamentos financeiros `draft`, somente para papéis autorizados.

## UI/UX Considerations

Uma coluna essencial em 375 px, com três níveis: Agora, Hoje e atenção, Planejamento. Ações só confirmam sucesso após persistência; mensagens de estado usam regiões anunciáveis e foco/teclado preservados.

## Integration Points

- `GET /workspace/summary`
- `POST /workspace/tasks`
- `PUT /workspace/tasks/{id}`
- página `frontend/src/app/dashboard/page.tsx`
- autorização e auditoria existentes em `workspace.py`

## Risks and Challenges

- Transformar o resumo em relatório amplo demais.
- Introduzir urgência não sustentada pelos modelos de documentos e financeiro.
- Regressão de isolamento por caso em consultas agregadas.
- Sobrescrever alterações preexistentes no checkout ainda não consolidado.

## Open Questions

Nenhuma questão de produto bloqueante. Índices só serão decididos após medição com PostgreSQL real.

## References

- [SQLAlchemy 2.0 — SELECT and Related Constructs](https://docs.sqlalchemy.org/en/20/core/selectable.html)
- Documentação local do Next.js 16 em `frontend/node_modules/next/dist/docs/`.

