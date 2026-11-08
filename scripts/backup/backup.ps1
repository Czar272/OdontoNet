<#
.SYNOPSIS
Respaldo cifrado de OdontoNet: base de datos + imágenes clínicas (ODON-226).

.DESCRIPTION
1. Vuelca la base con pg_dump (formato custom) y escribe su manifiesto.
2. Respalda volcado, manifiesto e imágenes con restic (cifrado en este equipo,
   antes de salir) al repositorio local y, si está configurado, a la nube.
3. Aplica la retención en el repositorio local: 7 diarios, 4 semanales,
   12 mensuales y uno por año (los anuales no se borran).
El volcado sin cifrar solo existe en una carpeta temporal y se borra siempre.
Base primero, imágenes después: los archivos son inmutables, así que todo lo
que la base registra ya existe; una subida durante el respaldo solo deja un
archivo sin registro (verify_images lo informa como huérfano).

.PARAMETER Config
Archivo de configuración (copia de scripts\backup\backup.env.example fuera del repositorio).

.PARAMETER Init
Inicializa los repositorios restic (solo la primera vez).

.PARAMETER Tag
Etiqueta adicional, p. ej. "pre-migracion" antes de alembic upgrade.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\backup\backup.ps1 -Config $env:USERPROFILE\.odontonet\backup.env
#>
param(
    [Parameter(Mandatory = $true)][string]$Config,
    [switch]$Init,
    [string]$Tag = "diario"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$started = Get-Date
Start-BackupLog "respaldo"
$settings = Get-BackupConfig $Config
$db = Get-DatabaseSettings
$repositories = @($settings["ODONTONET_BACKUP_LOCAL_REPO"])
if ($settings["ODONTONET_BACKUP_CLOUD_REPO"]) { $repositories += $settings["ODONTONET_BACKUP_CLOUD_REPO"] }

if ($Init) {
    foreach ($repository in $repositories) {
        Write-Step "Inicializando repositorio $repository"
        Invoke-Restic $settings $repository @("init")
    }
}

$images = Get-ImageStorageDir
try {
    if (Test-Path $StagingDir) { Remove-Item -Recurse -Force $StagingDir }
    New-Item -ItemType Directory -Path $StagingDir | Out-Null

    # Volcado y manifiesto del mismo snapshot de la base (backup_manifest dump): lo que
    # pase en la API durante el respaldo no altera la comparación del ensayo. El volcado
    # se borra del contenedor aunque falle, y se comprueba que no esté vacío.
    Write-Step "Volcando la base $($db.Database) y escribiendo el manifiesto"
    Push-Location $BackendDir
    try {
        & $VenvPython -m scripts.backup_manifest dump $StagingDir $Container $db.User $db.Database
        if ($LASTEXITCODE -ne 0) { throw "No se pudo volcar la base o escribir el manifiesto" }
    }
    finally { Pop-Location }
    $dump = Join-Path $StagingDir "odontonet.dump"
    if (-not (Test-Path $dump) -or (Get-Item $dump).Length -eq 0) { throw "El volcado de la base está vacío." }

    $paths = @($StagingDir)
    if (Test-Path $images) { $paths += $images } else { Write-Step "Sin carpeta de imágenes ($images)" }

    foreach ($repository in $repositories) {
        Write-Step "Respaldando en $repository"
        Invoke-Restic $settings $repository (@("backup") + $paths + @("--host", "odontonet", "--tag", "odontonet", "--tag", $Tag))
    }

    # Retención solo en el repositorio local: la clave de la nube no puede borrar.
    Write-Step "Aplicando la retención en el repositorio local"
    Invoke-Restic $settings $settings["ODONTONET_BACKUP_LOCAL_REPO"] @(
        "forget", "--host", "odontonet", "--tag", "odontonet",
        "--keep-daily", "7", "--keep-weekly", "4", "--keep-monthly", "12", "--keep-yearly", "1000", "--prune"
    )
}
finally {
    if (Test-Path $StagingDir) { Remove-Item -Recurse -Force $StagingDir }
    Write-Step ("Fin del respaldo ({0:N0} s)" -f ((Get-Date) - $started).TotalSeconds)
    Stop-Transcript | Out-Null
}
