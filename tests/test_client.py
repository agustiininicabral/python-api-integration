import json
import sys

import pytest
import requests

from api_integration.client import APIClient, APIClientError, main


class FakeResponse:
    def __init__(self, payload=None, status=200, headers=None, json_error=None):
        self.payload = payload
        self.status_code = status
        self.headers = headers or {}
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def get(self, url, headers, timeout):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


def test_get_returns_json_and_builds_request():
    session = FakeSession([FakeResponse([{"id": 1}])])
    with APIClient("https://example.test/api", session=session, timeout=3) as client:
        result = client.get("posts", {"tag": ["a", "b"]})
    assert result == [{"id": 1}]
    assert session.calls[0]["url"] == "https://example.test/api/posts?tag=a&tag=b"
    assert session.calls[0]["timeout"] == 3
    assert session.closed is False


def test_bearer_token_is_added_from_environment(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret-token")
    session = FakeSession([FakeResponse({})])
    client = APIClient("https://example.test", session=session)
    client.get("profile")
    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in repr(client.__dict__)


def test_retries_transient_http_error_then_succeeds():
    session = FakeSession([
        FakeResponse(status=503),
        FakeResponse([{"ok": True}]),
    ])
    delays = []
    client = APIClient("https://example.test", session=session, sleep=delays.append)
    assert client.get("items") == [{"ok": True}]
    assert len(session.calls) == 2
    assert delays == [0.5]


def test_retry_after_header_is_respected():
    session = FakeSession([FakeResponse(status=429, headers={"Retry-After": "3"}), FakeResponse([])])
    delays = []
    client = APIClient("https://example.test", session=session, sleep=delays.append)
    assert client.get("items") == []
    assert delays == [3.0]


def test_connection_error_is_retried_and_then_wrapped():
    session = FakeSession([requests.Timeout(), requests.Timeout()])
    delays = []
    client = APIClient("https://example.test", session=session, max_retries=1, sleep=delays.append)
    with pytest.raises(APIClientError, match="retry limit"):
        client.get("items")
    assert delays == [0.5]


def test_non_retryable_http_error_fails_immediately():
    session = FakeSession([FakeResponse(status=404)])
    client = APIClient("https://example.test", session=session)
    with pytest.raises(APIClientError, match="HTTP 404"):
        client.get("missing")
    assert len(session.calls) == 1


def test_invalid_json_is_reported():
    session = FakeSession([FakeResponse(json_error=ValueError("bad json"))])
    client = APIClient("https://example.test", session=session)
    with pytest.raises(APIClientError, match="invalid JSON"):
        client.get("items")


def test_pagination_stops_on_short_page():
    session = FakeSession([
        FakeResponse([{"id": 1}, {"id": 2}]),
        FakeResponse([{"id": 3}]),
    ])
    client = APIClient("https://example.test", session=session)
    result = client.get_all("posts", page_size=2, max_pages=5)
    assert [row["id"] for row in result] == [1, 2, 3]
    assert len(session.calls) == 2


def test_pagination_rejects_non_array_and_invalid_limits():
    client = APIClient("https://example.test", session=FakeSession([FakeResponse({"id": 1})]))
    with pytest.raises(APIClientError, match="JSON array"):
        client.get_all("posts", page_size=2)
    with pytest.raises(ValueError, match="positive"):
        client.get_all("posts", page_size=0)


@pytest.mark.parametrize("base_url", ["example.test", "ftp://example.test", "https:///missing-host"])
def test_invalid_base_url_is_rejected(base_url):
    with pytest.raises(ValueError, match="absolute HTTP"):
        APIClient(base_url)


def test_invalid_resource_path_is_rejected():
    client = APIClient("https://example.test", session=FakeSession([]))
    with pytest.raises(ValueError, match="relative API path"):
        client.get("../admin")


def test_cli_saves_mocked_response(tmp_path, monkeypatch):
    session = FakeSession([FakeResponse([{"id": 1}])])
    monkeypatch.setattr("api_integration.client.APIClient", lambda *args, **kwargs: _ClientContext(session))
    output = tmp_path / "response.json"
    monkeypatch.setattr(sys, "argv", ["api-integration", "--output", str(output), "--limit", "1"])
    assert main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == [{"id": 1}]


class _ClientContext:
    def __init__(self, session):
        self.client = APIClient("https://example.test", session=session)

    def __enter__(self):
        return self.client

    def __exit__(self, *args):
        self.client.close()
