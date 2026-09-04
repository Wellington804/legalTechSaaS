# Implementação dos itens 1–5

Esta execução substitui o escopo anterior de apenas hardening. A auditoria de 27/08 permanece como fotografia anterior, não como descrição da nova versão.

## Contratos e divisão

1. Contas: sessões revogáveis, equipe/RBAC, convites, recuperação/verificação, MFA, escritório e limites de assinatura. Migration `20260827_0002`.
2. Núcleo: clientes, casos/partes, agenda, documentos privados/versionados, biblioteca, publicações, horas/despesas/honorários, busca e visão diária. Migration `20260827_0003`.
3. Operação: recuperação de entregas e recibos, configuração de segredos, backup/restore, CI e execução VPS. Migration `20260827_0004`.
4. Integração: interfaces conectadas ao núcleo; portal e comunicação vinculados ao cliente/caso; conectores com origem explícita. Migration `20260827_0005`.
5. Revisão independente, testes com PostgreSQL restrito, testes do navegador, build e atualização do runtime local.

Os contratos anteriores permanecem preservados até a migração do consumidor. Não habilitar protótipos para contornar implementação ausente. Não confirmar pagamentos, assinaturas, envios, publicações ou dados judiciais por timers, fixtures ou estado do navegador.

## Limites externos

- Cloudflare, domínio e VPS dependem de acesso e configuração do operador.
- Resend/Evolution/Sentry dependem de credenciais e homologação; os adaptadores não enviam mensagens reais nesta execução.
- Cobrança automática do SaaS e assinatura por provedor exigem escolha/contratação. Registro de honorários não é confirmação de cobrança por um banco. Integridade de documento não é certificado ICP-Brasil.
- Dados públicos judiciais têm cobertura limitada. Não transformar automaticamente uma movimentação em prazo fatal sem revisão profissional.
- IA exige habilitação explícita e autorização de tratamento; conteúdo gerado precisa de revisão humana. Não substituir fontes por citações inventadas.

## Entrega por item solicitado

| Item | Implementação no código | Limite atual |
|---|---|---|
| 1 — corrigir erros | Núcleo demonstrativo substituído nas áreas operacionais; erros de contratos/revisão, falsos sucessos, concorrência, permissões e datas corrigidos | As migrations novas ainda não foram executadas em banco real nesta rodada; não afirmar que todos os defeitos possíveis foram eliminados |
| 2 — segredos | `.env` ignorado e `.env.example` com todos os campos de credenciais vazios, flags de provedores desligadas | Preencher na VPS; token de source maps só na CI; instâncias WhatsApp por escritório são cifradas no banco |
| 3 — VPS | Compose privado, startup migrations/grants, runtime restrito, Caddy, workers/Beat, lock Python com hashes, CI, backup/restore e health checks | Sem deploy, teste real de restore, medição de capacidade, TLS/domínio ou homologação de provedores |
| 4 — SaaS | Cliente→caso→tarefa→documento→honorário→comunicação; contas, convites, MFA, quotas, exportação, trial/read-only e suporte auditado | Contratação e cancelamento assistidos; cobrança automática depende de escolher e integrar provedor |
| 5 — Central | Central diária, cliente/caso 360°, documentos/modelos, pesquisa na carteira, acervo, DataJud, portal e assistência textual por IA | Assinatura externa, entrada bidirecional de WhatsApp/e-mail e recursos preditivos não estão implementados; não são simples credenciais faltantes |

## Mapa da aplicação implementada

