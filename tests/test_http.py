import re
from pathlib import Path

import httpx
import pytest
from conftest import fixture

from qavanin_mcp import http

pytestmark = pytest.mark.anyio

SOLVED = "__arcsjs=65a2702e3f055851fe9b944c98dd63f7; __arcsjsc=arcookie-1792328457-18de153d487228eee46f8e0e591b968f"


def test_challenge_is_solved_without_javascript():
    assert http.solve_challenge(fixture("arvan_challenge.html")) == {
        "__arcsjs": "65a2702e3f055851fe9b944c98dd63f7",
        "__arcsjsc": "arcookie-1792328457-18de153d487228eee46f8e0e591b968f",
    }
    assert http.solve_challenge("<html>تعداد یافته ها</html>") is None


async def test_all_tools_are_read_only(client):
    tools = (await client.list_tools()).tools
    assert len(tools) == 7
    for t in tools:
        assert t.name.startswith("qv_"), t.name
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False, t.name
        assert t.description and t.title, t.name


async def test_readme_tool_table_matches_tools(client):
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `(qv_\w+)` \|", readme, re.M))
    assert listed == {t.name for t in (await client.list_tools()).tools}


async def test_challenge_page_is_solved_and_cookie_kept(client, api):
    def guarded(request):
        if request.headers.get("cookie", "") != SOLVED:
            return httpx.Response(200, text=fixture("arvan_challenge.html"))
        return httpx.Response(200, text=fixture("search_results.html"))

    api["/"] = guarded
    result = await client.call_tool("qv_search", {})
    assert not result.is_error and len(api.calls) == 2
    await client.call_tool("qv_search", {})
    assert len(api.calls) == 3  # the cookie is kept for later requests


async def test_challenge_that_never_clears(client, api):
    api["/"] = lambda r: httpx.Response(200, text=fixture("arvan_challenge.html"))
    result = await client.call_tool("qv_search", {})
    assert result.is_error and "bot challenge" in result.content[0].text and len(api.calls) == 3


async def test_dropped_connection_is_retried(client, api):
    attempts = []

    def flaky(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.", request=request)
        return httpx.Response(200, text=fixture("search_results.html"))

    api["/"] = flaky
    assert not (await client.call_tool("qv_search", {})).is_error and len(attempts) == 2


async def test_http_errors_become_tool_errors(client, api):
    api["/Law/TreeText/"] = lambda r: httpx.Response(500, text="Runtime Error")
    result = await client.call_tool("qv_law", {"ids": "1"})
    assert result.is_error and "server error (HTTP 500)" in result.content[0].text and len(api.calls) == 3
    api["/Law/TreeText/"] = lambda r: httpx.Response(404, text="")
    result = await client.call_tool("qv_law", {"ids": "2"})
    assert result.is_error and "Not found" in result.content[0].text
