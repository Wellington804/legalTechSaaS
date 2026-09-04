# Piloto fechado — um advogado

O piloto reúne os fluxos existentes; não é homologação de produção nem revisão jurídica dos modelos. Começar com casos fictícios, durante duas a quatro semanas. Dados reais dependem dos gates abaixo.

## Uso

- **Piloto** (`/dashboard/pilot`): primeiros passos calculados pelos cadastros reais, período restante, configuração de segurança, relato explícito de problemas e revisão semanal. Os relatos são privados por usuário; não capturam automaticamente clientes, URLs, imagens ou console. Evite dados pessoais no texto.
- **Caso 360**: checklists operacionais criam tarefas reais, sem presumir datas legais. Resultado da diligência vira nota versionada do caso. Tarefas têm local, contato e observações.
- **Agenda/Central**: casos sem próxima ação e lembretes pessoais. O advogado confere a data e escolhe quando lembrar. Alterar data, responsável, estado ou conferência invalida o lembrete anterior. A indicação dentro do sistema independe de push. Aceitação pelo provedor não significa entrega no aparelho; notificações não substituem conferência dos prazos.
- **Documentos**: ficha, procuração e honorários são rascunhos genéricos. Cadastro preenche os dados conhecidos, campos faltantes bloqueiam a gravação e alterações entre prévia e gravação exigem nova revisão. Poderes, escopo, valores e condições não são inventados. Exportação Word/PDF reutiliza versões e Branding. O advogado deve revisar conteúdo e adequação ao caso antes de qualquer uso externo.
- **Celular**: rascunhos de texto dos formulários protegidos ficam somente na memória da conta e podem ser retomados ao voltar à tela na mesma aba. Não há cache persistente de documentos ou banco offline; arquivos selecionados para upload não são guardados. Recarregar, fechar ou trocar de conta descarta o texto não salvo. Sessão expirada abre reautenticação sobre a tela, sem enviar o rascunho automaticamente. A instalação e o push seguem [PWA e Web Push](pwa-web-push.md).

Rascunhos retomados mantêm a revisão original do registro/documento: se outra edição já foi salva, o servidor rejeita a sobrescrita com conflito. Confira a versão atual e revise o texto antes de tentar novamente; não há mesclagem automática.

## Período e suporte

Não ativar automaticamente todos os escritórios. Identificar o tenant e registrar uma data final explícita com a CLI já existente, usando credenciais operacionais e uma janela de duas a quatro semanas:

```sh
python -m app.cli.account_support set-subscription-status \
  --tenant-id ID_CONFIRMADO --status active --plan pilot \
  --ends-at DATA_ISO_COM_FUSO --operator OPERADOR --reason "Piloto fechado autorizado"
```

A expiração bloqueia novas operações comerciais; não estende a assinatura e mantém envio de feedback disponível. `SUPPORT_URL` aceita contato `mailto:` simples ou HTTPS público. Deixá-lo vazio não cria um canal fictício. Definir quem responde e combinar uma revisão semanal; a tela registra o que foi concluído e onde houve necessidade de ajuda. O relato persistido não envia e-mail automaticamente ao suporte.

## Gates antes de dados reais

1. Publicar **docker-compose.prod.yml**, nunca o Compose local de desenvolvimento. Para um piloto estritamente privado sem domínio, combine-o com `docker-compose.tailscale.yml` e siga [Piloto privado via Tailscale](piloto-tailscale.md). Produção pública continua exigindo domínio próprio no Cloudflare, HTTPS ponta a ponta e TLS estrito. Em ambos os casos, PostgreSQL/Redis não podem ter exposição pública.
2. Configurar valores reais no `.env` protegido: `APP_DOMAIN`, `ACME_EMAIL`, `FRONTEND_URL`, credenciais de banco/Redis, `SECRET_KEY`, `BACKEND_SENTRY_DSN`, `FRONTEND_SENTRY_DSN`, `RELEASE`, `SUPPORT_URL`, Resend e chaves VAPID. Não versionar nem compartilhar os valores. `SENTRY_AUTH_TOKEN` é segredo de build/CI, não do runtime. Integrações desligadas permanecem explicitamente indisponíveis.
3. Habilitar e verificar entrega real do Resend, domínio remetente e SPF/DKIM/DMARC; testar verificação de e-mail e recuperação de senha. Confirmar MFA, código de recuperação, logout, revogação de sessões e perfis de acesso com a conta do piloto. O teste local usa banco real e transporte de e-mail simulado, não prova entrega.
4. Criar alertas no projeto Sentry e um monitor externo para HTTPS/`/readyz`, com destinatário real. Executar `deploy/notification-recovery-health.sh` e `deploy/backup-health.sh` pelo monitor operacional. O primeiro verifica Beat → worker, lembretes e outboxes; o segundo verifica atualidade/checksum. DSN configurado e heartbeat local **não** provam recebimento de alertas.
5. Backup criptografado, cópia fora da VPS e chave de recuperação separada. Fazer o ensaio abaixo na infraestrutura final, inclusive teste de acesso aos documentos restaurados. Definir responsáveis e janela de recuperação.
6. Homologar no aparelho do advogado: instalação Android/iOS, permissão explícita, recebimento de push com app fechado, abertura do destino após autenticação, consulta de caso e registro de diligência. Sem evidência no aparelho, push continua não homologado.
7. Conferir modelos e revisar o fluxo ponta a ponta com casos fictícios. Avaliar semanalmente tarefas esquecidas, dificuldades e qualidade dos documentos; ajustar o piloto antes de expandir usuários.

