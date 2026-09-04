#!/bin/sh
set -eu
umask 077

fail() { printf '%s\n' "restore: $*" >&2; exit 1; }
verify_checksum() {
  checksum_archive=$1
  checksum_file=$2
  checksum_name=$(basename -- "$checksum_archive")
  [ -f "$checksum_file" ] || fail "backup checksum does not exist"
  [ "$(wc -l < "$checksum_file" | tr -d ' ')" = "1" ] || fail "checksum must contain exactly one line"
  expected_digest=$(cut -d ' ' -f 1 "$checksum_file")
  [ "${#expected_digest}" -eq 64 ] || fail "checksum digest has an invalid length"
  case "$expected_digest" in *[!0123456789abcdefABCDEF]*) fail "checksum digest is invalid";; esac
  checksum_record=$(cat "$checksum_file")
  case "$checksum_record" in
    "$expected_digest  $checksum_name"|"$expected_digest *$checksum_name") ;;
    *) fail "checksum is not bound to the selected archive";;
  esac
  actual_digest=$(sha256sum "$checksum_archive" | cut -d ' ' -f 1)
  [ "$actual_digest" = "$expected_digest" ] || fail "checksum does not match archive"
}
[ "$#" -eq 2 ] || fail "usage: $0 /absolute/backup.dump.gpg legaltech_restore_YYYYMMDD"
archive=$1
target_database=$2

: "${POSTGRES_DB:?set POSTGRES_DB}"
: "${BACKUP_PASSPHRASE_FILE:?set BACKUP_PASSPHRASE_FILE}"
: "${CONFIRM_RESTORE_TARGET:?set CONFIRM_RESTORE_TARGET to the isolated target database}"
[ "$CONFIRM_RESTORE_TARGET" = "$target_database" ] || fail "confirmation must exactly match the target database"
[ "$target_database" != "$POSTGRES_DB" ] || fail "refusing to restore over the production database"
case "$target_database" in legaltech_restore_[a-z0-9_]* ) ;; *) fail "target must be an isolated legaltech_restore_* database";; esac
case "$target_database" in *[!a-z0-9_]* ) fail "target may contain only lowercase letters, numbers, and underscores";; esac
case "$archive" in /*) ;; *) fail "backup archive path must be absolute";; esac
[ -f "$archive" ] || fail "backup archive does not exist"
[ -f "$archive.sha256" ] || fail "backup checksum does not exist"
[ -s "$BACKUP_PASSPHRASE_FILE" ] || fail "missing or empty BACKUP_PASSPHRASE_FILE"
command -v docker >/dev/null || fail "docker is required"
command -v gpg >/dev/null || fail "gpg is required"
command -v sha256sum >/dev/null || fail "sha256sum is required"

verify_checksum "$archive" "$archive.sha256"

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
compose_file=${LEGALTECH_COMPOSE_FILE:-"$script_dir/../docker-compose.prod.yml"}
compose() {
  if [ -n "${LEGALTECH_ENV_FILE:-}" ]; then
    docker compose --env-file "$LEGALTECH_ENV_FILE" -f "$compose_file" "$@"
  else
    docker compose -f "$compose_file" "$@"
  fi
}

existing=$(compose exec -T -e RESTORE_TARGET="$target_database" db sh -ceu \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = '\''$RESTORE_TARGET'\''"')
[ -z "$existing" ] || fail "target database already exists; it will not be changed"

tmp_dump=$(mktemp "${TMPDIR:-/tmp}/legaltech-restore.XXXXXX.dump")
cleanup() { rm -f -- "$tmp_dump"; }
trap cleanup EXIT HUP INT TERM
gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
  --decrypt "$archive" > "$tmp_dump"
compose exec -T db pg_restore --list --file=/dev/null < "$tmp_dump" >/dev/null

compose exec -T -e RESTORE_TARGET="$target_database" db sh -ceu \
  'exec createdb -U "$POSTGRES_USER" "$RESTORE_TARGET"'
compose exec -T -e RESTORE_TARGET="$target_database" db sh -ceu \
  'exec pg_restore --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$RESTORE_TARGET"' \
  < "$tmp_dump"

printf 'restore: completed only into isolated database %s\n' "$target_database"
