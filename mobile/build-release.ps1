<#
  Builds the files for Google Play: a signed .aab (the upload file) and a signed .apk (for installing on a phone to try the real thing).
  Needs the signing key (mobile\android\keystore.properties, created once; see mobile\store\play-console-answers.md) and the
  Java + Android SDK folder from mobile\README.md.
     powershell -ExecutionPolicy Bypass -File mobile\build-release.ps1
  Options: -Root <folder with Java and the SDK> (default ~\Android)
  Output:  mobile\release\ChatBridge-<version>.aab   and   mobile\release\ChatBridge-<version>.apk
#>
param([string]$Root = "$env:USERPROFILE\Android")
$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:JAVA_HOME = "$Root\jdk"; $env:ANDROID_HOME = "$Root\sdk"; $env:ANDROID_SDK_ROOT = "$Root\sdk"
$env:Path = "$Root\jdk\bin;$Root\sdk\platform-tools;$env:Path"
if (-not (Test-Path "$proj\android\keystore.properties")) { throw "No signing key found (mobile\android\keystore.properties). See mobile\store\play-console-answers.md." }
$version = (Get-Content "$proj\package.json" -Raw | ConvertFrom-Json).version
Push-Location $proj
npx cap sync android | Out-Null
"sdk.dir=$(($Root + '\sdk').Replace('\', '\\'))" | Set-Content "$proj\android\local.properties" -Encoding ASCII
Push-Location "$proj\android"
& .\gradlew.bat bundleRelease assembleRelease --no-daemon --console=plain | Select-Object -Last 4
Pop-Location; Pop-Location
$out = "$proj\release"; New-Item -ItemType Directory -Force $out | Out-Null
$aab = "$proj\android\app\build\outputs\bundle\release\app-release.aab"
$apk = "$proj\android\app\build\outputs\apk\release\app-release.apk"
if (-not (Test-Path $aab)) { throw "The build did not produce an .aab" }
Copy-Item $aab "$out\ChatBridge-$version.aab" -Force
Copy-Item $apk "$out\ChatBridge-$version.apk" -Force
# prove both are signed, and by our key
$apksigner = Get-ChildItem "$Root\sdk\build-tools" -Recurse -Filter apksigner.bat | Sort-Object FullName | Select-Object -Last 1
& $apksigner.FullName verify --print-certs "$out\ChatBridge-$version.apk" | Select-String "Signer #1 certificate (DN|SHA-256)"
& "$Root\jdk\bin\jarsigner.exe" -verify "$out\ChatBridge-$version.aab" | Select-Object -First 1
Write-Host "Done: $out\ChatBridge-$version.aab  (upload this to Google Play)  and  $out\ChatBridge-$version.apk"
