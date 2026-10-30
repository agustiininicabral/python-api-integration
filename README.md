# Python API Integration

![CI](https://github.com/agustiininicabral/python-api-integration/actions/workflows/ci.yml/badge.svg)

A reusable REST API client and API contract-testing example built with Python, Requests and pytest.

## Coverage

- REST methods: GET, POST, PUT, PATCH and DELETE.
- Bearer-token authentication through `API_TOKEN`; credentials are never printed in the client representation.
- Explicit connect/read timeout, bounded retries, Retry-After and exponential backoff for transient failures.
- HTTP status contract assertions (for example, POST must return 201).
- JSON decoding failures, non-retryable 4xx responses, connection errors and retry exhaustion.
- Bounded page-based pagination and CLI JSON export.
- A Postman collection for manual and exploratory CRUD/status checks.

## Install and run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=api_integration --cov-report=term-missing
python -m api_integration --base-url https://jsonplaceholder.typicode.com --resource posts --limit 10 --output output/posts.json
```

## Python example

```python
from api_integration.client import APIClient

with APIClient("https://jsonplaceholder.typicode.com", timeout=10, max_retries=2) as api:
    posts = api.get("posts", params={"_limit": 5})
    created = api.post("posts", {"title": "demo", "body": "contract test", "userId": 1},
                       expected_status={201})
    updated = api.patch(f"posts/{created['id']}", {"title": "updated"},
                        expected_status={200})
```

For protected services, set `API_TOKEN` in the environment. Never commit real tokens. The JSONPlaceholder demo API does not enforce authentication; the Postman bearer-token request is an example for a protected target and does not prove authorization enforcement on JSONPlaceholder.

## Postman

Import [API-Integration.postman_collection.json](postman/API-Integration.postman_collection.json). Set `baseUrl` to the target API and `apiToken` only when using a protected service. Requests include GET, missing-resource 404, POST 201, PUT 200, PATCH 200, DELETE and a bearer-auth example.

## Retry and error policy

Retries are limited to HTTP 429, 500, 502, 503, 504, timeouts and connection errors. Other HTTP errors fail immediately. Numeric Retry-After values are honored; otherwise exponential backoff is used. `expected_status` enables explicit endpoint contracts. A 204 response returns `None`.

## Test strategy

Tests use deterministic fake sessions; CI does not depend on third-party API uptime or secrets. The suite covers request construction, auth header handling, pagination, invalid URLs/resources, malformed JSON, HTTP errors, retry behavior and all REST methods. GitHub Actions runs Python 3.11–3.13.

## Limitations

Pagination is page-number based; cursor and Link-header APIs require an adapter. The public demo API is not an authentication test environment. The client currently exposes JSON request bodies and JSON responses rather than streaming or multipart uploads.

## License

MIT. See [LICENSE](LICENSE).
