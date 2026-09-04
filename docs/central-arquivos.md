# Central de Arquivos Jurídicos

## O que foi implementado

- Pastas persistidas por cliente e, opcionalmente, por processo, com até oito níveis e nomes únicos por pasta-pai.
- Upload direto para bucket privado Cloudflare R2 por URL assinada de cinco minutos. A chave do objeto usa apenas IDs internos.
- PDF, DOCX, XLSX, TXT, JPG e PNG de até 25 MB, com validação de estrutura, tamanho, checksum SHA-256, ClamAV e OCR em worker isolado.
- Busca PostgreSQL em português por nome e texto extraído, histórico imutável, quota por escritório, auditoria de upload/download/movimentação e lixeira por 30 dias.
- Compartilhamento revogável de pasta e subpastas somente dentro do portal já vinculado ao processo. Envio pelo cliente depende de permissão explícita.

Em desenvolvimento, com `R2_ENABLED=false`, o fluxo anterior em PostgreSQL continua disponível. Produção exige R2; o preflight de go-live falha se ele estiver desativado.

## Cloudflare R2

Crie um bucket sem acesso público e uma credencial limitada a esse bucket. Configure CORS apenas para a origem HTTPS da aplicação:

```json
[
  {
    "AllowedOrigins": ["https://SEU_DOMINIO"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

Configure uma regra de lifecycle para apagar `quarantine/` apó um dia. Uma bucket lock de pelo menos 35 dias nos prefixos `documents/` e `exports/` reduz exclusão acidental; o expurgo do LexFlow só marca o objeto como removido depois que o R2 confirma a exclusão.

R2 durável não substitui backup. Antes de dados reais, espelhe os objetos para outro bucket/conta ou provedor com credencial separada, compare inventário e hashes e execute uma recuperação amostral. O backup PostgreSQL cobre metadados e arquivos legados em `bytea`, mas não os objetos novos do R2.

## Migração e ativação

1. Faça backup e restore isolado do PostgreSQL.
2. Execute `alembic upgrade head` e `deploy/postgres/grant-runtime-role.sh` com a conta administrativa.
3. Configure `R2_*` e inicie `clamav` e `document-worker` pelo Compose de produção.
4. Rode primeiro o backfill sem `--apply`; depois repita com `--apply` por tenant usando `MIGRATION_DATABASE_URL`:

```sh
DATABASE_URL="$MIGRATION_DATABASE_URL" python -m app.cli.document_storage --tenant-id ID_DO_ESCRITORIO --batch 100
DATABASE_URL="$MIGRATION_DATABASE_URL" python -m app.cli.document_storage --tenant-id ID_DO_ESCRITORIO --batch 100 --apply
```

O backfill lê novamente cada objeto e compara SHA-256 antes de gravar o ponteiro, sem apagar o binário original. Só remova os `bytea` legados em uma migração posterior, depois de comprovar backup e restore do R2.

## Gates antes de liberar arquivos reais

- upload, antivírus, OCR, busca, download, compartilhamento e revogação exercitados com casos fictícios;
- CORS restrito ao domínio, bucket privado e token de menor privilégio;
- `document-worker` e ClamAV saudáveis no `production-health.sh`;
- restore conjunto PostgreSQL + objetos comprovado e RPO/RTO registrados;
- descarte de lixeira e quarantine observado em staging sem perda de arquivo ativo.
