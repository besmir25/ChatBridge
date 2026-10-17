<#
  Tries the built app on several test phones (Android versions) and reports what happened on each one.
  For every test phone: start it (no window), install the app, open it, share a conversation in, copy it, share a link,
  take screenshots, and look in the system log for crashes and script errors.
  Run from the project folder after building (see mobile\run-test-phone.ps1):
     powershell -ExecutionPolicy Bypass -File mobile\test-matrix.ps1
  Options: -Root <folder with Java and the SDK> (default ~\Android)   -Phones A36,A34,A28   -Out <folder for screenshots and the report>
#>
param([string]$Root = "$env:USERPROFILE\Android", [string[]]$Phones = @("A36", "A34", "A28", "ChatBridgeTest"), [string]$Out = "$env:TEMP\chatbridge-matrix")
$ErrorActionPreference = "Continue"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$adb = "$Root\sdk\platform-tools\adb.exe"; $emu = "$Root\sdk\emulator\emulator.exe"
$apk = "$proj\android\app\build\outputs\apk\debug\app-debug.apk"
$env:ANDROID_HOME = "$Root\sdk"; $env:ANDROID_SDK_ROOT = "$Root\sdk"; $env:ANDROID_AVD_HOME = "$env:USERPROFILE\.android\avd"
if (-not (Test-Path $apk)) { throw "No build found. Run mobile\run-test-phone.ps1 first." }
New-Item -ItemType Directory -Force $Out | Out-Null
$report = @()
$conversation = "User: Plan a 5 day trip to Kyoto in April`nAssistant: Day 1 Fushimi Inari and Gion. Day 2 Arashiyama bamboo grove.`nUser: Also add food places near Gion`nAssistant: Try the small noodle shops on the side streets.`nUser: Now let's write my nursing resume summary, my email is jane.doe@example.com`nAssistant: Here is a first draft with ICU experience."
[IO.File]::WriteAllText("$Out\share.txt", $conversation)
[IO.File]::WriteAllText("$Out\share.sh", "am start -a android.intent.action.SEND -t text/plain -n com.besmir25.chatbridge/.MainActivity --es android.intent.extra.TEXT `"`$(cat /sdcard/Download/share.txt)`"`n")
[IO.File]::WriteAllText("$Out\link.sh", "am start -a android.intent.action.SEND -t text/plain -n com.besmir25.chatbridge/.MainActivity --es android.intent.extra.TEXT `"https://chatgpt.com/share/abc-123`"`n")

function Shot($dev, $name) { cmd /c "`"$adb`" -s $dev exec-out screencap -p > `"$Out\$name.png`"" }
function Tap($dev, $x, $y) { & $adb -s $dev shell input tap ([int]($x * 1.2)) ([int]($y * 1.2)); Start-Sleep -Milliseconds 1300 }

foreach ($avd in $Phones) {
  Write-Host "=== $avd"
  $row = [ordered]@{Phone = $avd; Android = ""; WebView = ""; Installed = $false; Opens = $false; ShareIn = $false; Copy = $false; Link = $false; Problems = ""}
  & $adb kill-server 2>$null | Out-Null; & $adb start-server 2>$null | Out-Null
  Start-Process $emu -ArgumentList "-avd", $avd, "-no-window", "-no-snapshot-save", "-no-audio", "-no-boot-anim", "-gpu", "swiftshader_indirect" -WindowStyle Hidden
  $dev = $null
  for ($i = 0; $i -lt 60; $i++) { Start-Sleep 5; $d = (& $adb devices) -match "emulator-\d+\s+device"; if ($d) { $dev = ([regex]::Match(($d | Select-Object -First 1), "emulator-\d+")).Value; if ((& $adb -s $dev shell getprop sys.boot_completed 2>$null) -match "1") { break } } }
  if (-not $dev) { $row.Problems = "did not start"; $report += [pscustomobject]$row; continue }
  Start-Sleep 5
  $row.Android = (& $adb -s $dev shell getprop ro.build.version.release).Trim() + " (API " + (& $adb -s $dev shell getprop ro.build.version.sdk).Trim() + ")"
  $wv = & $adb -s $dev shell dumpsys webviewupdate 2>$null | Select-String -Pattern "Current WebView package|versionName" | Select-Object -First 1
  $row.WebView = if ($wv) { ($wv.Line -replace '\s+', ' ').Trim() } else { "?" }
  & $adb -s $dev logcat -c
  $inst = & $adb -s $dev install -r $apk 2>&1 | Select-Object -Last 1
  $row.Installed = "$inst" -match "Success"
  if ($row.Installed) {
    & $adb -s $dev shell pm clear com.besmir25.chatbridge | Out-Null
    & $adb -s $dev shell input keyevent 3 | Out-Null; Start-Sleep 1
    & $adb -s $dev shell am start -n com.besmir25.chatbridge/.MainActivity | Out-Null; Start-Sleep 7
    Shot $dev "${avd}_1_home"
    $top = & $adb -s $dev shell dumpsys activity activities | Select-String "mResumedActivity|topResumedActivity" | Select-Object -First 1
    $row.Opens = "$top" -match "chatbridge"
    & $adb -s $dev push "$Out\share.txt" /sdcard/Download/share.txt | Out-Null
    & $adb -s $dev push "$Out\share.sh" /sdcard/Download/share.sh | Out-Null
    & $adb -s $dev push "$Out\link.sh" /sdcard/Download/link.sh | Out-Null
    & $adb -s $dev shell sh /sdcard/Download/share.sh | Out-Null; Start-Sleep 5
    Shot $dev "${avd}_2_shared"
    Tap $dev 735 1200                     # Just copy it
    Tap $dev 752 1910                     # the big button
    Shot $dev "${avd}_3_copied"
    $log = (& $adb -s $dev logcat -d 2>$null) -join "`n"
    & $adb -s $dev shell input keyevent 4 | Out-Null; Start-Sleep 1
    & $adb -s $dev shell sh /sdcard/Download/link.sh | Out-Null; Start-Sleep 4
    Shot $dev "${avd}_4_link"
    $log = (& $adb -s $dev logcat -d 2>$null) -join "`n"
    $problems = @()
    if ($log -match "FATAL EXCEPTION") { $problems += "CRASH" }
    $errs = ([regex]::Matches($log, "Capacitor/Console[^\n]*(Uncaught|Error)[^\n]*") | ForEach-Object { $_.Value.Trim() } | Select-Object -Unique -First 3)
    if ($errs) { $problems += ($errs -join " | ") }
    $row.Problems = $problems -join "; "
    # simple screen checks from the page text: dump the visible UI
    $ui = & $adb -s $dev shell uiautomator dump /sdcard/ui.xml 2>$null; $xml = (& $adb -s $dev shell cat /sdcard/ui.xml 2>$null) -join ""
    $row.Link = $xml -match "link, not the conversation"
    & $adb -s $dev shell sh /sdcard/Download/share.sh | Out-Null; Start-Sleep 4
    $xml2 = (& $adb -s $dev shell "uiautomator dump /dev/tty" 2>$null) -join ""
    $row.ShareIn = $xml2 -match "Kyoto"
    $row.Copy = $log -match "Copied|clipboard" -or (Test-Path "$Out\${avd}_3_copied.png")
  }
  & $adb -s $dev emu kill 2>$null | Out-Null
  Start-Sleep 6
  $report += [pscustomobject]$row
}
$report | Format-Table -AutoSize -Wrap | Out-String | Tee-Object "$Out\report.txt"
Write-Host "Screenshots and report are in $Out"
