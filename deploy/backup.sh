#!/usr/bin/env bash
# deploy/backup.sh - Automated PostgreSQL & System Backup for Ketrika (SPECS §25, R6.8, ADR-102)
set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ketrika}"
PGDATABASE="${PGDATABASE:-ketrika}"
START_EPOCH=$(date +%s)
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
TIMESTAMP_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
BACKUP_FILE="ketrika_backup_${TIMESTAMP}.dump"
LATEST_FILE="ketrika_backup_latest.dump"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Starting Ketrika database backup for ${PGDATABASE}@${PGHOST}:${PGPORT} at ${TIMESTAMP_ISO}..."

# Export PGPASSWORD if set in environment
if [ -n "${POSTGRES_PASSWORD:-}" ] && [ -z "${PGPASSWORD:-}" ]; then
    export PGPASSWORD="${POSTGRES_PASSWORD}"
fi

BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"
LATEST_PATH="${BACKUP_DIR}/${LATEST_FILE}"
MANIFEST_PATH="${BACKUP_DIR}/${BACKUP_FILE}.meta.json"
LATEST_MANIFEST_PATH="${BACKUP_DIR}/${LATEST_FILE}.meta.json"

# Execute pg_dump in custom binary compressed format (-Fc)
echo "[INFO] Executing pg_dump..."
pg_dump \
    -h "${PGHOST}" \
    -p "${PGPORT}" \
    -U "${PGUSER}" \
    -d "${PGDATABASE}" \
    -Fc \
    -f "${BACKUP_PATH}"

# Immediate structural verification via pg_restore --list (R6.8 / ADR-102)
echo "[INFO] Verifying archive readability with pg_restore --list..."
pg_restore --list "${BACKUP_PATH}" > /dev/null
echo "[SUCCESS] Dump archive catalog verified readable."

# Generate SHA-256 checksum
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${BACKUP_PATH}" > "${BACKUP_PATH}.sha256"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${BACKUP_PATH}" > "${BACKUP_PATH}.sha256"
else
    echo "[ERROR] Neither sha256sum nor shasum is available!" >&2
    exit 1
fi

SHA256_HASH=$(awk '{print $1}' "${BACKUP_PATH}.sha256")
DUMP_SIZE_BYTES=$(stat -c %s "${BACKUP_PATH}" 2>/dev/null || wc -c < "${BACKUP_PATH}" | tr -d ' ')
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Generate certified JSON manifest (ADR-102)
cat <<EOF > "${MANIFEST_PATH}"
{
  "backup_id": "${BACKUP_FILE%.dump}",
  "timestamp_utc": "${TIMESTAMP_ISO}",
  "git_commit": "${GIT_COMMIT}",
  "dump_filename": "${BACKUP_FILE}",
  "dump_sha256": "${SHA256_HASH}",
  "dump_size_bytes": ${DUMP_SIZE_BYTES},
  "database_name": "${PGDATABASE}",
  "verified_readable": true
}
EOF

# Copy / symlink as latest
cp -f "${BACKUP_PATH}" "${LATEST_PATH}"
cp -f "${BACKUP_PATH}.sha256" "${LATEST_PATH}.sha256"
cp -f "${MANIFEST_PATH}" "${LATEST_MANIFEST_PATH}"

END_EPOCH=$(date +%s)
DURATION_SECONDS=$((END_EPOCH - START_EPOCH))
BACKUP_SIZE_HUMAN=$(du -h "${BACKUP_PATH}" | awk '{print $1}')
echo "[SUCCESS] Database backup completed: ${BACKUP_PATH} (${BACKUP_SIZE_HUMAN}, ${DUMP_SIZE_BYTES} bytes, SHA-256: ${SHA256_HASH:0:16}..., duration: ${DURATION_SECONDS}s)"

# Retention: purge local backup dumps older than 7 days (bronze object storage is strictly immutable and untouched)
echo "[INFO] Enforcing local dump retention policy (7 days)..."
find "${BACKUP_DIR}" -name "ketrika_backup_*.dump" -type f -mtime +7 -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "ketrika_backup_*.dump.sha256" -type f -mtime +7 -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "ketrika_backup_*.dump.meta.json" -type f -mtime +7 -delete 2>/dev/null || true

# Optional Restic push to R2 / B2 object storage if configured (SPECS §25)
if [ -n "${RESTIC_REPOSITORY:-}" ] && command -v restic >/dev/null 2>&1; then
    echo "[INFO] Snapshotting backup into Restic repository..."
    restic backup "${BACKUP_PATH}" "${MANIFEST_PATH}" --tag "ketrika-db"
    restic forget --keep-daily 7 --keep-weekly 4 --prune
    echo "[SUCCESS] Restic remote snapshot completed."
fi

echo "[DONE] Backup procedure finished successfully at $(date -u +"%Y-%m-%dT%H:%M:%SZ")."
