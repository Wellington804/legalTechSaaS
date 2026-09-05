# LexFlow — Central do Advogado

SaaS de gestão de escritórios, implementado como monólito modular Next.js/FastAPI/PostgreSQL. O núcleo agora tem APIs e interfaces conectadas, substituindo os dados demonstrativos das áreas operacionais.

**Piloto fechado, ainda não homologado para produção:** migrations, testes PostgreSQL restrito e restauração isolada foram verificados localmente. VPS, backup offsite, alertas e entrega dos provedores continuam exigindo homologação real. Veja o [guia do piloto e evidências](docs/piloto-fechado.md), o [piloto privado via Tailscale](docs/piloto-tailscale.md), a [Central de Arquivos](docs/central-arquivos.md) e a [matriz de implementação](docs/implementacao-central-advogado.md).

## Núcleo implementado

- Sessões revogáveis, recuperação/verificação de e-mail, MFA TOTP, equipe e permissões, trial/quotas e contratação assistida.
- Clientes, casos/partes e acesso restrito; agenda; documentos privados e versões; modelos; biblioteca e publicações; busca na carteira e conflitos.
- Horas, despesas, honorários, recebimentos manuais idempotentes e estornos; não é confirmação bancária.
- Comunicação vinculada ao caso, portal revogável, mensagens e checklist/upload do cliente.
- Primeiros passos derivados dos cadastros, kit documental revisável, diligências, checklists operacionais, lembretes pessoais e feedback semanal em `/dashboard/pilot`.
- CRM persistente em `/dashboard/crm`, com oportunidades por etapa, responsável, próxima ação e vínculos opcionais com cliente, processo e atendimento; alterações são auditadas e separadas por escritório.
- Acompanhamento pessoal de inscrição em `/dashboard/oab`, com busca das 27 Seccionais, links oficiais e checklist preenchido pelo próprio usuário. Não envia inscrição, consulta protocolo nem sincroniza andamento com a OAB.
- Jurimetria descritiva em `/dashboard/jurimetria`, baseada em amostras limitadas da API Pública do DataJud e com snapshots opcionais por escritório. Depende de credencial/configuração ativa e não prevê êxito, prazo ou estratégia.
- Qualidade da IA em `/dashboard/audit/ai-quality`, com importação de casos de avaliação, revisão independente registrada e execuções somente sobre casos aprovados. Depende do provedor de IA habilitado e não homologa juridicamente suas respostas.
- Conectores opcionais Gemini, Resend e Evolution com origem, autorização, limites, revisão humana ou recibos conforme o fluxo; disponibilidade depende de configuração e homologação reais.
- Caixa omnichannel persistida para WhatsApp/e-mail, com vínculo seguro ao processo e fila humana para mensagens ou anexos ambíguos.
- Monitoramento judicial por fontes configuradas, motor versionado de prazos e dupla aprovação humana antes de qualquer prazo ser efetivado.
- Corpus jurídico revisado por advogados, benchmarks com evidência citável e inteligência documental com OCR, classificação, linha do tempo e contradições.
- Calendários Google/Microsoft bidirecionais e assinatura Clicksign/Autentique com credenciais cifradas por escritório; ativação depende de homologação real.

Cobrança automática do SaaS, protocolo/consulta automatizada na OAB ou FGV e jurimetria preditiva **não estão concluídos**. Integrações externas permanecem indisponíveis sem credenciais, contrato e homologação; resultados do DataJud, sugestões de prazo e respostas de IA nunca dispensam conferência profissional. Os routers demonstrativos foram removidos do runtime e as rotas antigas falham fechado.

## Execução local

Com Docker Engine funcionando e os volumes existentes identificados, execute na raiz deste repositório:

```sh
docker compose up -d db redis
docker compose build backend frontend
docker compose run --rm --no-deps backend alembic upgrade head
docker compose up -d backend worker beat frontend
```

Frontend: <http://localhost:3000>; API: <http://localhost:8000>; Swagger local: <http://localhost:8000/api/v1/docs>. O cadastro está em `/account/access`. Não há senha de produção predefinida. O Compose local usa credenciais de desenvolvimento, portas loopback e protótipos desligados; **não use na VPS**. Integrações externas exigem configuração explícita.

Se o Docker tiver sido restaurado para padrões de fábrica, inspecione primeiro `docker volume ls` e `docker ps -a`. Não inicialize um banco vazio como se fosse o banco anterior. As migrations não recriam dados perdidos.

## VPS e credenciais

O `.env` local é ignorado pelo Git e `.env.example` documenta os campos necessários sem segredos. Valores de desenvolvimento não são credenciais de produção. Na VPS, use `.env.production` com permissões restritas e o [runbook operacional](docs/operacao-vps.md). Cloudflare, domínio, TLS, Resend, Evolution Go, Sentry e backups externos exigem configuração real.

Credenciais de instância WhatsApp são exclusivas do escritório e armazenadas cifradas. `SENTRY_AUTH_TOKEN` pertence somente à CI, nunca ao runtime/browser. `UNBOUND_NOTIFICATION_DISPATCH_ENABLED` e protótipos permanecem `false`.

## Testes

```sh
# Backend: requirements.txt para desenvolvimento local; requirements.lock para Linux/Python 3.11.
cd backend
python -m unittest discover -s tests -v
alembic upgrade head --sql

# Frontend
cd ../frontend
node --test tests/*.test.cjs
npm run lint
npm run build
```

`lint` é typecheck TypeScript. `AUDIT_TEST_DATABASE_URL` e `ACCOUNT_TEST_DATABASE_URL` devem apontar ao mesmo banco **descartável, migrado e com grants**, usando role `NOSUPERUSER NOBYPASSRLS`. Sem essas variáveis, os testes de PostgreSQL são explicitamente ignorados. A CI provisiona esse banco; sua execução deve ser conferida antes de publicar.

O smoke `frontend/tests/local-smoke.cjs` usa a aplicação real e cria registros de verificação com nomes únicos; não é uma limpeza de dados. Requer Playwright disponível e `AUDIT_LOGIN_EMAIL`/`AUDIT_LOGIN_PASSWORD` locais. Testes com API simulada validam apenas interface/contratos, não persistência, RLS ou provedores.

A [auditoria original](docs/auditoria-modulos-2026-08-27.md) é uma fotografia anterior às implementações atuais, preservada como histórico.
