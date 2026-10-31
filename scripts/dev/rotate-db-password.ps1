<#
.SYNOPSIS
  Rota la contraseña del usuario PostgreSQL de desarrollo (contenedor odontonet-db)
  y actualiza .env (raíz) y backend/.env.

.DESCRIPTION
  1. Lee POSTGRES_USER y POSTGRES_DB del .env de la raíz.
  2. Genera una contraseña aleatoria segura para URL (A-Z a-z 0-9 - _).
  3. Ejecuta ALTER USER dentro del contenedor (la contraseña viaja por stdin).
  4. Verifica la conexión por TCP con la nueva contraseña.
  5. Respalda los .env (*.bak-<fecha>, ignorados por Git) y los actualiza.
  La contraseña nunca se imprime, salvo si falla la escritura de los .env.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev\rotate-db-password.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File scripts\dev\rotate-db-password.ps1
#>
[CmdletBinding()]
param(
    [string]$Container = "odontonet-db",
    [ValidateRange(20, 64)][int]$Length = 32,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$RootEnv    = Join-Path $RepoRoot ".env"
$BackendEnv = Join-Path $RepoRoot "backend\.env"
$Utf8NoBom  = New-Object System.Text.UTF8Encoding($false)

# Reemplazos por línea. [^\r\n]* conserva los fines de línea CRLF.
$PasswordLine = '(?m)^(\s*POSTGRES_PASSWORD\s*=)[^\r\n]*'
$UrlLine      = '(?m)^(\s*DATABASE_URL\s*=\s*[^:\r\n]+://[^:@\r\n]+:)[^@\r\n]*(@[^\r\n]*)'

function Read-EnvValue([string]$Path, [string]$Key) {
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match "^\s*$Key\s*=\s*(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

function New-Password([int]$Len) {
    # 64 símbolos: 256 es múltiplo de 64, sin sesgo de módulo.
    $chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'.ToCharArray()
    $bytes = New-Object byte[] $Len
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return -join ($bytes | ForEach-Object { $chars[$_ % 64] })
}

function Get-UpdatedContent([string]$Path, [string]$NewPassword, [bool]$IsRoot) {
    $text = [System.IO.File]::ReadAllText($Path)
    $count = 0
    if ($IsRoot) {
        $count += ([regex]::Matches($text, $PasswordLine)).Count
        $text = [regex]::Replace($text, $PasswordLine, { param($m) $m.Groups[1].Value + $NewPassword })
    }
    $count += ([regex]::Matches($text, $UrlLine)).Count
    $text = [regex]::Replace($text, $UrlLine, { param($m) $m.Groups[1].Value + $NewPassword + $m.Groups[2].Value })
    return @{ Text = $text; Count = $count }
}

# --- 1. Validaciones previas ---
foreach ($f in @($RootEnv, $BackendEnv)) {
    if (-not (Test-Path $f)) { throw "No existe $f" }
}
$DbUser = Read-EnvValue $RootEnv "POSTGRES_USER"
$DbName = Read-EnvValue $RootEnv "POSTGRES_DB"
if (-not $DbUser -or -not $DbName) { throw "POSTGRES_USER o POSTGRES_DB faltan en .env de la raíz" }

$running = (docker inspect -f "{{.State.Running}}" $Container 2>$null)
if ($LASTEXITCODE -ne 0 -or $running -ne "true") {
    throw "El contenedor $Container no está en ejecución. Ejecuta: docker compose up -d"
}

$NewPassword = New-Password $Length
$rootUpd    = Get-UpdatedContent $RootEnv $NewPassword $true
$backendUpd = Get-UpdatedContent $BackendEnv $NewPassword $false

Write-Host "Usuario: $DbUser | Base: $DbName | Contenedor: $Container"
Write-Host ".env (raíz): $($rootUpd.Count) línea(s) a actualizar (POSTGRES_PASSWORD y DATABASE_URL si existe)"
Write-Host "backend/.env: $($backendUpd.Count) línea(s) a actualizar (DATABASE_URL)"
if ($rootUpd.Count -lt 1 -or $backendUpd.Count -lt 1) {
    throw "No se encontraron las líneas esperadas en los .env; no se cambió nada."
}
if ($DryRun) {
    Write-Host "DryRun: validación correcta. No se modificó la base ni los archivos." -ForegroundColor Cyan
    return
}

# --- 2. Cambiar contraseña en PostgreSQL (socket local del contenedor) ---
$sql = "ALTER USER `"$DbUser`" WITH PASSWORD '$NewPassword';"
$sql | docker exec -i $Container psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -q | Out-Null
if ($LASTEXITCODE -ne 0) { throw "ALTER USER falló; la contraseña anterior sigue vigente y no se tocaron los .env." }

# --- 3. Verificar autenticación por TCP con la nueva contraseña ---
$check = docker exec -e "PGPASSWORD=$NewPassword" $Container psql -h 127.0.0.1 -U $DbUser -d $DbName -tAc "SELECT 1" 2>&1
$authOk = ($LASTEXITCODE -eq 0 -and ("$check").Trim() -eq "1")

# --- 4. Respaldar y escribir los .env ---
try {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $RootEnv "$RootEnv.bak-$stamp"
    Copy-Item $BackendEnv "$BackendEnv.bak-$stamp"
    [System.IO.File]::WriteAllText($RootEnv, $rootUpd.Text, $Utf8NoBom)
    [System.IO.File]::WriteAllText($BackendEnv, $backendUpd.Text, $Utf8NoBom)
} catch {
    Write-Host "La contraseña YA cambió en PostgreSQL, pero no se pudieron escribir los .env." -ForegroundColor Red
    Write-Host "Actualízalos manualmente con esta contraseña: $NewPassword" -ForegroundColor Yellow
    throw
}

if ((Read-EnvValue $RootEnv "POSTGRES_PASSWORD") -ne $NewPassword) { throw "Verificación de .env (raíz) fallida." }

Write-Host "Contraseña rotada y .env actualizados." -ForegroundColor Green
if (-not $authOk) {
    Write-Host "Aviso: la verificación TCP no devolvió 1 ($check). Prueba con 'alembic current' desde backend/." -ForegroundColor Yellow
}
Write-Host "Respaldos: .env.bak-$stamp y backend\.env.bak-$stamp (bórralos tras verificar)."
Write-Host "Siguiente: reinicia uvicorn y ejecuta 'alembic current' desde backend/."
