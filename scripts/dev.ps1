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

$RepoRoot = Split-Path -Parent $PSScriptRoot
$QaComposeArgs = @("compose", "--env-file", (Join-Path $RepoRoot "scripts/qualification.env"), "--project-name", "ketrika-qualification", "-f", (Join-Path $RepoRoot "docker-compose.qualification.yml"))

function Invoke-QaDocker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Qualification Docker step failed (exit $LASTEXITCODE)" }
}

function Test-QaResourceOwnership {
    param([string]$Kind, [string]$Name)
    $resourceNames = @(& docker $Kind ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw "Cannot list qualification resources" }
    if ($resourceNames -contains $Name) {
        $labelJson = & docker $Kind inspect --format '{{json .Labels}}' $Name
        if ($LASTEXITCODE -ne 0) { throw "Cannot inspect qualification labels" }
        $labels = $labelJson | ConvertFrom-Json
        if ($labels.'ketrika.scope' -ne "qualification" -or $labels.'com.docker.compose.project' -ne "ketrika-qualification") {
            throw "Refusing foreign qualification resource: $Name"
        }
    }
}

function Get-QaCommit {
    $gitLocation = Join-Path $RepoRoot ".git"
    if (Test-Path $gitLocation -PathType Leaf) {
        $gitLocation = (Get-Content $gitLocation -Raw).Trim() -replace '^gitdir:\s*', ''
        if ($gitLocation -match '^/mnt/([a-z])/(.*)$') {
            $gitLocation = $Matches[1].ToUpper() + ':\' + $Matches[2].Replace('/', '\')
        } elseif ($gitLocation.StartsWith('/')) {
            $gitLocation = '\\wsl.localhost\Ubuntu' + $gitLocation.Replace('/', '\')
        }
    }
    $commit = & git -c "safe.directory=$RepoRoot" "--git-dir=$gitLocation" "--work-tree=$RepoRoot" rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') { throw "Cannot bind proof to Git commit" }
    $dirty = & git -c "safe.directory=$RepoRoot" "--git-dir=$gitLocation" "--work-tree=$RepoRoot" status --porcelain --untracked-files=normal -- backend web scripts registry taxonomy geo docker docker-compose.qualification.yml .gitattributes
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw "Source changes must be committed before qualification" }
    return $commit.Trim()
}

function Get-QaProofArgs {
    $proofCommit = Get-QaCommit
    $fingerprint = & docker run --rm --network none --mount "type=bind,source=$RepoRoot,target=/workspace,readonly" -e PYTHONPATH=/workspace/backend/src ketrika-backend:qa-r03 python -m ketrika.core.qualification_reports fingerprint /workspace
    if ($LASTEXITCODE -ne 0 -or $fingerprint -notmatch '^[0-9a-f]{64}$') { throw "Cannot bind source snapshot" }
    $result = @("-e", "KETRIKA_SOURCE_COMMIT=$proofCommit", "-e", "KETRIKA_SOURCE_FINGERPRINT=$fingerprint")
    foreach ($entry in @(@("BACKEND", "ketrika-backend:qa-r03"), @("WEB", "ketrika-web:qa-r03"), @("BROWSER", "ketrika-backend:qa-browser-r03"))) {
        $imageId = & docker image inspect --format '{{.Id}}' $entry[1]
        if ($LASTEXITCODE -ne 0 -or $imageId -notmatch '^sha256:[0-9a-f]{64}$') { throw "Cannot bind runtime image" }
        $result += @("-e", ("KETRIKA_PROOF_" + $entry[0] + "_IMAGE_ID=" + $imageId))
    }
    return $result
}

