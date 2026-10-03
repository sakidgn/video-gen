param(
    [string]$Saatler = "09:45 12:45 15:45 18:45 21:15",
    [string]$IgSaatler = "12:45 18:45 21:15",
    [switch]$Kaldir,
    [int]$Test = 0
)

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

foreach ($i in 1..20) {
    Unregister-ScheduledTask -TaskName "Shitpost $i" -Confirm:$false -ErrorAction SilentlyContinue
}
Unregister-ScheduledTask -TaskName "Shitpost Test" -Confirm:$false -ErrorAction SilentlyContinue
if ($Kaldir) {
    Write-Host "Otomatik calistirma kaldirildi."
    exit 0
}

$liste = @($Saatler -split '[\s,;]+' | Where-Object { $_ })
$igListe = @($IgSaatler -split '[\s,;]+' | Where-Object { $_ })

$i = 1
foreach ($saat in $liste) {
    if ($igListe -contains $saat) {
        $action = New-ScheduledTaskAction -Execute "$dir\calistir.bat" -WorkingDirectory $dir
        $not = "YouTube + TikTok + Instagram"
    } else {
        $action = New-ScheduledTaskAction -Execute "$dir\calistir.bat" -Argument "--atla instagram_web" -WorkingDirectory $dir
        $not = "YouTube + TikTok"
    }
    $trigger = New-ScheduledTaskTrigger -Daily -At $saat
    Register-ScheduledTask -TaskName "Shitpost $i" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host ("  " + $saat + "  ->  " + $not)
    $i++
}
Write-Host ("Kuruldu: her gun " + $liste.Count + " video (bilgisayar uykudaysa uyandirilir).")
