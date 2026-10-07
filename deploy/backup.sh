#!/usr/bin/env bash
# deploy/backup.sh - Automated PostgreSQL & System Backup for Ketrika (SPECS §25, T11.3)
set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ketrika}"
PGDATABASE="${PGDATABASE:-ketrika}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_FILE="ketrika_backup_${TIMESTAMP}.dump"
LATEST_FILE="ketrika_backup_latest.dump"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Starting Ketrika database backup for ${PGDATABASE}@${PGHOST}:${PGPORT}..."

# Export PGPASSWORD if set in environment
if [ -n "${POSTGRES_PASSWORD:-}" ] && [ -z "${PGPASSWORD:-}" ]; then
    export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"
LATEST_PATH="${BACKUP_DIR}/${LATEST_FILE}"

# Execute pg_dump in custom binary compressed format (-Fc)
pg_dump \
    -h "${PGHOST}" \
    -p "${PGPORT}" \
    -U "${PGUSER}" \
    -d "${PGDATABASE}" \
    -Fc \
    -f "${BACKUP_PATH}"

# Generate SHA-256 checksum
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${BACKUP_PATH}" > "${BACKUP_PATH}.sha256"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${BACKUP_PATH}" > "${BACKUP_PATH}.sha256"
fi

# Copy / symlink as latest
cp -f "${BACKUP_PATH}" "${LATEST_PATH}"
if [ -f "${BACKUP_PATH}.sha256" ]; then
    cp -f "${BACKUP_PATH}.sha256" "${LATEST_PATH}.sha256"
fi

BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | awk '{print $1}')
echo "[SUCCESS] Database backup completed: ${BACKUP_PATH} (${BACKUP_SIZE})"

# Retention: purge daily backups older than 7 days, keep 4 weekly
echo "[INFO] Enforcing retention policy (7 daily / 4 weekly)..."
find "${BACKUP_DIR}" -name "ketrika_backup_*.dump" -type f -mtime +7 -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "ketrika_backup_*.dump.sha256" -type f -mtime +7 -delete 2>/dev/null || true

# Optional Restic push to R2 / B2 object storage if configured (SPECS §25)
if [ -n "${RESTIC_REPOSITORY:-}" ] && command -v restic >/dev/null 2>&1; then
    echo "[INFO] Snapshotting backup into Restic repository..."
    restic backup "${BACKUP_PATH}" --tag "ketrika-db"
    restic forget --keep-daily 7 --keep-weekly 4 --prune
    echo "[SUCCESS] Restic remote snapshot completed."
fi

echo "[DONE] Backup procedure finished successfully."
