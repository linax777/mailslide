from __future__ import annotations

import asyncio
import sys

from mailslide.cli_args import build_parser
from mailslide.cli_exit_map import map_exception_to_exit_code
from mailslide.cli_presenter import write_error, write_success_output
from outlook_mail_extractor.config import load_config
from outlook_mail_extractor.contracts.dependency_guard import DEPENDENCY_GUARD_REASON
from outlook_mail_extractor.i18n import resolve_language, set_language, t
from outlook_mail_extractor.logger import get_logger
from outlook_mail_extractor.models import DependencyGuardError
from outlook_mail_extractor.runtime import get_runtime_context
from outlook_mail_extractor.services.job_execution import JobExecutionService
from outlook_mail_extractor.services.preflight import PreflightCheckService
from outlook_mail_extractor.terminal_title import (
    resolve_terminal_title,
    set_terminal_title,
)


def _detect_lang_arg(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--lang" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--lang="):
            return arg.split("=", maxsplit=1)[1]
    return None


async def run_cli_async(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    runtime = get_runtime_context()
    set_terminal_title(resolve_terminal_title(runtime.paths.config_file))
    set_language(
        resolve_language(
            runtime.paths.config_file,
            explicit_language=_detect_lang_arg(argv),
        )
    )

    runtime.logger_manager.start_session()
    logger = get_logger()
    logger.info(t("cli.log.start"))

    parser = build_parser(runtime.paths.config_file, t("cli.description"))
    args = parser.parse_args(argv)
    if args.lang:
        set_language(args.lang)

    if not args.config.exists():
        message = t("cli.error.config_not_found", path=args.config)
        write_error(message)
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
                write_error(t("cli.error.preflight_failed", issues=issue_preview))
                return 1

        service = JobExecutionService(
            client_factory=runtime.client_factory,
            logger_manager=runtime.logger_manager,
            default_llm_config_path=runtime.paths.llm_config_file,
            default_plugin_config_dir=runtime.paths.plugins_dir,
        )
        results = await service.process_config_file(
            config_file=args.config,
            dry_run=args.dry_run,
            no_move=args.no_move,
        )
        write_success_output(results, args.output)
        logger.info(t("cli.log.finish"))
        return 0
    except Exception as error:
        if isinstance(error, DependencyGuardError):
            logger.error(t("log.job_execution.dependency_guard_failed", error=error))
            write_error(
                t(
                    "cli.error.dependency_guard_failed",
                    error=error,
                    reason=DEPENDENCY_GUARD_REASON,
                )
            )
        else:
            logger.exception(f"執行失敗: {error}")
            write_error(t("cli.error.execution_failed", error=error))
        return map_exception_to_exit_code(error)


def run_cli(argv: list[str] | None = None) -> int:
    return asyncio.run(run_cli_async(argv))
