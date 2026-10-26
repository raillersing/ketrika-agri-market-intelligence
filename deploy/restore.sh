#!/usr/bin/env bash
# ADR-124: restore only to an explicitly confirmed, newly created clone.
set -euo pipefail

BACKUP_FILE="${1:-./backups/ketrika_backup_latest.dump}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-ketrika}"
PGDATABASE="${PGDATABASE:-ketrika_restore_clone}"

refuse() { echo "[ERROR] $1" >&2; exit 2; }
[[ "${ALLOW_ACTIVE_DB_OVERWRITE:-0}" == 0 ]] || refuse 'Database overwrite is forbidden.'
[[ "$PGDATABASE" =~ ^ketrika_restore_[a-z0-9_]+$ && ${#PGDATABASE} -le 63 ]] || refuse 'A dedicated ketrika_restore_* target is required.'
[[ "${RESTORE_CONFIRM_DATABASE:-}" == "$PGDATABASE" ]] || refuse 'RESTORE_CONFIRM_DATABASE must exactly confirm the new target.'
for required in psql createdb pg_restore; do
    command -v "$required" >/dev/null || refuse "Required tool unavailable: $required"
done
command -v sha256sum >/dev/null || refuse 'sha256sum is required.'
[[ -f "$BACKUP_FILE" && -f "$BACKUP_FILE.sha256" ]] || refuse 'Archive and SHA256 companion are required.'
MANIFEST_FILE="${BACKUP_FILE%.dump}.meta.json"
[[ -f "$MANIFEST_FILE" ]] || MANIFEST_FILE="$BACKUP_FILE.meta.json"
[[ -f "$MANIFEST_FILE" ]] || refuse 'A JSON manifest is required.'

read -r expected_hash checksum_filename < "$BACKUP_FILE.sha256"
actual_hash="$(sha256sum "$BACKUP_FILE")"
actual_hash="${actual_hash%% *}"
archive_filename="$(basename "$BACKUP_FILE")"
[[ "$expected_hash" =~ ^[a-f0-9]{64}$ && "$expected_hash" == "$actual_hash" && "${checksum_filename#\*}" == "$archive_filename" ]] || refuse 'Archive checksum or filename mismatch.'
archive_size="$(wc -c < "$BACKUP_FILE" | tr -d '[:space:]')"

if [[ -n "${POSTGRES_PASSWORD:-}" && -z "${PGPASSWORD:-}" ]]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
fi
pg_admin() { psql -X -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres "$@"; }
# The manifest is a bound psql value, never executable SQL or shell code.
source_database="$(pg_admin -At -v "manifest=$(cat "$MANIFEST_FILE")" -v "filename=$archive_filename" -v "sha=$actual_hash" -v "bytes=$archive_size" <<'SQL'
WITH m AS (SELECT :'manifest'::jsonb AS v)
SELECT CASE WHEN v->>'dump_filename'=:'filename'
    AND v->>'dump_sha256'=:'sha'
    AND (v->>'dump_size_bytes')::bigint=:'bytes'::bigint
    AND v->'verified_readable'='true'::jsonb
    AND v->>'timestamp_utc' ~ '(Z|[+]00:00)$'
    AND (v->>'timestamp_utc')::timestamptz IS NOT NULL
    AND length(trim(v->>'database_name'))>0
THEN v->>'database_name' ELSE '' END FROM m;
SQL
)"
[[ -n "$source_database" && "$source_database" != "$PGDATABASE" ]] || refuse 'Invalid manifest or source equals target.'
pg_restore --list "$BACKUP_FILE" >/dev/null
existing="$(pg_admin -At -v "target=$PGDATABASE" <<'SQL'
SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:'target');
SQL
)"
[[ "$existing" == f ]] || refuse 'Target already exists or its absence could not be verified.'

# createdb is atomic: a concurrent creation refuses rather than reusing a database.
createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --maintenance-db=postgres --owner "$PGUSER" "$PGDATABASE"
echo "[INFO] Restoring to new clone $PGDATABASE."
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
    --single-transaction --exit-on-error --no-owner --no-privileges "$BACKUP_FILE"
# No --clean, connection termination, DROP, or automatic Gold recalculation.
identity="$(psql -X -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -At -v "target=$PGDATABASE" <<'SQL'
SELECT current_database()=:'target';
SQL
)"
[[ "$identity" == t ]] || refuse 'Restored connection does not identify the requested clone.'
psql -X -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -At <<'SQL'
SELECT 'meta.source_record', count(*) FROM meta.source_record
UNION ALL SELECT 'obs.price_observation', count(*) FROM obs.price_observation
UNION ALL SELECT 'ops.bulletin', count(*) FROM ops.bulletin;
SQL
echo "[SUCCESS] Archive restored transactionally to the new clone; corpus qualification remains separate."
