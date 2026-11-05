# Planifie l'exécution hebdomadaire de VeilleIA (Planificateur de tâches Windows).
# Collecte + analyse + synthèse + monitorage chaque mercredi à 18 h, pour que la
# synthèse soit prête au créneau de veille du jeudi 9 h – 10 h.
#
# Utilisation (PowerShell, depuis la racine du projet) :
#   powershell -ExecutionPolicy Bypass -File scripts\planifier_tache_windows.ps1
# Suppression :
#   Unregister-ScheduledTask -TaskName "VeilleIA-hebdo" -Confirm:$false

$racine = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $racine ".venv\Scripts\veilleia.exe"
if (-not (Test-Path $exe)) { throw "Environnement introuvable : installer le projet d'abord (voir README)." }

$action = New-ScheduledTaskAction -Execute $exe -Argument "hebdo" -WorkingDirectory $racine
$declencheur = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At 18:00
$reglages = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName "VeilleIA-hebdo" -Action $action -Trigger $declencheur -Settings $reglages `
    -Description "Veille IA hebdomadaire – collecte, analyse, synthèse, monitorage" -Force
Write-Host "Tâche 'VeilleIA-hebdo' planifiée : chaque mercredi à 18:00."
