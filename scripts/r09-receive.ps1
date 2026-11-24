# Run from a clean, committed Windows worktree, never the production checkout.
param([switch]$BuildImages)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Commit = (& git -C $Root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $Commit -notmatch '^[0-9a-f]{40}$') { throw "Cannot bind commit" }
$Dirty = & git -C $Root status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0 -or $Dirty) { throw "Use a clean dedicated worktree" }
if (Test-Path (Join-Path $Root ".env")) { throw "Active .env forbidden in reception worktree" }
$Prefix = "ketrika-r09-" + [Guid]::NewGuid().ToString("N").Substring(0,12)
$Packet = "ketrika_wb_revision_packet_20261104"
$DbName = "ketrika_rebuild_qualification"
$DbImage = "postgis/postgis:17-3.5"
$ShellExe = (Get-Process -Id $PID).Path
$DatabaseContainers = @()

function D([string[]]$CommandArgs) {
    & docker @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker failed: $($CommandArgs[0]), exit $LASTEXITCODE" }
}
function RunDev([string[]]$CommandArgs) {
    & $ShellExe -NoProfile -File (Join-Path $PSScriptRoot "dev.ps1") @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "QA step failed: $($CommandArgs -join ' ')" }
}
function MountVolume([string]$Name, [string]$Target, [bool]$ReadOnly = $false) {
    $Suffix = if ($ReadOnly) { ",readonly" } else { "" }
    return @("--mount", "type=volume,source=$Name,target=$Target$Suffix")
}
function WaitDatabase([string]$Name, [string]$Database) {
    for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {
        & docker exec $Name pg_isready -h /var/run/postgresql -U ketrika -d $Database *> $null
        if ($LASTEXITCODE -eq 0) {
            Start-Sleep -Seconds 2
            & docker exec $Name psql -h /var/run/postgresql -U ketrika -d $Database -Atc "SELECT 1" *> $null
            if ($LASTEXITCODE -eq 0) { return }
        }
        Start-Sleep -Seconds 2
    }
    throw "Dedicated database not ready"
}
function StartDatabase([string]$Role, [string]$InitialDatabase) {
    $Name = "$Prefix-$Role-db"
    $Args = @("run","-d","--pull","never","--name",$Name,"--network","none",
        "--label","ketrika.scope=r09-reception","-e","POSTGRES_USER=ketrika",
        "-e","POSTGRES_PASSWORD=qa-local-only","-e","POSTGRES_DB=$InitialDatabase")
    $Args += MountVolume "$Prefix-$Role-data" "/var/lib/postgresql/data"
    $Args += MountVolume "$Prefix-$Role-socket" "/var/run/postgresql"
    $Args += MountVolume "$Prefix-dump" "/handoff"
    $Args += @($DbImage,"postgres","-c","listen_addresses=")
    D $Args | Out-Host
    $script:DatabaseContainers += $Name
    WaitDatabase $Name $InitialDatabase
    return $Name
}
function Worker([string]$Role, [string]$Socket, [string]$User, [bool]$BronzeReadOnly, [string[]]$Program) {
    $Args = $Common + @("--name","$Prefix-$Role","--user",$User,
        "--tmpfs","/tmp:rw,nosuid,nodev,mode=1777",
        "--workdir","/workspace/backend",
        "-e","DATABASE_URL=postgresql+psycopg://ketrika:qa-local-only@/ketrika_rebuild_qualification?host=/run/ketrika-rebuild")
    $Args += MountVolume "$Prefix-$Socket-socket" "/run/ketrika-rebuild"
    $Args += MountVolume "$Prefix-bronze" "/copy" $BronzeReadOnly
    $Args += MountVolume "$Prefix-output" "/out"
    $Args += @($BackendId) + $Program
    D $Args
}
Write-Host "R0.9 run: $Prefix / $Commit"
D @("volume","inspect","--format","{{.Name}}",$Packet)
D @("image","inspect","--format","{{.Id}}",$DbImage)
if ($BuildImages) { RunDev @("qa-build") }
# Native software receipts must originate on the same content and runtime images.
RunDev @("qa-isolated","check")
RunDev @("qa-isolated","e2e")
$BackendId = (D @("image","inspect","--format","{{.Id}}","ketrika-backend:qa-codex-r05")).Trim()
$WebId = (D @("image","inspect","--format","{{.Id}}","ketrika-web:qa-codex-r05")).Trim()
$BrowserId = (D @("image","inspect","--format","{{.Id}}","ketrika-backend:qa-codex-browser-r05")).Trim()
foreach ($Id in @($BackendId,$WebId,$BrowserId)) {
    if ($Id -notmatch '^sha256:[0-9a-f]{64}$') { throw "Invalid runtime image identity" }
}
$Common = @("run","--pull","never","--network","none","--read-only",
    "--label","ketrika.scope=r09-reception","--security-opt","no-new-privileges:true",
    "--mount","type=bind,source=$Root,target=/workspace,readonly",
    "-e","PYTHONPATH=/workspace/backend/src","-e","PYTHONDONTWRITEBYTECODE=1",
    "-e","APP_ENV=test","-e","LLM_PROVIDER=replay","-e","EXTERNAL_SEND_ENABLED=0")
