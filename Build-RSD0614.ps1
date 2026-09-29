[CmdletBinding()]
param(
    [switch]$BuilderOnly,
    [switch]$RebuildBuilder,
    [ValidateRange(1, 8)][int]$Jobs = 2
)
$ErrorActionPreference = 'Stop'
# Keep native failures inspectable and logged before throwing an exception.
$PSNativeCommandUseErrorActionPreference = $false
$Here = $PSScriptRoot
$Image = 'rsd0614-openwrt-builder:v5.1'
$Volume = 'rsd0614-openwrt-v534-work'
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$Logs = Join-Path $Here 'logs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
if ($Here.Contains(',')) { throw 'Extract into a directory without a comma in its path.' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found.' }
$OSType = & docker info --format '{{.OSType}}' 2>&1
if ($LASTEXITCODE -ne 0 -or ($OSType -join '').Trim() -ne 'linux') {
    throw 'Start Docker Desktop with Linux containers, then retry.'
}
function Invoke-DockerLogged {
    param([string[]]$DockerArgs, [string]$LogPath)
    & docker @DockerArgs 2>&1 | Tee-Object -FilePath $LogPath
    $Code = $LASTEXITCODE
    if ($Code -ne 0) { throw "Docker exited with code $Code. Full log: $LogPath" }
}

# Reuse the already-working builder; rebuild only when absent or explicitly requested.
$ExistingImage = & docker image inspect $Image --format '{{.Id}}' 2>$null
$HaveBuilder = ($LASTEXITCODE -eq 0)
if (-not $HaveBuilder -or $RebuildBuilder) {
    $BuildArgs = @('build', '--platform=linux/amd64', '--progress=plain', '--pull',
        '--build-arg', 'DEBIAN_SNAPSHOT=20260901T000000Z', '-t', $Image)
    if ($RebuildBuilder) { $BuildArgs += '--no-cache' }
    $BuildArgs += $Here
    Invoke-DockerLogged -DockerArgs $BuildArgs -LogPath (Join-Path $Logs "$RunId-builder.log")
} else {
    "Reusing verified-family builder: $($ExistingImage -join '')" | Set-Content -Encoding utf8 (Join-Path $Logs "$RunId-builder.log")
}

$Smoke = 'set -eu; test "$(id -u)" = 1000; python2 --version; python3 --version; git --version; command -v gcc; command -v make; command -v flock; cat /opt/rsd0614/debian-snapshot.txt'
Invoke-DockerLogged -DockerArgs @('run', '--rm', '--platform=linux/amd64', '--network=none', $Image, 'sh', '-c', $Smoke) -LogPath (Join-Path $Logs "$RunId-builder-smoke.log")
& docker image inspect $Image --format '{{.Id}}' | Set-Content -Encoding utf8 (Join-Path $Logs "$RunId-builder-image-id.txt")
if ($LASTEXITCODE -ne 0) { throw 'Unable to record builder image ID.' }
Write-Host 'BUILDER EXECUTION PASS on this Docker engine.'
if ($BuilderOnly) {
    Write-Host 'Builder check completed. No source checkout, firmware compile, or router access was performed.'
    return
}

# Linux source/toolchain volume; only logs/artifacts are exported to Windows.
$Volumes = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'Cannot list Docker volumes.' }
if ($Volumes -contains $Volume) {
    $Owner = & docker volume inspect $Volume --format '{{ index .Labels "rsd0614.work" }}'
    if ($LASTEXITCODE -ne 0 -or ($Owner -join '').Trim() -ne 'v5.3.4') {
        throw 'Existing work volume has an unexpected ownership label; refusing to use it.'
    }
} else {
    & docker volume create --label 'rsd0614.work=v5.3.4' $Volume | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the dedicated Linux work volume.' }
}
# Chown only the root of this dedicated volume; do not touch the host filesystem.
Invoke-DockerLogged -DockerArgs @('run','--rm','--platform=linux/amd64','--network=none','--user','0:0',
    '--mount',"type=volume,source=$Volume,target=/work",$Image,'sh','-c','set -eu; chown 1000:1000 /work; chmod u+rwx /work') -LogPath (Join-Path $Logs "$RunId-volume-init.log")

$OutputDir = Join-Path (Join-Path $Here 'out') $RunId
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$RunArgs = @('run','--rm','--platform=linux/amd64','--user','1000:1000',
    '--mount',"type=volume,source=$Volume,target=/work",
    '--mount',"type=bind,source=$Here,target=/port,readonly",
    '--mount',"type=bind,source=$OutputDir,target=/out",
    '--env',"JOBS=$Jobs",'--env',"BUILDER_IMAGE_ID=$($ImageId -join '')",'--workdir','/work',$Image,'bash','/port/build-rsd0614-initramfs.sh')
Invoke-DockerLogged -DockerArgs $RunArgs -LogPath (Join-Path $Logs "$RunId-openwrt.log")
Write-Host "Candidate and evidence: $OutputDir"
Write-Host 'Do not load or execute the candidate on the router. Binary review is still required.'
