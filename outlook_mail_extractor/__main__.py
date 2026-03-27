"""命令列入口點"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import load_config
from .i18n import resolve_language, set_language, t
from .logger import get_logger
from .runtime import get_runtime_context
from .services.job_execution import JobExecutionService
from .services.preflight import PreflightCheckService


async def async_main() -> int:
    """CLI 主函式"""
    runtime = get_runtime_context()
    lang_override = _detect_lang_arg(sys.argv[1:])
    set_language(
        resolve_language(runtime.paths.config_file, explicit_language=lang_override)
    )

    runtime.logger_manager.start_session()
    logger = get_logger()
    logger.info(t("cli.log.start"))

    parser = argparse.ArgumentParser(description=t("cli.description"))
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=runtime.paths.config_file,
        help=t("cli.arg.config"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("cli.arg.dry_run"),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=t("cli.arg.output"),
    )
    parser.add_argument(
        "--no-move",
        action="store_true",
        help=t("cli.arg.no_move"),
    )
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

    args = parser.parse_args()
    if args.lang:
        set_language(args.lang)

    if not args.config.exists():
        message = t("cli.error.config_not_found", path=args.config)
        print(message, file=sys.stderr)
        logger.error(message)
        return 1

    try:
        if not args.skip_preflight:
            config = load_config(args.config)
            preflight = PreflightCheckService(client_factory=runtime.client_factory)
            preflight_result = preflight.run(config)

            if preflight_result.issues:
                issue_preview = "\n".join(
                    f"- {issue}" for issue in preflight_result.issues[:5]
                )
                if len(preflight_result.issues) > 5:
                    issue_preview += t(
                        "cli.preflight.more_issues",
                        count=len(preflight_result.issues) - 5,
                    )

                logger.error(f"Preflight failed with config issues:\n{issue_preview}")
                print(
                    t("cli.error.preflight_failed", issues=issue_preview),
                    file=sys.stderr,
                )
                return 1

        execution_service = JobExecutionService(
            client_factory=runtime.client_factory,
            logger_manager=runtime.logger_manager,
            default_llm_config_path=runtime.paths.llm_config_file,
            default_plugin_config_dir=runtime.paths.plugins_dir,
        )
        results = await execution_service.process_config_file(
            config_file=args.config,
            dry_run=args.dry_run,
            no_move=args.no_move,
        )

        json_str = json.dumps(results, ensure_ascii=False, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_str)
            result_saved_message = t(
                "cli.info.result_saved", path=args.output.resolve()
            )
            print(result_saved_message)
            logger.info(result_saved_message)
        else:
            print(json_str)

        logger.info(t("cli.log.finish"))
        return 0

    except Exception as e:
        logger.exception(f"執行失敗: {e}")
        print(t("cli.error.execution_failed", error=e), file=sys.stderr)
        return 1


def _detect_lang_arg(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--lang" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--lang="):
            return arg.split("=", maxsplit=1)[1]
    return None


def main() -> int:
    """同步包裝函式，提供 console script 使用。"""
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
