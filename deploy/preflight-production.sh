#!/bin/sh
set -eu

fail() { printf '%s\n' "preflight: $*" >&2; exit 1; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || fail "usage: preflight-production.sh /absolute/.env.production [config|go-live]"
env_file=$1
mode=${2:-config}
[ "$mode" = config ] || [ "$mode" = go-live ] || fail "mode must be config or go-live"
case "$env_file" in /*) ;; *) fail "environment file must be absolute";; esac
[ -f "$env_file" ] && [ -s "$env_file" ] || fail "environment file is missing or empty"
case "$(stat -c %a "$env_file")" in *00) ;; *) fail "environment file must not be readable or writable by group/others";; esac
command -v docker >/dev/null || fail "docker is required"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"
duplicates=$(awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{seen[$1]++} END{for (key in seen) if (seen[key] > 1) printf " %s", key}' "$env_file")
[ -z "$duplicates" ] || fail "duplicate fields:$duplicates"

value_of() { awk -v key="$1" 'index($0, key "=") == 1 { sub("^[^=]*=", ""); sub("\\r$", ""); print; exit }' "$env_file"; }
require_keys() {
  missing=""
  for key in $*; do [ -n "$(value_of "$key")" ] || missing="$missing $key"; done
  [ -z "$missing" ] || fail "missing required fields:$missing"
}

require_keys APP_DOMAIN ACME_EMAIL FRONTEND_URL RELEASE SECRET_KEY ACCOUNT_TOKEN_PEPPER MFA_ENCRYPTION_KEY POSTGRES_ADMIN_PASSWORD POSTGRES_APP_PASSWORD MIGRATION_DATABASE_URL DATABASE_URL REDIS_PASSWORD REDIS_URL
[ "$(value_of PROTOTYPE_MODULES_ENABLED)" != true ] || fail "prototype modules must remain disabled"
[ "$(value_of UNBOUND_NOTIFICATION_DISPATCH_ENABLED)" != true ] || fail "unbound notification dispatch must remain disabled"
domain=$(value_of APP_DOMAIN)
frontend_url=$(value_of FRONTEND_URL)
case "$frontend_url" in
  "https://$domain") ;;
  "https://$domain:"*)
    port=${frontend_url#"https://$domain:"}
    case "$port" in *[!0-9]*|'') fail "FRONTEND_URL port must be numeric" ;; esac
    [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || fail "FRONTEND_URL port must be between 1 and 65535"
    ;;
  *) fail "FRONTEND_URL must be the HTTPS APP_DOMAIN origin, with an optional port" ;;
esac
[ "$(value_of RELEASE)" != local ] || fail "RELEASE must identify an approved commit"

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
compose_file="$script_dir/../docker-compose.prod.yml"
docker compose --env-file "$env_file" -f "$compose_file" config -q

if [ "$mode" = go-live ]; then
  require_keys BACKEND_SENTRY_DSN FRONTEND_SENTRY_DSN OPENROUTER_API_KEY OPENROUTER_MODEL RESEND_API_KEY RESEND_FROM_EMAIL RESEND_WEBHOOK_SECRET EVOLUTION_API_KEY WEB_PUSH_VAPID_PUBLIC_KEY WEB_PUSH_VAPID_PRIVATE_KEY WEB_PUSH_VAPID_SUBJECT R2_ACCOUNT_ID R2_BUCKET_NAME R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY BACKUP_DIRECTORY BACKUP_PASSPHRASE_FILE BACKUP_OFFSITE_SSH_DESTINATION BACKUP_OFFSITE_SSH_KEY_PATH
  for flag in AI_ENABLED ACCOUNT_EMAILS_ENABLED RESEND_ENABLED EVOLUTION_ENABLED WEB_PUSH_ENABLED; do
    [ "$(value_of "$flag")" = true ] || fail "$flag must be true only after its homologation evidence is recorded"
  done
  [ "$(value_of R2_ENABLED)" = true ] || fail "R2_ENABLED must be true after private bucket, CORS, retention and recovery are verified"
  [ "$(value_of NOTIFICATIONS_DRY_RUN)" = false ] || fail "NOTIFICATIONS_DRY_RUN must be false only at the approved cutover"
  docker compose --env-file "$env_file" -f "$compose_file" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()"
fi
printf '%s\n' "preflight: $mode checks passed without printing credential values"
