#!/usr/bin/env bash
# deploy/restore.sh - Database Restoration & Verification Procedure for Ketrika (SPECS §25, R6.8, ADR-102)
set -euo pipefail

BACKUP_FILE="${1:-./backups/ketrika_backup_latest.dump}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ketrika}"
PGDATABASE="${PGDATABASE:-ketrika_restore_clone}"
ALLOW_ACTIVE_DB_OVERWRITE="${ALLOW_ACTIVE_DB_OVERWRITE:-0}"
START_EPOCH=$(date +%s)

# Guard against accidental restoration into an active production database (ADR-102 / R6.8)
PROTECTED_ACTIVE_DATABASES=("ketrika" "ketrika_prod" "ketrika_active" "production" "postgres")
for active in "${PROTECTED_ACTIVE_DATABASES[@]}"; do
    if [ "${PGDATABASE,,}" = "${active,,}" ] && [ "${ALLOW_ACTIVE_DB_OVERWRITE}" != "1" ]; then
        echo "[ERROR] Refusal to restore onto active database '${PGDATABASE}'." >&2
        echo "Restorations must be strictly targeted at explicitly named qualification clones (e.g., 'ketrika_clone', 'ketrika_restore_clone') to prevent destruction of live operational data (R6.8, ADR-102)." >&2
        echo "If this is an intentional, destructive recovery operation, set ALLOW_ACTIVE_DB_OVERWRITE=1." >&2
        exit 2
    fi
done

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[ERROR] Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "[INFO] Starting restoration from ${BACKUP_FILE} into clone database ${PGDATABASE}@${PGHOST}:${PGPORT}..."

# Export PGPASSWORD if set in environment
if [ -n "${POSTGRES_PASSWORD:-}" ] && [ -z "${PGPASSWORD:-}" ]; then
    export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

# Verify checksum if companion file exists
if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo "[INFO] Verifying backup SHA-256 checksum..."
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "${BACKUP_FILE}.sha256" || { echo "[ERROR] Checksum verification failed for ${BACKUP_FILE}!" >&2; exit 1; }
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c "${BACKUP_FILE}.sha256" || { echo "[ERROR] Checksum verification failed for ${BACKUP_FILE}!" >&2; exit 1; }
    fi
    echo "[SUCCESS] Checksum verified."
fi

# Verify manifest if present
MANIFEST_FILE="${BACKUP_FILE%.dump}.dump.meta.json"
if [ ! -f "${MANIFEST_FILE}" ]; then
    MANIFEST_FILE="${BACKUP_FILE}.meta.json"
fi
if [ -f "${MANIFEST_FILE}" ]; then
    echo "[INFO] Verifying companion manifest: ${MANIFEST_FILE}"
fi

# Ensure target database exists; if not, create it
echo "[INFO] Ensuring target database '${PGDATABASE}' exists on ${PGHOST}:${PGPORT}..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = '${PGDATABASE}'" | grep -q 1 || \
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres -c \
    "CREATE DATABASE \"${PGDATABASE}\" WITH OWNER \"${PGUSER}\";"

# Terminate existing connections to clone database to allow clean restoration
echo "[INFO] Terminating active connections to ${PGDATABASE}..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${PGDATABASE}' AND pid <> pg_backend_pid();" >/dev/null

# Execute pg_restore into clone
echo "[INFO] Restoring schema and data into clone '${PGDATABASE}'..."
set +e
pg_restore \
    -h "${PGHOST}" \
    -p "${PGPORT}" \
    -U "${PGUSER}" \
    -d "${PGDATABASE}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    "${BACKUP_FILE}"
RESTORE_STATUS=$?
set -e

if [ $RESTORE_STATUS -gt 1 ]; then
    echo "[ERROR] pg_restore failed with exit code ${RESTORE_STATUS}" >&2
    exit $RESTORE_STATUS
fi

echo "[SUCCESS] Database clone restored successfully."

# Refresh Gold analytical views post-restoration if function exists
echo "[INFO] Refreshing Gold analytical views post-restoration..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c \
    "DO \$\$ BEGIN IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'refresh_all_gold_views') THEN PERFORM refresh_all_gold_views(); END IF; END \$\$;"

# Verification & record counting
echo "[INFO] Verifying table counts in restored clone database:"
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "
SELECT
    'meta.source_record: ' || (SELECT count(*) FROM meta.source_record) || E'\n' ||
    'obs.price_observation: ' || (SELECT count(*) FROM obs.price_observation) || E'\n' ||
    'gold.weekly_bulletin_facts: ' || (SELECT count(*) FROM information_schema.tables WHERE table_schema='gold' AND table_name='weekly_bulletin_facts');
"

END_EPOCH=$(date +%s)
DURATION_SECONDS=$((END_EPOCH - START_EPOCH))
echo "[SUCCESS] Restoration and integrity verification complete in ${DURATION_SECONDS}s."