function Invoke-QaIsolated {
    param([string]$Action, [string[]]$RemainingArgs = @())
    if ($Action -notin @("check", "test", "governance", "prepare", "qa", "e2e", "negative-build")) {
        throw "Unsupported isolated command; protected targets are never implicit"
    }
    if ($Action -notin @("test", "qa") -and $RemainingArgs.Count -gt 0) {
        throw "Unexpected isolated command arguments"
    }
    if ($Action -eq "qa") {
        if ($RemainingArgs.Count -ne 1) { throw "QA requires exactly one configured task ID" }
        Invoke-QaDocker -DockerArgs (@("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "-e", "PYTHONPATH=/workspace/backend/src", "ketrika-backend:qa-r03", "python", "-m", "ketrika.core.qa_manifest", $RemainingArgs[0], "--validate-only"))
    }
    Invoke-QaDocker -DockerArgs @("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "-e", "PYTHONPATH=/workspace/backend/src", "ketrika-backend:qa-r03", "python", "-m", "ketrika.core.qualification", "compose", "/workspace/docker-compose.qualification.yml")
    Test-QaResourceOwnership -Kind "network" -Name "ketrika_qualification_network"
    foreach ($suffix in @("pgdata", "bronze", "backend_venv_r03", "backend_source_r03", "web_source_r03", "web_node_modules_r03", "web_next_r03", "browser_venv_r03")) {
        Test-QaResourceOwnership -Kind "volume" -Name "ketrika_qualification_$suffix"
    }
    Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("config", "--quiet"))
    if ($Action -eq "check") {
        Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("stop", "api", "web"))
    }
    Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("up", "-d", "--wait", "--wait-timeout", "120", "db", "minio", "mailpit"))
    Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps", "minio-init"))
    Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps", "api", "sh", "/workspace/scripts/qa-backend.sh", "prepare"))
    switch ($Action) {
        "check" {
            $proofArgs = Get-QaProofArgs
            Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps") + $proofArgs + @("api", "sh", "/workspace/scripts/qa-backend.sh", "check"))
            Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps") + $proofArgs + @("web", "sh", "/workspace/scripts/qa-web.sh", "check"))
            Invoke-QaDocker -DockerArgs (@("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "--mount", "type=volume,source=ketrika_qualification_web_node_modules_r03,target=/frontend,readonly", "-e", "PYTHONPATH=/workspace/backend/src") + $proofArgs + @("ketrika-backend:qa-r03", "python", "-m", "ketrika.core.qualification_reports", "check-frontend", "/frontend/.qa-results", "--commit", (Get-QaCommit)))
        }
        "test" { Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps", "api", "sh", "/workspace/scripts/qa-backend.sh", "test") + $RemainingArgs) }
        "governance" { Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps", "api", "sh", "/workspace/scripts/qa-backend.sh", "governance")) }
        "qa" { Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps", "api", "sh", "/workspace/scripts/qa-backend.sh", "qa") + $RemainingArgs) }
        "negative-build" { Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps", "web", "sh", "/workspace/scripts/qa-web.sh", "negative-build")) }
        "e2e" {
            $proofArgs = Get-QaProofArgs
            Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("up", "-d", "--no-deps", "--force-recreate", "api", "web"))
            Invoke-QaDocker -DockerArgs ($QaComposeArgs + @("run", "--rm", "--no-deps") + $proofArgs + @("browser"))
        }
        "prepare" { Write-Host "Dedicated qualification environment ready; no live source/model qualified" }
    }
}

function Show-Help {
    Write-Host "Ketrika Agri Market Intelligence - Dev Runner" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: ./scripts/dev.ps1 <command> [args...]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  up                 - Start Docker development services and await healthchecks"
    Write-Host "  down               - Stop Docker development services"
    Write-Host "  reset              - Refused: immutable Bronze must never be deleted"
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
    Write-Host "  backup             - Dump PostgreSQL database to ./backups"
    Write-Host "  restore [file]     - Restore database from backup and refresh Gold views"
    Write-Host "  logs <service>     - Follow Docker logs for a specific service"
    Write-Host "  validate-registry  - Validate registry/sources.yaml against Pydantic schema"
    Write-Host "  qa-isolated <cmd>  - Dedicated profile: check, test, governance, prepare"
    Write-Host "  qa-build           - Build locked backend, web and browser QA images"
    Write-Host "  qa <task_id>       - Run a declared measured software subset"
    Write-Host "  qa-profile <xml>   - Read archived JUnit timings; no test execution or database"
}


switch ($Command) {
    "qa-profile" {
        if ($ArgsList.Count -ne 1) { throw "QA profile requires one relative XML report path" }
        Invoke-QaDocker -DockerArgs @("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "-e", "PYTHONPATH=/workspace/backend/src", "ketrika-backend:qa-r03", "python", "-m", "ketrika.core.qa_profile", $ArgsList[0])
        exit 0
    }
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
        Write-Error "Reset refused: it would delete immutable Bronze volumes. Use qa-isolated prepare."
        exit 1
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
        Invoke-QaIsolated -Action "check"
        exit 0
    }
    "test" {
        Invoke-QaIsolated -Action "test" -RemainingArgs $ArgsList
        exit 0
    }
    "qa-isolated" {
        $action = if ($ArgsList) { $ArgsList[0] } else { "" }
        $remaining = if ($ArgsList.Count -gt 1) { $ArgsList[1..($ArgsList.Count - 1)] } else { @() }
        Invoke-QaIsolated -Action $action -RemainingArgs $remaining
        exit 0
    }
    "qa-build" {
        Invoke-QaDocker -DockerArgs @("build", "--target", "base", "-t", "ketrika-backend:qa-r03", (Join-Path $RepoRoot "backend"))
        Invoke-QaDocker -DockerArgs @("build", "-t", "ketrika-web:qa-r03", (Join-Path $RepoRoot "web"))
        Invoke-QaDocker -DockerArgs @("build", "--target", "backend-browser", "-t", "ketrika-backend:qa-browser-r03", (Join-Path $RepoRoot "backend"))
        exit 0
    }
    "qa" {
        Invoke-QaIsolated -Action "qa" -RemainingArgs $ArgsList
        exit 0
    }
    "qualify" {
        if ($ArgsList.Count -lt 1 -or $ArgsList.Count -gt 2 -or $ArgsList[0] -notin @("R0", "all")) { throw "qualify requires R0|all and optional relative evidence directory" }
        Test-QaResourceOwnership -Kind "volume" -Name "ketrika_qualification_backend_venv_r03"
        $proofArgs = Get-QaProofArgs
        $evidence = if ($ArgsList.Count -eq 2) { $ArgsList[1] } else { "docs/evidence/qualification" }
        Invoke-QaDocker -DockerArgs (@("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "--mount", "type=volume,source=ketrika_qualification_backend_venv_r03,target=/reports", "-e", "PYTHONPATH=/workspace/backend/src") + $proofArgs + @("ketrika-backend:qa-r03", "python", "-m", "ketrika.core.qualify", $ArgsList[0], "--commit", (Get-QaCommit), "--evidence", $evidence))
        exit 0
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
        Invoke-QaIsolated -Action "e2e"
        exit 0
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
    "backup" {
        Write-Host "Creating database backup..." -ForegroundColor Cyan
        $backupDir = Join-Path $PSScriptRoot "..\backups"
        if (!(Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
        $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
        $backupFile = "ketrika_backup_$timestamp.dump"
        $latestFile = "ketrika_backup_latest.dump"
        $backupPath = Join-Path $backupDir $backupFile
        $latestPath = Join-Path $backupDir $latestFile

        docker compose exec -T db pg_dump -U ketrika -d ketrika -Fc -f /tmp/backup.dump
        docker compose cp db:/tmp/backup.dump $backupPath
        docker compose exec -T db rm -f /tmp/backup.dump
        Copy-Item -Force $backupPath $latestPath
        $size = (Get-Item $backupPath).Length
        Write-Host "Database backup successfully created: $backupPath ($size bytes)" -ForegroundColor Green
        exit 0
    }
    "restore" {
        $backupPath = if ($ArgsList) { $ArgsList[0] } else { Join-Path $PSScriptRoot "..\backups\ketrika_backup_latest.dump" }
        if (!(Test-Path $backupPath)) {
            Write-Error "Backup file not found: $backupPath"
            exit 1
        }
        Write-Host "Restoring database from $backupPath..." -ForegroundColor Cyan
        docker compose cp $backupPath db:/tmp/restore.dump
        docker compose exec -T db pg_restore -U ketrika -d ketrika --clean --if-exists --no-owner --no-privileges /tmp/restore.dump
        docker compose exec -T db rm -f /tmp/restore.dump
        Write-Host "Refreshing Gold analytical views post-restore..." -ForegroundColor Cyan
        docker compose exec -T api python -c "from ketrika.core.db import get_session; from ketrika.gold.refresh import refresh_gold_views;
with get_session() as s:
    refresh_gold_views(s)
    s.commit()
"
        Write-Host "Restoration complete." -ForegroundColor Green
        exit 0
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
        docker run --rm -v "${PWD}:/workspace" -w /workspace -e PYTHONPATH=/workspace/backend/src ketrika-backend:test python -m ketrika.core.registry
        exit $LASTEXITCODE
    }
    default {
        Write-Host "Error: Unknown command '$Command'" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
