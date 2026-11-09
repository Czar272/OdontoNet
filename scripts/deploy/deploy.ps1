<#
.SYNOPSIS
Instala o actualiza OdontoNet en el equipo de la clínica (ODON-238).

.DESCRIPTION
1. Comprueba la configuración y construye las imágenes.
2. Respalda la base antes de migrar. Si el respaldo falla, se detiene sin tocar nada.
3. Aplica las migraciones con la API detenida.
4. Levanta la aplicación y espera a que esté sana.
5. Exporta el certificado raíz para instalarlo en los equipos de la clínica.

.PARAMETER FirstInstall
Instalación nueva, sin datos que respaldar.

.PARAMETER BackupConfig
Archivo de configuración de respaldos (ver docs/BACKUPS.md). Obligatorio al actualizar.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy.ps1 -BackupConfig $env:USERPROFILE\.odontonet\backup.env
#>
param(
    [switch]$FirstInstall,
    [string]$BackupConfig
)
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ComposeFile = Join-Path $Root "compose.prod.yml"
$Certificate = Join-Path $Root "deploy\odontonet-ca.crt"

function Write-Step([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

function Invoke-Compose {
    & docker compose -f $ComposeFile --project-directory $Root @args
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($args -join ' ') terminó con código $LASTEXITCODE" }
}

function Read-EnvValue([string]$File, [string]$Name) {
    foreach ($line in Get-Content $File) {
        if ($line -match "^\s*$Name\s*=\s*(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

function Wait-Healthy([string]$Service, [int]$Seconds = 120) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    $id = (& docker compose -f $ComposeFile --project-directory $Root ps -q $Service)
    while ((Get-Date) -lt $deadline) {
        $health = (& docker inspect --format "{{.State.Health.Status}}" $id)
        if ($health -eq "healthy") { return }
        Start-Sleep -Seconds 3
    }
    throw "$Service no quedó sano en $Seconds s. Revisa: docker compose -f compose.prod.yml logs $Service"
}

$rootEnv = Join-Path $Root ".env"
$backendEnv = Join-Path $Root "backend\.env"
foreach ($file in @($rootEnv, $backendEnv)) {
    if (-not (Test-Path $file)) { throw "Falta $file. Sigue la sección «Configuración» de docs/DEPLOYMENT.md." }
}
if ((Read-EnvValue $backendEnv "APP_ENV") -ne "production") {
    throw "backend\.env no tiene APP_ENV=production. Este script no se usa en una copia de desarrollo."
}
$composeImages = Read-EnvValue $rootEnv "ODONTONET_IMAGE_DIR"
$backendImages = Read-EnvValue $backendEnv "IMAGE_STORAGE_DIR"
if (-not $composeImages -or $composeImages -ne $backendImages) {
    throw "ODONTONET_IMAGE_DIR (.env) e IMAGE_STORAGE_DIR (backend\.env) deben ser la misma carpeta: los respaldos leen esa ruta."
}
if (-not $FirstInstall -and -not $BackupConfig) {
    throw "Para actualizar indica -BackupConfig: las migraciones se aplican solo con un respaldo previo. En una instalación nueva usa -FirstInstall."
}
if (-not (Test-Path $composeImages)) { New-Item -ItemType Directory -Path $composeImages | Out-Null }

Write-Step "Construyendo las imágenes"
Invoke-Compose build

Write-Step "Levantando la base de datos"
Invoke-Compose up -d --wait db

if (-not $FirstInstall) {
    Write-Step "Respaldando antes de migrar"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\backup\backup.ps1") -Config $BackupConfig -Tag pre-migracion
    if ($LASTEXITCODE -ne 0) { throw "El respaldo falló: no se aplicó ningún cambio." }
}

Write-Step "Deteniendo la API y aplicando las migraciones"
Invoke-Compose stop api proxy
Invoke-Compose run --rm -T api alembic upgrade head

Write-Step "Levantando la aplicación"
Invoke-Compose up -d
Wait-Healthy "api"
Wait-Healthy "proxy"

Write-Step "Exportando el certificado raíz"
# Caddy crea la CA al arrancar: puede tardar unos segundos. Mientras tanto, el
# error de docker en stderr no debe detener el script.
$ErrorActionPreference = "Continue"
$deadline = (Get-Date).AddSeconds(30)
do {
    & docker compose -f $ComposeFile --project-directory $Root cp proxy:/data/caddy/pki/authorities/local/root.crt $Certificate 2>$null
    $exported = $LASTEXITCODE -eq 0
    if (-not $exported) { Start-Sleep -Seconds 2 }
} while (-not $exported -and (Get-Date) -lt $deadline)
$ErrorActionPreference = "Stop"
if (-not $exported) { throw "No se pudo exportar el certificado raíz." }

Write-Step "Listo. Certificado raíz: $Certificate"
