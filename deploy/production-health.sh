#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${LEGALTECH_ENV_FILE:?set LEGALTECH_ENV_FILE}"
: "${BACKUP_DIRECTORY:?set BACKUP_DIRECTORY}"
: "${BACKUP_MAX_AGE_HOURS:?set BACKUP_MAX_AGE_HOURS}"
compose_file=${LEGALTECH_COMPOSE_FILE:-"$script_dir/../docker-compose.prod.yml"}
docker compose --env-file "$LEGALTECH_ENV_FILE" -f "$compose_file" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()"
for service in document-worker clamav; do
  container=$(docker compose --env-file "$LEGALTECH_ENV_FILE" -f "$compose_file" ps -q "$service")
  [ -n "$container" ] || { printf 'production-health: missing %s\n' "$service" >&2; exit 1; }
  [ "$(docker inspect -f '{{.State.Status}}' "$container")" = running ] || { printf 'production-health: %s is not running\n' "$service" >&2; exit 1; }
  [ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")" = healthy ] || { printf 'production-health: %s is not healthy\n' "$service" >&2; exit 1; }
done
docker compose --env-file "$LEGALTECH_ENV_FILE" -f "$compose_file" exec -T backend python -c "from app.services.document_storage import check; check()"
/bin/sh "$script_dir/notification-recovery-health.sh"
/bin/sh "$script_dir/backup-health.sh"
/bin/sh "$script_dir/volume-health.sh" >/dev/null
printf '%s\n' "production-health: readiness, workers, outboxes, backup and volumes are healthy"
