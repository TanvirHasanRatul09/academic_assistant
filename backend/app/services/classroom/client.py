import random
import time
from collections.abc import Iterator
from typing import Any

import httpx


class ClassroomError(Exception):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class ClassroomClient:
    base_url = "https://classroom.googleapis.com/v1"

    def __init__(
        self,
        access_token: str,
        client: httpx.Client | None = None,
        *,
        deadline: float | None = None,
    ) -> None:
        self.request_count = 0
        self.request_seconds = 0.0
        self.page_count = 0
        self.deadline = deadline
        self._client = client or httpx.Client(
            headers={"Authorization": f"Bearer {access_token}"}, timeout=5
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(3):
            remaining = self.deadline - time.perf_counter() if self.deadline else None
            if remaining is not None and remaining <= 0:
                raise ClassroomError("quick_sync_deadline", retryable=True)
            started = time.perf_counter()
            try:
                response = self._client.get(
                    f"{self.base_url}{path}",
                    params=params,
                    timeout=min(5.0, max(0.1, remaining)) if remaining is not None else 5.0,
                )
                self.request_count += 1
                self.request_seconds += time.perf_counter() - started
            except httpx.TimeoutException as exc:
                self.request_count += 1
                self.request_seconds += time.perf_counter() - started
                if attempt == 2:
                    raise ClassroomError("provider_timeout", retryable=True) from exc
                time.sleep((0.2 * (2**attempt)) + random.uniform(0, 0.15))
                continue
            if response.status_code == 401:
                raise ClassroomError("authorization_revoked")
            if response.status_code in {403, 404}:
                raise ClassroomError("resource_unavailable")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise ClassroomError("provider_unavailable", retryable=True)
                time.sleep((0.2 * (2**attempt)) + random.uniform(0, 0.15))
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ClassroomError("provider_request_failed") from exc
            payload = response.json()
            if not isinstance(payload, dict):
                raise ClassroomError("invalid_provider_response")
            return payload
        raise ClassroomError("provider_unavailable", retryable=True)

    def pages(
        self,
        path: str,
        collection: str,
        params: dict[str, Any] | None = None,
        *,
        max_pages: int = 100,
    ) -> Iterator[list[dict[str, Any]]]:
        query = dict(params or {})
        query.setdefault("pageSize", 100)
        for _ in range(max_pages):
            payload = self.get(path, query)
            values = payload.get(collection, [])
            if not isinstance(values, list):
                raise ClassroomError("invalid_provider_response")
            self.page_count += 1
            yield [value for value in values if isinstance(value, dict)]
            token = payload.get("nextPageToken")
            if not token:
                return
            query["pageToken"] = token
        if max_pages >= 100:
            raise ClassroomError("provider_pagination_limit")