| Interface / domínio | API e persistência | Regras importantes |
|---|---|---|
| `/account/access`, `/dashboard/account` | `auth.py`, `account.py`; users, tenants, auth_sessions, account_tokens | Cookie HttpOnly + sessão persistida, logout/revogação, senha, verificação e MFA; tokens de uso único/expirantes, hashes, locks contra replay |
| Equipe | `/account/team`; team_invitations | Administrador gerencia; sócio consulta; último administrador e quota de assentos protegidos |
| Clientes e oportunidades | `/workspace/clients`; workspace_clients | Cadastro único/etapas, edição com revisão, importação JSON ≤200 atômica e deduplicada |
| Cliente/caso 360° | `/workspace/cases?client_id=…`, `/workspace/cases/{id}`; cases, parties, case_access | Visibilidade por caso, responsável e membros; FKs compostas impedem vínculos entre escritórios |
| Agenda e prazos | `/workspace/tasks` | Status persistido, responsável, data com timezone e revisão manual; central filtra pendências antes de limitar resultados |
| Documentos/modelos | `/workspace/documents`, `/workspace/templates` | Texto e anexos privados PDF/TXT/DOCX ≤10 MB, versões, conflito de edição; quota inclui versões; cópia de modelo exige salvar/revisar |
| Financeiro consolidado | `/workspace/ledger` | Decimal, rascunho/efetivação, baixa manual com UUID e evidência, estorno preserva histórico; somente admin/sócio |
| Biblioteca/publicações | `/workspace/library`, `/workspace/publications` | Fonte e data, confirmação de leitura; consulta pública DataJud deduplicada, sem criar prazo automaticamente |
| Conflitos, busca, indicadores | `/workspace/conflicts`, `/workspace/search`, `/workspace/summary`, `/workspace/analytics` | Somente registros autorizados, sem scores inventados ou previsão de êxito |
| Comunicações | `/engagement/cases/{id}/messages`, `/engagement/channels` | Destinatário derivado do cadastro; idempotência e limites; credenciais exclusivas por tenant; estado registrado ≠ entregue |
| Portal | `/client-portal`; portal_grants, portal_checklist, case_messages | Convite de uso único 24h, grant até7d, sessão até8h, revogação, mensagens e apenas documentos compartilhados; uploads com origem portal preservada |
| IA textual | `/engagement/documents/{id}/assist` | Opt-in do escritório + confirmação do usuário, texto limitado, quota, snapshot/hash, resultado não salvo e aviso se documento mudou |
| Assinatura SaaS assistida | `/account/subscription`, CLI `app.cli.account_support` | Trial, quotas, somente leitura após período; pedidos comerciais persistidos; nunca confirma pagamento do SaaS via navegador |
| Auditoria | `/audit/logs`, audit_logs | Eventos reais, sem alegação de blockchain, selagem inviolável ou certificação |

As camadas estão em `frontend/src/components/workspace`, `backend/app/api/v1/endpoints`, `backend/app/services` e `backend/app/models`. Migrations: `0002` contas → `0003` núcleo → `0004` recuperação → `0005` comunicações/portal. Nenhuma migration antiga em produção foi revertida nesta execução.

## Segurança e operação corrigidas

- FORCE RLS nos novos domínios; identificador do tenant na query e nas relações; funções públicas de recuperação resolvem somente tenant por hash antes de consultas com GUC/lock.
- Histórico de versões não pode ser alterado/apagado pelo runtime; lançamentos, mensagens e grants preservados. Auditoria não é editável pelo papel da aplicação.
- Confirmação MFA atualiza a sessão corrente; repetição do mesmo TOTP não abre sessões simultâneas. Em produção, dados do escritório exigem e-mail verificado e MFA privilegiado.
- Entregas persistidas mas não publicadas na fila são recuperadas; processamento abandonado é reconciliado. Resultado ambíguo WhatsApp não é reenviado. E-mail respeita a janela de idempotência do Resend.
- Callbacks antecipados ficam em inbox com identificadores hasheados; o tenant da instância Evolution precisa corresponder ao da entrega. Legado sem recurso vinculado falha antes de chamar o provedor.
- API pública de IA antiga e módulos de assinatura/OAB/calculadora/simulação continuam bloqueados; não há fallback com dado fictício nas novas áreas.
- Exportação JSON transmite registros e versões/arquivos sem truncar em 200; é leitura ao vivo, não snapshot consistente nem substituto de backup. Armazenamento de anexos em PostgreSQL simplifica o restore, mas exige medir espaço/IO e considerar que versão corrente e histórico ocupam espaço físico.

## Dependências externas e trabalho que não foi entregue

