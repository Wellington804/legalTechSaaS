# Auditoria funcional e prontidão SaaS — 27/08/2026

> Registro histórico. Não use esta fotografia como estado atual; consulte README, CI e runbooks vigentes.

## Parecer executivo

**NO-GO para comercialização do produto completo e para uso de dados reais nos módulos demonstrativos.** Existe uma base real de autenticação, tenant, migrations, auditoria parcial e comunicação assíncrona. A maior parte do produto de escritório ainda é protótipo. Publicar containers na VPS não resolve essa diferença.

Escopo: código atual e processo local. A skill `orquestracao-de-agentes` dividiu a auditoria entre backend, frontend e infraestrutura, com integração/verificações pelo agente principal. Não houve pentest completo, auditoria externa de VPS, revisão jurídica de modelos ou homologação dos provedores. Nenhuma mensagem real foi enviada.

Critério: uma funcionalidade operacional autentica/autoriza, persiste na fonte correta, recupera o resultado e trata falhas sem falso sucesso. React state, fixtures e `localStorage` não atendem ao uso compartilhado por um escritório.

## 1. Quais módulos funcionam realmente?

| Módulo / rotas | O que existe de fato | Situação de produção |
|---|---|---|
| Cadastro/login/sessão | Tenant/User persistidos, senha com hash, cookie HttpOnly, usuário/escritório ativo, limites Redis | Base funcional; faltam ciclo de conta, revogação de sessão e onboarding completo |
| `/dashboard` | Perfil autenticado e readiness de banco/Redis | Painel técnico real; indicadores de negócio do antigo dashboard são demo |
| `/dashboard/admin/users` | Apenas usuário da sessão; mutações são no-op | Sem gestão de equipe/RBAC completo; não basta configuração |
| `/dashboard/crm` | Leads, detalhes e kanban em memória | Falta cadastro persistido, histórico e conversão |
| `/dashboard/tracker` | Lista fixa de magistrados e dados demonstrativos | Não é acompanhamento processual real; núcleo de casos/processos ainda ausente |
| `/dashboard/peticoes` | Texto gerado localmente por timer; cópia funciona | Sem documentos persistidos nem protocolo; DOCX é alerta |
| `/dashboard/petitions/editor` | Editor/exportação locais; autosave apenas muda relógio | Não é repositório multiusuário/versionado |
| `/dashboard/templates` | Catálogo estático backend e substituição local de variáveis | Utilitário parcial; sem CRUD/versionamento por escritório ou revisão jurídica |
| `/dashboard/brand` | Configuração/preview/exportação local | Sem identidade persistida do escritório; IA não homologada |
| `/dashboard/assinaturas` | Documentos em `localStorage` global; impressão e alguns exports | Não é serviço real de assinatura; faltam arquivos privados, identidade, tokens e provas |
| `/sign/[id]` | Signatários fixos, token Base64 de e-mail, OTP não vazio, timer | Não há OTP/biometria/ICP-Brasil real; não liberar como assinatura válida |
| `/verify/[id]` | Consulta mocks/`localStorage` | Não verifica integridade/autoria de um arquivo |
| `/dashboard/audit` | Fixtures e cadeia aprovada por timer | Tela demo. API `/audit/logs` e gravação OAB são reais, porém parciais; não blockchain/selagem inviolável |
| `/dashboard/financeiro` | Faturas/totais/filtros locais | Sem contas persistidas, baixa confiável ou conciliação |
| `/dashboard/financial` | Segunda experiência financeira em React | Duplicação; consolidar ao implementar o financeiro real |
| `/dashboard/calculadora` | Fórmulas/endpoint com fatores fixos | Experimental; faltam índices/versionamento e homologação jurídica |
| `/dashboard/conflitos` | Pontuação por palavras-chave e hash aleatório | Não consulta carteira real; não usar para aceitar casos |
| `/dashboard/analytics/judge-profiling` | Perfis e scores fixos; upload lê nome, não conteúdo | Sem base, proveniência ou metodologia validada |
| `/dashboard/simulator` | Simulação roteirizada; voz do navegador | Não é modelo homologado ou previsão de êxito |
| Busca global | Resultados hardcoded | Sem índice dos registros autorizados |
| `/portal` | Consulta/chat híbridos com fixtures; upload/download não implementados | Sem identidade de cliente, caso autorizado, arquivos ou cobrança real |
| `/oab-hub`, checklist e declarações | Backend persiste requerimento/checklist/rascunho; telas usam estado local | Parcial; sem submissão OAB, consulta FGV ou certificação |
| OAB calculadora/SUA/honorários | Taxas, descontos e conteúdo fixos | Exige fontes por seccional/vigência e revisão profissional |
| Storage backend | Respostas de upload/metadados simuladas | Sem armazenamento privado efetivo |
| `/api/ai/generate` | Havia Gemini sem auth/quotas adequadas e fallback de chave pública | Deve ficar bloqueado até implementação segura; não basta inserir chave |
| `/api/v1/notifications` | Schema/fila/adaptadores/webhooks reais | Dispatch bloqueado em produção; exige recurso/destinatário autorizado e homologação |

