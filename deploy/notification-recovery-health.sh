#!/bin/sh
set -eu

fail() { printf '%s\n' "notification-recovery-health: $*" >&2; exit 1; }

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
compose_file=${LEGALTECH_COMPOSE_FILE:-"$script_dir/../docker-compose.prod.yml"}
compose() {
  if [ -n "${LEGALTECH_ENV_FILE:-}" ]; then
    docker compose --env-file "$LEGALTECH_ENV_FILE" -f "$compose_file" "$@"
  else
    docker compose -f "$compose_file" "$@"
  fi
}

# Read numbers from the running worker so the monitor cannot silently diverge
# from the deployed Compose environment. They are aggregate operational values.
worker_config=$(compose exec -T worker sh -ceu \
  'printf "%s %s" "$NOTIFICATION_PROCESSING_TIMEOUT_SECONDS" "$NOTIFICATION_RECOVERY_HEARTBEAT_MAX_AGE_SECONDS"')
set -- $worker_config
[ "$#" -eq 2 ] || fail "worker did not return recovery health configuration"
processing_timeout=$1
heartbeat_max_age=$2
case "$processing_timeout" in *[!0-9]*|'') fail "timeout must be an integer";; esac
case "$heartbeat_max_age" in *[!0-9]*|'') fail "heartbeat max age must be an integer";; esac

heartbeat=$(compose exec -T redis sh -ceu \
  'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --raw get legaltech:notifications:recovery-heartbeat')
case "$heartbeat" in *[!0-9]*|'') fail "no valid Beat-to-worker heartbeat";; esac
now=$(date +%s)
[ "$heartbeat" -le "$now" ] || fail "heartbeat is in the future"
[ $((now - heartbeat)) -le "$heartbeat_max_age" ] || \
  fail "Beat-to-worker heartbeat is stale"

# This security-definer function returns only opaque IDs. A non-empty result means
# queued due work or abandoned processing still needs reconciliation, so do not
# declare the production release healthy yet.
stale=$(compose exec -T db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM notification_recovery_candidates(1, $processing_timeout)")
case "$stale" in 0) ;; *[!0-9]*|'') fail "could not evaluate notification recovery state";; *) fail "recoverable notification outbox work remains";; esac

push_enabled=$(compose exec -T worker python -c 'from app.core.config import settings; print(int(settings.WEB_PUSH_ENABLED))')
if [ "$push_enabled" = "1" ]; then
  push_heartbeat=$(compose exec -T redis sh -ceu \
    'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --raw get legaltech:push:recovery-heartbeat')
  now=$(date +%s)
  case "$push_heartbeat" in *[!0-9]*|'') fail "no valid Web Push heartbeat";; esac
  [ "$push_heartbeat" -le "$now" ] || fail "Web Push heartbeat is in the future"
  [ $((now - push_heartbeat)) -le "$heartbeat_max_age" ] || fail "Web Push heartbeat is stale"
  push_stale=$(compose exec -T db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT count(*) FROM push_recovery_candidates(1, 120)")
  [ "$push_stale" = "0" ] || fail "recoverable Web Push outbox work remains"
fi

routine_heartbeat=$(compose exec -T redis sh -ceu \
  'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --raw get legaltech:routines:recovery-heartbeat')
now=$(date +%s)
case "$routine_heartbeat" in *[!0-9]*|'') fail "no valid routine reminder heartbeat";; esac
[ "$routine_heartbeat" -le "$now" ] || fail "routine reminder heartbeat is in the future"
[ $((now - routine_heartbeat)) -le "$heartbeat_max_age" ] || fail "routine reminder heartbeat is stale"
routine_due=$(compose exec -T db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM routine_reminder_candidates(1)")
[ "$routine_due" = "0" ] || fail "due routine reminders remain to be processed"

printf '%s\n' 'notification-recovery-health: Beat, worker, reminders, and durable outboxes are healthy'
