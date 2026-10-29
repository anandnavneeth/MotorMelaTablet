[CmdletBinding()]
param([string]$Tools='H:/Work/NoHesiLabTools/Android',[switch]$Install)
$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
$build=Join-Path $project 'Saved/Tablet/AndroidBuild'
$output=Join-Path $project 'Binaries/Tablet'
New-Item -ItemType Directory -Force -Path $build,$output,"$build/classes","$build/dex" | Out-Null
$jdk=Get-ChildItem $Tools -Directory -Filter 'jdk-*' | Select-Object -First 1
if(!$jdk){throw 'Portable JDK missing. See TABLET_TUNING.md.'}
$env:JAVA_HOME=$jdk.FullName
$env:PATH="$($jdk.FullName)/bin;"+$env:PATH
$bt=Join-Path $Tools 'android-15'
$platform=Join-Path $Tools 'android-35/android.jar'
function Check {if($LASTEXITCODE -ne 0){throw "Android build command failed: $LASTEXITCODE"}}
& "$($jdk.FullName)/bin/javac.exe" -encoding UTF-8 -source 17 -target 17 -classpath $platform -d "$build/classes" "$PSScriptRoot/android/MainActivity.java"; Check
& "$bt/aapt2.exe" link -I $platform --manifest "$PSScriptRoot/android/AndroidManifest.xml" -o "$build/base.apk"; Check
$classes=Get-ChildItem "$build/classes" -Recurse -Filter '*.class' | Select-Object -ExpandProperty FullName
& "$bt/d8.bat" --lib $platform --min-api 26 --output "$build/dex" @classes; Check
Copy-Item -LiteralPath "$build/base.apk" -Destination "$build/unsigned.apk" -Force
& "$($jdk.FullName)/bin/jar.exe" uf "$build/unsigned.apk" -C "$build/dex" classes.dex; Check
& "$bt/zipalign.exe" -f 4 "$build/unsigned.apk" "$build/aligned.apk"; Check
# Local development signing key, excluded from source control. Keep it for updates.
$key=Join-Path $project 'Saved/Tablet/development.keystore'
if(!(Test-Path -LiteralPath $key)){
    & "$($jdk.FullName)/bin/keytool.exe" -genkeypair -keystore $key -storepass android -keypass android -alias handlinglab -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=NoHesi Local Development' -noprompt; Check
}
& "$bt/apksigner.bat" sign --ks $key --ks-key-alias handlinglab --ks-pass pass:android --key-pass pass:android --out "$output/HandlingLab.apk" "$build/aligned.apk"; Check
& "$bt/apksigner.bat" verify "$output/HandlingLab.apk"; Check
Write-Output "Built $output/HandlingLab.apk"
if($Install){
    $adb=Join-Path $Tools 'platform-tools/adb.exe'
    $devices=& $adb devices
    if(@($devices | Where-Object {$_ -match '\sdevice$'}).Count -ne 1){throw 'Connect and authorize exactly one Android tablet.'}
    & $adb install -r "$output/HandlingLab.apk"; Check
    & $adb reverse tcp:18740 tcp:18740; Check
    & $adb shell am start -n com.nohesi.handlinglab/.MainActivity; Check
}
