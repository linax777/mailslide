param(
    [Parameter(Position = 0)]
    [ValidateSet("extract", "init", "update", "compile", "all")]
    [string]$Action = "all"
)

$ErrorActionPreference = "Stop"

$pot = "outlook_mail_extractor/locales/gettext/messages.pot"
$domain = "messages"
$localeDir = "outlook_mail_extractor/locales/gettext"

function Run-Extract {
    uv run pybabel extract -F babel.cfg -o $pot .
}

function Run-Init {
    if (-not (Test-Path $pot)) {
        throw "POT file not found. Run extract first."
    }

    $zhPo = "$localeDir/zh_TW/LC_MESSAGES/messages.po"
    if (-not (Test-Path $zhPo)) {
        uv run pybabel init -i $pot -d $localeDir -D $domain -l zh_TW
    }

    $enPo = "$localeDir/en_US/LC_MESSAGES/messages.po"
    if (-not (Test-Path $enPo)) {
        uv run pybabel init -i $pot -d $localeDir -D $domain -l en_US
    }
}

function Run-Update {
    if (-not (Test-Path $pot)) {
        throw "POT file not found. Run extract first."
    }
    uv run pybabel update -i $pot -d $localeDir -D $domain
}

function Run-Compile {
    uv run pybabel compile -d $localeDir -D $domain
}

switch ($Action) {
    "extract" { Run-Extract }
    "init" { Run-Init }
    "update" { Run-Update }
    "compile" { Run-Compile }
    "all" {
        Run-Extract
        Run-Init
        Run-Update
        Run-Compile
    }
}
