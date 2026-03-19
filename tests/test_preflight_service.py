from outlook_mail_extractor.core import FolderNotFoundError
from outlook_mail_extractor.services.preflight import PreflightCheckService


class _FakeOutlookClient:
    def __init__(self) -> None:
        self.connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self._accounts = ["acc-a", "acc-b"]
        self._folders = {
            ("acc-a", "Inbox"),
            ("acc-b", "Inbox"),
        }

    def connect(self) -> None:
        self.connect_calls += 1
        self.connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    def list_accounts(self) -> list[str]:
        return self._accounts

    def get_folder(
        self,
        account: str,
        folder_path: str,
        create_if_missing: bool = False,
    ) -> str:
        del create_if_missing
        if (account, folder_path) in self._folders:
            return folder_path
        raise FolderNotFoundError(f"Path not found: {folder_path}")


def test_preflight_reports_account_and_source_issues() -> None:
    fake_client = _FakeOutlookClient()
    service = PreflightCheckService(client_factory=lambda: fake_client)

    result = service.run(
        {
            "jobs": [
                {
                    "name": "J1",
                    "enable": True,
                    "account": "missing-account",
                    "source": "Inbox",
                },
                {
                    "name": "J2",
                    "enable": True,
                    "account": "acc-a",
                    "source": "MissingFolder",
                },
            ]
        }
    )

    assert result.account_count == 2
    assert result.is_ok is False
    assert result.issues == [
        "J1: Account not found: missing-account",
        "J2: Path not found: MissingFolder",
    ]


def test_preflight_ignores_disabled_jobs() -> None:
    fake_client = _FakeOutlookClient()
    service = PreflightCheckService(client_factory=lambda: fake_client)

    result = service.run(
        {
            "jobs": [
                {
                    "name": "Disabled",
                    "enable": False,
                    "account": "missing-account",
                    "source": "MissingFolder",
                }
            ]
        }
    )

    assert result.account_count == 2
    assert result.is_ok is True
    assert result.issues == []


def test_preflight_connects_and_disconnects_even_without_enabled_jobs() -> None:
    fake_client = _FakeOutlookClient()
    service = PreflightCheckService(client_factory=lambda: fake_client)

    result = service.run({"jobs": []})

    assert result.account_count == 2
    assert result.issues == []
    assert fake_client.connect_calls == 1
    assert fake_client.disconnect_calls == 1
