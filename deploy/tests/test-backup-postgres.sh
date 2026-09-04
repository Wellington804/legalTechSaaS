#!/bin/sh
set -eu

# Executes the real backup script with only ephemeral, local command doubles.
# It proves the decrypt path accepts the script-owned existing mktemp target.
root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/legaltech-backup-test.XXXXXX")
cleanup() { rm -rf -- "$tmp_root"; }
trap cleanup EXIT HUP INT TERM

mock_bin="$tmp_root/bin"
backup_dir="$tmp_root/backups"
mkdir -p "$mock_bin" "$backup_dir"
printf '%s\n' mock-passphrase > "$tmp_root/passphrase"
printf '%s\n' mock-key > "$tmp_root/key"

cat > "$mock_bin/docker" <<'SCRIPT'
#!/bin/sh
set -eu
case "$*" in
  *pg_dump*) printf '%s' mock-postgres-custom-dump ;;
  *pg_restore*) content=$(cat); [ "$content" = mock-postgres-custom-dump ] ;;
  *) exit 0 ;;
esac
SCRIPT

cat > "$mock_bin/gpg" <<'SCRIPT'
#!/bin/sh
set -eu
output=
input=
decrypt=false
allow_existing=false
last=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes) allow_existing=true; shift ;;
    --output) output=$2; shift 2 ;;
    --decrypt) decrypt=true; input=$2; shift 2 ;;
    --passphrase-file|--cipher-algo) shift 2 ;;
    --batch|--quiet|--pinentry-mode|loopback|--symmetric) shift ;;
    *) last=$1; shift ;;
  esac
done
[ -n "$output" ]
if [ "$decrypt" = true ]; then
  [ "$allow_existing" = true ] || exit 31
  [ -n "$input" ] && cp "$input" "$output"
else
  [ -n "$last" ] && cp "$last" "$output"
fi
SCRIPT

cat > "$mock_bin/scp" <<'SCRIPT'
#!/bin/sh
set -eu
archive=false
checksum=false
for arg in "$@"; do
  case "$arg" in
    *.dump.gpg) [ -f "$arg" ] && archive=true ;;
    *.dump.gpg.sha256) [ -f "$arg" ] && checksum=true ;;
  esac
done
[ "$archive" = true ] && [ "$checksum" = true ]
SCRIPT

cat > "$mock_bin/flock" <<'SCRIPT'
#!/bin/sh
set -eu
[ "$1" = '-n' ]
[ "$2" = '9' ]
: "${FLOCK_MARKER:?}"
: > "$FLOCK_MARKER"
SCRIPT
chmod 700 "$mock_bin/docker" "$mock_bin/gpg" "$mock_bin/scp" "$mock_bin/flock"

PATH="$mock_bin:$PATH" \
BACKUP_DIRECTORY="$backup_dir" \
BACKUP_PASSPHRASE_FILE="$tmp_root/passphrase" \
BACKUP_RETENTION_DAYS=14 \
BACKUP_OFFSITE_SSH_DESTINATION='ops@backup.example:/archives/legaltech' \
BACKUP_OFFSITE_SSH_KEY_PATH="$tmp_root/key" \
LEGALTECH_COMPOSE_FILE="$tmp_root/compose.yml" \
FLOCK_MARKER="$tmp_root/flock-used" \
  sh "$root_dir/deploy/backup-postgres.sh" >/dev/null

set -- "$backup_dir"/legaltech-postgres-*.dump.gpg
[ "$#" -eq 1 ]
[ -f "$1.sha256" ]
[ -f "$tmp_root/flock-used" ]
printf '%s\n' 'backup mock integration: passed'
