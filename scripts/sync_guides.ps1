param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path "pyproject.toml")) {
    throw "Please run this script from repository root."
}

$pairs = @(
    @{ Source = "GUIDE.md"; Target = "outlook_mail_extractor/resources/docs/GUIDE.md" },
    @{ Source = "GUIDE.en.md"; Target = "outlook_mail_extractor/resources/docs/GUIDE.en.md" }
)

$mismatch = $false

foreach ($pair in $pairs) {
    $source = $pair.Source
    $target = $pair.Target

    if (-not (Test-Path $source)) {
        throw "Source guide not found: $source"
    }

    if (-not (Test-Path $target)) {
        if ($CheckOnly) {
            Write-Host "Missing packaged guide: $target" -ForegroundColor Red
            $mismatch = $true
            continue
        }
        $targetDir = Split-Path -Path $target -Parent
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        Copy-Item -Path $source -Destination $target -Force
        Write-Host "Copied $source -> $target" -ForegroundColor Green
        continue
    }

    $sourceHash = (Get-FileHash -Algorithm SHA256 -Path $source).Hash
    $targetHash = (Get-FileHash -Algorithm SHA256 -Path $target).Hash

    if ($sourceHash -eq $targetHash) {
        Write-Host "Up-to-date: $target" -ForegroundColor DarkGray
        continue
    }

    if ($CheckOnly) {
        Write-Host "Out-of-sync: $source != $target" -ForegroundColor Red
        $mismatch = $true
        continue
    }

    Copy-Item -Path $source -Destination $target -Force
    Write-Host "Synced $source -> $target" -ForegroundColor Green
}

if ($CheckOnly -and $mismatch) {
    throw "Packaged guides are out of sync. Run: ./scripts/sync_guides.ps1"
}

if ($CheckOnly) {
    Write-Host "Guide resources are in sync." -ForegroundColor Green
}