1. **Cobrança automática e assinatura eletrônica:** ainda precisam de escolha de provedores e implementação/homologação de checkout/webhooks/identidade/evidências. Foram solicitadas as escolhas ao usuário. O fluxo assistido não é apresentado como cobrança automática.
2. **WhatsApp/e-mail bidirecionais:** esta versão envia mensagens vinculadas e recebe recibos de entrega. Conversa bidirecional existe no portal. Receber mensagens externas, lidar com anexos e atribuir conversa ambígua a um caso continua pendente.
3. **Cobertura judicial:** DataJud público não é DJEN, Domicílio Judicial, autos completos ou peticionamento. Integrações adicionais exigem fontes, termos e contratos. Cálculo de prazo, OAB/FGV e jurimetria preditiva continuam indisponíveis.
4. **Conformidade comercial:** termos, política de retenção/exclusão, resposta a incidentes, suporte/SLA e revisão jurídica precisam de definição do operador; não houve certificação LGPD.
5. **Interface:** listas têm limites explícitos; exportação é completa. Paginação avançada, caixa unificada externa e calendários de tribunais não foram simulados. Sem alteração de identidade visual; foram trocados os consumidores demonstrativos por formulários operacionais.

## Verificação desta execução

- Typecheck TypeScript e build Next.js passaram; o Windows usou fallback SWC/WASM com aviso do binário nativo. Isso não equivale a build Docker/Linux.
- Seis testes frontend existentes passaram (HTTP, privacidade, gates e escape de impressão).
- Backend final: **67 testes executados pelo runner: 54 aprovados e 13 ignorados**, todos estes últimos opt-in de PostgreSQL. Inclui novas regressões de MFA Unicode, fontes externas malformadas, snapshot de IA, suporte comercial e isolamento de identificadores. Nenhuma mensagem externa foi enviada.
- `frontend/tests/workspace-ui.cjs` passou no bundle recompilado servido temporariamente em `127.0.0.1:3109`: desktop/375 px, cliente/caso, documentos com controle de versão, comunicação, conta, onboarding de segurança e equipe admin versus sócio. Todas as respostas de API são fixtures locais do teste; **não é E2E com backend/banco**. O servidor temporário foi encerrado ao concluir a verificação.
- Geração SQL offline de todas as migrations até `20260827_0005` passou. Não comprova execução de DDL, RLS, grants ou constraints no PostgreSQL.
- Auditoria da lock Python Linux/Python 3.11: nenhuma vulnerabilidade conhecida reportada; instalação com hashes configurada no Docker e CI. Compose positivo com dados sintéticos e rejeição de segredos vazios passaram.
- Scripts de operação tiveram validação sintática e preflights de entradas inválidas. `deploy/tests/test-backup-postgres.sh` executou o script real de backup com comandos externos simulados, validando o arquivo temporário de decifragem, checksum e uso de lock; dump, cópia externa e restore reais não foram executados.

### Bloqueio local

O Docker Engine local não responde no pipe `dockerDesktopLinuxEngine`; tentativas de abertura do Docker Desktop encerraram sem deixar o daemon ativo. Os logs registraram uma ação externa de restauração para padrões de fábrica; essa ação **não foi executada pelo agente**. Não foi recriado banco, removido volume nem aplicado schema no banco da aplicação. Antes de qualquer reinício da stack, inspecionar volumes/containers existentes e esclarecer a preservação dos dados locais.

Continuam pendentes: PostgreSQL descartável restrito (duas contas/tenants, RLS, concorrência e portal), smoke E2E real, imagem Docker final, restore isolado, runtime local atualizado e homologação de todos os serviços externos. **NO-GO para uso de dados reais/comercialização até fechar esses gates e os limites de produto contratados.**

Última checagem: portas locais 3000/8000 sem listener; somente o servidor temporário de teste estava ativo. Não foi feito commit, push, deploy ou envio a provedores. O código foi mantido no worktree junto às alterações pré-existentes.

## Fontes dos contratos externos

- [Resend — idempotência](https://resend.com/docs/dashboard/emails/idempotency-keys): janela do provedor para repetição segura.
- [CNJ — acesso DataJud](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) e [endpoints](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/): consulta pública de metadados e tribunais.
- [Gemini — generateContent](https://ai.google.dev/api/generate-content): contrato REST usado pelo conector textual. O modelo concreto permanece campo de configuração, não uma promessa de disponibilidade.
