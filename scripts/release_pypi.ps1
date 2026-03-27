param(
    [switch]$SkipTests,
    [switch]$SkipSmoke,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Step($Name, [scriptblock]$Command) {
    Write-Step $Name
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name"
    }
}

function Get-VersionFromFile {
    param(
        [string]$Path,
        [string]$Pattern,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw "$Label not found: $Path"
    }

    $raw = Get-Content -Path $Path -Raw
    $m = [regex]::Match($raw, $Pattern)
    if (-not $m.Success) {
        throw "Cannot parse $Label version in $Path"
    }

    return $m.Groups[1].Value
}

if (-not (Test-Path "pyproject.toml")) {
    throw "Please run this script from repository root."
}

if (-not $AllowDirty) {
    $status = git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read git status."
    }
    if ($status) {
        throw "Working tree is not clean. Commit/stash changes, or pass -AllowDirty."
    }
}

$projectVersion = Get-VersionFromFile -Path "pyproject.toml" -Pattern '(?m)^version\s*=\s*"([^"]+)"' -Label "pyproject"
$initVersion = Get-VersionFromFile -Path "outlook_mail_extractor/__init__.py" -Pattern '(?m)^__version__\s*=\s*"([^"]+)"' -Label "package"
$aboutVersion = Get-VersionFromFile -Path "outlook_mail_extractor/screens/about.py" -Pattern '(?m)^\s*VERSION\s*=\s*"([^"]+)"' -Label "about screen"
$lockVersion = Get-VersionFromFile -Path "uv.lock" -Pattern '(?s)\[\[package\]\]\s*name\s*=\s*"mailslide".*?version\s*=\s*"([^"]+)"' -Label "uv.lock"

if ($projectVersion -ne $initVersion -or $projectVersion -ne $aboutVersion -or $projectVersion -ne $lockVersion) {
    throw "Version mismatch: pyproject=$projectVersion, __init__=$initVersion, about=$aboutVersion, uv.lock=$lockVersion"
}

$changelog = Get-Content -Path "CHANGELOG.md" -Raw
$headerPattern = "(?m)^## \[v$([regex]::Escape($projectVersion))\]"
if (-not [regex]::IsMatch($changelog, $headerPattern)) {
    throw "CHANGELOG.md does not contain header for v$projectVersion"
}

if (Test-Path "dist") {
    Invoke-Step "Clean dist/" { Remove-Item -Recurse -Force "dist" }
}

Invoke-Step "Check packaged guide sync" { ./scripts/sync_guides.ps1 -CheckOnly }

if (-not $SkipTests) {
    Invoke-Step "Run tests" { uv run pytest -q }
} else {
    Write-Step "Skip tests (-SkipTests)"
}

Invoke-Step "Build distribution" { uv build }
Invoke-Step "Check package metadata" { uvx twine check dist/* }

if (-not $SkipSmoke) {
    Invoke-Step "Smoke check CLI help" { uv run mailslide --help }
} else {
    Write-Step "Skip smoke check (-SkipSmoke)"
}

Write-Host ""
Write-Host "Pre-release checks passed for version $projectVersion." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1) Upload to TestPyPI: uvx twine upload --repository testpypi dist/*"
Write-Host "2) Verify install:     uv tool install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mailslide"
Write-Host "3) Upload to PyPI:     uvx twine upload dist/*"
Write-Host "4) Verify upgrade:     uv tool upgrade mailslide"
