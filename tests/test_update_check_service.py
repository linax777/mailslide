import httpx

from outlook_mail_extractor.services.update_check import UpdateCheckService


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("GET", "https://pypi.org/pypi/mailslide/json"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> object:
        return self._payload


def test_update_check_detects_newer_version(monkeypatch) -> None:
    def _fake_get(url: str, timeout: float) -> _FakeResponse:
        del timeout
        assert url == "https://pypi.org/pypi/mailslide/json"
        return _FakeResponse({"info": {"version": "0.3.7"}})

    monkeypatch.setattr(httpx, "get", _fake_get)

    result = UpdateCheckService(current_version="0.3.6").check()

    assert result.error is None
    assert result.latest_version == "0.3.7"
    assert result.has_update is True


def test_update_check_reports_up_to_date(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, timeout: _FakeResponse({"info": {"version": "0.3.6"}}),
    )

    result = UpdateCheckService(current_version="0.3.6").check()

    assert result.error is None
    assert result.latest_version == "0.3.6"
    assert result.has_update is False


def test_update_check_handles_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, timeout: _FakeResponse(
            {"info": {"version": "0.3.7"}}, status_code=500
        ),
    )

    result = UpdateCheckService(current_version="0.3.6").check()

    assert result.has_update is False
    assert result.latest_version is None
    assert result.error


def test_update_check_handles_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda url, timeout: _FakeResponse({"foo": "bar"})
    )

    result = UpdateCheckService(current_version="0.3.6").check()

    assert result.has_update is False
    assert result.latest_version is None
    assert result.error == "Invalid PyPI response: missing info.version"
