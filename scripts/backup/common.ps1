# Funciones compartidas de los scripts de respaldo (ODON-226).

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackendDir = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $BackendDir "odonto_venv\Scripts\python.exe"
$Container = "odontonet-db"
$StagingDir = Join-Path $env:TEMP "odontonet-backup-staging"
$LogDir = Join-Path $env:LOCALAPPDATA "OdontoNet\backup-logs"

# Registro de cada ejecución en un archivo (las tareas programadas no muestran la consola).
function Start-BackupLog([string]$Name) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $path = Join-Path $LogDir ("{0}-{1}.log" -f $Name, (Get-Date -Format "yyyyMMdd-HHmmss"))
    Start-Transcript -Path $path | Out-Null
    # Se conservan los últimos 60 registros.
    Get-ChildItem $LogDir -Filter "$Name-*.log" | Sort-Object Name -Descending | Select-Object -Skip 60 | Remove-Item -Force
}

function Read-KeyValueFile([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { throw "No existe el archivo de configuración: $Path" }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $index = $trimmed.IndexOf("=")
        if ($index -lt 1) { continue }
        $values[$trimmed.Substring(0, $index).Trim()] = $trimmed.Substring($index + 1).Trim()
    }
    return $values
}

function Get-BackupConfig([string]$ConfigPath) {
    $config = Read-KeyValueFile $ConfigPath
    foreach ($required in @("ODONTONET_BACKUP_LOCAL_REPO", "ODONTONET_BACKUP_PASSWORD_FILE")) {
        if (-not $config[$required]) { throw "Falta $required en $ConfigPath" }
    }
    if (-not (Test-Path $config["ODONTONET_BACKUP_PASSWORD_FILE"])) {
        throw "No existe el archivo de contraseña de restic: $($config['ODONTONET_BACKUP_PASSWORD_FILE'])"
    }
    $restic = if ($config["RESTIC_EXE"]) { $config["RESTIC_EXE"] } else { "restic" }
    if (-not (Get-Command $restic -ErrorAction SilentlyContinue)) {
        throw "No se encontró restic ($restic). Instálalo con: winget install restic.restic"
    }
    $config["RESTIC"] = $restic
    return $config
}

function Get-DatabaseSettings {
    # Credenciales de la base desde el .env de la raíz (las mismas que usa docker compose).
    $envFile = Join-Path $RepoRoot ".env"
    $values = Read-KeyValueFile $envFile
    return @{ User = $values["POSTGRES_USER"]; Database = $values["POSTGRES_DB"] }
}

function Invoke-Restic($Config, [string]$Repository, [string[]]$Arguments) {
    $previous = @{ AWS_ACCESS_KEY_ID = $env:AWS_ACCESS_KEY_ID; AWS_SECRET_ACCESS_KEY = $env:AWS_SECRET_ACCESS_KEY }
    try {
        # Las credenciales de la nube solo se exponen como variables de entorno mientras
        # corre restic. Siguen guardadas en backup.env: restringe sus permisos a la
        # cuenta que corre los respaldos (ver docs/BACKUPS.md).
        if ($Config["AWS_ACCESS_KEY_ID"]) { $env:AWS_ACCESS_KEY_ID = $Config["AWS_ACCESS_KEY_ID"] }
        if ($Config["AWS_SECRET_ACCESS_KEY"]) { $env:AWS_SECRET_ACCESS_KEY = $Config["AWS_SECRET_ACCESS_KEY"] }
        # --retry-lock: si otra operación (respaldo o ensayo) usa el repositorio, espera en vez de fallar.
        & $Config["RESTIC"] -r $Repository --password-file $Config["ODONTONET_BACKUP_PASSWORD_FILE"] --retry-lock 30m @Arguments
        if ($LASTEXITCODE -ne 0) { throw "restic terminó con código $LASTEXITCODE ($($Arguments[0]) en $Repository)" }
    }
    finally {
        $env:AWS_ACCESS_KEY_ID = $previous.AWS_ACCESS_KEY_ID
        $env:AWS_SECRET_ACCESS_KEY = $previous.AWS_SECRET_ACCESS_KEY
    }
}

function Get-ImageStorageDir {
    $backendEnv = Join-Path $BackendDir ".env"
    $values = if (Test-Path $backendEnv) { Read-KeyValueFile $backendEnv } else { @{} }
    if ($values["IMAGE_STORAGE_DIR"]) {
        # Una ruta relativa se resuelve desde backend\, como lo hace la aplicación.
        $path = $values["IMAGE_STORAGE_DIR"]
        if (-not [System.IO.Path]::IsPathRooted($path)) { $path = Join-Path $BackendDir $path }
        return [System.IO.Path]::GetFullPath($path)
    }
    return (Join-Path $BackendDir "storage\images")
}

# Ruta dentro del snapshot de restic: C:\x\y se guarda como /C/x/y.
function Get-SnapshotPath([string]$OriginalPath) {
    return "/" + $OriginalPath.Substring(0, 1) + "/" + $OriginalPath.Substring(3).Replace("\", "/")
}

function Write-Step([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}
