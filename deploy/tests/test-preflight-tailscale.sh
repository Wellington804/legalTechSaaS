#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"
printf '#!/bin/sh\nexit 0\n' > "$tmp/bin/docker"
printf '#!/bin/sh\n[ "$1" = status ] || exit 1\nprintf "{}\\n"\n' > "$tmp/bin/tailscale"
chmod 700 "$tmp/bin/docker" "$tmp/bin/tailscale"
env_file="$tmp/production.env"
cat > "$env_file" <<'EOF'
APP_DOMAIN=lexflow-pilot.example-tailnet.ts.net
ACME_EMAIL=ops@example.com
FRONTEND_URL=https://lexflow-pilot.example-tailnet.ts.net
RELEASE=0123456789abcdef
SECRET_KEY=secret
ACCOUNT_TOKEN_PEPPER=pepper
MFA_ENCRYPTION_KEY=fernet
POSTGRES_ADMIN_PASSWORD=admin
POSTGRES_APP_PASSWORD=app
MIGRATION_DATABASE_URL=postgresql+asyncpg://admin:admin@db/legaltech
DATABASE_URL=postgresql+asyncpg://app:app@db/legaltech
REDIS_PASSWORD=redis
REDIS_URL=redis://:redis@redis:6379/0
PROTOTYPE_MODULES_ENABLED=false
UNBOUND_NOTIFICATION_DISPATCH_ENABLED=false
EOF
chmod 600 "$env_file"
PATH="$tmp/bin:$PATH" /bin/sh "$root/deploy/preflight-tailscale.sh" "$env_file" >/dev/null
sed -i 's/\.ts\.net$/.example.com/' "$env_file"
if PATH="$tmp/bin:$PATH" /bin/sh "$root/deploy/preflight-tailscale.sh" "$env_file" >/dev/null 2>&1; then
  printf '%s\n' 'tailscale preflight accepted a public domain' >&2
  exit 1
fi
printf '%s\n' 'tailscale preflight tests passed'
