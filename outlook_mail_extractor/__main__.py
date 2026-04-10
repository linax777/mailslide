"""CLI entrypoint for legacy path."""

from mailslide.cli_app import run_cli


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
