from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class APIClientError(RuntimeError):
    """Raised when an API request cannot be completed or decoded safely."""


class APIClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        token: str | None = None,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if backoff_factor < 0:
            raise ValueError("backoff_factor cannot be negative")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()
        self._owns_session = session is None
        self._sleep = sleep
        self.headers = {"Accept": "application/json", "User-Agent": "python-api-integration/1.0"}
        resolved_token = token if token is not None else os.getenv("API_TOKEN")
        if resolved_token:
            self.headers["Authorization"] = f"Bearer {resolved_token}"

    def __repr__(self) -> str:
        return (
            f"APIClient(base_url={self.base_url!r}, timeout={self.timeout!r}, "
            f"max_retries={self.max_retries!r}, token_configured="
            f"{'Authorization' in self.headers})"
        )

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _build_url(self, resource: str, params: dict[str, Any] | None) -> str:
        clean_resource = resource.strip("/")
        parsed = urlsplit(clean_resource)
        if not clean_resource or parsed.scheme or parsed.netloc or ".." in clean_resource.split("/"):
            raise ValueError("resource must be a non-empty relative API path")
        url = self.base_url + "/".join(quote(part, safe="") for part in clean_resource.split("/"))
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"
        return url

    def get(self, resource: str, params: dict[str, Any] | None = None) -> Any:
        """GET one resource, retrying only transient failures."""
        url = self._build_url(resource, params)
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, headers=self.headers, timeout=self.timeout)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries:
                        self._sleep(self._retry_delay(response, attempt))
                        continue
                    raise APIClientError(f"API request failed with HTTP {response.status_code}")
                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    status = response.status_code
                    raise APIClientError(f"API request failed with HTTP {status}") from exc
                try:
                    return response.json()
                except ValueError as exc:
                    raise APIClientError("API returned invalid JSON") from exc
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt >= self.max_retries:
                    raise APIClientError("API request failed after retry limit") from exc
                self._sleep(self.backoff_factor * (2 ** attempt))
        raise APIClientError("API request failed unexpectedly")

    def _retry_delay(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return self.backoff_factor * (2 ** attempt)

    def get_all(
        self,
        resource: str,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
        max_pages: int = 10,
        page_param: str = "_page",
        page_size_param: str = "_limit",
    ) -> list[Any]:
        """Collect a bounded set of pages from an API returning JSON arrays."""
        if page_size <= 0 or max_pages <= 0:
            raise ValueError("page_size and max_pages must be positive")
        results: list[Any] = []
        base_params = dict(params or {})
        for page in range(1, max_pages + 1):
            page_params = {**base_params, page_param: page, page_size_param: page_size}
            payload = self.get(resource, page_params)
            if not isinstance(payload, list):
                raise APIClientError("Paginated endpoint must return a JSON array")
            results.extend(payload)
            if len(payload) < page_size:
                break
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a REST API resource and save its JSON response.")
    parser.add_argument("--base-url", default="https://jsonplaceholder.typicode.com")
    parser.add_argument("--resource", default="posts")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("output/api_response.json"))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    with APIClient(args.base_url, timeout=args.timeout, max_retries=args.retries) as client:
        payload = client.get(args.resource, params={"_limit": args.limit})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved {len(payload) if isinstance(payload, list) else 1} item(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
