"""인증 헤더를 빠뜨리지 않도록 하는 Desktop HTTP 공통 Client."""

import httpx as _httpx

from app_context import app_context

HTTPStatusError = _httpx.HTTPStatusError


def _kwargs(kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    if app_context.access_token:
        headers["Authorization"] = f"Bearer {app_context.access_token}"
    kwargs["headers"] = headers
    return kwargs


def get(url, **kwargs):
    return _httpx.get(url, **_kwargs(kwargs))


def post(url, **kwargs):
    return _httpx.post(url, **_kwargs(kwargs))


def put(url, **kwargs):
    return _httpx.put(url, **_kwargs(kwargs))


def patch(url, **kwargs):
    return _httpx.patch(url, **_kwargs(kwargs))


def delete(url, **kwargs):
    return _httpx.delete(url, **_kwargs(kwargs))