$Common += MountVolume $Packet "/packet" $true
$Fingerprint = (D ($Common + @("--rm","--user","1000:1000",$BackendId,"python","-m","ketrika.core.qualification_reports","fingerprint","/workspace"))).Trim()
if ($Fingerprint -notmatch '^[0-9a-f]{64}$') { throw "Invalid source fingerprint" }
$Common += @("-e","KETRIKA_SOURCE_COMMIT=$Commit","-e","KETRIKA_SOURCE_FINGERPRINT=$Fingerprint",
    "-e","KETRIKA_PROOF_BACKEND_IMAGE_ID=$BackendId","-e","KETRIKA_PROOF_WEB_IMAGE_ID=$WebId",
    "-e","KETRIKA_PROOF_BROWSER_IMAGE_ID=$BrowserId")
foreach ($Suffix in @("positive-data","positive-socket","negative-data","negative-socket","bronze","output","dump")) {
    $Name = "$Prefix-$Suffix"
    & docker volume inspect $Name *> $null
    if ($LASTEXITCODE -eq 0) { throw "Refusing existing destination volume $Name" }
    D @("volume","create","--label","ketrika.scope=r09-reception",$Name)
}
try {
    Write-Host "=== Prepare native authentic WB data ==="
    $Positive = StartDatabase "positive" $DbName
    Worker "prepare" "positive" "0:0" $false @("python","/workspace/backend/scripts/wb_archive_qualification.py","prepare")
    # Dedicated new output only; no historical volume permissions changed.
    D ($Common + @("--rm","--user","0:0") + (MountVolume "$Prefix-output" "/out") +
        @($BackendId,"sh","-c","chown 1000:1000 /out"))
    Write-Host "=== Preserve baseline and restore separate counterproof clone ==="
    D @("exec",$Positive,"pg_dump","-h","/var/run/postgresql","-U","ketrika","-Fc","-f","/handoff/before.dump",$DbName)
    # Preserve role membership and ACL; copy no role passwords. Only a fresh QA cluster.
    D @("exec",$Positive,"sh","-c","pg_dumpall -h /var/run/postgresql -U ketrika --roles-only --no-role-passwords > /handoff/roles.sql")
    $Negative = StartDatabase "negative" "postgres"
    # ketrika is the only pre-created application role in the new image. Reuse its identity.
    D @("exec",$Negative,"sh","-c","sed '/^CREATE ROLE ketrika;$/d' /handoff/roles.sql > /tmp/r09-roles.sql")
    D @("exec",$Negative,"psql","-h","/var/run/postgresql","-U","ketrika","-d","postgres","-v","ON_ERROR_STOP=1","-f","/tmp/r09-roles.sql")
    D @("exec",$Negative,"createdb","-h","/var/run/postgresql","-U","ketrika","-T","template0",$DbName)
    D @("exec",$Negative,"pg_restore","-h","/var/run/postgresql","-U","ketrika","--exit-on-error","--single-transaction","-d",$DbName,"/handoff/before.dump")
    Write-Host "=== Replay and counterproof (same baseline, no network) ==="
    Worker "positive" "positive" "1000:1000" $true @("python","/workspace/backend/scripts/r09_native_replay.py","positive")
    Worker "negative" "negative" "1000:1000" $true @("python","/workspace/backend/scripts/r09_native_replay.py","negative")
    $Assembler = $Common + @("--name","$Prefix-assemble","--user","1000:1000")
    $Assembler += MountVolume "$Prefix-output" "/out"
    $Assembler += MountVolume "ketrika_qualification_main_final_backend_venv_r05" "/qa-backend" $true
    $Assembler += MountVolume "ketrika_qualification_main_final_web_node_modules_r05" "/qa-frontend" $true
    $Assembler += MountVolume "ketrika_qualification_main_final_browser_venv_r05" "/qa-browser" $true
    D ($Assembler + @($BackendId,"python","/workspace/backend/scripts/r09_assemble.py"))
    Write-Host "=== Final qualify R0 ==="
    $Gate = $Common + @("--name","$Prefix-gate","--user","1000:1000")
    $Gate += MountVolume "$Prefix-output" "/out"
    $Gate += MountVolume "$Prefix-bronze" "/copy" $true
    & docker @Gate $BackendId python -m ketrika.core.qualify R0 --commit $Commit --external-root /packet --external-corpus /packet/corpus --external-bronze /copy --external-evidence /out/bundle --reports /out/final
    $GateExit = $LASTEXITCODE
    D ($Common + @("--rm","--user","1000:1000") + (MountVolume "$Prefix-output" "/out" $true) +
        @($BackendId,"python","-c","from pathlib import Path; p=list(Path('/out/final').glob('*/qualification.md')); print(p[0].read_text() if len(p)==1 else 'No unique final report')"))
    foreach ($Name in @($Positive,$Negative,"$Prefix-prepare","$Prefix-positive","$Prefix-negative","$Prefix-assemble","$Prefix-gate")) {
        D @("inspect","--format","{{.Id}} {{.Name}} {{.Image}} {{.HostConfig.NetworkMode}} {{range .Mounts}}{{.Name}}:{{.Destination}}:{{.RW}} {{end}}",$Name)
    }
    Write-Host "R0.9 receipts retained: $Prefix-output"
    if ($GateExit -ne 0) { throw "R0 gate did not pass (exit $GateExit)" }
    Write-Host "R0 GATE PASSED (local evidence; no release tag created)"
} finally {
    foreach ($Name in $DatabaseContainers) {
        & docker stop $Name | Out-Host
    }
    Write-Host "All created volumes retained; run identity: $Prefix"
}
