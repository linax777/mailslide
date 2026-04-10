from __future__ import annotations

import json
import sys
from pathlib import Path

from outlook_mail_extractor.i18n import t


def render_results(results: dict) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2)


def write_success_output(results: dict, output: Path | None) -> None:
    body = render_results(results)
    if output is None:
        print(body)
        return
    output.write_text(body, encoding="utf-8")
    print(t("cli.info.result_saved", path=output.resolve()))


def write_error(message: str) -> None:
    print(message, file=sys.stderr)
