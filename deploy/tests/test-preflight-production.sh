#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"
printf '#!/bin/sh\nexit 0\n' > "$tmp/bin/docker"
chmod 700 "$tmp/bin/docker"
env_file="$tmp/production.env"
cat > "$env_file" <<'EOF'
APP_DOMAIN=lexflow.example.com
ACME_EMAIL=ops@example.com
FRONTEND_URL=https://lexflow.example.com
RELEASE=0123456789abcdef
SECRET_KEY=secret
ACCOUNT_TOKEN_PEPPER=pepper
MFA_ENCRYPTION_KEY=mfa
POSTGRES_ADMIN_PASSWORD=admin
POSTGRES_APP_PASSWORD=app
MIGRATION_DATABASE_URL=postgresql://migration
DATABASE_URL=postgresql://runtime
REDIS_PASSWORD=redis
REDIS_URL=redis://runtime
JUDICIAL_MONITORING_PROVIDER=datajud
PROTOTYPE_MODULES_ENABLED=false
UNBOUND_NOTIFICATION_DISPATCH_ENABLED=false
EOF
chmod 600 "$env_file"
PATH="$tmp/bin:$PATH" /bin/sh "$root/deploy/preflight-production.sh" "$env_file" config >/dev/null
sed -i 's/UNBOUND_NOTIFICATION_DISPATCH_ENABLED=false/UNBOUND_NOTIFICATION_DISPATCH_ENABLED=true/' "$env_file"
if PATH="$tmp/bin:$PATH" /bin/sh "$root/deploy/preflight-production.sh" "$env_file" config >/dev/null 2>&1; then
  printf '%s\n' 'preflight accepted unsafe notification dispatch' >&2
  exit 1
fi
sed -i 's/UNBOUND_NOTIFICATION_DISPATCH_ENABLED=true/UNBOUND_NOTIFICATION_DISPATCH_ENABLED=false/' "$env_file"
printf '%s\n' 'ESCAVADOR_ENABLED=true' >> "$env_file"
if PATH="$tmp/bin:$PATH" /bin/sh "$root/deploy/preflight-production.sh" "$env_file" config >/dev/null 2>&1; then
  printf '%s\n' 'preflight accepted Escavador without callback credentials' >&2
  exit 1
fi
printf '%s\n' 'ESCAVADOR_API_TOKEN=api-token' 'ESCAVADOR_CALLBACK_TOKEN=callback-token' >> "$env_file"
PATH="$tmp/bin:$PATH" /bin/sh "$root/deploy/preflight-production.sh" "$env_file" config >/dev/null
printf '%s\n' 'preflight tests passed'
