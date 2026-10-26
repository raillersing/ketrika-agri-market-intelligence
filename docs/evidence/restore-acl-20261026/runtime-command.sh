#!/usr/bin/env bash
set -euo pipefail
restore_acl_container=ketrika-restore-audit-20261026-db
restore_acl_repo=/home/raillersing/projects/ketrika-qa-worktrees/r08-restore-acl-20261026
[ "$(docker inspect --format '{{index .Config.Labels "ketrika.scope"}}' "$restore_acl_container")" = restore-qualification ]
docker cp "$restore_acl_repo/deploy/restore.sh" "$restore_acl_container:/tmp/restore-acl.sh"
docker exec -e PGHOST=localhost -e PGUSER=ketrika -e PGDATABASE=ketrika_restore_acl_positive -e RESTORE_CONFIRM_DATABASE=ketrika_restore_acl_positive "$restore_acl_container" bash /tmp/restore-acl.sh /tmp/positive-backup/ketrika_backup_latest.dump
docker exec "$restore_acl_container" createdb -U ketrika -T ketrika_restore_positive fixture_acl_source
docker exec "$restore_acl_container" psql -X -v ON_ERROR_STOP=1 -U ketrika -d fixture_acl_source -c 'CREATE ROLE restore_acl_missing_20261026 NOLOGIN; GRANT SELECT ON ops.restore_probe TO restore_acl_missing_20261026;'
docker exec -e PGHOST=localhost -e PGUSER=ketrika -e PGDATABASE=fixture_acl_source -e BACKUP_DIR=/tmp/missing-role-backup -e RESTIC_REPOSITORY= "$restore_acl_container" bash /workspace/deploy/backup.sh
docker exec "$restore_acl_container" psql -X -v ON_ERROR_STOP=1 -U ketrika -d fixture_acl_source -c 'REVOKE SELECT ON ops.restore_probe FROM restore_acl_missing_20261026; DROP ROLE restore_acl_missing_20261026;'
set +e
docker exec -e PGHOST=localhost -e PGUSER=ketrika -e PGDATABASE=ketrika_restore_acl_missing -e RESTORE_CONFIRM_DATABASE=ketrika_restore_acl_missing "$restore_acl_container" bash /tmp/restore-acl.sh /tmp/missing-role-backup/ketrika_backup_latest.dump
restore_acl_missing_exit=$?
set -e
[ "$restore_acl_missing_exit" = 1 ]
[ "$(docker exec "$restore_acl_container" psql -XAt -v ON_ERROR_STOP=1 -U ketrika -d ketrika_restore_acl_missing -c "SELECT to_regclass('ops.restore_probe') IS NULL")" = t ]
echo '{"scope":"private synthetic SQL only; no Bronze or active data","positive_exit":0,"missing_role_exit":1,"missing_role_transaction_rolled_back":true}'
