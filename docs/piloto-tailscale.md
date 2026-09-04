# Piloto privado via Tailscale

Este perfil serve ao teste fechado de um advogado antes da compra do domínio. Ele usa o Compose de produção, mantém banco, Redis, API e frontend sem portas públicas e publica somente o proxy HTTP local `127.0.0.1:8080` por padrão. Em uma VPS compartilhada, defina `TAILSCALE_LOOPBACK_PORT` para uma porta livre. O Tailscale Serve termina HTTPS e torna o LexFlow acessível apenas a usuários autorizados. Não use Tailscale Funnel: Funnel é acesso público.

## Decisão de acesso

- Compartilhe somente a máquina `lexflow-pilot` com o advogado; não o convide para toda a sua tailnet.
- A máquina compartilhada não pode usar tag. Instale-a como nó pertencente à sua conta e restrinja o destinatário à porta 443 na política da tailnet.
- O convite Tailscale e a conta LexFlow são controles separados. Não compartilhe sua senha. O advogado aceita o convite, instala o Tailscale e cria a própria conta e senha em `/account/access`.
- Tailscale Serve envia cabeçalhos de identidade, mas o LexFlow não os usa para autenticação. O Caddy fica acessível apenas em loopback para impedir falsificação desses cabeçalhos por outra máquina.

## 1. Preparar a VPS

Use uma VPS Linux atualizada, SSH por chave e firewall padrão negando entrada. Não abra 80, 443, 3000, 8000, 5432 ou 6379 no firewall. Instale Docker Engine/Compose v2 e o cliente Tailscale conforme a documentação oficial. Depois conecte o host sem tag:

```sh
sudo tailscale up --hostname=lexflow-pilot
tailscale status
tailscale ip -4
```

Ative MagicDNS no painel do Tailscale. Anote o nome completo exibido para o host, no formato `lexflow-pilot.NOME-DA-TAILNET.ts.net`.

## 2. Ambiente do piloto

Copie `.env.example` para `/opt/legaltech/.env.production`, aplique `chmod 600` e preencha segredos independentes. Para este perfil:

```dotenv
APP_DOMAIN=lexflow-pilot.NOME-DA-TAILNET.ts.net
FRONTEND_URL=https://lexflow-pilot.NOME-DA-TAILNET.ts.net
TAILSCALE_LOOPBACK_PORT=8080
TAILSCALE_HTTPS_PORT=443
ACME_EMAIL=SEU_EMAIL_OPERACIONAL
RELEASE=SHA_EXATO_DO_COMMIT

ACCOUNT_EMAILS_ENABLED=false
AI_ENABLED=false
RESEND_ENABLED=false
EVOLUTION_ENABLED=false
WEB_PUSH_ENABLED=false
R2_ENABLED=false
NOTIFICATIONS_DRY_RUN=true
UNBOUND_NOTIFICATION_DISPATCH_ENABLED=false
PROTOTYPE_MODULES_ENABLED=false
```

O `ACME_EMAIL` permanece preenchido porque o preflight é compartilhado; o Caddy do overlay Tailscale não solicita certificado. Não habilite provedor apenas porque a chave existe: habilite cada integração depois de um teste real específico.

Valide sem imprimir valores:

```sh
cd /opt/legaltech
/bin/sh deploy/preflight-tailscale.sh /opt/legaltech/.env.production
docker compose --env-file .env.production \
  -f docker-compose.prod.yml -f docker-compose.tailscale.yml config --quiet
```

## 3. Subir e publicar somente na tailnet

```sh
docker compose --env-file .env.production \
  -f docker-compose.prod.yml -f docker-compose.tailscale.yml \
  up --build -d --remove-orphans

curl --fail --silent --show-error "http://127.0.0.1:${TAILSCALE_LOOPBACK_PORT:-8080}/readyz"
sudo tailscale serve --yes --bg --https="${TAILSCALE_HTTPS_PORT:-443}" "http://127.0.0.1:${TAILSCALE_LOOPBACK_PORT:-8080}"
tailscale serve status --json
curl --fail --silent --show-error "$FRONTEND_URL/readyz"
```

O último `curl` precisa ser executado em uma máquina conectada à tailnet. Confirme também que `http://IP_PUBLICO_DA_VPS`, `https://IP_PUBLICO_DA_VPS` e as portas 3000/8000 não respondem externamente. `tailscale serve --bg` persiste após reinício; valide novamente depois de reiniciar a VPS.

## 4. Restringir e compartilhar com o advogado

No editor de políticas do Tailscale, preserve suas regras administrativas existentes e acrescente uma concessão específica. Substitua o e-mail e o IP Tailscale pelos valores reais:

```json
{
  "src": ["EMAIL_TAILSCALE_DO_ADVOGADO"],
  "dst": ["100.X.Y.Z"],
  "ip": ["443"]
}
```

No painel **Machines**, abra `lexflow-pilot` → **Share** → **Share by email** e envie um convite de uso único. Não use link reutilizável. O advogado deve:

1. instalar o Tailscale no computador e no celular;
2. entrar com a própria conta e aceitar o compartilhamento;
3. manter o Tailscale conectado;
4. abrir `https://lexflow-pilot.NOME-DA-TAILNET.ts.net/account/access`;
5. escolher **Criar escritório** e cadastrar a própria senha, com 12 ou mais caracteres.

## 5. Aprovar a conta sem Resend e ativar MFA

Sem domínio de e-mail, a verificação automática e a recuperação de senha ficam indisponíveis. Depois que o advogado registrar a conta e você confirmar o endereço por chamada, execute o comando auditado abaixo. O serviço `migrate` fornece o papel administrativo necessário; não altere a tabela manualmente.

```sh
docker compose --env-file .env.production \
  -f docker-compose.prod.yml -f docker-compose.tailscale.yml \
  run --rm migrate python -m app.cli.account_support approve-pilot-email \
  --user-email EMAIL_EXATO_DO_ADVOGADO \
  --operator SEU_IDENTIFICADOR \
  --reason "E-mail confirmado por chamada para o piloto privado"
```

O advogado atualiza a tela, configura MFA em **Conta → Segurança** e guarda os códigos de recuperação fora do celular. Como não há recuperação por e-mail, deve usar um gerenciador de senhas. Não envie senha por WhatsApp, e-mail ou mensagem comum.

## 6. Limites do primeiro teste

- Pode cadastrar os dados profissionais próprios depois de MFA.
- Use clientes e processos fictícios até comprovar backup criptografado, cópia fora da VPS e restauração na infraestrutura final.
- IA, e-mail, WhatsApp, Web Push e armazenamento R2 permanecem desligados até credenciais e homologações próprias.
- PWA e acesso móvel dependem do Tailscale conectado. O túnel não substitui backup, Sentry, atualização da VPS nem testes de isolamento entre escritórios.
- Ao encerrar o piloto, revogue o compartilhamento no painel do Tailscale, execute `sudo tailscale serve reset` e revogue as sessões do usuário no LexFlow.
