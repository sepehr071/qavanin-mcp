"""Shared async HTTP client for qavanin.ir.

Every tool goes through `get_page` (server-rendered ASP.NET MVC HTML) or `post_json`. `_send` caps concurrency,
solves the site's ArvanCloud JS cookie challenge, retries timeouts, dropped connections, 429 and 5xx (never 403)
with jittered backoff, and turns HTTP failures into `ToolError` messages the model can act on. The wire format is a
Chrome impersonation (curl_cffi).
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from httpx_curl_cffi import AsyncCurlTransport
from mcp.server.mcpserver.exceptions import ToolError

BASE = "https://qavanin.ir"

# User-Agent, sec-ch-ua and TLS come from the impersonated Chrome profile (see _get_client).
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}

MAX_CONCURRENCY = 2
JITTER = (0.15, 0.6)  # seconds before each upstream call
MAX_RETRIES = 2
MAX_RETRY_WAIT = 10  # cap for Retry-After and backoff, seconds
RETRY_DELAY = 0.5

_transport: httpx.AsyncBaseTransport | None = None
_client: httpx.AsyncClient | None = None
_limit: asyncio.Semaphore | None = None
_proxy_index = 0
_cache: dict[Any, tuple[float, Any]] = {}


class ApiError(ToolError):
    """A failed upstream call. `status` is the HTTP status, or None for network errors."""

    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Swap the transport (tests use httpx.MockTransport). Drops the current client."""
    global _transport, _client, _limit, _proxy_index
    _transport, _client, _limit, _proxy_index = transport, None, None, 0
    _cache.clear()


async def cached(key: Any, ttl: float, make: Callable[[], Awaitable[Any]]) -> Any:
    """Return make()'s result, reused for `ttl` seconds per key. Only for results nobody mutates."""
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    value = await make()
    if len(_cache) >= 32:  # parsed laws can be large: keep only the newest entries
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic(), value)
    return value


def _proxies() -> list[str]:
    """QAVANIN_MCP_PROXY: one proxy URL, or a comma-separated list used one at a time."""
    return [p.strip() for p in os.environ.get("QAVANIN_MCP_PROXY", "").split(",") if p.strip()]


def _get_client() -> tuple[httpx.AsyncClient, asyncio.Semaphore]:
    global _client, _limit
    if _client is None:
        # Direct connections work; a system proxy is only used when the user opts in with QAVANIN_MCP_PROXY.
        proxies = _proxies()
        _client = httpx.AsyncClient(
            transport=_transport
            or AsyncCurlTransport(
                impersonate="chrome",
                default_headers=True,
                proxy=proxies[_proxy_index % len(proxies)] if proxies else None,
                max_connections=2 * MAX_CONCURRENCY,
            ),
            headers=HEADERS,
            timeout=60,  # the origin is slow: 1-18 s typical, the civil code about 14 s, rare 40 s hangs
            limits=httpx.Limits(max_connections=2 * MAX_CONCURRENCY),
            follow_redirects=True,
            trust_env=False,
        )
        _limit = asyncio.Semaphore(MAX_CONCURRENCY)
    assert _limit is not None
    return _client, _limit


# --- ArvanCloud JS challenge -------------------------------------------------------------------------------
# A first visit (or an expired cookie, Max-Age 100 s) gets a 200 page whose script computes two cookies from two
# JSFuck constants (the page's E(E(x)) is the identity) and reloads. The constants are built only from the atoms
# below, so they are evaluated here instead of running the page's JavaScript.
_CHALLENGE = re.compile(r"'value_v1': eval\(\"(.*?)\"\), 'value': eval\(\"(.*?)\"\)", re.S)
_NUM = r"(?:\+!\+\[\]|\+\[\]|!\+\[\](?:\+!\+\[\])*)"  # 1, 0, or n x "!+[]" (n)
_WORDS = {"(![]+[])": "false", "(!![]+[])": "true", "([][[]]+[])": "undefined"}


def _num(expr: str) -> int:
    return 0 if expr == "+[]" else expr.count("!+[]")


