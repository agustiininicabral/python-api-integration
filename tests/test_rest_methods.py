import requests
import pytest

from api_integration.client import APIClient, APIClientError


class Response:
    def __init__(self, status=200, payload=None, content=b"json"):
        self.status_code, self.payload, self.content = status, payload, content
        self.headers = {}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))
    def json(self):
        return self.payload


class Session:
    def __init__(self, response):
        self.response, self.calls = response, []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


@pytest.mark.parametrize(("method","expected"), [("post",201),("put",200),("patch",200),("delete",204)])
def test_rest_methods_send_expected_method_and_validate_status(method, expected):
    response = Response(status=204, content=b"") if method == "delete" else Response(status=expected, payload={"ok": True})
    session = Session(response)
    client = APIClient("https://example.test", session=session)
    result = getattr(client, method)("resource", {"name":"demo"}, expected_status={expected}) if method != "delete" else client.delete("resource", expected_status={204})
    assert session.calls[0][0] == method.upper()
    assert result is None if method == "delete" else result == {"ok": True}


def test_unexpected_success_status_fails_contract():
    client = APIClient("https://example.test", session=Session(Response(status=200, payload={})))
    with pytest.raises(APIClientError, match="Unexpected HTTP status 200"):
        client.post("items", {"name":"x"}, expected_status={201})


def test_auth_header_is_not_exposed_in_repr():
    client = APIClient("https://example.test", token="private")
    assert client.headers["Authorization"] == "Bearer private"
    assert "private" not in repr(client)
    client.close()
