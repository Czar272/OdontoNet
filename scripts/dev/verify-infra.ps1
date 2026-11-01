<#
.SYNOPSIS
  Verifica la infraestructura local de OdontoNet:
  PostgreSQL y Docker Compose (ODON-26) y migraciones Alembic (ODON-30).

.DESCRIPTION
  No modifica datos. Únicamente:
   - reinicia el contenedor una vez para comprobar que los datos persisten;
   - crea una base temporal "<base>_migration_check", prueba en ella
     upgrade -> downgrade base -> upgrade, y la elimina al terminar.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev\verify-infra.ps1
#>
[CmdletBinding()]
param(
    [string]$Container = "odontonet-db",
    [string]$Service = "postgres",
    [string]$ApiUrl = "http://127.0.0.1:8000/health"
)

# Los comandos nativos escriben en stderr; los errores se evalúan con $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackendDir = Join-Path $RepoRoot "backend"
$Python = Join-Path $BackendDir "odonto_venv\Scripts\python.exe"
$script:Failures = 0

function Write-Check([string]$Name, [bool]$Ok, [string]$Info = "") {
    if ($Ok) { Write-Host ("[OK]    {0} {1}" -f $Name, $Info) -ForegroundColor Green }
    else { Write-Host ("[FALLA] {0} {1}" -f $Name, $Info) -ForegroundColor Red; $script:Failures++ }
}

function Read-EnvValue([string]$Path, [string]$Key) {
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match "^\s*$Key\s*=\s*(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

function Get-Health { (docker inspect -f "{{.State.Health.Status}}" $Container 2>$null | Out-String).Trim() }

function Wait-Healthy([int]$Seconds = 60) {
    for ($i = 0; $i -lt $Seconds; $i += 2) {
        if ((Get-Health) -eq "healthy") { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Invoke-Psql([string]$Sql, [string]$Database) {
    (docker exec $Container psql -U $DbUser -d $Database -tAc $Sql 2>&1 | Out-String).Trim()
}

function Invoke-Alembic([string[]]$Arguments) {
    $output = & $Python -m alembic @Arguments 2>&1 | Out-String
    return @{ Code = $LASTEXITCODE; Output = $output }
}

Write-Host "== OdontoNet: verificación de infraestructura ==" -ForegroundColor Cyan
$DbUser = Read-EnvValue (Join-Path $RepoRoot ".env") "POSTGRES_USER"
$DbName = Read-EnvValue (Join-Path $RepoRoot ".env") "POSTGRES_DB"
$BackendUrl = Read-EnvValue (Join-Path $BackendDir ".env") "DATABASE_URL"
if (-not $DbUser -or -not $DbName -or -not $BackendUrl) { throw "Faltan POSTGRES_USER/POSTGRES_DB en .env o DATABASE_URL en backend/.env" }
if (-not (Test-Path $Python)) { throw "No se encontró $Python (crea odonto_venv según docs/DEVELOPMENT.md)" }

Push-Location $RepoRoot
try {
    # --- ODON-26: Docker Compose y PostgreSQL ---
    docker compose config --quiet 2>&1 | Out-Null
    Write-Check "docker-compose.yml válido" ($LASTEXITCODE -eq 0)

    Write-Check "Contenedor $Container healthy" ((Get-Health) -eq "healthy") "(estado: $(Get-Health))"

    $countSql = "SELECT (SELECT count(*) FROM clinics)||','||(SELECT count(*) FROM users)||','||(SELECT count(*) FROM doctors)||','||(SELECT count(*) FROM patients)"
    $before = Invoke-Psql $countSql $DbName

    Write-Host "        Reiniciando el contenedor para comprobar persistencia..."
    docker compose restart $Service 2>&1 | Out-Null
    Write-Check "Contenedor healthy tras reinicio" (Wait-Healthy 60)

    $after = Invoke-Psql $countSql $DbName
    Write-Check "Datos persisten tras reinicio" (($before -ne "") -and ($before -eq $after)) "(clínicas,usuarios,doctores,pacientes: antes $before / después $after)"

    $published = (docker port $Container 5432 2>$null | Out-String).Trim()
    Write-Check "Puerto publicado solo en 127.0.0.1" ($published -match "^127\.0\.0\.1:") "($published)"

    # --- ODON-30: Alembic ---
    Push-Location $BackendDir
    try {
        $current = Invoke-Alembic @("current")
        $heads = Invoke-Alembic @("heads")
        $headRev = ([regex]::Match($heads.Output, "([0-9a-f]{12}) \(head\)")).Groups[1].Value
        Write-Check "Una sola cabeza de migraciones" (([regex]::Matches($heads.Output, "\(head\)")).Count -eq 1) "($headRev)"
        Write-Check "Base local en la última migración (current = head)" ($current.Output -match "$headRev \(head\)")

        $check = Invoke-Alembic @("check")
        Write-Check "Modelos y migraciones coinciden (alembic check)" ($check.Code -eq 0)

        # Migración completa en una base vacía temporal
        $tempDb = "${DbName}_migration_check"
        docker exec $Container dropdb -U $DbUser --if-exists $tempDb 2>&1 | Out-Null
        docker exec $Container createdb -U $DbUser $tempDb 2>&1 | Out-Null
        $previousUrl = $env:DATABASE_URL
        $env:DATABASE_URL = $BackendUrl -replace "/[^/?]+(\?.*)?$", "/$tempDb`$1"
        try {
            $up = Invoke-Alembic @("upgrade", "head")
            $down = Invoke-Alembic @("downgrade", "base")
            $up2 = Invoke-Alembic @("upgrade", "head")
            Write-Check "Migración desde base vacía (upgrade, downgrade base, upgrade)" (($up.Code -eq 0) -and ($down.Code -eq 0) -and ($up2.Code -eq 0))
            if ($up.Code -ne 0 -or $down.Code -ne 0 -or $up2.Code -ne 0) { Write-Host ($up.Output + $down.Output + $up2.Output) }
        } finally {
            $env:DATABASE_URL = $previousUrl
            docker exec $Container dropdb -U $DbUser --if-exists $tempDb 2>&1 | Out-Null
        }
    } finally {
        Pop-Location
    }

    # --- Conexión backend (opcional: requiere uvicorn en ejecución) ---
    try {
        $health = Invoke-RestMethod -Uri $ApiUrl -TimeoutSec 5
        Write-Check "Backend conectado a la base (/health)" (($health.status -eq "ok") -and ($health.database -eq "ok"))
    } catch {
        Write-Host "[--]    /health no respondió: inicia uvicorn para incluir esta comprobación." -ForegroundColor Yellow
    }
} finally {
    Pop-Location
}

if ($script:Failures -eq 0) { Write-Host "Resultado: todas las comprobaciones pasaron." -ForegroundColor Green; exit 0 }
Write-Host "Resultado: $($script:Failures) comprobación(es) fallaron." -ForegroundColor Red
exit 1