Evidências: `frontend/src/app/**/page.tsx`, `frontend/src/context/user-context.tsx`, `frontend/src/components/layout/{header,notification-popover,global-search-modal,tenant-switcher}.tsx`, `backend/app/api/v1/router.py`, `backend/app/api/v1/endpoints/*.py`, `backend/app/models/*.py`, `backend/app/services/{oab_service,audit_service,notification_service,tasks}.py`.

O banco local tem 14 tabelas incluindo `alembic_version`, mas não um domínio completo de clientes/processos/documentos/financeiro. Tabelas de métricas ou embeddings não provam uso operacional das telas.

## 2. Configuração versus implementação

| Integração | Configuração/homologação | Código ainda necessário |
|---|---|---|
| Cloudflare/domínio | Domínio, DNS, DNSSEC, proxy, TLS Full (strict), cache, firewall/allowlist | Validar Caddy/renovação/acesso externo; sem novo módulo de produto |
| Resend | Domínio/remetente verificado, SPF/DKIM, política DMARC, chave, webhook e entrega/replay | Vincular destinatário/conteúdo ao recurso autorizado; o envio atual é genérico e permanece bloqueado |
| Evolution Go | Licença, instância, pareamento, credenciais, recibos e reconexão da versão pinada | Vínculo por escritório/caso; configuração global não equivale a WhatsApp por tenant |
| Sentry | Projetos, DSNs, releases, source maps via secret CI, alertas e evento sanitizado | Correções de privacidade/worker desta rodada; tracing ficará desligado até revisão específica |
| Banco/fila | Credenciais, migrations, runtime sem bypass RLS, volumes/healthchecks | Implementar domínios ausentes, não apenas configurar URLs |
| Documentos/assinaturas | Escolher armazenamento privado/provedor | Upload validado, autorização, versionamento, tokens expirantes, identidade/evidências |
| Tribunais/publicações/OAB | Fontes, cobertura, termos e credenciais | Conectores, proveniência, deduplicação, reconciliação e revisão de prazos |
| Cobrança SaaS | Provedor comercial e regras de planos | Trial, assinatura, limites, cancelamento, inadimplência e webhooks idempotentes |

Separar cobrança **do SaaS** do financeiro de honorários **do escritório**. Separar e-mail transacional da plataforma de comunicações enviadas em nome de cada escritório.

## 3. Mudanças para a VPS

Antes de piloto com dados reais:

1. Manter protótipos e dispatch não vinculado bloqueados. Não resolver ausência de domínio ativando flags.
2. Usar Compose de produção: Caddy como única entrada pública, serviços privados, segredos únicos, runtime não-root e PostgreSQL `NOSUPERUSER NOBYPASSRLS`.
3. Configurar domínio/TLS/firewall; testar bloqueio do IP direto e confiança de proxy. Não aplicar cache público a API/páginas privadas.
4. Testar dois tenants, IDs cruzados, commit/rollback e concorrência com role restrito; teste unitário de SQL não basta.
5. Automatizar backups criptografados externos, retenção e alertas; comprovar restore incluindo permissões/arquivos. Definir RPO/RTO com o negócio.
6. Medir CPU/memória/IO da VPS escolhida e estabelecer limites/alertas. Rotação de logs e limites de processos reduzem risco; não substituem capacidade medida. Evitar build concorrendo com banco ativo.
7. Pipeline de testes/typecheck/build, auditoria de dependências/imagens, release identificável e rollback compatível com schema. Falta estratégia de lock das dependências Python transitivas.
8. Homologar Sentry para API/worker/frontend e monitorar uptime, fila, entregas paradas, disco e backups. Sentry sozinho não cobre todos esses controles.
9. Completar recuperação/verificação de e-mail, convites, desativação, revogação de sessão e MFA privilegiado. Definir permissões por operação/caso antes de equipe multiusuário.
10. Formalizar privacidade, incidentes, retenção/exportação/exclusão e contrato de tratamento de dados. Hardening não equivale a certificação LGPD.

### Limites de confiabilidade das notificações

Ainda falta recuperação durável de entregas persistidas mas não enfileiradas e de estados `processing` abandonados. Callback recebido antes de persistir o ID do provedor também precisa de reconciliação. Definir outbox/reconciliador antes de habilitar produção. WhatsApp com resultado ambíguo não deve reenviar automaticamente sem contrato de idempotência.

