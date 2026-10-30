import pytest

from api_integration.client import APIClient, APIClientError
from test_client import FakeResponse, FakeSession


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_surfaces_non_retryable_client_errors_without_retry(status):
    session = FakeSession([FakeResponse(status=status)])
    client = APIClient("https://example.test", session=session, max_retries=3)
    with pytest.raises(APIClientError, match=f"HTTP {status}"):
        client.get("protected-resource")
    assert len(session.calls) == 1
