# Python API Integration

A reusable REST API client built with Python and Requests. It centralizes URL handling, bearer-token authentication, timeouts, retries, pagination, JSON validation and safe error reporting.

## Features

- Configurable HTTP(S) base URL and resource paths.
- Optional bearer-token authentication via an environment variable.
- Explicit request timeout and bounded retries for transient network failures, HTTP 429 and selected 5xx responses.
- Retry-After support and exponential backoff.
- JSON response validation and actionable errors without exposing credentials.
- Generic page-based list pagination.
- CLI that writes API responses to a JSON file.
- Fully mocked tests; CI does not depend on a third-party API being online.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m api_integration --base-url https://jsonplaceholder.typicode.com --resource posts --limit 10 --output output/posts.json
pytest
```

Set `API_TOKEN` in the environment when the target API requires bearer authentication. The token is never written to output or logs.

## Python usage

```python
from api_integration.client import APIClient

with APIClient("https://jsonplaceholder.typicode.com", timeout=10, max_retries=2) as client:
    posts = client.get("posts", params={"_limit": 10})
    all_posts = client.get_all("posts", page_size=50, max_pages=10)
```

## Retry policy

Retries are bounded by `max_retries` (additional attempts after the first request). HTTP 429, 500, 502, 503 and 504 plus connection/time-out errors are retryable. Other HTTP errors fail immediately. Delay uses Retry-After when it is a numeric number of seconds; otherwise exponential backoff is applied.

## Limitations

Pagination uses configurable page and page-size query parameter names; APIs with cursor or Link-header pagination need an adapter. The default CLI endpoint is a public demo API and should be replaced for real integrations. Credentials are read from environment variables, not committed to source.

## License

MIT. See [LICENSE](LICENSE).