## Ensaio de restauração sem sobrescrever a origem

O script existente `deploy/restore-postgres.sh` verifica checksum/decriptação e aceita somente banco novo `legaltech_restore_*`. Nunca apontar o sistema real para o banco restaurado: tokens e filas também são restaurados. Não iniciar workers nem enviar notificações nele.

1. Anexar um arquivo fictício e gerar exportação de teste. Pausar escritas da origem durante snapshot/backup/comparação.
2. Fazer backup com `deploy/backup-postgres.sh`. Restaurar em banco isolado, passando caminho absoluto, `BACKUP_PASSPHRASE_FILE` e `CONFIRM_RESTORE_TARGET` exatamente iguais ao alvo esperado.
3. Injetar `RESTORE_SOURCE_DATABASE_URL` e `RESTORE_TARGET_DATABASE_URL` no processo verificador sem imprimir valores. Ambas usam PostgreSQL com usuário de leitura que veja todas as linhas (administrador/BYPASSRLS); a conta runtime não serve para comparar outros tenants.
4. Executar `python -m app.cli.verify_restore`. A comparação é somente leitura, fixa UTC e compara SHA-256 e contagem de todas as linhas públicas, inclusive bytes de documentos, versões, ativos e exportações. Exige arquivo não vazio; banco vazio ou só texto não prova recuperação de anexos.
5. Registrar resultado, duração e acesso real ao arquivo fictício. Liberar escritas só após concluir a comparação. Eliminar o ambiente de ensaio conforme a política de retenção.

Esse ensaio não valida automaticamente recuperação de segredos, DNS, configuração da VPS ou alertas. Guardar separadamente a configuração necessária para restaurar o serviço; sem a mesma `SECRET_KEY`, dados cifrados podem ficar inutilizáveis.

## Critérios de segurança usados

[OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) orienta os gates de acesso, sessões e isolamento. A instalação depende dos [requisitos de PWA do navegador](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable); não basta exibir um botão de instalar.

## Evidências locais

Em 28/08/2026: 132 testes de backend aprovados, sem skips, com as suítes PostgreSQL usando usuário NOBYPASSRLS. Cobrem MFA/recuperação/sessões, isolamento, revisão e concorrência documental, notas e lembretes. Os transportes externos são simulados.

Ensaio local real `pg_dump` → `pg_restore` em PostgreSQL descartável: **43 tabelas, 884 linhas, 23 registros documentais/versões e 152.304 bytes de arquivos** comparados. Alterar um byte no banco restaurado fez a verificação falhar corretamente. A checagem de saúde dos lembretes também tem teste executável que rejeita heartbeat ausente/antigo e pendências não processadas. Criptografia, cópia offsite e recuperação na VPS final permanecem gates externos.

Migrações locais aplicadas até `20260828_0009` após backup, `/readyz` saudável e tarefa de lembretes registrada no worker com heartbeat ativo.

Build Docker e TypeScript aprovados. No pacote final, `pilot-ui.cjs`, `workspace-ui.cjs`, `mobile-ui.cjs` (18 rotas × 5 larguras) e `pwa-ui.cjs` passaram, além dos 13 testes Node. Cobertura inclui rascunhos/reautenticação, troca de conta e de caso, resposta perdida sem duplicação e preservação da revisão original ao retomar uma edição. Capturas mobile inspecionadas. Esses testes de interface usam fixtures locais; não são homologação do aparelho nem dos provedores.

Imagens locais verificadas: backend/worker/Beat `sha256:7c50b0d6036bd4e7802440b1f51ecd24795ecbf68ca9dbd8b36b7331ff07e29b`; frontend `sha256:81208e7efdbba3d31f4449eddfad6be55876d30613bb04d013ebe716ecf7c73c`. Nenhuma publicação na VPS foi realizada.
