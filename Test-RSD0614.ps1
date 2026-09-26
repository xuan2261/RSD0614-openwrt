[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$Here = $PSScriptRoot
$Image = 'rsd0614-openwrt-builder:v5.1'
if ($Here.Contains(',')) { throw 'Extract into a directory without a comma in its path.' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found.' }
$OSType = & docker info --format '{{.OSType}}' 2>&1
if ($LASTEXITCODE -ne 0 -or ($OSType -join '').Trim() -ne 'linux') {
    throw 'Start Docker Desktop with Linux containers, then retry.'
}
$ImageId = & docker image inspect $Image --format '{{.Id}}' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Existing RSD0614 builder not found. This test command does not install or rebuild it.'
}
$Logs = Join-Path $Here 'logs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$LogPath = Join-Path $Logs "$RunId-preflight.log"
"TEST_ONLY=YES; BUILDER=$Image; IMAGE_ID=$($ImageId -join '')" | Set-Content -Encoding utf8 $LogPath
$DockerArgs = @('run','--rm','--platform=linux/amd64','--network=none','--user','1000:1000',
    '--mount',"type=bind,source=$Here,target=/port,readonly",
    '--env','PYTHONDONTWRITEBYTECODE=1','--workdir','/tmp',
    $Image,'python3','/port/run_tests.py')
& docker @DockerArgs 2>&1 | Tee-Object -FilePath $LogPath -Append
$Code = $LASTEXITCODE
if ($Code -ne 0) { throw "Preflight failed with code $Code. Keep this log: $LogPath" }
Write-Host "PREFLIGHT EXECUTION PASS in the existing builder. Log: $LogPath"
Write-Host 'No source checkout, firmware compile, router access, or boot authorization.'
