# Runbook de produção — VPS, Cloudflare e observabilidade

Este runbook pressupõe uma VPS Linux recente com Docker Engine e Compose v2. A aplicação usa uma única origem (`https://APP_DOMAIN`): Caddy encaminha `/api/v1`, `/healthz`, `/readyz` e `/webhooks` ao FastAPI e o restante ao Next.js.

## 1. Preparação

1. Crie um usuário de deploy sem login por senha; permita SSH somente por chave.
2. Copie `.env.example` para `.env.production` e preencha os valores. Use valores aleatórios independentes e URL-safe; senhas presentes em URLs precisam estar URL-encoded. O usuário `POSTGRES_ADMIN_USER` pertence apenas às migrations; `DATABASE_URL` deve usar `POSTGRES_APP_USER`, criado como `NOSUPERUSER` e `NOBYPASSRLS`.
3. Não coloque `SENTRY_AUTH_TOKEN` na VPS. Ele pertence somente ao CI que envia source maps/releases.
4. Valide antes de iniciar:

```sh
/bin/sh deploy/preflight-production.sh /opt/legaltech/.env.production config
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml build
```

O backend recusa iniciar em `production` com segredo curto, cookie inseguro, banco local/default, Redis sem senha, CORS HTTP, hosts curinga, protótipos habilitados ou configuração incompleta de um provedor habilitado. O frontend usa Node 24 LTS. O Compose limita logs por container a três arquivos de 10 MB e processos a 256; memória/CPU precisam ser dimensionadas na VPS escolhida e validadas com carga.

## 2. Cloudflare e firewall

1. Cadastre `APP_DOMAIN` como A/AAAA proxied (orange cloud) apontando para a VPS.
2. Mantenha SPF, DKIM, DMARC, MX e registros de verificação do Resend como DNS-only.
3. Depois do primeiro certificado válido no Caddy, configure SSL/TLS como **Full (strict)** e ative DNSSEC.
4. Não aplique cache a `/api/*`, `/healthz`, `/readyz` ou `/webhooks/*`. Use rate limits de borda especialmente em login e webhooks, mantendo os limites da aplicação.
5. Abra SSH apenas para IPs administrativos. Nas portas 80/443, permita somente os ranges publicados em `https://www.cloudflare.com/ips/`.

Portas publicadas por Docker podem contornar regras UFW. Aplique a allowlist na cadeia `DOCKER-USER` (ou no firewall do provedor) e teste a partir de uma rede externa. Atualize juntos a allowlist e os ranges `trusted_proxies` do `deploy/Caddyfile` quando a Cloudflare alterar a lista. Nunca aceite `CF-Connecting-IP` de uma origem fora dessa allowlist.

Critério de aceite: `https://APP_DOMAIN/healthz` responde via Cloudflare, enquanto requisições a `http(s)://IP_DA_VPS` não chegam ao Caddy.

## 3. Migração e deploy

Execute backup antes de cada mudança de schema. O processo web não cria tabelas nem índices no startup. O serviço `migrate` usa `MIGRATION_DATABASE_URL`; em seguida, `permissions` concede somente DML ao role usado por backend/worker. Nunca use a URL administrativa em `DATABASE_URL`.

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm migrate
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Verifique `/healthz` (processo vivo) e `/readyz` (PostgreSQL e Redis disponíveis). Os endpoints retornam somente um estado agregado e não expõem credenciais ou detalhes das dependências.

Para rollback, volte para uma imagem/release compatível com o schema já aplicado. Downgrade de banco só deve ocorrer quando a migration foi escrita e testada explicitamente para isso.

## 4. Sentry

- Configure projetos separados para FastAPI e Next.js e use `BACKEND_SENTRY_DSN`, `FRONTEND_SENTRY_DSN` e `RELEASE` (SHA do commit). A inicialização inclui o worker Celery.
- O SDK está limitado a erros: tracing fica fixado em zero até existir política de privacidade testada para transações/spans. Não há variável que habilite tracing neste corte.
- `send_default_pii` permanece desabilitado. O filtro remove headers, cookies, corpo, metadados livres, credenciais/query/fragmento de URLs e variáveis de stack; padrões conhecidos de PII são mascarados. Isso não garante remoção de todo texto sensível: examine eventos completos com dados sintéticos.
- A CSP permite ingestão Sentry padrão e regiões US/DE. Se o DSN usar outro host ou instalação própria, ajuste explicitamente `connect-src` antes do teste no navegador.
- Gere uma exceção sintética em staging e confirme environment/release. Examine o evento inteiro antes de habilitar produção.
- Configure alertas para nova regressão, pico de 5xx e falhas após release. A indisponibilidade do Sentry não deve bloquear requisições.
- No CI, forneça o token somente como secret BuildKit: `docker build --secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN --build-arg SENTRY_ORG --build-arg SENTRY_PROJECT --build-arg NEXT_PUBLIC_SENTRY_RELEASE="$RELEASE" -f frontend/Dockerfile .`. O token não deve virar `ARG`, camada ou variável da imagem.

