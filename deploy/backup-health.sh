#!/bin/sh
set -eu

fail() { printf '%s\n' "backup-health: $*" >&2; exit 1; }
: "${BACKUP_DIRECTORY:?set BACKUP_DIRECTORY}"
: "${BACKUP_MAX_AGE_HOURS:?set BACKUP_MAX_AGE_HOURS}"
case "$BACKUP_MAX_AGE_HOURS" in *[!0-9]*|'') fail "BACKUP_MAX_AGE_HOURS must be an integer";; esac
case "$BACKUP_DIRECTORY" in /*) ;; *) fail "BACKUP_DIRECTORY must be absolute";; esac
command -v sha256sum >/dev/null || fail "sha256sum is required"

backup_dir=$(cd "$BACKUP_DIRECTORY" 2>/dev/null && pwd -P) || fail "backup directory is unavailable"
case "$backup_dir" in /|.) fail "BACKUP_DIRECTORY must be a dedicated directory";; esac
latest=$(find "$backup_dir" -mindepth 1 -maxdepth 1 -type f -name 'legaltech-postgres-*.dump.gpg' \
  -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d ' ' -f 2-)
[ -n "$latest" ] || fail "no encrypted PostgreSQL backup found"
[ -f "$latest.sha256" ] || fail "checksum missing for latest backup"
(cd "$backup_dir" && sha256sum -c "$(basename "$latest").sha256" >/dev/null)

age_seconds=$(( $(date +%s) - $(stat -c %Y "$latest") ))
max_age_seconds=$(( BACKUP_MAX_AGE_HOURS * 3600 ))
[ "$age_seconds" -le "$max_age_seconds" ] || fail "latest backup exceeds BACKUP_MAX_AGE_HOURS"
printf 'backup-health: latest encrypted PostgreSQL backup is current and checksum-valid\n'