## 4. Evolução comercial SaaS

Recomendo **monólito modular**, reaproveitando FastAPI/PostgreSQL/Next. Não há necessidade demonstrada de microserviços ou Kubernetes.

Completar um fluxo: **cliente → atendimento/caso → processo → prazo/tarefa → documento → honorário → comunicação**. Os módulos devem compartilhar registros persistidos, não manter cópias divergentes no navegador.

- Primeiro: clientes/partes, conflitos reais, processos, prazos/tarefas, documentos e permissões; incluir import/export e trilha de alterações.
- Segundo: honorários, recebimentos confirmados e portal autenticado. Consolidar as duas telas financeiras na experiência escolhida.
- Terceiro: onboarding, planos, cobrança, quotas de usuários/armazenamento/mensagens, suspensão sem perda de dados e suporte administrativo auditado.
- Quarto: conectores judiciais, assinatura externa, pesquisa e IA com fontes/revisão. Medir custo por tenant antes de oferecer uso ilimitado.

OAB/iniciação profissional pode ser complementar; não usaria isso como núcleo do SaaS de gestão. IA/jurimetria não compensam documentos ou prazos sem persistência confiável.

## 5. Central do Advogado — funcionalidades futuras

| Prioridade | Funcionalidade | Condição de segurança/qualidade |
|---|---|---|
| Alta | Central diária de prazos, audiências, tarefas e publicações | Origem, responsável, calendário aplicável e revisão; sem promessa de cálculo infalível |
| Alta | Cliente/caso 360°, partes e conflitos | Cadastro único e permissões por caso/equipe |
| Alta | Documentos, modelos versionados e assinatura integrada | Arquivos privados, identidade e evidência verificável |
| Alta | Caixa WhatsApp/e-mail vinculada ao caso | Conectores por escritório, opt-outs quando aplicáveis e segregação |
| Média | Biblioteca/pesquisa de jurisprudência e legislação | Fonte, data, link e cobertura; acervo privado segregado |
| Média | Captura de andamentos/publicações | Adaptadores por fonte, deduplicação, indisponibilidade explícita e reconciliação |
| Média | Horas, despesas, honorários e prestação de contas | Valores decimais, estornos, histórico e conciliação |
| Média | Portal e checklist de documentos do cliente | Identidade própria, casos autorizados e compartilhamento expirante |
| Posterior | IA para resumo de autos, tarefas e redação | Revisão humana, citações verificáveis, contrato de processamento e controle de custos |
| Posterior | Jurimetria e análise de carteira | Base confiável, amostragem, metodologia e limites estatísticos |

DataJud público fornece metadados de processos públicos; não é acesso irrestrito a autos/segredo de justiça nem fonte única de prazos. DJEN e Domicílio Judicial Eletrônico têm finalidades distintas. Validar termos e cobertura antes de prometer integração universal ou peticionamento automático.

## Correções e verificações desta rodada

### Correções implementadas

| Defeito confirmado | Correção | Arquivo principal |
|---|---|---|
| `where_by` inexistente e perda do GUC após commit/rollback | `filter_by`, savepoint/flush e commit no endpoint antes de publicar tarefa | `backend/app/services/notification_service.py`, `backend/app/api/v1/endpoints/notifications.py` |
| Corrida entre recibos e finalização WhatsApp | Lock de linha, identidade da tentativa e conclusão da tentativa original sem reenvio | `backend/app/services/{notification_service,tasks}.py` |
| Worker dependia somente de RLS | Predicado tenant explícito em seus três selects | `backend/app/services/tasks.py` |
| Protótipos ativáveis em produção e auditoria sem restrição por papel | Config recusa flag em staging/produção; logs só para admin/partner do tenant | `backend/app/core/config.py`, `backend/app/api/v1/endpoints/audit.py` |
| URLs locais erradas, repetição de escrita e parse de 204 | Cliente HTTP compartilhado, origem correta, retry apenas GET/HEAD, resposta vazia suportada | `frontend/src/lib/{api-client,api}.ts` e consumidores |
| Login sem erro de rede e logout com falso sucesso | Feedback explícito e estado preservado quando logout falha | `frontend/src/context/user-context.tsx` |
| API com falha substituída por dados fictícios | Portal/templates/calculadora mostram falha; não carregam fallback de sucesso | Páginas correspondentes em `frontend/src/app` |
| Administração no-op e alertas fictícios no ambiente endurecido | Mutações indisponíveis, demos ocultas, um dono de Ctrl+K e rotas corrigidas | `admin/users`, `header.tsx`, `command-palette.tsx` |
| IA sem fronteira segura/chave pública | Endpoint 503 e retirada de chamada direta/fallback Gemini no browser | `api/ai/generate/route.ts`, `dashboard/brand/page.tsx` |
| HTML de usuário interpolado na impressão | Escape de todos os campos, popup sem opener e teste com payload malicioso | `print-safety.ts`, `dashboard/assinaturas/page.tsx` |
| Demonstração confundida com certificação/envio | Banner global, disclaimer em impressão/PDF e criação local sem anúncio de envio | `app/layout.tsx`, `dashboard/assinaturas/page.tsx` |
| Sentry não cobria worker e filtro não cobria todo payload configurado | Inicialização no worker, remoção de metadados/credenciais em URLs e tracing fixado em zero | `backend/app/core/{observability,celery_app}.py`, configurações Sentry frontend |
| Node 20 EOL, CSP regional/logs sem rotação | Node 24 pinado, CSP US/DE, logs 10 MB × 3 e limite 256 processos/serviço | `frontend/Dockerfile`, `deploy/Caddyfile`, `docker-compose.prod.yml` |
| README afirmava recursos inexistentes | Documentação alinhada à implementação e execução local real | `README.md`, `docs/production-runbook.md` |

