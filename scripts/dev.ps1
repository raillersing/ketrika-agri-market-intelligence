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
$QaComposeArgs = @("compose", "--env-file", (Join-Path $RepoRoot "scripts/qualification.env"), "--project-name", "ketrika-qualification-main-final", "-f", (Join-Path $RepoRoot "docker-compose.qualification.yml"))

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
        if ($labels.'ketrika.scope' -ne "qualification" -or $labels.'com.docker.compose.project' -ne "ketrika-qualification-main-final") {
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
    $fingerprint = & docker run --rm --network none --mount "type=bind,source=$RepoRoot,target=/workspace,readonly" -e PYTHONPATH=/workspace/backend/src ketrika-backend:qa-codex-r04 python -m ketrika.core.qualification_reports fingerprint /workspace
    if ($LASTEXITCODE -ne 0 -or $fingerprint -notmatch '^[0-9a-f]{64}$') { throw "Cannot bind source snapshot" }
    $result = @("-e", "KETRIKA_SOURCE_COMMIT=$proofCommit", "-e", "KETRIKA_SOURCE_FINGERPRINT=$fingerprint")
    foreach ($entry in @(@("BACKEND", "ketrika-backend:qa-codex-r04"), @("WEB", "ketrika-web:qa-codex-r04"), @("BROWSER", "ketrika-backend:qa-codex-browser-r04"))) {
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
        Invoke-QaDocker -DockerArgs (@("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "-e", "PYTHONPATH=/workspace/backend/src", "ketrika-backend:qa-codex-r04", "python", "-m", "ketrika.core.qa_manifest", $RemainingArgs[0], "--validate-only"))
    }
    Invoke-QaDocker -DockerArgs @("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "-e", "PYTHONPATH=/workspace/backend/src", "ketrika-backend:qa-codex-r04", "python", "-m", "ketrika.core.qualification", "compose", "/workspace/docker-compose.qualification.yml")
    Test-QaResourceOwnership -Kind "network" -Name "ketrika_qualification_main_final_network"
    foreach ($suffix in @("pgdata", "bronze", "backend_venv_r04", "backend_source_r04", "web_source_r04", "web_node_modules_r04", "web_next_r04", "browser_venv_r04")) {
        Test-QaResourceOwnership -Kind "volume" -Name "ketrika_qualification_main_final_$suffix"
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
            Invoke-QaDocker -DockerArgs (@("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "--mount", "type=volume,source=ketrika_qualification_main_final_web_node_modules_r04,target=/frontend,readonly", "-e", "PYTHONPATH=/workspace/backend/src") + $proofArgs + @("ketrika-backend:qa-codex-r04", "python", "-m", "ketrika.core.qualification_reports", "check-frontend", "/frontend/.qa-results", "--commit", (Get-QaCommit)))
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
    Write-Host "  rebuild-smoke <prepare|replay> - Synthetic software proof, dedicated network-none DB"
    Write-Host "  e2e                - Run Playwright end-to-end tests"
    Write-Host "  bulletin           - Generate a weekly PPN bulletin draft"
    Write-Host "  demo               - Execute the final MVP acceptance scenario (T11.6)"
    Write-Host "  backup             - Dump PostgreSQL database to ./backups"
    Write-Host "  restore [file]     - Restore database from backup and refresh Gold views"
    Write-Host "  logs <service>     - Follow Docker logs for a specific service"
    Write-Host "  validate-registry  - Validate registry/sources.yaml against Pydantic schema"
    Write-Host "  qa-isolated <cmd>  - Dedicated profile: check, test, governance, prepare"
    Write-Host "  qa-build           - Build locked backend, web, browser and MinIO QA images"
    Write-Host "  qa <task_id>       - Run a declared measured software subset"
    Write-Host "  qa-profile <xml>   - Read archived JUnit timings; no test execution or database"
}


switch ($Command) {
    "qa-profile" {
        if ($ArgsList.Count -ne 1) { throw "QA profile requires one relative XML report path" }
        Invoke-QaDocker -DockerArgs @("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "-e", "PYTHONPATH=/workspace/backend/src", "ketrika-backend:qa-codex-r04", "python", "-m", "ketrika.core.qa_profile", $ArgsList[0])
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
        Invoke-QaDocker -DockerArgs @("build", "-t", "ketrika-minio:qa-r0", (Join-Path $RepoRoot "docker/minio"))
        Invoke-QaDocker -DockerArgs @("build", "--target", "base", "-t", "ketrika-backend:qa-codex-r04", (Join-Path $RepoRoot "backend"))
        Invoke-QaDocker -DockerArgs @("build", "-t", "ketrika-web:qa-codex-r04", (Join-Path $RepoRoot "web"))
        Invoke-QaDocker -DockerArgs @("build", "--target", "backend-browser", "-t", "ketrika-backend:qa-codex-browser-r04", (Join-Path $RepoRoot "backend"))
        exit 0
    }
    "qa" {
        Invoke-QaIsolated -Action "qa" -RemainingArgs $ArgsList
        exit 0
    }
    "qualify" {
        if ($ArgsList.Count -lt 1 -or $ArgsList.Count -gt 2 -or $ArgsList[0] -notin @("R0", "all")) { throw "qualify requires R0|all and optional relative evidence directory" }
        Test-QaResourceOwnership -Kind "volume" -Name "ketrika_qualification_main_final_backend_venv_r04"
        $proofArgs = Get-QaProofArgs
        $evidence = if ($ArgsList.Count -eq 2) { $ArgsList[1] } else { "docs/evidence/qualification" }
        Invoke-QaDocker -DockerArgs (@("run", "--rm", "--network", "none", "--mount", "type=bind,source=$RepoRoot,target=/workspace,readonly", "--mount", "type=volume,source=ketrika_qualification_main_final_backend_venv_r04,target=/reports", "-e", "PYTHONPATH=/workspace/backend/src") + $proofArgs + @("ketrika-backend:qa-codex-r04", "python", "-m", "ketrika.core.qualify", $ArgsList[0], "--commit", (Get-QaCommit), "--evidence", $evidence))
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
    "rebuild-smoke" {
        if ($ArgsList.Count -ne 1 -or $ArgsList[0] -notin @("prepare", "replay")) { throw "rebuild-smoke requires prepare|replay" }
        Test-QaResourceOwnership -Kind "volume" -Name "ketrika_qualification_main_final_backend_venv_r04"
        foreach ($suffix in @("pgdata", "socket", "copy", "reports")) {
            $name = "ketrika_rebuild_qualification_$suffix"
            $existing = @(& docker volume ls --format '{{.Name}}')
            if ($LASTEXITCODE -ne 0) { throw "Cannot list rebuild volumes" }
            if ($existing -contains $name) {
                $labels = (& docker volume inspect --format '{{json .Labels}}' $name) | ConvertFrom-Json
                if ($LASTEXITCODE -ne 0 -or $labels.'ketrika.scope' -ne "rebuild-qualification" -or $labels.'com.docker.compose.project' -ne "ketrika-rebuild-qualification") { throw "Foreign rebuild volume refused" }
            }
        }
        $rebuildCompose = @("compose", "--env-file", (Join-Path $RepoRoot "scripts/qualification.env"), "--project-name", "ketrika-rebuild-qualification", "-f", (Join-Path $RepoRoot "docker-compose.rebuild-qualification.yml"))
        Invoke-QaDocker -DockerArgs ($rebuildCompose + @("config", "--quiet"))
        Invoke-QaDocker -DockerArgs ($rebuildCompose + @("up", "-d", "--wait", "db"))
        $service = if ($ArgsList[0] -eq "prepare") { "prepare" } else { "worker" }
        $runName = "ketrika-rebuild-" + $ArgsList[0] + "-" + [guid]::NewGuid().ToString("N")
        Invoke-QaDocker -DockerArgs ($rebuildCompose + @("run", "--no-deps", "--name", $runName, $service))
        exit 0
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
        $backupDir = Join-Path $PSScriptRoot "..\backups"
        if (!(Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }
        $backupJob = "ketrika_backup_" + [guid]::NewGuid().ToString("N")
        docker compose cp (Join-Path $RepoRoot "deploy/backup.sh") "db:/tmp/$backupJob.sh"
        if ($LASTEXITCODE -ne 0) { throw "Backup tooling copy failed" }
        docker compose exec -T -e "BACKUP_DIR=/tmp/$backupJob" -e RESTIC_REPOSITORY= db bash -ec 'export PGHOST=localhost PGUSER="$POSTGRES_USER" PGDATABASE="$POSTGRES_DB"; exec bash "$1"' -- "/tmp/$backupJob.sh"
        if ($LASTEXITCODE -ne 0) { throw "Backup or integrity verification failed" }
        docker compose cp "db:/tmp/$backupJob/." $backupDir
        if ($LASTEXITCODE -ne 0) { throw "Backup evidence export failed" }
        Write-Host "Backup archive, SHA256 and manifest exported to $backupDir" -ForegroundColor Green
        exit 0
    }
    "restore" {
        $backupPath = if ($ArgsList) { $ArgsList[0] } else { Join-Path $PSScriptRoot "..\backups\ketrika_backup_latest.dump" }
        if (!(Test-Path $backupPath)) {
            Write-Error "Backup file not found: $backupPath"
            exit 1
        }
        if (!$env:PGHOST -or !$env:PGUSER -or !$env:PGDATABASE -or !$env:KETRIKA_RESTORE_NETWORK -or $env:RESTORE_CONFIRM_DATABASE -ne $env:PGDATABASE) {
            throw "Explicit clone connection, confirmation and isolated network are required"
        }
        $restoreNetworkJson = & docker network inspect $env:KETRIKA_RESTORE_NETWORK
        if ($LASTEXITCODE -ne 0) { throw "Cannot inspect restore network" }
        $restoreNetworks = @($restoreNetworkJson | ConvertFrom-Json)
        if ($restoreNetworks.Count -ne 1 -or !$restoreNetworks[0].Internal -or $restoreNetworks[0].Labels.'ketrika.scope' -ne 'restore-qualification') {
            throw "Foreign restore network refused"
        }
        $backupPath = (Resolve-Path $backupPath).Path
        $backupParent = Split-Path -Parent $backupPath
        $backupName = Split-Path -Leaf $backupPath
        docker run --rm --pull never --network $env:KETRIKA_RESTORE_NETWORK `
            --mount "type=bind,source=$backupParent,target=/backup,readonly" `
            --mount "type=bind,source=$RepoRoot,target=/workspace,readonly" `
            -e PGHOST -e PGPORT -e PGUSER -e PGDATABASE -e PGPASSWORD -e POSTGRES_PASSWORD `
            -e RESTORE_CONFIRM_DATABASE -e ALLOW_ACTIVE_DB_OVERWRITE `
            --entrypoint bash postgis/postgis:17-3.5 /workspace/deploy/restore.sh "/backup/$backupName"
        if ($LASTEXITCODE -ne 0) { throw "Isolated restore failed (exit $LASTEXITCODE)" }
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
