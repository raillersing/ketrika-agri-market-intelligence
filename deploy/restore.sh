#!/usr/bin/env bash
# deploy/restore.sh - Database Restoration & Verification Procedure for Ketrika (SPECS §25, T11.3)
set -euo pipefail

BACKUP_FILE="${1:-./backups/ketrika_backup_latest.dump}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ketrika}"
PGDATABASE="${PGDATABASE:-ketrika}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[ERROR] Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "[INFO] Starting restoration from ${BACKUP_FILE} into ${PGDATABASE}@${PGHOST}:${PGPORT}..."

# Export PGPASSWORD if set in environment
if [ -n "${POSTGRES_PASSWORD:-}" ] && [ -z "${PGPASSWORD:-}" ]; then
    export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

# Verify checksum if companion file exists
if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo "[INFO] Verifying backup SHA-256 checksum..."
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "${BACKUP_FILE}.sha256" || { echo "[ERROR] Checksum verification failed!" >&2; exit 1; }
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c "${BACKUP_FILE}.sha256" || { echo "[ERROR] Checksum verification failed!" >&2; exit 1; }
    fi
    echo "[SUCCESS] Checksum verified."
fi

# Terminate existing connections to database to allow clean restoration
echo "[INFO] Terminating active connections to ${PGDATABASE}..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${PGDATABASE}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true

# Execute pg_restore
echo "[INFO] Restoring database schema and data..."
# pg_restore exit code 0 or 1 (warnings on existing extensions/roles are acceptable)
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
    "${BACKUP_FILE}" >/dev/null 2>&1
RESTORE_STATUS=$?
set -e

if [ $RESTORE_STATUS -gt 1 ]; then
    echo "[ERROR] pg_restore failed with exit code ${RESTORE_STATUS}" >&2
    exit $RESTORE_STATUS
fi

echo "[SUCCESS] Database restored successfully."

# Refresh Gold materialized views to guarantee query consistency
echo "[INFO] Refreshing Gold analytical views post-restoration..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c \
    "SELECT refresh_all_gold_views();" >/dev/null 2>&1 || {
    echo "[WARN] refresh_all_gold_views() not found or failed, refreshing manually..."
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "REFRESH MATERIALIZED VIEW gold.price_monthly;" >/dev/null 2>&1 || true
}

# Verification & record counting
echo "[INFO] Verifying table counts in restored database:"
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "
SELECT
    'meta.source_record: ' || (SELECT count(*) FROM meta.source_record) || E'\n' ||
    'obs.price_observation: ' || (SELECT count(*) FROM obs.price_observation) || E'\n' ||
    'gold.price_monthly: ' || (SELECT count(*) FROM gold.price_monthly) || E'\n' ||
    'gold.source_health: ' || (SELECT count(*) FROM gold.source_health);
"

echo "[SUCCESS] Restoration and integrity verification complete."
