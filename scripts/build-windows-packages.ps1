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
        Write-Host '[CapsWriter] Syncing the reproducible uv build environment...' -ForegroundColor Cyan
        & $uvExecutable @uvPrefix sync --frozen --group build
        if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
    }

    $commonArgs = @('--noconfirm')
    if (-not $SkipClean) { $commonArgs += '--clean' }

    Write-Host '[CapsWriter] Building the full Client + Server package...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync pyinstaller @commonArgs build.spec
    if ($LASTEXITCODE -ne 0) { throw 'Full package PyInstaller build failed.' }

    Write-Host '[CapsWriter] Building the client-only package...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync pyinstaller @commonArgs build-client.spec
    if ($LASTEXITCODE -ne 0) { throw 'Client-only PyInstaller build failed.' }

    Write-Host '[CapsWriter] Creating both ZIP release packages...' -ForegroundColor Cyan
    & $uvExecutable @uvPrefix run --no-sync python zip_release.py
    if ($LASTEXITCODE -ne 0) { throw 'ZIP packaging failed.' }

    Write-Host "[CapsWriter] Build complete: $projectRoot\release" -ForegroundColor Green
}
finally {
    Pop-Location
}
