param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:[A-Za-z][0-9A-Za-z.-]*)?$')]
    [string]$Version,

    [Parameter(Position = 1)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),

    [switch]$SkipChangelog
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Read-Text([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function Write-Text([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Replace-ExactlyOne {
    param(
        [Parameter(Mandatory = $true)] [string]$Text,
        [Parameter(Mandatory = $true)] [string]$Pattern,
        [Parameter(Mandatory = $true)] [string]$Replacement,
        [Parameter(Mandatory = $true)] [string]$Label
    )

    $matches = [System.Text.RegularExpressions.Regex]::Matches($Text, $Pattern)
    if ($matches.Count -ne 1) {
        throw "$Label expected exactly 1 match, found $($matches.Count)."
    }

    return [System.Text.RegularExpressions.Regex]::Replace($Text, $Pattern, $Replacement, 1)
}

function Update-VersionLine {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$Pattern,
        [Parameter(Mandatory = $true)] [string]$Template,
        [Parameter(Mandatory = $true)] [string]$Label
    )

    $text = Read-Text $Path
    $replacement = [string]::Format($Template, $Version)
    $newText = Replace-ExactlyOne -Text $text -Pattern $Pattern -Replacement $replacement -Label $Label
    Write-Text -Path $Path -Content $newText
    Write-Host "Updated $Label -> $Version"
}

$pyprojectPath = Join-Path $repoRoot 'pyproject.toml'
$initPath = Join-Path $repoRoot 'outlook_mail_extractor/__init__.py'
$aboutPath = Join-Path $repoRoot 'outlook_mail_extractor/screens/about.py'
$lockPath = Join-Path $repoRoot 'uv.lock'
$changelogPath = Join-Path $repoRoot 'CHANGELOG.md'

Update-VersionLine -Path $pyprojectPath -Pattern '(?m)^version = "[^"]+"(?=\r?$)' -Template 'version = "{0}"' -Label 'pyproject.toml [project].version'
Update-VersionLine -Path $initPath -Pattern '(?m)^__version__ = "[^"]+"(?=\r?$)' -Template '__version__ = "{0}"' -Label '__init__.__version__'
Update-VersionLine -Path $aboutPath -Pattern '(?m)^\s*VERSION = "[^"]+"(?=\r?$)' -Template '    VERSION = "{0}"' -Label 'AboutScreen.VERSION'

$lockText = Read-Text $lockPath
$lockPattern = '(?ms)(?<prefix>\[\[package\]\]\r?\nname = "mailslide"\r?\nversion = ")[^"]+(?<suffix>"\r?\nsource = \{ editable = "\." \})'
$lockReplacement = "`${prefix}$Version`${suffix}"
$newLockText = Replace-ExactlyOne -Text $lockText -Pattern $lockPattern -Replacement $lockReplacement -Label 'uv.lock mailslide package version'
Write-Text -Path $lockPath -Content $newLockText
Write-Host "Updated uv.lock mailslide package version -> $Version"

if (-not $SkipChangelog) {
    $changelogText = Read-Text $changelogPath
    $header = "## [v$Version] - $Date"
    $newline = if ($changelogText.Contains("`r`n")) { "`r`n" } else { "`n" }

    if ($changelogText -match [Regex]::Escape($header)) {
        Write-Host "CHANGELOG already has $header"
    }
    else {
        $insertBlock = @(
            $header,
            '',
            '### Changed',
            '',
            '- TODO: add release notes.',
            ''
        ) -join $newline

        $anchorPattern = '(?m)^The format is based on Keep a Changelog, with entries grouped by release date\.?\s*$'
        $anchorMatch = [Regex]::Match($changelogText, $anchorPattern)

        if ($anchorMatch.Success) {
            $insertIndex = $anchorMatch.Index + $anchorMatch.Length
            $prefix = $changelogText.Substring(0, $insertIndex)
            $suffix = $changelogText.Substring($insertIndex).TrimStart("`r", "`n")
            $newChangelog = "$prefix$newline$newline$insertBlock$suffix"
        }
        else {
            $firstReleasePattern = '(?m)^## \['
            $firstReleaseMatch = [Regex]::Match($changelogText, $firstReleasePattern)
            if (-not $firstReleaseMatch.Success) {
                throw 'Failed to locate changelog insertion point.'
            }

            $insertIndex = $firstReleaseMatch.Index
            $prefix = $changelogText.Substring(0, $insertIndex).TrimEnd("`r", "`n")
            $suffix = $changelogText.Substring($insertIndex).TrimStart("`r", "`n")
            $newChangelog = "$prefix$newline$newline$insertBlock$suffix"
        }

        Write-Text -Path $changelogPath -Content $newChangelog
        Write-Host "Inserted CHANGELOG header -> $header"
    }
}

Write-Host 'Done.'
