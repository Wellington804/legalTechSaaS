# Operação da VPS

Este é um runbook de operação, não uma autorização para ativar módulos demonstrativos. Mantenha `UNBOUND_NOTIFICATION_DISPATCH_ENABLED=false`; comunicações só devem sair após recurso, destinatário e tenant estarem vinculados e homologados.

## Preparação

1. No host, use um usuário operacional sem privilégios de banco e um diretório dedicado, por exemplo `/opt/legaltech`. Mantenha Docker, firewall, GPG e OpenSSH atualizados. Os timers rodam pelo systemd para não conceder o socket Docker (equivalente a root) a um usuário humano.
2. Copie `.env.example` para `.env.production`, preencha apenas segredos/identificadores reais e aplique `chmod 600 .env.production`. As URLs de banco e Redis no template ficam vazias de propósito: construa-as com as senhas reais URL-encoded.
3. Crie também `/etc/legaltech/ops.env` (modo `600`, dono `root`) para os campos `BACKUP_*` e `LEGALTECH_ENV_FILE=/opt/legaltech/.env.production`. Não coloque `SENTRY_AUTH_TOKEN` nem chaves privadas no repositório ou no `.env.production`; o token do Sentry pertence somente ao secret da CI e a chave de cópia remota fica no caminho configurado.
4. No Cloudflare, crie o DNS do domínio, habilite proxy e somente use TLS **Full (strict)** depois de confirmar certificado válido no Caddy. O token Cloudflare deve ter o menor escopo possível e só é necessário para automações que realmente o usam.

Na CI, configure `SENTRY_AUTH_TOKEN` como secret e `SENTRY_ORG`/`SENTRY_PROJECT` como variables do repositório quando desejar upload de source maps. O token não vai para a VPS nem para a imagem final.

Valide a configuração sem expor valores:

```sh
/bin/sh deploy/preflight-production.sh /opt/legaltech/.env.production config
docker compose --env-file .env.production -f docker-compose.prod.yml config -q
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend \
  python -c "from app.core.config import settings; assert settings.is_hardened_environment"
```

As dependências Python de produção são instaladas de `backend/requirements.lock` com hashes. Altere somente `backend/requirements.txt`, gere novamente a lock para Linux/Python 3.11 e rode a auditoria antes de aceitar qualquer atualização:

```sh
uv pip compile --python-version 3.11 --python-platform x86_64-unknown-linux-gnu \
  --generate-hashes --output-file backend/requirements.lock backend/requirements.txt
uvx pip-audit -r backend/requirements.lock --strict --require-hashes --disable-pip
```

`pip-audit` executa em ambiente de ferramenta descartável; não é dependência da aplicação.

## Release e rollback

Para uma release identificável, defina `RELEASE` como o SHA exato do commit aprovado, confirme CI verde e faça backup antes da mudança.

```sh
git fetch --tags --prune
git checkout --detach "$RELEASE"
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d --remove-orphans
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl --fail --silent --show-error "https://$APP_DOMAIN/readyz" >/dev/null
```

O serviço `migrate` aplica migrations antes de `permissions`, e backend/worker/beat aguardam os grants. Confira os logs de `migrate`, `permissions`, `worker` e `beat` após cada release. Execute somente uma instância de `beat`; a claim de entrega tolera publicação duplicada, mas dois schedulers não são uma topologia suportada.

Depois de aguardar um ciclo do Beat, use o gate agregado abaixo. Ele exige que o trabalho agendado tenha chegado a um worker e que não exista entrega `queued` devida nem processamento abandonado. Ele não imprime segredos, destinatários ou payloads:

```sh
sudo --preserve-env=LEGALTECH_ENV_FILE /bin/sh \
  /opt/legaltech/deploy/notification-recovery-health.sh
```

Uma falha desse comando bloqueia a declaração de prontidão da release. Investigue Beat, worker e Redis; não altere manualmente a outbox para forçar o resultado.

Rollback é de **imagem/código**, não de destruição automática de schema: volte para o SHA anterior somente se as migrations continuarem compatíveis e execute o mesmo `up --build -d`. Não rode `alembic downgrade` na base de produção como atalho. Se a compatibilidade não estiver comprovada, restaure primeiro para banco isolado, investigue e faça um hotfix forward.

## Notificações e recuperação

O Beat republica entregas `queued` e `processing` abandonadas. O worker usa lock de linha e conta tentativas:

- e-mail só é reenviado dentro da janela de idempotência de 24 horas do Resend; depois disso fica `unknown` para revisão;
- WhatsApp com resultado ambíguo nunca é reenviado automaticamente;
- recibos recebidos antes de o worker gravar o ID do provedor entram em inbox com IDs hasheados e são reconciliados depois; o payload bruto do webhook não é retido.

Para acompanhar apenas estados agregados:

```sh
docker compose --env-file .env.production -f docker-compose.prod.yml exec db \
  psql -U "$POSTGRES_ADMIN_USER" -d "$POSTGRES_DB" -c \
  "SELECT status, count(*) FROM notification_deliveries GROUP BY status ORDER BY status;"
```

