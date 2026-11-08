<#
.SYNOPSIS
Programa los respaldos automáticos de OdontoNet en el Programador de tareas de Windows (ODON-226).

.DESCRIPTION
Crea dos tareas del usuario actual (no requiere administrador):
- "OdontoNet - Respaldo diario": backup.ps1 todos los días a la hora indicada.
- "OdontoNet - Ensayo de restauración": restore-check.ps1 cada 4 semanas (domingo), 2 horas
  después del respaldo, para no usar el repositorio a la vez.
Si el equipo está apagado a esa hora, la tarea corre al encenderse (StartWhenAvailable).
Las tareas corren solo con la sesión del usuario iniciada, porque Docker Desktop vive en su
sesión. Cada ejecución deja un registro en %LOCALAPPDATA%\OdontoNet\backup-logs, y el resultado
se ve en el Programador de tareas («Último resultado»: 0 = correcto). Lo corre el administrador
del servidor de la clínica; vuelve a correrlo para cambiar la hora. Para quitarlas: -Remove.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\backup\register-tasks.ps1 -Config $env:USERPROFILE\.odontonet\backup.env -At 21:00
#>
param(
    [string]$Config,
    [string]$At = "21:00",
    [switch]$Remove
)
$ErrorActionPreference = "Stop"
$names = @("OdontoNet - Respaldo diario", "OdontoNet - Ensayo de restauración")

if ($Remove) {
    foreach ($name in $names) { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue }
    Write-Host "Tareas de respaldo eliminadas."
    return
}
if (-not $Config -or -not (Test-Path $Config)) { throw "Indica -Config con la ruta del archivo de configuración de respaldos." }
$Config = (Resolve-Path $Config).Path

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$backup = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\backup.ps1`" -Config `"$Config`""
$check = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\restore-check.ps1`" -Config `"$Config`""

Register-ScheduledTask -TaskName $names[0] -Action $backup -Settings $settings -Force `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $At) | Out-Null
# Cada 4 semanas, el domingo (el cmdlet no tiene disparador mensual): un ensayo al mes.
$checkAt = ([datetime]::ParseExact($At, "HH:mm", $null)).AddHours(2).ToString("HH:mm")
Register-ScheduledTask -TaskName $names[1] -Action $check -Settings $settings -Force `
    -Trigger (New-ScheduledTaskTrigger -Weekly -WeeksInterval 4 -DaysOfWeek Sunday -At $checkAt) | Out-Null

Write-Host "Tareas registradas: respaldo diario a las $At y ensayo de restauración cada 4 semanas (domingo) a las $checkAt."
Write-Host "Registros: $env:LOCALAPPDATA\OdontoNet\backup-logs"
