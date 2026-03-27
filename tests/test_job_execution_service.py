from pathlib import Path

from outlook_mail_extractor.services.job_execution import JobExecutionService


def test_normalize_plugin_output_paths_resolves_relative_to_config_dir(
    tmp_path: Path,
) -> None:
    service = JobExecutionService()
    base_dir = tmp_path / "config-root"

    configs = {
        "write_file": {"output_dir": "output"},
        "summary_file": {"output_file": "output/email_summaries.csv"},
        "event_table": {"output_file": "output/events.xlsx"},
    }

    normalized = service._normalize_plugin_output_paths(configs, base_dir=base_dir)

    assert normalized["write_file"]["output_dir"] == str(
        (base_dir / "output").resolve()
    )
    assert normalized["summary_file"]["output_file"] == str(
        (base_dir / "output" / "email_summaries.csv").resolve()
    )
    assert normalized["event_table"]["output_file"] == str(
        (base_dir / "output" / "events.xlsx").resolve()
    )


def test_normalize_plugin_output_paths_keeps_absolute_and_unrelated_values(
    tmp_path: Path,
) -> None:
    service = JobExecutionService()
    base_dir = tmp_path / "config-root"
    absolute = (tmp_path / "exports" / "events.xlsx").resolve()

    configs = {
        "event_table": {"output_file": str(absolute), "enabled": True},
        "add_category": {"response_format": "json"},
    }

    normalized = service._normalize_plugin_output_paths(configs, base_dir=base_dir)

    assert normalized["event_table"]["output_file"] == str(absolute)
    assert normalized["event_table"]["enabled"] is True
    assert normalized["add_category"]["response_format"] == "json"
