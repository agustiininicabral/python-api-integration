import pytest

import requests
from api_integration.client import APIClient, APIClientError


class ErrorResponse:
    def __init__(self, status):
        self.status_code = status
        self.headers = {}
        self.content = b"{}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return {}


class ErrorSession:
    def __init__(self, status):
        self.response = ErrorResponse(status)
        self.calls = []

    def get(self, url, headers, timeout):
        self.calls.append(url)
        return self.response


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_surfaces_non_retryable_client_errors_without_retry(status):
    session = ErrorSession(status)
    client = APIClient("https://example.test", session=session, max_retries=3)
    with pytest.raises(APIClientError, match=f"HTTP {status}"):
        client.get("protected-resource")
    assert len(session.calls) == 1
