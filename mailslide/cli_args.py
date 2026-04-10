from __future__ import annotations

import argparse
from pathlib import Path

from outlook_mail_extractor.i18n import t


def build_parser(default_config: Path, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=default_config,
        help=t("cli.arg.config"),
    )
    parser.add_argument("--dry-run", action="store_true", help=t("cli.arg.dry_run"))
    parser.add_argument(
        "--output", "-o", type=Path, default=None, help=t("cli.arg.output")
    )
    parser.add_argument("--no-move", action="store_true", help=t("cli.arg.no_move"))
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help=t("cli.arg.skip_preflight"),
    )
    parser.add_argument(
        "--lang",
        choices=["zh-TW", "en-US"],
        default=None,
        help=t("cli.arg.lang"),
    )
    return parser
