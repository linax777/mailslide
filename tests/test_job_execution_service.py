import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

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


class _FakeLoggerManager:
    def set_ui_sink(self, callback):
        del callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        return Path("dummy.log")

    def get_current_log_path(self) -> Path | None:
        return Path("dummy.log")

    def get_display_level(self) -> str:
        return "INFO"

    def set_display_level(self, level: str) -> None:
        del level


class _FakeClient:
    def __init__(self) -> None:
        self._connected = False
        self.disconnect_calls = 0

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


class _FakeProcessor:
    def __init__(self, _client) -> None:
        self.processed_jobs: list[str] = []

    async def process_job(self, job_config: dict, **_kwargs) -> list[dict]:
        self.processed_jobs.append(str(job_config.get("name", "Unnamed Job")))
        return []


def test_process_config_file_cancelled_before_first_job() -> None:
    clients: list[_FakeClient] = []
    processors: list[_FakeProcessor] = []

    def client_factory() -> _FakeClient:
        client = _FakeClient()
        clients.append(client)
        return client

    def processor_factory(client, **_kwargs) -> _FakeProcessor:
        processor = _FakeProcessor(client)
        processors.append(processor)
        return processor

    service = JobExecutionService(
        client_factory=cast(Any, client_factory),
        processor_factory=cast(Any, processor_factory),
        config_loader=lambda _path: {
            "jobs": [{"name": "job-1", "account": "acc", "source": "Inbox"}]
        },
        llm_config_loader=lambda _path: SimpleNamespace(api_base="", model=""),
        plugin_config_loader=lambda _path: {},
        logger_manager=_FakeLoggerManager(),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            service.process_config_file(
                config_file="dummy.yaml",
                cancel_requested=lambda: True,
            )
        )

    assert len(clients) == 1
    assert clients[0].disconnect_calls == 1
    assert len(processors) == 1
    assert processors[0].processed_jobs == []


def test_process_config_file_cancelled_before_second_job() -> None:
    processors: list[_FakeProcessor] = []

    def processor_factory(client, **_kwargs) -> _FakeProcessor:
        processor = _FakeProcessor(client)
        processors.append(processor)
        return processor

    call_count = {"count": 0}

    def cancel_requested() -> bool:
        call_count["count"] += 1
        return call_count["count"] >= 2

    service = JobExecutionService(
        client_factory=cast(Any, _FakeClient),
        processor_factory=cast(Any, processor_factory),
        config_loader=lambda _path: {
            "jobs": [
                {"name": "job-1", "account": "acc", "source": "Inbox"},
                {"name": "job-2", "account": "acc", "source": "Inbox"},
            ]
        },
        llm_config_loader=lambda _path: SimpleNamespace(api_base="", model=""),
        plugin_config_loader=lambda _path: {},
        logger_manager=_FakeLoggerManager(),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            service.process_config_file(
                config_file="dummy.yaml",
                cancel_requested=cancel_requested,
            )
        )

    assert len(processors) == 1
    assert processors[0].processed_jobs == ["job-1"]
