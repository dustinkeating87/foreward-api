#!/bin/bash
# Good Lie Golf — Postgres backup script
# Reads config from ~/.goodlie-backup-env
# Designed to run via launchd (Sundays 10 AM) or manually.
#
# Usage:
#   bash backup.sh              # Manual run, useful for testing
#   launchd handles weekly schedule once installed (see setup docs).

set -euo pipefail

# --- Config -----------------------------------------------------------------

CONFIG_FILE="$HOME/.goodlie-backup-env"
STATUS_FILE="$HOME/.goodlie-backup-status"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    echo ""
    echo "Create it with the template at:"
    echo "  scripts/backup/.goodlie-backup-env.template"
    echo "Save as ~/.goodlie-backup-env, then run: chmod 600 ~/.goodlie-backup-env"
    echo "FAIL $(date) — config missing" > "$STATUS_FILE"
    exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${SUPABASE_DB_URL:?SUPABASE_DB_URL not set in $CONFIG_FILE}"
: "${BACKUP_DIR:?BACKUP_DIR not set in $CONFIG_FILE}"

# launchd starts with minimal PATH — ensure pg_dump is reachable
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/libpq/bin:$PATH"

if ! command -v pg_dump &>/dev/null; then
    echo "ERROR: pg_dump not found. PATH=$PATH"
    echo "FAIL $(date) — pg_dump missing from PATH" > "$STATUS_FILE"
    exit 1
fi

# Trap unexpected errors so status file always reflects reality
trap 'echo "FAIL $(date) — unexpected error (see log)" > "$STATUS_FILE"' ERR

# --- Verify connection (fail fast with clearer error than pg_dump) ---------

echo "[$(date)] Testing connection to Supabase..."
if ! psql "$SUPABASE_DB_URL" -c 'SELECT 1' &>/dev/null; then
    echo "ERROR: Cannot connect to database."
    echo "Check the SUPABASE_DB_URL in $CONFIG_FILE"
    echo "FAIL $(date) — connection failed" > "$STATUS_FILE"
    exit 1
fi
echo "[$(date)] Connection OK"

# --- Run the backup --------------------------------------------------------

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/goodlie_$TIMESTAMP.sql.gz"

echo "[$(date)] Backing up to $BACKUP_FILE"

# --no-owner / --no-acl: strip ownership and permissions so restore works on
#                        a fresh project without role conflicts.
# --clean --if-exists:   restore script will DROP IF EXISTS before CREATE,
#                        making it idempotent against existing schemas.
# --schema=public:       app data
# --schema=auth:         user accounts (Supabase manages this schema)
pg_dump "$SUPABASE_DB_URL" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    --schema=public \
    --schema=auth \
    | gzip > "$BACKUP_FILE"

# Sanity check: a real backup should be much larger than this. If it isn't,
# something went wrong (auth failure, empty database, broken pipe, etc).
SIZE_BYTES=$(stat -f%z "$BACKUP_FILE")
if [[ "$SIZE_BYTES" -lt 10000 ]]; then
    echo "ERROR: Backup file suspiciously small ($SIZE_BYTES bytes). Failing."
    rm -f "$BACKUP_FILE"
    echo "FAIL $(date) — backup too small ($SIZE_BYTES bytes)" > "$STATUS_FILE"
    exit 1
fi

SIZE_HUMAN=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup complete: $SIZE_HUMAN"

# --- Prune backups older than 28 days --------------------------------------

echo "[$(date)] Pruning backups older than 28 days..."
find "$BACKUP_DIR" -name "goodlie_*.sql.gz" -type f -mtime +28 -print -delete

COUNT=$(find "$BACKUP_DIR" -name "goodlie_*.sql.gz" -type f | wc -l | tr -d ' ')
echo "[$(date)] Done. $COUNT backup(s) retained."

# Status file: human-readable, tail with `cat ~/.goodlie-backup-status`
echo "OK $(date) — $COUNT backup(s) retained, latest $SIZE_HUMAN" > "$STATUS_FILE"
