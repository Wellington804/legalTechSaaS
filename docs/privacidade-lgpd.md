# Privacidade, retenção e incidentes

O LexFlow registra por escritório o aviso publicado, sua versão, o contato de privacidade e o prazo operacional de retenção. Esses campos são política configurada pelo controlador; o software não presume prazo jurídico universal.

O formulário público só pode permanecer ativo com aviso HTTPS e versões explícitas de aviso e consentimento. Cada uso de IA em um documento exige autorização específica antes do envio ao provedor configurado.

## Solicitações de titular

Em **Conta e escritório > Privacidade**, o usuário abre protocolo de exportação, anonimização ou exclusão. O administrador pode pedir operação sobre todo o tenant. Pedidos repetidos em aberto são idempotentes. Exclusão e anonimização nunca são automáticas: primeiro separam-se dados sujeitos a retenção profissional, legal, probatória ou contratual.

O operador autorizado lista e encerra solicitações no mesmo tenant; a decisão e sua justificativa entram no log de auditoria:

```sh
python -m app.cli.account_support list-privacy-requests --tenant-id TENANT
python -m app.cli.account_support resolve-privacy-request --tenant-id TENANT \
  --request-id PEDIDO --status completed --operator OPERADOR \
  --resolution-note 'Escopo executado e evidência conferida no chamado interno'
```

## Incidente de privacidade

1. Conter: desabilitar a integração ou credencial afetada sem apagar logs, outbox ou recibos.
2. Preservar: registrar release, janela, tenants potencialmente afetados e hashes/IDs; nunca copiar conteúdo sensível para tickets comuns.
3. Avaliar: confirmar natureza, volume, titulares, controles comprometidos e risco com o responsável jurídico/privacidade.
4. Comunicar: cumprir os prazos e destinatários definidos pelo controlador e pela assessoria; o Sentry não substitui esse processo.
5. Recuperar: rotacionar credenciais, validar restore isolado quando aplicável, executar testes e documentar causa/contramedida antes de reativar.

Pedidos e incidentes não autorizam apagar diretamente o banco, volumes, auditoria ou backups. O descarte segue a política aprovada e deve manter evidência suficiente da execução.
