#!/usr/bin/env bash
# scripts/dev.sh : Single entry point for local development operations on Linux / VPS

set -euo pipefail

COMMAND="${1:-help}"
shift || true

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

qa_compose() {
  docker compose --env-file "$REPO_ROOT/scripts/qualification.env" --project-name ketrika-qualification-main-integration -f "$REPO_ROOT/docker-compose.qualification.yml" "$@"
}

qa_proof_args() {
  qa_commit="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  qa_dirty="$(git -C "$REPO_ROOT" status --porcelain --untracked-files=normal -- backend web scripts registry taxonomy geo docker docker-compose.qualification.yml .gitattributes)"
  [ -z "$qa_dirty" ] || { echo "Source changes must be committed before qualification" >&2; exit 1; }
  qa_fingerprint="$(docker run --rm --network none --mount "type=bind,source=$REPO_ROOT,target=/workspace,readonly" -e PYTHONPATH=/workspace/backend/src ketrika-backend:qa-codex-r03 python -m ketrika.core.qualification_reports fingerprint /workspace)"
  [[ "$qa_commit" =~ ^[0-9a-f]{40}$ && "$qa_fingerprint" =~ ^[0-9a-f]{64}$ ]] || { echo "Cannot bind source proof" >&2; exit 1; }
  QA_PROOF_ARGS=(-e "KETRIKA_SOURCE_COMMIT=$qa_commit" -e "KETRIKA_SOURCE_FINGERPRINT=$qa_fingerprint")
  for qa_role in BACKEND WEB BROWSER; do
    case "$qa_role" in
      BACKEND) qa_image=ketrika-backend:qa-codex-r03 ;;
      WEB) qa_image=ketrika-web:qa-codex-r03 ;;
      BROWSER) qa_image=ketrika-backend:qa-codex-browser-r03 ;;
    esac
    qa_image_id="$(docker image inspect --format '{{.Id}}' "$qa_image")"
    [[ "$qa_image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Cannot bind runtime image" >&2; exit 1; }
    QA_PROOF_ARGS+=(-e "KETRIKA_PROOF_${qa_role}_IMAGE_ID=$qa_image_id")
  done
}

qa_owned_resource() {
  resource_kind="$1"
  resource_name="$2"
  if docker "$resource_kind" inspect "$resource_name" >/dev/null 2>&1; then
    resource_scope="$(docker "$resource_kind" inspect --format '{{index .Labels "ketrika.scope"}}' "$resource_name")"
    resource_project="$(docker "$resource_kind" inspect --format '{{index .Labels "com.docker.compose.project"}}' "$resource_name")"
    if [ "$resource_scope" != "qualification" ] || [ "$resource_project" != "ketrika-qualification-main-integration" ]; then
      echo "Refusing foreign qualification resource: $resource_name" >&2
      exit 1
    fi
  fi
}

qa_prepare() {
  docker run --rm --network none --mount "type=bind,source=$REPO_ROOT,target=/workspace,readonly" -e PYTHONPATH=/workspace/backend/src ketrika-backend:qa-codex-r03 python -m ketrika.core.qualification compose /workspace/docker-compose.qualification.yml
  qa_owned_resource network ketrika_qualification_main_integration_network
  for qa_volume in pgdata bronze backend_venv_r03 backend_source_r03 web_source_r03 web_node_modules_r03 web_next_r03 browser_venv_r03; do
    qa_owned_resource volume "ketrika_qualification_main_integration_$qa_volume"
  done
  qa_compose config --quiet
  if [ "${1:-}" = check ]; then
    qa_compose stop api web
  fi
  qa_compose up -d --wait --wait-timeout 120 db minio mailpit
  qa_compose run --rm --no-deps minio-init
  qa_compose run --rm --no-deps api sh /workspace/scripts/qa-backend.sh prepare
}

