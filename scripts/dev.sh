#!/usr/bin/env bash
# scripts/dev.sh : Single entry point for local development operations on Linux / VPS

set -euo pipefail

COMMAND="${1:-help}"
shift || true

show_help() {
  echo "Ketrika Agri Market Intelligence - Dev Runner (Linux)"
  echo ""
  echo "Usage: ./scripts/dev.sh <command> [args...]"
  echo ""
  echo "Commands:"
  echo "  up                 - Start Docker development services and await healthchecks"
  echo "  down               - Stop Docker development services"
  echo "  reset              - Reset Docker volumes, restart, migrate and seed"
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
    docker compose down -v
    "$0" up
    "$0" migrate
    "$0" seed
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
    echo "=== Running Backend Quality Checks ==="
    if docker network ls --filter "name=aiagent_default" -q | grep -q .; then
      docker run --rm --network aiagent_default -v "${PWD}/backend:/app" -v "${PWD}:/workspace" -w /app ketrika-backend:test sh -c "ruff check src tests && ruff format --check src tests && mypy src tests && pytest -m 'not network'"
    else
      docker run --rm -v "${PWD}/backend:/app" -v "${PWD}:/workspace" -w /app ketrika-backend:test sh -c "ruff check src tests && ruff format --check src tests && mypy src tests && pytest -m 'not network and not integration'"
    fi
    echo "=== Running Web Quality Checks ==="
    docker run --rm -v "${PWD}/web:/app" -v /app/node_modules -w /app ketrika-web:dev pnpm test
    echo "All checks passed successfully!"
    ;;
  test)
    docker compose exec -T api pytest
    ;;
  test-network)
    docker compose exec -T api pytest -m "network"
    ;;
  backfill)
    SRC="${1:-all}"
    docker compose exec -T api python -m ketrika.pipelines.backfill "$SRC"
    ;;
  rebuild)
    docker compose exec -T -e HTTP_OFFLINE=1 api python -m ketrika.pipelines.rebuild
    ;;
  e2e)
    if [ -f "scripts/run_e2e.mjs" ] && command -v node >/dev/null 2>&1; then
      node scripts/run_e2e.mjs
    else
      docker compose exec -T web pnpm e2e
    fi
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
