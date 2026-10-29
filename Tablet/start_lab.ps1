[CmdletBinding()]
param([ValidateSet('Supra','Heat','Favourite')][string]$Model='Supra',[switch]$Lan,[switch]$BridgeOnly,[switch]$Windowed)
$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
$connection=Join-Path $project 'Saved/Tablet/connection.json'
New-Item -ItemType Directory -Force (Split-Path -Parent $connection) | Out-Null
$running=$false
try{$health=Invoke-RestMethod 'http://127.0.0.1:18740/health' -TimeoutSec 1;$running=$health.service -eq 'handling-tablet'}catch{}
if(!$running){
    $args=@(('"'+$PSScriptRoot+'/bridge.py"'),'--state',('"'+$connection+'"'))
    if($Lan){$args+='--lan'}
    Start-Process -FilePath (Get-Command python).Source -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput "$project/Saved/Tablet/bridge.log" -RedirectStandardError "$project/Saved/Tablet/bridge-error.log"
    for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 100;try{$health=Invoke-RestMethod 'http://127.0.0.1:18740/health' -TimeoutSec 1;if($health.ok){break}}catch{}}
}
$info=Get-Content -LiteralPath $connection -Raw | ConvertFrom-Json
Write-Output "Tablet pairing code: $($info.pin)"
Write-Output "USB address: http://127.0.0.1:18740"
if($Lan -and !$info.lan){throw 'The existing bridge is USB-only. Close that bridge before restarting with -Lan.'}
$adb='H:/Work/NoHesiLabTools/Android/platform-tools/adb.exe'
if(Test-Path -LiteralPath $adb){
    $devices=& $adb devices
    if(@($devices | Where-Object {$_ -match '\sdevice$'}).Count -eq 1){
        & $adb reverse tcp:18740 tcp:18740 | Out-Null
        & $adb shell am start -n com.nohesi.handlinglab/.MainActivity --es pairingPin $info.pin | Out-Null
    }
}
if($BridgeOnly){return}
if(Get-Process UnrealEditor,UnrealEditor-Cmd,NoHesiArcade,CitySample -ErrorAction SilentlyContinue){throw 'Close the running game/editor before starting Tablet Lab. The bridge remains available.'}
$gameProject=$project
if($Model -eq 'Favourite'){
    & "$project/Scripts/play_heat_accepted.ps1" -Version Favourite-FFB-2026-10-29 -VerifyOnly
    $version=Get-Content -LiteralPath "$project/Config/Heat/Versions/Favourite-FFB-2026-10-29.json" -Raw | ConvertFrom-Json
    $gameProject=Join-Path $version.directory 'NoHesiArcade'
}
$map=if($Model -ne 'Supra'){'/Game/HeatLab/Maps/L_HeatScenicHighway?HeatBaseline=0'}else{'/Game/Maps/L_HighwayLab'}
$args=@(('"'+$gameProject+'/NoHesiArcade.uproject"'),$map,'-game','-NoMainMenu','-TabletTuning','-NoLiveCoding','-DisablePython','-ResX=1920','-ResY=1080','-ZenDataPath=H:/UnrealCache/Zen/Data','-LocalDataCachePath=H:/UnrealCache/DerivedDataCache')
$args+=if($Windowed){'-windowed'}else{'-fullscreen'}
$previous=[Environment]::GetEnvironmentVariable('UE_SKIP_UBT_SDK_SETUP','Process')
try{[Environment]::SetEnvironmentVariable('UE_SKIP_UBT_SDK_SETUP','1','Process');Start-Process 'H:/EpicGames/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList $args -WorkingDirectory $gameProject -WindowStyle Normal}
finally{[Environment]::SetEnvironmentVariable('UE_SKIP_UBT_SDK_SETUP',$previous,'Process')}