qa_isolated() {
  qa_action="${1:-}"
  [ "$#" -gt 0 ] && shift
  case "$qa_action" in
    check|test|governance|prepare|qa|e2e|negative-build) ;;
    *) echo "Unsupported isolated command; protected targets are never implicit" >&2; exit 1 ;;
  esac
  case "$qa_action" in
    test|qa) ;;
    *) [ "$#" -eq 0 ] || { echo "Unexpected isolated command arguments" >&2; exit 1; } ;;
  esac
  if [ "$qa_action" = qa ]; then
    [ "$#" -eq 1 ] || { echo "QA requires exactly one configured task ID" >&2; exit 1; }
    docker run --rm --network none --mount "type=bind,source=$REPO_ROOT,target=/workspace,readonly" -e PYTHONPATH=/workspace/backend/src ketrika-backend:qa-codex-r03 python -m ketrika.core.qa_manifest "$1" --validate-only
  fi
  qa_prepare "$qa_action"
  case "$qa_action" in
    check)
      qa_proof_args
      qa_compose run --rm --no-deps "${QA_PROOF_ARGS[@]}" api sh /workspace/scripts/qa-backend.sh check
      qa_compose run --rm --no-deps "${QA_PROOF_ARGS[@]}" web sh /workspace/scripts/qa-web.sh check
      docker run --rm --network none --mount "type=bind,source=$REPO_ROOT,target=/workspace,readonly" --mount type=volume,source=ketrika_qualification_main_integration_web_node_modules_r03,target=/frontend,readonly -e PYTHONPATH=/workspace/backend/src "${QA_PROOF_ARGS[@]}" ketrika-backend:qa-codex-r03 python -m ketrika.core.qualification_reports check-frontend /frontend/.qa-results --commit "$qa_commit"
      ;;
    test) qa_compose run --rm --no-deps api sh /workspace/scripts/qa-backend.sh test "$@" ;;
    governance) qa_compose run --rm --no-deps api sh /workspace/scripts/qa-backend.sh governance ;;
    qa) qa_compose run --rm --no-deps api sh /workspace/scripts/qa-backend.sh qa "$@" ;;
    negative-build) qa_compose run --rm --no-deps web sh /workspace/scripts/qa-web.sh negative-build ;;
    e2e)
      qa_proof_args
      qa_compose up -d --no-deps --force-recreate api web
      qa_compose run --rm --no-deps "${QA_PROOF_ARGS[@]}" browser
      ;;
    prepare) echo "Dedicated qualification environment ready; no live source/model qualified" ;;
  esac
}

show_help() {
  echo "Ketrika Agri Market Intelligence - Dev Runner (Linux)"
  echo ""
  echo "Usage: ./scripts/dev.sh <command> [args...]"
  echo ""
  echo "Commands:"
  echo "  up                 - Start Docker development services and await healthchecks"
  echo "  down               - Stop Docker development services"
  echo "  reset              - Refused: immutable Bronze must never be deleted"
  echo "  migrate            - Run Alembic database migrations"
  echo "  seed               - Seed sources, taxonomy, units, geo and demo users"
  echo "  check              - Run lint, format, typecheck and unit tests (backend & web)"
  echo "  test               - Run all backend integration and unit tests"
  echo "  test-network       - Run tests requiring live network access"
  echo "  backfill <src>     - Run Dagster backfill for specified source or all"
  echo "  rebuild            - Rebuild Silver and Gold from Bronze with network disabled"
  echo "  e2e                - Run Playwright end-to-end tests"
  echo "  bulletin           - Generate a weekly PPN bulletin draft"
  echo "  demo               - Execute the final MVP acceptance scenario (T11.6)"
  echo "  backup             - Dump PostgreSQL database to ./backups"
  echo "  restore [file]     - Restore database from backup and refresh Gold views"
  echo "  logs <service>     - Follow Docker logs for a specific service"
  echo "  validate-registry  - Validate registry/sources.yaml against Pydantic schema"
  echo "  qa-isolated <cmd>  - Dedicated profile: check, test, governance, prepare"
  echo "  qa-build           - Build locked backend, web and browser QA images"
  echo "  qa-profile <xml>   - Read archived JUnit timings; no tests or database"
  echo "  qa <task_id>       - Run a declared measured software subset"
}


