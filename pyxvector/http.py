from __future__ import annotations

from typing import Any

import httpx

from pyxvector.exceptions import XvectorApiError


class HttpClient:
    def __init__(self, uri: str, token: str, timeout: float = 60.0):
        self.uri = uri.rstrip("/")
        self.token = token
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        hdrs = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        resp = self._client.request(method, f"{self.uri}{path}", json=json or {}, headers=hdrs)
        if resp.status_code == 401:
            raise XvectorApiError(1800, resp.text)
        try:
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            raise XvectorApiError(2000, f"invalid json response: {resp.text}") from e
        if isinstance(data, dict) and data.get("code", 0) != 0:
            raise XvectorApiError(int(data.get("code", 2000)), str(data.get("message", "error")))
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data
