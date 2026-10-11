[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [ValidateSet('mock', 'live')][string]$Mode = 'live',
    [string]$Topic = 'AI',
    [string]$TaskName = 'HKDN-AI-News-Weekly'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$jobPath = Join-Path $PSScriptRoot 'weekly_job.py'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Missing .venv; see README.' }
if ($Topic -match '["\r\n]') { throw 'Topic must not contain quotes or newlines.' }
# Fail instead of overwriting an existing task.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw "Task $TaskName already exists." }
$arguments = '"{0}" --mode {1} --topic "{2}"' -f $jobPath, $Mode, $Topic
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday -At '08:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
if ($PSCmdlet.ShouldProcess($TaskName, 'Register weekly AI news job on Monday at 08:00 in the Windows timezone')) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'HKDN: 5 AI news items per ISO week' | Out-Null
    Write-Output "Registered $TaskName. Runs while signed in, on Mondays at 08:00 in the Windows timezone."
}
