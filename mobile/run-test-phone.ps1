<#
  Builds the Android app on this PC, starts the test phone (an emulator) and installs and opens the app on it.
  Run from the project folder:   powershell -ExecutionPolicy Bypass -File mobile\run-test-phone.ps1
  Needs the one-time setup in mobile\README.md ("Test on this PC"): Java 21 and the Android SDK in a folder, and a test phone named ChatBridgeTest.
  Options:  -Root <folder>   where Java and the SDK live (default: ~\Android)     -NoBuild   reuse the last build
#>
param([string]$Root = "$env:USERPROFILE\Android", [switch]$NoBuild)
$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:JAVA_HOME = "$Root\jdk"; $env:ANDROID_HOME = "$Root\sdk"; $env:ANDROID_SDK_ROOT = "$Root\sdk"
$env:Path = "$Root\jdk\bin;$Root\sdk\platform-tools;$env:Path"
$adb = "$Root\sdk\platform-tools\adb.exe"
if (-not (Test-Path $adb)) { throw "Android tools not found in $Root. See mobile\README.md, section 'Test on this PC'." }

if (-not $NoBuild) {
  Push-Location $proj
  Write-Host "Copying the screen into the Android project..."
  npx cap sync android | Out-Null
  "sdk.dir=$(($Root + '\sdk').Replace('\', '\\'))" | Set-Content "$proj\android\local.properties" -Encoding ASCII
  Push-Location "$proj\android"
  Write-Host "Building (the first time takes a few minutes)..."
  & .\gradlew.bat assembleDebug --no-daemon --console=plain | Select-Object -Last 3
  Pop-Location; Pop-Location
}
$apk = "$proj\android\app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path $apk)) { throw "No build found. Run again without -NoBuild." }

$running = (& $adb devices) -match "emulator-\d+\s+device"
if (-not $running) {
  Write-Host "Starting the test phone..."
  $env:ANDROID_AVD_HOME = "$env:USERPROFILE\.android\avd"
  Start-Process "$Root\sdk\emulator\emulator.exe" -ArgumentList "-avd", "ChatBridgeTest", "-no-snapshot-save", "-no-audio", "-no-boot-anim"
  & $adb wait-for-device
  while ((& $adb shell getprop sys.boot_completed 2>$null) -notmatch "1") { Start-Sleep 3 }
}
Write-Host "Installing and opening ChatBridge..."
& $adb install -r $apk | Select-Object -Last 1
& $adb shell am start -n com.besmir25.chatbridge/.MainActivity | Out-Null
Write-Host "Done. ChatBridge is open on the test phone."
Write-Host "To try 'Share into ChatBridge': open any app on the test phone, use its Share button and pick ChatBridge."
