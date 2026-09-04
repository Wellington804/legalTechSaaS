# PWA e Web Push — implementação

Escopo aprovado: aplicativo instalável e notificações reais para o advogado, aproveitando Next/FastAPI/PostgreSQL/Celery. Sem cache de documentos, APIs privadas ou HTML autenticado. Não é consulta jurídica offline.

## Divisão e contratos

1. Backend especialista: tabelas `push_subscriptions` e `push_deliveries`, migration `20260828_0007`, RLS/FKs, endpoints `/push`, provedor VAPID/pywebpush e fila durável. Alterações exclusivas em novos arquivos push, config, requirements/lock, alembic env/migration, router e testes push. Não editar endpoints workspace/engagement/auth/account nem Compose/grants; integração pelo agente principal.
2. Frontend especialista: manifesto/ícones originais, worker `/sw.js`, fallback público offline, registro/atualização controlada, instalação, painel na conta, inscrição/revogação/teste e limpeza no logout. Apenas frontend. Sem dados jurídicos em CacheStorage/IndexedDB/localStorage. Testes de worker, contratos e navegação responsiva.
3. Principal: integrar eventos reais, configurar worker/beat e segredos, grants, testes HTTP/PG, build e operação local; documentação e revisão de segurança.

## API congelada

- GET `/push/capabilities` autenticado -> `{enabled:boolean, public_key:string|null}`.
- GET `/push/subscriptions` -> `{items:[{id, label, endpoint_hash, created_at, last_seen_at, expires_at}]}` apenas inscrições ativas do usuário/escritório. Nunca devolver endpoint/chaves.
- POST `/push/subscriptions` -> `{id,label,endpoint_hash,created_at,last_seen_at,expires_at}`; corpo `{endpoint, keys:{p256dh,auth}, label, consent:true}`. Vínculo ao usuário/tenant e `request.state.auth_session.id` do servidor. Consentimento explícito; máximo10 dispositivos; não transferir endpoint entre usuários/escritórios.
- DELETE `/push/subscriptions/{id}` -> 204, revogação idempotente somente titular.
- POST `/push/subscriptions/{id}/test` -> 202 `{status:"queued"}`; envio via fila, não simular entrega. Limitar teste a5/h por usuário.

Payload push fixo, sem PII: `{title:"LegalFlow",body:"Há uma atualização no seu escritório. Entre no LegalFlow para consultar.",url:"/dashboard",tag:<opaque delivery id>}`. Mensagem de teste igualmente genérica. Clique somente mesma origem/rotas fixas, sem IDs de caso/token no payload.

## Eventos e entrega

Função backend `async enqueue_user_push(db, *, tenant_id, user_id, event_key, kind, case_id=None, task_id=None) -> int`, insere outbox por inscrição ativa na mesma transação de negócio, sem commit/chamada externa. `kind`: `task_assigned`, `portal_message`, `portal_document`, `test`. `event_key` dedupe por evento+inscrição; fonte é revalidada na entrega para impedir vazamento após revogação de ACL/reatribuição. Principal liga atribuição/mudança de tarefa e recebimento no portal ao responsável.

Worker Celery `push.dispatch_pending` a cada30s descobre apenas IDs/tenant por função SQL SECURITY DEFINER limitada, estabelece contexto RLS e faz claim concorrente. Não usar bypass RLS no runtime. Retry limitado/transiente com backoff, estados queued/processing/accepted/failed/expired/cancelled/unknown; timeout/crash ambíguo não vira sucesso nem reenvio ilimitado. 404/410 revogam inscrição. HTTP2xx significa aceito pelo serviço, não lido/entregue no celular. Idempotência e tags reduzem duplicação; não prometer exactly-once.

Inscrição dura até90dias/renovação, vinculada à sessão que autorizou. Expiração da sessão de navegação exige login ao abrir, mas não impede alertas genéricos com app fechado; revogação explícita da sessão/logout, inativação do usuário/tenant e revogação de acesso bloqueiam envio. Isso não prolonga autenticação. Principal revoga inscrições da sessão no logout; worker também verifica sessão revogada.

## Segurança e operação

VAPID: `WEB_PUSH_ENABLED=false`, `WEB_PUSH_VAPID_PUBLIC_KEY=`, `WEB_PUSH_VAPID_PRIVATE_KEY=`, `WEB_PUSH_VAPID_SUBJECT=`. Chave privada exclusivamente backend/worker. Config valida par de chaves P-256 e subject em produção. Criptografar endpoint e chaves do navegador com helper Fernet existente (MFA_ENCRYPTION_KEY); fingerprint público somente SHA256. Provedor permite apenas HTTPS/443 de hosts conhecidos de Google/Mozilla/Apple, sem redirects/proxies herdados; rejeita URLs locais/credenciais/fragmentos e chaves inválidas. Não aceitar texto/URL/destinatário arbitrário para push.

PWA guarda somente fallback público e ícones explicitamente permitidos. Nenhuma rota /dashboard, /portal, /api, PDF ou resposta RSC é armazenada. Atualização não força reload com formulário aberto. Manifesto `id:/`, `start_url:/dashboard`, `scope:/`, display standalone, ícones192/512 e apple180, português. Permissão de notificação somente no clique. iOS requer instalação na tela inicial antes de solicitar push. HTTPS na VPS; localhost é somente teste do computador.

## Gates

Plano verificado antes de delegar. Testar worker/cache, CSRF, sessão/tenant, SSRF, chaves, dedupe, expiração, falhas de provedor, revogação, eventos reais, sem chamadas a push externo nos testes. Validar manifesto e worker servidos no build real, navegador mobile e migrations/grants reais em banco descartável. Homologação em Android/iPhone e domínio HTTPS permanece externa até acesso a dispositivos/domínio.

Status: implementação e validação local concluídas. 114 testes backend sem skips, 13 testes Node, TypeScript/builds, SW real/cache/offline e 85 combinações mobile aprovados. Migration0007 aplicada localmente após backup; backend/frontend/worker/beat atualizados. Auditoria do lock Python sem vulnerabilidades conhecidas. Homologação de entrega em Android/iPhone físicos e domínio HTTPS permanece pendente; nenhum envio externo ou deploy VPS executado. Guia operacional: `docs/pwa-web-push.md`.
