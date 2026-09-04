#!/bin/sh
set -eu

fail() { printf '%s\n' "tailscale-preflight: $*" >&2; exit 1; }
[ "$#" -eq 1 ] || fail "usage: preflight-tailscale.sh /absolute/.env.production"
env_file=$1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

/bin/sh "$script_dir/preflight-production.sh" "$env_file" config
command -v tailscale >/dev/null || fail "tailscale is required on the VPS host"
tailscale status --json >/dev/null || fail "tailscale must be connected"

value_of() { awk -v key="$1" 'index($0, key "=") == 1 { sub("^[^=]*=", ""); sub("\\r$", ""); print; exit }' "$env_file"; }
domain=$(value_of APP_DOMAIN)
case "$domain" in
  *[!A-Za-z0-9.-]*|.*|*..*|*.) fail "APP_DOMAIN must be a plain Tailscale DNS name" ;;
  *.ts.net) ;;
  *) fail "APP_DOMAIN must end in .ts.net for the private pilot" ;;
esac
compose_file="$script_dir/../docker-compose.prod.yml"
overlay_file="$script_dir/../docker-compose.tailscale.yml"
docker compose --env-file "$env_file" -f "$compose_file" -f "$overlay_file" config -q
printf '%s\n' "tailscale-preflight: private pilot configuration passed without printing credential values"
