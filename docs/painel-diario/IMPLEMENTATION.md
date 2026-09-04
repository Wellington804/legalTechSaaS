# Painel Diário — Implementation Plan

## Overview

Estender a visão diária do módulo `workspace`, reutilizar as mutações auditadas de tarefas e reorganizar a página inicial em torno da próxima ação, sem novas integrações, dependências ou infraestrutura.

## Prerequisites

- Design aprovado em [`../design-painel-diario.md`](../design-painel-diario.md).
- Alterações preexistentes do checkout preservadas.
- Testes backend executados no ambiente Python existente.
- Typecheck e testes Node executados no frontend.

## Phase Summary

1. Contrato e consultas autorizadas do resumo diário.
2. Interface e ações rápidas responsivas.
3. Remoção do legado simulado e validação integrada.

---

## Phase 1: Visão diária no backend

### Objective

Entregar em `/workspace/summary` contadores SQL e uma fila limitada, determinística e autorizada.

### Rationale

É a fonte única necessária para a interface e remove cálculos não limitados antes de ampliar o painel.

### Tasks

- [x] Definir serialização mínima dos itens de atenção.
- [x] Substituir contagens em memória por agregações SQL.
- [x] Consultar casos sem tarefa com `NOT EXISTS`.
- [x] Incluir tarefas, publicações, falhas de comunicação/documento e rascunhos financeiros permitidos.
- [x] Respeitar fuso do tenant, tenant, ACL de caso e papéis financeiros.
- [x] Adicionar testes pequenos de ordenação, fuso e autorização estrutural.

### Success Criteria

Uma requisição retorna conteúdo diário limitado e ordenado sem carregar coleções completas; testes focados passam.

### Files Likely Affected

- `backend/app/api/v1/endpoints/workspace.py`
- `backend/tests/test_workspace.py`
- `backend/tests/test_workspace_postgres.py`, somente se o banco de auditoria estiver disponível.

---

## Phase 2: Painel operacional no frontend

### Objective

Permitir identificar, concluir, reagendar e cadastrar a próxima ação diretamente na página inicial.

### Rationale

Converte a visão backend em valor percebido sem duplicar módulos especializados.

### Tasks

- [x] Consumir apenas o resumo para o conteúdo essencial.
- [x] Renderizar Agora, Hoje e atenção, Planejamento.
- [x] Implementar concluir e reagendar com `expected_revision`.
- [x] Implementar formulário curto de próxima ação com processo fixado.
- [x] Tratar `401`, `403`, `409`, `422`, rede e `5xx` sem falso sucesso.
- [x] Preservar teclado, foco, região anunciável e viewport de 375 px.
- [x] Adicionar teste de contrato/estrutura segundo o padrão Node existente.

### Success Criteria

O fluxo essencial funciona no dashboard, só confirma após persistência e passa no typecheck/testes focados.

### Files Likely Affected

- `frontend/src/app/dashboard/page.tsx`
- `frontend/tests/workspace-ui.cjs`

---

## Phase 3: Legado e validação

### Objective

Eliminar caminhos simulados e verificar o fluxo completo sem ampliar o escopo.

### Rationale

Fallback fictício e código morto contradizem o contrato de confiabilidade do painel.

### Tasks

- [x] Confirmar referências e remover serviço/endpoint/modelo legado quando seguros.
- [x] Verificar que a rota antiga falha fechada.
- [x] Rodar testes backend, testes Node, lint, build e Playwright proporcionalmente ao ambiente.
- [x] Validar `git diff --check` e revisar somente os arquivos desta feature.
- [x] Registrar limitações de performance e homologação externa não executadas.

### Success Criteria

Nenhum dado simulado participa do runtime; verificações locais passam ou têm bloqueio objetivo documentado.

### Files Likely Affected

- `frontend/src/lib/dashboardService.ts`
- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/models/dashboard.py`
- documentação e acompanhamento da feature.

---

## Post-Implementation

- [ ] Medir p95 com PostgreSQL representativo antes de alegar a meta de 2 segundos/500 ms.
- [ ] Homologar backup/restauração e disponibilidade no ambiente real.
- [ ] Validar a experiência em celular físico durante o piloto.

## Notes

- Fases pequenas foram escolhidas por padrão para reduzir risco no checkout sujo.
- Índices, paginação adicional e estados jurídicos novos permanecem fora do escopo até evidência de necessidade.
