"""Budgeted safe HTTP client; every real request is counted and redirects revalidated."""
from __future__ import annotations

from typing import Any

import httpx

from raven_validator.security.network_policy import NetworkPolicy
from raven_validator.security.request_policy import RequestPolicy


class BudgetedSafeClient:
    def __init__(self, client: httpx.AsyncClient, request_policy: RequestPolicy, network_policy: NetworkPolicy, max_redirects: int = 5) -> None:
        self.client = client
        self.request_policy = request_policy
        self.network_policy = network_policy
        self.max_redirects = max_redirects

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        current = self.network_policy.validate_url(url)
        for _ in range(self.max_redirects + 1):
            self.request_policy.consume_request()
            response = await self.client.request(method, current, follow_redirects=False, **kwargs)
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            current = self.network_policy.redirected_url(current, location)
            if response.status_code == 303:
                method = "GET"
                kwargs.pop("json", None)
                kwargs.pop("content", None)
        raise httpx.TooManyRedirects("redirect limit exceeded")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("OPTIONS", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)