### Evidências verificadas

- Backend: **22/22 testes passaram, sem skips**, com código atual montado read-only no container e PostgreSQL descartável. Inclui cinco testes reais de GUC, RLS, duplicata concorrente, eventos concorrentes e worker WhatsApp com transporte simulado; nenhuma mensagem externa.
- Papel PostgreSQL confirmado não-superuser/`NOBYPASSRLS`, RLS e FORCE RLS nas tabelas de entregas/eventos. Consulta a entrega de outro tenant sem filtro tenant e consulta sem GUC não retornam a entrega.
- Frontend: **6/6 testes passaram** (HTTP, sanitização Sentry, gates de protótipos, escaping de impressão e disclaimers PDF). Typecheck e build Next.js passaram; imagens Docker de backend/frontend reconstruídas.
- Navegador Chromium: login/cookie HttpOnly real, readiness correto, Ctrl+K único, erro de logout preservando sessão, administração indisponível, falhas de templates/portal sem fixtures, IA 503 e dashboard sem overflow em 375 px. Sem erros JavaScript de página no fluxo exercitado.
- `npm audit`: zero vulnerabilidades conhecidas reportadas no snapshot. Não equivale a pentest nem scanner completo de imagens/OS.
- Compose de produção validado com variáveis sintéticas; Caddy validado sem acesso a provedores. Worker local responde `pong`.
- Runtime frontend atualizado para Node **24.19.0**; Sentry CLI 2.58.6 disponível na imagem. DSNs e provedores permanecem desligados no ambiente local.
- API e worker em execução possuem o mesmo hash de `tasks.py` que o código auditado. A execução local mantém protótipos habilitados apenas para avaliação, portas em loopback e dispatch desligado; não é uma implantação de produção.
- Revisão independente cobriu backend/cliente HTTP e patches frontend; integração também revisou a frente de infraestrutura. Sem novo bloqueador identificado nos patches para o escopo limitado e com gates mantidos.
- O banco/volume/rede exclusivos dos testes foram removidos após repetição independente. Dados da aplicação local preservados.

Testes reproduzíveis: `backend/tests/test_notification_postgres.py` requer `AUDIT_TEST_DATABASE_URL` apontando a um banco **descartável já migrado**, com grants de runtime; sem variável é explicitamente ignorado. `frontend/tests/local-smoke.cjs` requer stack local, módulo Playwright disponível e `AUDIT_LOGIN_EMAIL`/`AUDIT_LOGIN_PASSWORD`; não criar credenciais reais nesses arquivos.

As funcionalidades propostas nas seções 4–5 são roadmap, não implementações entregues nesta auditoria. Permanecem pendentes o núcleo jurídico persistido, RBAC completo, ciclo de contas, revogação de sessão, reconciliação durável de notificações, contratação/configuração de infraestrutura e homologações externas. **O resultado continua NO-GO comercial.**

## Fontes primárias consultadas

- [Node.js — suporte](https://nodejs.org/en/about/previous-releases): Node 20 EOL; usar LTS suportado.
- [Cloudflare — Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/): certificado de origem.
- [Resend — domínios](https://resend.com/docs/dashboard/domains/introduction): SPF/DKIM e verificação do remetente.
- [ANPD — guia de segurança](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-vf.pdf): controles de proteção de dados, não certificação do sistema.
- [CNJ — DataJud](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) e [comunicações processuais](https://www.cnj.jus.br/programas-e-acoes/processo-judicial-eletronico-pje/comunicacoes-processuais/): cobertura e distinção das fontes.
- [ITI — conceitos de assinatura](https://validar.iti.gov.br/conceitos.html): identidade/integridade não se comprovam por selo visual/estado do navegador.
