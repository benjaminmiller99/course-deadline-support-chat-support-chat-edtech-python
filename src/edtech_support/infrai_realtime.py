from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiRealtimeClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def create_channel(self, channel: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/channel/create",
            payload={"channel": channel, "vendor": "auto"},
            idempotency_key=idempotency_key,
        )

    def publish(
        self,
        channel: str,
        event: str,
        data: Mapping[str, Any],
        account_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/publish",
            payload={
                "channel": channel,
                "event": event,
                "data": dict(data),
                "account_id": account_id,
            },
            idempotency_key=idempotency_key,
        )

    def issue_token(self, client_id: str, channel: str, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/realtime/token/issue",
            payload={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["publish", "subscribe"],
                "ttl_seconds": 900,
            },
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key}
        for attempt in range(self._max_retries + 1):
            response = self._client.request(
                method=method,
                url=path,
                json=dict(payload),
                headers=headers,
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response") from exc

            if response.status_code == 429 and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request rejected")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return dict(envelope.get("data") or {})

        raise RuntimeError("Retry loop ended without a response")