def _fuck(expr: str) -> str:
    """Evaluate a JSFuck string built from digits, false/true/undefined letters, fill/entries and fromCharCode."""
    expr = re.sub(
        rf"(\(!?!?\[\]\+\[\]\)|\(\[\]\[\[\]\]\+\[\]\))\[({_NUM})\]",
        lambda m: repr(_WORDS[m[1]][_num(m[2])]),
        expr,
    )
    expr = expr.replace("([]['fill']+'')[3]", "'c'").replace("([]['entries']()+'')[2]", "'b'")
    expr = re.sub(r"\(\[\]\+\[\]\)\['constructor'\]\['fromCharCode'\]\((\d+)\)", lambda m: repr(chr(int(m[1]))), expr)
    expr = re.sub(rf"\[({_NUM})\]", lambda m: repr(str(_num(m[1]))), expr)
    if left := re.sub(r"'[^']*'|\[\]|\+", "", expr):
        raise ValueError(left[:60])
    return "".join(re.findall(r"'([^']*)'", expr))


def solve_challenge(html: str) -> dict[str, str] | None:
    """The cookies a challenge page sets, or None when `html` is not (or not a solvable) challenge page."""
    m = _CHALLENGE.search(html) if "__arcsjs" in html else None
    if not m:
        return None
    try:
        return {"__arcsjs": _fuck(m[1]), "__arcsjsc": _fuck(m[2])}
    except ValueError:
        return None


async def get_page(path: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
    """GET a site page; returns (final URL after redirects, HTML)."""
    r = await _send("GET", f"{BASE}{path}", params=params)
    return str(r.url), r.content.decode("utf-8", "replace")


async def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET a JSON lookup endpoint (/Law/getOrgs/, /Law/getTopics/)."""
    r = await _send("GET", f"{BASE}{path}", params=params, headers={"Accept": "application/json, text/plain, */*"})
    try:
        return r.json()
    except ValueError as e:
        raise ApiError(f"qavanin.ir returned a non-JSON response for {path} (HTTP {r.status_code}).") from e


async def _send(method: str, url: str, **kwargs: Any) -> httpx.Response:
    host = httpx.URL(BASE).host
    retries = solved = 0
    while True:
        client, limit = _get_client()
        wait = None
        try:
            async with limit:
                await asyncio.sleep(random.uniform(*JITTER))
                r = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as e:
            err = ApiError(f"{host} did not answer in time. Try again in a moment.")
            err.__cause__ = e
        except httpx.TransportError as e:
            err = ApiError(
                f"Could not reach {host} ({type(e).__name__}). Check the internet connection, or set QAVANIN_MCP_PROXY."
            )
            err.__cause__ = e
        else:
            if r.status_code == 429 or r.status_code >= 500:
                err = ApiError(_status_message(r), r.status_code)
                wait = _retry_after(r)
            else:
                cookies = solve_challenge(r.text) if r.status_code == 200 and len(r.content) < 20_000 else None
                if cookies and solved < 2:
                    solved += 1
                    for name, value in cookies.items():
                        client.cookies.set(name, value, domain=host, path="/")
                    continue
                if cookies:
                    raise ApiError(f"{host} kept answering with its bot challenge. Try again in a moment.", 403)
                if r.status_code >= 400:
                    raise ApiError(_status_message(r), r.status_code)
                return r
        if retries == MAX_RETRIES:
            raise err
        wait = wait if wait is not None else RETRY_DELAY * 2**retries * random.uniform(1, 1.5)
        retries += 1
        await asyncio.sleep(min(wait, MAX_RETRY_WAIT))


def _retry_after(r: httpx.Response) -> float | None:
    """Seconds from a numeric Retry-After on a 429/503, else None (HTTP-date form is ignored)."""
    v = r.headers.get("retry-after", "")
    return float(v) if r.status_code in (429, 503) and v.replace(".", "", 1).isdigit() else None


def _status_message(r: httpx.Response) -> str:
    code = r.status_code
    if code == 403:
        return "qavanin.ir blocked the request (HTTP 403). Turn off VPN/proxy or set QAVANIN_MCP_PROXY."
    if code == 404:
        return "Not found on qavanin.ir (HTTP 404). Check the law id."
    if code == 429:
        return "qavanin.ir is rate limiting requests (HTTP 429). Wait a minute before retrying."
    if code >= 500:
        return f"qavanin.ir had a server error (HTTP {code}). Try again later."
    return f"qavanin.ir rejected the request (HTTP {code})."
