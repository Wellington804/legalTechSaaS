# PWA e Web Push

O LegalFlow pode ser instalado pela tela **Conta e escritório → Aplicativo e notificações**. Nesse painel o usuário autoriza notificações, identifica seus dispositivos, envia um teste e revoga inscrições. A permissão do navegador só é solicitada após consentimento e clique; nunca automaticamente.

## Escopo entregue

- Aplicativo `standalone`, manifesto, ícones e orientação de instalação. Em iPhone/iPad, abra pelo ícone adicionado à Tela de Início; Web Push requer iOS/iPadOS 16.4+. [Requisitos do WebKit](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
- Alertas para criação/reatribuição de tarefa ao usuário e recebimento de mensagem/arquivo do cliente no portal, destinados ao responsável atual pelo caso. Alterar somente uma descrição/data não dispara novo alerta. Não há cálculo nem alarme automático de prazo jurídico.
- Texto genérico, sem nome de cliente, número de processo, conteúdo ou token. Clique abre `/dashboard` e exige autenticação válida.
- Até 10 dispositivos ativos, 30 novos registros por dia e 5 notificações de teste por hora por usuário.
- Fila PostgreSQL por dispositivo, publicada por Celery Beat a cada 30 segundos. Broker indisponível não perde eventos já gravados; o evento e a operação de negócio compartilham a transação. Dedupe por evento/dispositivo e autorização revalidada antes do envio.
- Apenas `/offline.html` e os três ícones públicos entram em CacheStorage. Não há armazenamento offline de páginas autenticadas, APIs, documentos ou mensagens. Sem rede, a navegação mostra instrução de reconexão.
- Atualizações do service worker pedem ao usuário salvar suas edições antes de recarregar; não há reload forçado.

## Configuração

Variáveis compartilhadas entre backend e worker:

```dotenv
WEB_PUSH_ENABLED=false
WEB_PUSH_VAPID_PUBLIC_KEY=
WEB_PUSH_VAPID_PRIVATE_KEY=
WEB_PUSH_VAPID_SUBJECT=
```

Gere **uma vez**, conservando as chaves em cada deploy. A CLI preenche campos vazios atomicamente, preserva os demais segredos e não imprime chaves. Recusa um par já parcialmente preenchido. Com o ambiente Python do backend instalado, execute a partir de `backend/`:

```sh
python -m app.cli.push_keys --env-file ../.env.production --subject mailto:SEU_CONTATO_REAL --enable
```

Substitua `SEU_CONTATO_REAL` por um endereço real com domínio. Use `--env-file ../.env` para desenvolvimento. Um contato `.invalid` serve somente ao teste local e é rejeitado em produção. Não substitua chaves existentes para resolver erros de configuração: rotação exige que cada dispositivo se inscreva novamente.

Na VPS, configure também `MFA_ENCRYPTION_KEY` persistente: ela criptografa endpoint e chaves da inscrição. A chave VAPID privada nunca vai ao frontend; apenas a chave pública é retornada pela API autenticada. Preserve ambas as chaves de criptografia nos backups protegidos.

Workers compartilham no Redis os cabeçalhos VAPID criptografados por quatro horas (JWT válido por 12 horas), evitando renovar o token a cada mensagem/processo conforme [requisito da Apple](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers). Cache indisponível falha antes de chamar o provedor, com tentativa limitada. Não limpe esse cache rotineiramente.

## Operação local e VPS

1. Faça backup do banco antes da migration `20260828_0007`.
2. Construa a imagem, execute `alembic upgrade head` e o script `deploy/postgres/grant-runtime-role.sh` com o administrador de migrações. O runtime de produção continua sem superusuário/BYPASSRLS.
3. Inicie backend, frontend, worker e **uma única instância de Beat**. O Compose local agora inclui worker/beat. O Compose de produção já compartilha as quatro variáveis com os serviços.
4. VPS: domínio HTTPS, Cloudflare SSL Full (strict), sem regra Cache Everything para a aplicação. Não cachear `/sw.js`, `/api/*`, `/dashboard*` nem `/portal*`. Preserve `Cache-Control`/`Service-Worker-Allowed` do frontend. Não é necessário expor Redis, PostgreSQL ou worker à internet.
5. O worker precisa de saída HTTPS para os serviços Web Push de Google, Mozilla e Apple. A validação de endpoints rejeita destinos arbitrários, HTTP, portas alternativas, redirecionamentos e proxies herdados do ambiente.
6. `deploy/notification-recovery-health.sh` verifica também heartbeat/fila Push quando habilitado. O heartbeat fica em `legaltech:push:recovery-heartbeat`. A tabela `push_deliveries` distingue `queued`, `processing`, `accepted`, `failed`, `expired`, `cancelled` e `unknown`; investigar falhas sem registrar endpoints/chaves.

As inscrições renovam por até 90 dias quando o usuário utiliza o aplicativo autenticado. A expiração normal da sessão de navegação não desliga alertas genéricos; **logout ou revogação da sessão** os bloqueia. Abrir o alerta não prolonga autenticação. Dispositivo removido remotamente pode continuar com a permissão do navegador, mas o servidor deixa de enviar. Um envio já aceito pelo provedor não pode ser recuperado; por isso o conteúdo permanece genérico.

`accepted` significa aceitação pelo serviço Push, não recebimento/leitura no aparelho. 404/410 revogam a inscrição; 429/timeout de conexão têm até três tentativas. Timeout de resposta, 5xx ou worker interrompido após envio ficam `unknown`, sem reenvio automático ambíguo. Eventos expiram em 24 horas. Não utilizar push como garantia contra perda de prazo.

## Validação e limites

Testes automatizados cobrem API/CSRF, consentimento, criptografia, tenant/RLS, dedupe, eventos reais, revogação, resposta do provedor e cache público. Testes de interface usam API/PushManager simulados; o teste de runtime usa o service worker real no navegador local. Nenhum teste automatizado envia notificações a dispositivos externos.

Homologação necessária antes de liberar aos usuários: em domínio HTTPS, instalar no Android e iPhone, autorizar, enviar teste com app aberto/fechado e tela bloqueada, clicar com sessão expirada, revogar dispositivo e conferir Não Perturbe/permissões. `localhost` no telefone aponta para o próprio telefone; a aplicação local no computador não equivale a essa homologação.

### Evidências locais — 28/08/2026

- 114 testes backend aprovados, sem skips, com PostgreSQL descartável e runtime sem BYPASSRLS; inclui criptografia Web Push real com transporte simulado.
- 13 testes Node e TypeScript aprovados; builds Docker de frontend/backend concluídos. Auditoria do lock Python sem vulnerabilidades conhecidas.
- `pwa-ui.cjs`, `pwa-runtime.cjs`, `workspace-ui.cjs`, `branding-ui.cjs` e `mobile-ui.cjs` aprovados; mobile cobre 17 rotas em 5 larguras. PWA runtime usa service worker real; testes de envio/inscrição usam fixtures.
- Migration `20260828_0007` aplicada ao banco local após backup; API ready, Beat/worker consumindo descoberta a cada 30s. Dois processos independentes confirmaram reutilização do token VAPID no Redis real, sem envio externo.
- `.env` local recebeu VAPID com contato de desenvolvimento; demais segredos preservados. Na VPS é obrigatório trocar o contato de exemplo por um contato real e homologar a entrega. Nenhum deploy VPS realizado nesta etapa.