case "$COMMAND" in
  help)
    show_help
    exit 0
    ;;
  up)
    if [ ! -f .env ] && [ -f .env.example ]; then
      cp .env.example .env
    fi
    docker compose up -d --build --wait
    ;;
  down)
    docker compose down
    ;;
  reset)
    echo "Reset refused: it would delete immutable Bronze volumes. Use qa-isolated prepare." >&2
    exit 1
    ;;
  migrate)
    if docker compose exec -T api test -f /app/alembic.ini 2>/dev/null; then
      docker compose exec -T api alembic upgrade head
    else
      echo "Notice: alembic.ini not yet present (scheduled for T2.1). Skipping migration."
    fi
    ;;
  seed)
    if docker compose exec -T api python -c "import ketrika.normalize.loader" 2>/dev/null; then
      docker compose exec -T api python -m ketrika.normalize.loader seed
    else
      echo "Notice: ketrika.normalize.loader not yet present (scheduled for T2.5). Skipping seed."
    fi
    ;;
  check)
    qa_isolated check
    ;;
  test)
    qa_isolated test "$@"
    ;;
  qa-isolated)
    qa_isolated "$@"
    ;;
  qa-build)
    docker build --target base -t ketrika-backend:qa-codex-r03 "$REPO_ROOT/backend"
    docker build -t ketrika-web:qa-codex-r03 "$REPO_ROOT/web"
    docker build --target backend-browser -t ketrika-backend:qa-codex-browser-r03 "$REPO_ROOT/backend"
    ;;
  qa)
    qa_isolated qa "$@"
    ;;
  qa-profile)
    [ "$#" -eq 1 ] || { echo "QA profile requires one relative XML report path" >&2; exit 1; }
    docker run --rm --network none --mount "type=bind,source=$REPO_ROOT,target=/workspace,readonly" -e PYTHONPATH=/workspace/backend/src ketrika-backend:qa-codex-r03 python -m ketrika.core.qa_profile "$1"
    ;;
  qualify)
    [ "$#" -ge 1 ] && [ "$#" -le 2 ] || { echo "qualify requires R0|all and optional relative evidence directory" >&2; exit 1; }
    case "$1" in R0|all) ;; *) echo "Unavailable qualification phase" >&2; exit 1 ;; esac
    qa_owned_resource volume ketrika_qualification_main_integration_backend_venv_r03
    qa_proof_args
    docker run --rm --network none --mount "type=bind,source=$REPO_ROOT,target=/workspace,readonly" --mount type=volume,source=ketrika_qualification_main_integration_backend_venv_r03,target=/reports -e PYTHONPATH=/workspace/backend/src "${QA_PROOF_ARGS[@]}" ketrika-backend:qa-codex-r03 python -m ketrika.core.qualify "$1" --commit "$qa_commit" --evidence "${2:-docs/evidence/qualification}"
    ;;
  test-network)
    docker compose exec -T api pytest -m "network"
    ;;
  backfill)
    SRC="${1:-all}"
    docker compose exec -T api python -m ketrika.pipelines.backfill "$SRC"
    ;;
  rebuild-smoke)
    [ "$#" -eq 1 ] && { [ "$1" = prepare ] || [ "$1" = replay ]; } || { echo "rebuild-smoke requires prepare|replay" >&2; exit 1; }
    qa_owned_resource volume ketrika_qualification_main_integration_backend_venv_r03
    for rebuild_suffix in pgdata socket copy reports; do
      rebuild_name="ketrika_rebuild_qualification_$rebuild_suffix"
      if docker volume inspect "$rebuild_name" >/dev/null 2>&1; then
        [ "$(docker volume inspect --format '{{index .Labels "ketrika.scope"}}' "$rebuild_name")" = rebuild-qualification ] &&
        [ "$(docker volume inspect --format '{{index .Labels "com.docker.compose.project"}}' "$rebuild_name")" = ketrika-rebuild-qualification ] || { echo "Foreign rebuild volume refused" >&2; exit 1; }
      fi
    done
    rebuild_compose=(docker compose --env-file "$REPO_ROOT/scripts/qualification.env" --project-name ketrika-rebuild-qualification -f "$REPO_ROOT/docker-compose.rebuild-qualification.yml")
    "${rebuild_compose[@]}" config --quiet
    "${rebuild_compose[@]}" up -d --wait db
    rebuild_service=worker
    [ "$1" != prepare ] || rebuild_service=prepare
    "${rebuild_compose[@]}" run --no-deps "$rebuild_service"
    ;;
  rebuild)
    docker compose exec -T -e HTTP_OFFLINE=1 api python -m ketrika.pipelines.rebuild
    ;;
  e2e)
    qa_isolated e2e
    ;;
  bulletin)
    docker compose exec -T api python -m ketrika.bulletin.writer
    ;;
  demo)
    docker compose exec -T api python -m ketrika.demo
    ;;
  backup)
    mkdir -p ./backups
    docker compose exec -T db pg_dump -U ketrika -d ketrika -Fc -f /tmp/backup.dump
    TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
    docker compose cp db:/tmp/backup.dump "./backups/ketrika_backup_${TIMESTAMP}.dump"
    cp -f "./backups/ketrika_backup_${TIMESTAMP}.dump" "./backups/ketrika_backup_latest.dump"
    docker compose exec -T db rm -f /tmp/backup.dump
    echo "Backup created at ./backups/ketrika_backup_${TIMESTAMP}.dump"
    ;;
  restore)
    BACKUP_FILE="${1:-./backups/ketrika_backup_latest.dump}"
    if [ ! -f "$BACKUP_FILE" ]; then
      echo "Error: Backup file not found: $BACKUP_FILE" >&2
      exit 1
    fi
    docker compose cp "$BACKUP_FILE" db:/tmp/restore.dump
    docker compose exec -T db pg_restore -U ketrika -d ketrika --clean --if-exists --no-owner --no-privileges /tmp/restore.dump || true
    docker compose exec -T db rm -f /tmp/restore.dump
    docker compose exec -T api python -c "from ketrika.core.db import get_session; from ketrika.gold.refresh import refresh_gold_views;
with get_session() as s:
    refresh_gold_views(s)
    s.commit()
"
    echo "Restoration complete."

    ;;
  logs)
    docker compose logs -f "${1:-}"
    ;;
  validate-registry)
    docker run --rm -v "${PWD}:/workspace" -w /workspace -e PYTHONPATH=/workspace/backend/src ketrika-backend:test python -m ketrika.core.registry
    ;;
  *)
    echo "Error: Unknown command '$COMMAND'" >&2
    show_help
    exit 1
    ;;
esac
