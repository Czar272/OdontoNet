<#
.SYNOPSIS
Ensayo de restauración de OdontoNet (ODON-226): restaura el último respaldo en
una base y una carpeta temporales y comprueba que coincide con lo respaldado.

.DESCRIPTION
No toca la base ni las imágenes en uso. Comprueba:
- el manifiesto (versión de Alembic, filas por tabla, final de la cadena de auditoría);
- alembic check (el esquema restaurado coincide con los modelos);
- verify_images (archivos completos y sin alterar, SHA-256);
- verify_audit (cadena de auditoría íntegra).
Al terminar borra la base y la carpeta temporales (contienen datos sin cifrar).

.PARAMETER Config
Archivo de configuración de respaldos.

.PARAMETER Cloud
Restaurar desde el repositorio de la nube en lugar del local.

.PARAMETER Snapshot
Snapshot a restaurar (por defecto, el último).
#>
param(
    [Parameter(Mandatory = $true)][string]$Config,
    [switch]$Cloud,
    [string]$Snapshot = "latest"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$started = Get-Date
Start-BackupLog "ensayo"
$settings = Get-BackupConfig $Config
$db = Get-DatabaseSettings
$repository = if ($Cloud) { $settings["ODONTONET_BACKUP_CLOUD_REPO"] } else { $settings["ODONTONET_BACKUP_LOCAL_REPO"] }
if (-not $repository) { throw "No hay repositorio de nube configurado." }

$target = Join-Path $env:TEMP "odontonet-restore-check"
$tempDb = "odontonet_restore_check"
$failures = @()
try {
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Write-Step "Restaurando $Snapshot desde $repository"
    # Se restaura cada carpeta por separado (snapshot:/ruta): restaurar las rutas
    # absolutas completas copiaría también los permisos de carpetas como C:\Users.
    $staging = Join-Path $target "staging"
    $images = Join-Path $target "images"
    Invoke-Restic $settings $repository @("restore", "${Snapshot}:$(Get-SnapshotPath $StagingDir)", "--host", "odontonet", "--target", $staging)
    $imageSource = Get-ImageStorageDir
    if (Test-Path $imageSource) {
        Invoke-Restic $settings $repository @("restore", "${Snapshot}:$(Get-SnapshotPath $imageSource)", "--host", "odontonet", "--target", $images)
    } else {
        New-Item -ItemType Directory -Path $images | Out-Null
    }
    $restoreSeconds = ((Get-Date) - $started).TotalSeconds
    if (-not (Test-Path (Join-Path $staging "odontonet.dump"))) { throw "El respaldo no contiene el volcado de la base." }

    Write-Step "Cargando el volcado en la base temporal $tempDb"
    docker exec $Container dropdb -U $db.User --if-exists $tempDb | Out-Null
    docker exec $Container createdb -U $db.User $tempDb
    docker cp (Join-Path $staging "odontonet.dump") "${Container}:/tmp/restore.dump" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar el volcado al contenedor" }
    docker exec $Container pg_restore -U $db.User -d $tempDb --no-owner --exit-on-error /tmp/restore.dump
    if ($LASTEXITCODE -ne 0) { throw "pg_restore falló" }

    # La app y los scripts leen DATABASE_URL e IMAGE_STORAGE_DIR del entorno antes que de backend\.env.
    $previousUrl = $env:DATABASE_URL
    $previousImages = $env:IMAGE_STORAGE_DIR
    Push-Location $BackendDir
    try {
        # La URL de la base temporal se arma con SQLAlchemy (make_url), que verifica el nombre.
        $restoreUrl = & $VenvPython -m scripts.backup_manifest restore-url $tempDb
        if ($LASTEXITCODE -ne 0 -or -not $restoreUrl) { throw "No se pudo armar la URL de la base temporal" }
        $env:DATABASE_URL = $restoreUrl
        $env:IMAGE_STORAGE_DIR = $images
        $checks = [ordered]@{
            "manifiesto" = @("-m", "scripts.backup_manifest", "compare", (Join-Path $staging "manifest.json"))
            "esquema (alembic check)" = @("-m", "alembic", "check")
            # --orphans-ok: una imagen subida durante el respaldo no es un error.
            "imágenes (verify_images)" = @("-m", "scripts.verify_images", "--orphans-ok")
            "auditoría (verify_audit)" = @("-m", "scripts.verify_audit")
        }
        foreach ($name in $checks.Keys) {
            Write-Step "Comprobando $name"
            & $VenvPython @($checks[$name])
            if ($LASTEXITCODE -ne 0) { $failures += $name }
        }
    }
    finally {
        Pop-Location
        $env:DATABASE_URL = $previousUrl
        $env:IMAGE_STORAGE_DIR = $previousImages
    }
}
catch {
    $failures += "restauración: $($_.Exception.Message)"
}
finally {
    # Datos sin cifrar: la base, el volcado en el contenedor y la carpeta temporales se borran siempre.
    docker exec $Container rm -f /tmp/restore.dump | Out-Null
    docker exec $Container dropdb -U $db.User --if-exists $tempDb | Out-Null
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
}

$total = ((Get-Date) - $started).TotalSeconds
Write-Step ("Restauración desde el repositorio: {0:N0} s; ensayo completo: {1:N0} s" -f $restoreSeconds, $total)
if ($failures.Count -gt 0) {
    Write-Host "ENSAYO FALLIDO: $($failures -join ', ')" -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "Ensayo de restauración correcto: el respaldo se puede restaurar y coincide con lo respaldado." -ForegroundColor Green
Stop-Transcript | Out-Null
