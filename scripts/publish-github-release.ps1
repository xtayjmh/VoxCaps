[CmdletBinding()]
param(
    [string]$Version,
    [string]$Repository,
    [string]$NotesFile,
    [int]$MaxAttempts = 5,
    [switch]$SkipBuild,
    [switch]$SkipSync,
    [switch]$Draft
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Native {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)] [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory)] [scriptblock]$Action,
        [Parameter(Mandatory)] [string]$Description,
        [Parameter(Mandatory)] [int]$Attempts
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            & $Action
            return
        } catch {
            if ($attempt -eq $Attempts) {
                throw
            }
            $delaySeconds = [Math]::Min(60, [Math]::Pow(2, $attempt) * 3)
            Write-Warning "$Description failed on attempt $attempt/${Attempts}: $($_.Exception.Message)"
            Write-Host "Retrying in $delaySeconds seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds $delaySeconds
        }
    }
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $projectRoot
try {
    if ($MaxAttempts -lt 1) {
        throw 'MaxAttempts must be at least 1.'
    }

    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) {
        throw 'GitHub CLI (gh) is required. Install it, then run: gh auth login'
    }
    Invoke-Native $gh.Source 'auth' 'status'

    $dirtyEntries = @(git status --porcelain)
    if ($dirtyEntries.Count -gt 0) {
        throw "Working tree is not clean. Commit or stash changes before publishing:`n$($dirtyEntries -join [Environment]::NewLine)"
    }

    $branch = (git branch --show-current).Trim()
    if ($branch -ne 'master') {
        throw "Official releases must be made from master; current branch is '$branch'."
    }

    if (-not $Repository) {
        $Repository = (& $gh.Source repo view --json nameWithOwner --jq '.nameWithOwner').Trim()
        if ($LASTEXITCODE -ne 0 -or -not $Repository) {
            throw 'Could not determine the GitHub repository.'
        }
    }

    if (-not $Version) {
        $versionMatch = Select-String -Path 'config_server.py' -Pattern '^__version__\s*=\s*[\''"]([^\''"]+)[\''"]\s*$' | Select-Object -First 1
        if (-not $versionMatch) {
            throw 'Could not read __version__ from config_server.py.'
        }
        $Version = $versionMatch.Matches[0].Groups[1].Value
    }
    if ($Version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Version must use semantic versioning such as 3.0.2; got '$Version'."
    }

    $tag = "v$Version"
    if (-not $NotesFile) {
        $NotesFile = Join-Path 'docs/releases' "$tag.md"
    }
    $NotesPath = [IO.Path]::GetFullPath((Join-Path $projectRoot $NotesFile))
    if (-not (Test-Path -LiteralPath $NotesPath -PathType Leaf)) {
        throw "Release notes file does not exist: $NotesPath"
    }

    Write-Host "[VoxCaps] Pushing master to origin..." -ForegroundColor Cyan
    Invoke-Native 'git' 'push' 'origin' 'master'

    if (-not $SkipBuild) {
        $buildArgs = @('-NoProfile', '-File', 'scripts/build-windows-packages.ps1')
        if ($SkipSync) { $buildArgs += '-SkipSync' }
        Write-Host "[VoxCaps] Building and validating Windows packages..." -ForegroundColor Cyan
        Invoke-Native 'pwsh' @buildArgs
    }

    $releaseDate = Get-Date -Format 'yyyyMMdd'
    $fullPackage = Join-Path $projectRoot "release/VoxCaps-$releaseDate.zip"
    $clientPackage = Join-Path $projectRoot "release/VoxCaps-Client-$releaseDate.zip"
    foreach ($package in @($fullPackage, $clientPackage)) {
        if (-not (Test-Path -LiteralPath $package -PathType Leaf)) {
            throw "Expected release package was not found: $package"
        }
    }

    $existingRelease = & $gh.Source release view $tag --repo $Repository --json tagName 2>$null
    $releaseExists = $LASTEXITCODE -eq 0 -and $existingRelease
    if ($releaseExists) {
        throw "Release $tag already exists. Refusing to overwrite an existing public release."
    }

    $releaseArgs = @(
        'release', 'create', $tag,
        $fullPackage, $clientPackage,
        '--repo', $Repository,
        '--target', 'master',
        '--title', "VoxCaps $Version",
        '--notes-file', $NotesPath,
        '--latest'
    )
    if ($Draft) { $releaseArgs += '--draft' }

    Write-Host "[VoxCaps] Publishing $tag to $Repository..." -ForegroundColor Cyan
    Invoke-WithRetry -Description "GitHub release $tag" -Attempts $MaxAttempts -Action {
        Invoke-Native $gh.Source @releaseArgs
    }

    $releaseUrl = (& $gh.Source release view $tag --repo $Repository --json url --jq '.url').Trim()
    $fullHash = (Get-FileHash -LiteralPath $fullPackage -Algorithm SHA256).Hash
    $clientHash = (Get-FileHash -LiteralPath $clientPackage -Algorithm SHA256).Hash
    Write-Host "[VoxCaps] Release published: $releaseUrl" -ForegroundColor Green
    Write-Host "  $(Split-Path -Leaf $fullPackage): $fullHash"
    Write-Host "  $(Split-Path -Leaf $clientPackage): $clientHash"
}
finally {
    Pop-Location
}