## 5. Resend

Valide o domínio remetente no Resend e publique SPF/DKIM/DMARC pela Cloudflare. Em staging, configure o webhook HTTPS em `/api/v1/notifications/webhooks/resend`, confirme a assinatura Svix e exercite `sent`, `delivered`, `bounced` e replay do mesmo evento.

`UNBOUND_NOTIFICATION_DISPATCH_ENABLED` permanece **sempre** `false`. O envio de produção só é iniciado pela comunicação persistida e vinculada ao caso; a API não opera como relay arbitrário. A recuperação de `queued`/`processing`, a janela idempotente do Resend e a inbox de receipts hasheados estão documentadas em [Operação da VPS](operacao-vps.md#notificações-e-recuperação).

## 6. Evolution Go opcional

O profile não é iniciado no deploy padrão. Ele usa banco e redes próprios, não publica API/painel e não persiste mensagens.

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml --profile evolution up -d evolution-go
```

Antes de `EVOLUTION_ENABLED=true`, ative a licença e configure somente `EVOLUTION_API_KEY` como segredo global da VPS. Saúde HTTP do container não comprova `loggedIn`. Ao clicar em **Conectar WhatsApp**, o backend cria uma instância exclusiva, gera seu token, cifra a identidade no banco, configura o webhook e devolve somente o QR Code. A interface consulta o estado apenas durante o pareamento; depois, eventos assinados pela identidade da instância mantêm conexão e recibos atualizados. Confirme o ciclo real criar → QR → `LoggedIn=true` → enviar → receber confirmação → desconectar contra a imagem pinada antes de homologar.

## 7. Integrações jurídicas

- Escavador é opcional e global: preencha `ESCAVADOR_API_TOKEN` e um `ESCAVADOR_CALLBACK_TOKEN` aleatório, cadastre o callback `/api/v1/controladoria/webhooks/escavador` com o mesmo Bearer e só então ative `ESCAVADOR_ENABLED=true` e selecione `JUDICIAL_MONITORING_PROVIDER=escavador`. Sem as duas credenciais, produção falha fechado. DataJud continua disponível como alternativa.
- Clicksign é configurada por escritório em **Atendimento e cobranças → Configurar Clicksign**. Comece pelo sandbox e informe chave da conta, Access Token e segredo HMAC. Esses segredos são cifrados no banco e não pertencem ao `.env` global. O PFX e o PIN do certificado ICP-Brasil nunca devem ser enviados ou armazenados pelo LexFlow.
- A agenda Apple usa uma assinatura privada e revogável `webcal`/ICS. Ela é somente leitura, não exige segredo externo e pode sofrer o atraso de atualização do aplicativo de calendário.
- Asaas permanece fora deste corte. Evolution Go continua sendo o único transporte WhatsApp e deve seguir a homologação da seção anterior.

Antes de habilitar Escavador ou Clicksign em produção, valide criação, callback autenticado, replay idempotente, indisponibilidade e revogação em sandbox. Um adaptador publicado sem credenciais não comprova a homologação do provedor.

## 8. Backup e restore

O repositório inclui backup PostgreSQL cifrado, checksum, cópia SSH externa, retenção, health check e timers systemd. Eles só passam a existir operacionalmente depois de instalar as units, configurar `/etc/legaltech/ops.env` e comprovar um restore isolado. Não guardar a única cópia no disco da VPS.

Crie o dump fora do volume da VPS e envie-o criptografado a armazenamento externo:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > legaltech.dump
```

Faça teste de restore periódico em um banco descartável, nunca diretamente sobre produção:

```sh
createdb legaltech_restore_test
pg_restore --exit-on-error --clean --if-exists --no-owner -d legaltech_restore_test legaltech.dump
```

Valide migrations, contagem de registros críticos e autenticação no ambiente restaurado. Um arquivo de dump sem restore testado não atende ao gate de produção. Faça também backup dos volumes do Evolution antes de qualquer atualização dele.

## 9. Gates de corte

- `docker compose config`, builds, migrations e testes passam.
- Somente Caddy publica portas; Postgres, Redis, backend, frontend e Evolution são privados.
- Acesso direto à origem está bloqueado e Full (strict) está ativo.
- `/readyz` responde `ready`; worker responde `pong`.
- Evento Sentry de staging chega sanitizado e associado ao SHA correto.
- Restore externo foi executado com sucesso.
- Resend/Evolution continuam em dry-run até seus testes específicos de webhook, entrega e reconexão passarem.
- Módulos legados de protótipo permanecem fora do router/backend sem flag de reativação; rotas antigas falham fechado ou apontam para o fluxo persistido equivalente.
- O fluxo E2E da CI passa por cadastro, MFA, cliente, caso, documento, prazo, honorários e logout usando PostgreSQL real com o role runtime sujeito a RLS.
- Aviso de privacidade, retenção e contato estão configurados; pedidos de titular e procedimento de incidente foram ensaiados.
