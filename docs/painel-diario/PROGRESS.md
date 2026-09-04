# Painel Diário — Progress

## Status: Implemented and locally validated

## Quick Reference

- Research: [`RESEARCH.md`](RESEARCH.md)
- Implementation: [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
- Design aprovado: [`../design-painel-diario.md`](../design-painel-diario.md)

---

## Phase Progress

### Phase 1: Visão diária no backend

**Status:** Completed

#### Tasks Completed

- Pesquisa do fluxo atual, contratos, permissões e padrões SQLAlchemy.
- Resumo convertido para agregações SQL e `NOT EXISTS`.
- Fila autorizada e limitada compilada como uma consulta PostgreSQL com `UNION ALL`.
- Fuso do tenant, sinais operacionais e ações permitidas incluídos no contrato.
- 15 testes focados do backend aprovados.
- Migração `20260901_0017` aplicada do zero em PostgreSQL 16 isolado.
- Consulta `UNION ALL` executada com a role real `NOBYPASSRLS`.

#### Decisions Made

- Estender `/workspace/summary` de forma compatível.
- Manter consultas sequenciais na mesma `AsyncSession`; ela não é segura para tarefas concorrentes.
- Não adicionar índices antes de medição.

#### Blockers

- Nenhum.

### Phase 2: Painel operacional no frontend

**Status:** Completed

#### Tasks Completed

- Conteúdo essencial desacoplado de analytics e atividade secundária.
- Seções Agora, Hoje e atenção e Planejamento implementadas.
- Conclusão, reagendamento e criação da próxima ação persistem antes de confirmar sucesso.
- Criação de tarefa usa UUID estável por tentativa; mutações tratam revisão concorrente.
- Estados de carregamento, vazio, erro, conflito e permissão implementados.
- Teste Playwright do bundle compilado aprovado, inclusive em 375 px.

#### Decisions Made

- Manter a página como Client Component porque as ações exigem estado e eventos do navegador.
- Carregar membros somente ao abrir o formulário de criação.

#### Blockers

- Nenhum.

### Phase 3: Legado e validação

**Status:** Completed

#### Tasks Completed

- Confirmado que o router atual já não registra o endpoint legado `/dashboard`.
- Removidos o serviço frontend e os modelos/endpoints simulados sem consumidores.
- Removida a importação residual do modelo legado no ambiente Alembic.
- Backend: 175 testes aprovados e 36 ignorados por dependerem de PostgreSQL/renderer no primeiro passe local.
- Frontend: 13 testes Node, lint e build aprovados.
- Playwright do bundle compilado aprovado com mutações contratuais e responsividade.
- `git diff --check` aprovado para os arquivos da feature.

#### Decisions Made

- Manter as tabelas históricas do dashboard nesta entrega; removê-las exigiria uma migração destrutiva separada.

#### Blockers

- Nenhum.

---

## Session Log

### 01/09/2026

- Design aprovado e persistido.
- Pesquisa técnica e plano faseado concluídos.
- Fases 1 a 3 concluídas.
- Validação real da migration revelou e removeu a importação Alembic residual do dashboard legado.

## Files Changed

- `docs/design-painel-diario.md`
- `docs/painel-diario/RESEARCH.md`
- `docs/painel-diario/IMPLEMENTATION.md`
- `docs/painel-diario/PROGRESS.md`
- `backend/alembic/env.py`
- `backend/alembic/versions/20260901_0017_task_idempotency.py`
- `backend/app/api/v1/endpoints/workspace.py`
- `backend/app/models/workspace.py`
- `backend/app/schemas/workspace.py`
- `backend/tests/test_workspace.py`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/tests/workspace-ui.cjs`
- Removidos: `backend/app/api/v1/endpoints/dashboard.py`, `backend/app/models/dashboard.py` e `frontend/src/lib/dashboardService.ts`.

## Architectural Decisions

- PostgreSQL continua como fonte única; sem projeção materializada.
- O endpoint essencial permanece no módulo `workspace`.
- A idempotência de criação usa uma chave por tenant no próprio registro de tarefa; não foi criado serviço auxiliar.

## Lessons Learned

- O painel atual já usa contratos reais, mas há código legado simulado fora do router.
- A validação online da migration é necessária para capturar imports de modelos que a geração SQL offline pode não exercitar.

## Gates ainda externos

- Meta p95 de 2 s/500 ms depende de carga representativa e telemetria de produção.
- Backup/restauração, disponibilidade e celular físico continuam como gates de homologação.
