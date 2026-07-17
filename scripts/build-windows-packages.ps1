[CmdletBinding()]
param(
    [switch]$SkipSync,
    [switch]$SkipClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $projectRoot
try {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        $uvExecutable = $uvCommand.Source
        $uvPrefix = @()
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $uvExecutable = (Get-Command python).Source
        $uvPrefix = @('-m', 'uv')
        & $uvExecutable @uvPrefix --version *> $null
        if ($LASTEXITCODE -ne 0) {
            throw 'uv is unavailable. See https://docs.astral.sh/uv/getting-started/installation/'
        }
    } else {
        throw 'Neither uv nor Python was found.'
    }

    if (-not $SkipSync) {
        Write-Host '[VoxCaps] Syncing the reproducible uv build environment...' -ForegroundColor Cyan
        & $uvExecutable @uvPrefix sync --frozen --group build
        if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
    }

    $commonArgs = @('--noconfirm')
    if (-not $SkipClean) { $commonArgs += '--clean' }

    Write-Host '[VoxCaps] Running automated tests and source compilation checks...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed.' }
    & $uvExecutable @uvPrefix run --no-sync python -m compileall -q core tests scripts start_client.py start_server.py config_client.py config_server.py
    if ($LASTEXITCODE -ne 0) { throw 'Source compilation check failed.' }

    Write-Host '[VoxCaps] Generating and validating brand icon assets...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync python scripts/generate-brand-icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Brand icon generation failed.' }
    & $uvExecutable @uvPrefix run --no-sync python scripts/verify-brand-assets.py
    if ($LASTEXITCODE -ne 0) { throw 'Brand asset validation failed.' }

    Write-Host '[VoxCaps] Building the full Client + Server package...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync pyinstaller @commonArgs build.spec
    if ($LASTEXITCODE -ne 0) { throw 'Full package PyInstaller build failed.' }

    Write-Host '[VoxCaps] Building the client-only package...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync pyinstaller @commonArgs build-client.spec
    if ($LASTEXITCODE -ne 0) { throw 'Client-only PyInstaller build failed.' }

    Write-Host '[VoxCaps] Validating embedded EXE icon resources...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync python scripts/verify-brand-assets.py --executables `
        'dist\VoxCaps\start_client.exe' `
        'dist\VoxCaps\start_server.exe' `
        'dist\VoxCaps-Client\start_client.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Built EXE icon resource validation failed.' }

    Write-Host '[VoxCaps] Creating both ZIP release packages...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync python zip_release.py
    if ($LASTEXITCODE -ne 0) { throw 'ZIP packaging failed.' }
    & $uvExecutable @uvPrefix run --no-sync python scripts/verify-windows-packages.py --release-dir release
    if ($LASTEXITCODE -ne 0) { throw 'ZIP content validation failed.' }

    Write-Host "[VoxCaps] Build complete: $projectRoot\release" -ForegroundColor Green
}
finally {
    Pop-Location
}