`unknown` requer verificação no provedor e ação explícita. Não force reenvio de WhatsApp. Antes de ativar Resend, valide domínio/remetente, SPF/DKIM/DMARC e webhook assinado. Antes de Evolution, valide pareamento, instância por tenant, credenciais, callback e recibos com ambiente de homologação. Estas configurações não enviam mensagens nem fazem deploy por si só.

## Backup, restore e volumes

`backup-postgres.sh` faz `pg_dump` custom de todo PostgreSQL (inclusive `bytea` de documentos legados), valida o dump, cifra com GPG AES-256, valida checksum/cifra e copia o par arquivo/checksum para o destino SCP pré-configurado. A retenção só toca arquivos `legaltech-postgres-*` no diretório dedicado configurado. Os novos anexos ficam no R2 e exigem cópia independente e restore conjunto conforme o [runbook da Central de Arquivos](central-arquivos.md).

Instale as units fornecidas ajustando `/opt/legaltech` se o diretório for diferente, depois habilite timers:

```sh
sudo install -m 644 deploy/systemd/legaltech-backup*.service deploy/systemd/legaltech-backup*.timer /etc/systemd/system/
sudo install -m 644 deploy/systemd/legaltech-production-health.service deploy/systemd/legaltech-production-health.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now legaltech-backup.timer legaltech-backup-health.timer legaltech-production-health.timer
sudo systemctl start legaltech-backup.service
sudo systemctl status legaltech-backup-health.service
```

O restore exige arquivo absoluto, checksum correspondente, alvo `legaltech_restore_*` inexistente e confirmação literal. Ele nunca sobrescreve `POSTGRES_DB`.

```sh
sudo systemd-run --wait --collect \
  --property=EnvironmentFile=/etc/legaltech/ops.env \
  --setenv=POSTGRES_DB=legaltech_db \
  --setenv=CONFIRM_RESTORE_TARGET=legaltech_restore_20260827 \
  /bin/sh /opt/legaltech/deploy/restore-postgres.sh \
  /var/backups/legaltech/legaltech-postgres-YYYYMMDDTHHMMSSZ.dump.gpg \
  legaltech_restore_20260827
```

Execute um restore isolado regularmente e registre RPO/RTO observados. O health check de backup valida idade/checksum; `deploy/volume-health.sh` informa uso real pelo Docker sem prometer capacidade que não foi medida.

Antes do corte que ativa IA, e-mail, WhatsApp e Web Push, rode o gate estrito. Ele falha fechado se qualquer credencial selecionada, backup externo, monitoramento ou processo operacional estiver incompleto:

```sh
/bin/sh deploy/preflight-production.sh /opt/legaltech/.env.production go-live
sudo systemctl start legaltech-production-health.service
```

O primeiro comando valida apenas o ambiente da aplicação. Os segredos `BACKUP_*`
continuam exclusivamente em `/etc/legaltech/ops.env`; o segundo comando valida o
backup cifrado, checksum, idade, workers, outboxes, storage e volumes.

A política de retenção, pedidos de titular e resposta a incidente estão em [Privacidade, retenção e incidentes](privacidade-lgpd.md).

## Resposta a falhas

### Atendimento comercial assistido

Enquanto não há provedor de cobrança integrado, somente um operador com acesso controlado ao backend resolve pedidos comerciais. Use o tenant exato, confirme o acordo fora do sistema e registre operador/motivo. Estes comandos não efetuam cobrança bancária:

```sh
python -m app.cli.account_support list-pending-requests --tenant-id ID_DO_ESCRITORIO
python -m app.cli.account_support set-subscription-status \
  --tenant-id ID_DO_ESCRITORIO --request-id ID_DO_PEDIDO \
  --status active --plan plano-contratado --quota-users 5 \
  --quota-storage-bytes 1073741824 --quota-messages 100 \
  --ends-at 2026-09-30T23:59:59-03:00 \
  --operator OPERADOR --reason 'Acordo confirmado no atendimento'
```

Execute no ambiente correto do backend, nunca copie identificadores de exemplo para produção. O comando bloqueia registros, resolve somente pedido pendente do mesmo tenant e audita no mesmo commit. Quotas e data do exemplo não são política comercial recomendada. Cancelamento também precisa de resolução explícita, não de edição direta no banco.

### Diagnóstico operacional

- `migrate` ou `permissions` falhou: não suba backend manualmente; corrija a migration/grant, valide em banco descartável e reaplique.
- `beat` parou: mantenha a fila parada, mas não modifique entregas diretamente; restabeleça o único scheduler e acompanhe a recuperação.
- `unknown` aumentou: suspenda a habilitação do provedor afetado, preserve logs/IDs e reconcilie no painel do provedor antes de qualquer novo envio.
- backup-health falhou: trate como incidente operacional, confirme destino SCP e faça restore isolado; não reduza retenção nem apague volumes para liberar espaço.

Produção, homologação de provedores, teste de terminal físico e conformidade regulatória continuam sendo gates distintos.
