#!/bin/sh
set -eu
umask 077

fail() { printf '%s\n' "backup: $*" >&2; exit 1; }
require() { eval "value=\${$1:-}"; [ -n "$value" ] || fail "set $1"; }
verify_checksum() {
  checksum_archive=$1
  checksum_file=$2
  checksum_name=$(basename -- "$checksum_archive")
  [ -f "$checksum_file" ] || fail "checksum missing"
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

for name in BACKUP_DIRECTORY BACKUP_PASSPHRASE_FILE BACKUP_RETENTION_DAYS \
  BACKUP_OFFSITE_SSH_DESTINATION BACKUP_OFFSITE_SSH_KEY_PATH; do
  require "$name"
done

case "$BACKUP_RETENTION_DAYS" in *[!0-9]*|'') fail "BACKUP_RETENTION_DAYS must be an integer";; esac
case "$BACKUP_DIRECTORY" in /*) ;; *) fail "BACKUP_DIRECTORY must be absolute";; esac
offsite_user_host=${BACKUP_OFFSITE_SSH_DESTINATION%%:*}
offsite_path=${BACKUP_OFFSITE_SSH_DESTINATION#*:}
offsite_user=${offsite_user_host%@*}
offsite_host=${offsite_user_host#*@}
[ "$offsite_user_host" != "$BACKUP_OFFSITE_SSH_DESTINATION" ] || fail "BACKUP_OFFSITE_SSH_DESTINATION must be user@host:/absolute/path"
case "$offsite_user" in ''|*[!A-Za-z0-9._-]*) fail "offsite SSH user contains unsupported characters";; esac
case "$offsite_host" in ''|*[!A-Za-z0-9.-]*) fail "offsite SSH host contains unsupported characters";; esac
case "$offsite_path" in /*) ;; *) fail "offsite path must be absolute";; esac
case "$offsite_path" in *[!A-Za-z0-9._/-]*) fail "offsite path contains unsupported characters";; esac
[ -f "$BACKUP_PASSPHRASE_FILE" ] || fail "missing BACKUP_PASSPHRASE_FILE"
[ -s "$BACKUP_PASSPHRASE_FILE" ] || fail "empty BACKUP_PASSPHRASE_FILE"
[ -f "$BACKUP_OFFSITE_SSH_KEY_PATH" ] || fail "missing BACKUP_OFFSITE_SSH_KEY_PATH"
command -v docker >/dev/null || fail "docker is required"
command -v gpg >/dev/null || fail "gpg is required"
command -v scp >/dev/null || fail "scp is required"
command -v sha256sum >/dev/null || fail "sha256sum is required"
command -v flock >/dev/null || fail "flock is required"

mkdir -p "$BACKUP_DIRECTORY"
backup_dir=$(cd "$BACKUP_DIRECTORY" && pwd -P)
case "$backup_dir" in /|.) fail "BACKUP_DIRECTORY must be a dedicated directory";; esac

# Covers timer/manual overlap and makes the timestamped archive name collision-free.
lock_file="$backup_dir/.legaltech-postgres-backup.lock"
exec 9>"$lock_file"
flock -n 9 || fail "another backup is already running for this directory"

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
compose_file=${LEGALTECH_COMPOSE_FILE:-"$script_dir/../docker-compose.prod.yml"}
compose() {
  if [ -n "${LEGALTECH_ENV_FILE:-}" ]; then
    docker compose --env-file "$LEGALTECH_ENV_FILE" -f "$compose_file" "$@"
  else
    docker compose -f "$compose_file" "$@"
  fi
}

tmp_dump=$(mktemp "$backup_dir/.legaltech-postgres.XXXXXX.dump")
tmp_decrypted=$(mktemp "$backup_dir/.legaltech-postgres.verify.XXXXXX.dump")
cleanup() { rm -f -- "$tmp_dump" "$tmp_decrypted"; }
trap cleanup EXIT HUP INT TERM

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$backup_dir/legaltech-postgres-$timestamp.dump.gpg"
checksum="$archive.sha256"

# Custom pg_dump contains all PostgreSQL data, including document bytea values.
compose exec -T db sh -ceu \
  'exec pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > "$tmp_dump"
compose exec -T db pg_restore --list --file=/dev/null < "$tmp_dump" >/dev/null
gpg --batch --yes --pinentry-mode loopback --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
  --symmetric --cipher-algo AES256 --output "$archive" "$tmp_dump"
(cd "$backup_dir" && sha256sum "$(basename "$archive")" > "$(basename "$checksum")")
verify_checksum "$archive" "$checksum"
# tmp_decrypted is an empty mktemp file owned by this invocation; --yes only permits
# this known temporary destination to be overwritten after authenticated decryption.
gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
  --output "$tmp_decrypted" --decrypt "$archive"
cmp -s "$tmp_dump" "$tmp_decrypted" || fail "decrypted archive differs from original dump"
compose exec -T db pg_restore --list --file=/dev/null < "$tmp_decrypted" >/dev/null

# Offsite destination and key are fixed by the environment, never accepted as arguments.
scp -i "$BACKUP_OFFSITE_SSH_KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes \
  -- "$archive" "$checksum" "${BACKUP_OFFSITE_SSH_DESTINATION%/}/"

# Retention is limited to the resolved backup directory and only our generated names.
find "$backup_dir" -mindepth 1 -maxdepth 1 -type f \
  \( -name 'legaltech-postgres-*.dump.gpg' -o -name 'legaltech-postgres-*.dump.gpg.sha256' \) \
  -mtime +"$BACKUP_RETENTION_DAYS" -delete

printf 'backup: verified encrypted dump %s and copied it offsite\n' "$archive"
