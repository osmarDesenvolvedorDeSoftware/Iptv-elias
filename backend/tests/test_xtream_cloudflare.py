import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.xtream_client import XtreamClient


class FakeResponse:
    def __init__(self, *, text: str, json_data: dict | None = None, raises_json: bool = False) -> None:
        self.text = text
        self._json_data = json_data or {}
        self._raises_json = raises_json
        self.status_code = 200

    def json(self) -> dict:
        if self._raises_json:
            raise ValueError("invalid json")
        return self._json_data


def test_xtream_html_triggers_cloudflare_log_and_https(monkeypatch, caplog) -> None:
    fake_session = SimpleNamespace(headers={})
    monkeypatch.setattr(
        "app.services.xtream_client.cloudscraper.create_scraper",
        lambda: fake_session,
    )
    monkeypatch.setattr("app.services.xtream_client.time.sleep", lambda *_args, **_kwargs: None)

    client = XtreamClient(base_url="http://example.com", username="user", password="pass")

    html_response = FakeResponse(text="<html>blocked</html>", raises_json=True)
    success_response = FakeResponse(text="{}", json_data={"ok": True})

    requested_urls: list[str] = []

    def fake_request(url: str, *, params: dict, headers: dict) -> FakeResponse:
        requested_urls.append(url)
        if url.startswith("http://"):
            return html_response
        return success_response

    monkeypatch.setattr(client, "_perform_request", fake_request)

    caplog.set_level(logging.WARNING)

    result = client._call("get_vod_streams")

    assert requested_urls[0].startswith("http://")
    assert any(url.startswith("https://") for url in requested_urls)
    assert any("Xtream bloqueado pelo Cloudflare" in message for message in caplog.messages)
    assert result == {"ok": True}
    assert client.base_url.startswith("https://")
