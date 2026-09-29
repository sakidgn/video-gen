param([string]$S1 = "12:00", [string]$S2 = "17:00", [string]$S3 = "21:00", [switch]$Kaldir, [int]$Test = 0)

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
# WakeToRun: bilgisayar uykudaysa uyandirir. StartWhenAvailable: kacirilan gorev bilgisayar acilinca calisir.
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

if ($Test -gt 0) {
    $when = (Get-Date).AddMinutes($Test)
    $testAction = New-ScheduledTaskAction -Execute "$dir\calistir_test.bat" -WorkingDirectory $dir
    $trigger = New-ScheduledTaskTrigger -Once -At $when
    Register-ScheduledTask -TaskName "Shitpost Test" -Action $testAction -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host ("Test kuruldu: saat " + $when.ToString("HH:mm") + " civarinda bir kere calisacak (paylasmaz).")
    exit 0
}

foreach ($i in 1..3) {
    Unregister-ScheduledTask -TaskName "Shitpost $i" -Confirm:$false -ErrorAction SilentlyContinue
}
Unregister-ScheduledTask -TaskName "Shitpost Test" -Confirm:$false -ErrorAction SilentlyContinue
if ($Kaldir) {
    Write-Host "Otomatik calistirma kaldirildi."
    exit 0
}

$action = New-ScheduledTaskAction -Execute "$dir\calistir.bat" -WorkingDirectory $dir

$i = 1
foreach ($saat in @($S1, $S2, $S3)) {
    $trigger = New-ScheduledTaskTrigger -Daily -At $saat
    Register-ScheduledTask -TaskName "Shitpost $i" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    $i++
}
Write-Host "Kuruldu: her gun $S1, $S2 ve $S3 (bilgisayar uykudaysa uyandirilir)."
