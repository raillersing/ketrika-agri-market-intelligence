#!/usr/bin/env pwsh
<#
.SYNOPSIS
    scripts/dev.ps1 : Single entry point for local development operations on Windows.
#>

param(
    [Parameter(Position=0)]
    [string]$Command = "help",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$ArgsList
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host "Ketrika Agri Market Intelligence - Dev Runner" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: ./scripts/dev.ps1 <command> [args...]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  up                 - Start Docker development services and await healthchecks"
    Write-Host "  down               - Stop Docker development services"
    Write-Host "  reset              - Reset Docker volumes, restart, migrate and seed"
    Write-Host "  migrate            - Run Alembic database migrations"
    Write-Host "  seed               - Seed sources, taxonomy, units, geo and demo users"
    Write-Host "  check              - Run lint, format, typecheck and unit tests (backend & web)"
    Write-Host "  test               - Run all backend integration and unit tests"
    Write-Host "  test-network       - Run tests requiring live network access"
    Write-Host "  backfill <src>     - Run Dagster backfill for specified source or all"
    Write-Host "  rebuild            - Rebuild Silver and Gold from Bronze with network disabled"
    Write-Host "  e2e                - Run Playwright end-to-end tests"
    Write-Host "  bulletin           - Generate a weekly PPN bulletin draft"
    Write-Host "  demo               - Execute the final MVP acceptance scenario (T11.6)"
    Write-Host "  logs <service>     - Follow Docker logs for a specific service"
    Write-Host "  validate-registry  - Validate registry/sources.yaml against Pydantic schema"
}

switch ($Command) {
    "help" {
        Show-Help
        exit 0
    }
    "up" {
        Write-Host "Starting Docker development stack..." -ForegroundColor Green
        if (-not (Test-Path .env)) {
            if (Test-Path .env.example) {
                Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
                Copy-Item .env.example .env
            }
        }
        docker compose up -d --build --wait
        exit $LASTEXITCODE
    }
    "down" {
        Write-Host "Stopping Docker development stack..." -ForegroundColor Yellow
        docker compose down
        exit $LASTEXITCODE
    }
    "reset" {
        Write-Host "Resetting dev environment (wiping dev volumes)..." -ForegroundColor Red
        docker compose down -v
        & $PSCommandPath up
        & $PSCommandPath migrate
        & $PSCommandPath seed
        exit $LASTEXITCODE
    }
    "migrate" {
        Write-Host "Running Alembic migrations..." -ForegroundColor Cyan
        $check = docker compose exec -T api sh -c "test -f /app/alembic.ini && echo yes || echo no"
        if ($check.Trim() -eq "yes") {
            docker compose exec -T api alembic upgrade head
            exit $LASTEXITCODE
        } else {
            Write-Host "Notice: alembic.ini not yet present (scheduled for T2.1). Skipping migration." -ForegroundColor Yellow
            exit 0
        }
    }
    "seed" {
        Write-Host "Seeding database..." -ForegroundColor Cyan
        $check = docker compose exec -T api sh -c "python -c 'import ketrika.normalize.loader' 2>/dev/null && echo yes || echo no"
        if ($check.Trim() -eq "yes") {
            docker compose exec -T api python -m ketrika.normalize.loader seed
            exit $LASTEXITCODE
        } else {
            Write-Host "Notice: ketrika.normalize.loader not yet present (scheduled for T2.5). Skipping seed." -ForegroundColor Yellow
            exit 0
        }
    }
    "check" {
        Write-Host "=== Running Backend Quality Checks ===" -ForegroundColor Cyan
        $backendExit = 0
        try {
            docker run --rm -v "${PWD}/backend:/app" -w /app ketrika-backend:test sh -c "ruff check src tests && ruff format --check src tests && mypy src tests && pytest -m 'not network'"
            $backendExit = $LASTEXITCODE
        } catch {
            $backendExit = 1
        }

        Write-Host "=== Running Web Quality Checks ===" -ForegroundColor Cyan
        $webExit = 0
        try {
            docker run --rm -v "${PWD}/web:/app" -v /app/node_modules -w /app ketrika-web:dev pnpm test
            $webExit = $LASTEXITCODE
        } catch {
            $webExit = 1
        }

        if ($backendExit -ne 0 -or $webExit -ne 0) {
            Write-Error "Quality checks failed: backend exit code $backendExit, web exit code $webExit"
            exit 1
        }

        Write-Host "All checks passed successfully!" -ForegroundColor Green
        exit 0
    }
    "test" {
        Write-Host "Running backend tests..." -ForegroundColor Cyan
        docker compose exec -T api pytest
        exit $LASTEXITCODE
    }
    "test-network" {
        Write-Host "Running live network tests..." -ForegroundColor Cyan
        docker compose exec -T api pytest -m "network"
        exit $LASTEXITCODE
    }
    "backfill" {
        $source = if ($ArgsList) { $ArgsList[0] } else { "all" }
        Write-Host "Running backfill for $source..." -ForegroundColor Cyan
        docker compose exec -T api python -m ketrika.pipelines.backfill $source
        exit $LASTEXITCODE
    }
    "rebuild" {
        Write-Host "Rebuilding Silver/Gold from Bronze offline..." -ForegroundColor Cyan
        docker compose exec -T -e HTTP_OFFLINE=1 api python -m ketrika.pipelines.rebuild
        exit $LASTEXITCODE
    }
    "e2e" {
        Write-Host "Running web E2E tests..." -ForegroundColor Cyan
        docker compose exec -T web pnpm e2e
        exit $LASTEXITCODE
    }
    "bulletin" {
        Write-Host "Generating bulletin draft..." -ForegroundColor Cyan
        docker compose exec -T api python -m ketrika.bulletin.writer
        exit $LASTEXITCODE
    }
    "demo" {
        Write-Host "Executing MVP acceptance test scenario..." -ForegroundColor Cyan
        docker compose exec -T api python -m ketrika.demo
        exit $LASTEXITCODE
    }
    "logs" {
        $service = if ($ArgsList) { $ArgsList[0] } else { "" }
        if ($service) {
            docker compose logs -f $service
        } else {
            docker compose logs -f
        }
        exit 0
    }
    "validate-registry" {
        Write-Host "Validating source registry schema..." -ForegroundColor Cyan
        docker run --rm -v "${PWD}:/workspace" -w /workspace ketrika-backend:test python -m ketrika.core.registry
        exit $LASTEXITCODE
    }
    default {
        Write-Host "Error: Unknown command '$Command'" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
