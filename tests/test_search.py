import httpx
import pytest
from conftest import fixture

from qavanin_mcp import search

pytestmark = pytest.mark.anyio


def test_parse_results_rows_and_repealed_marker():
    out = search.parse_results(fixture("search_results.html"))
    assert out["total"] == 1545 and out["pages"] == 62 and out["description"] == "واژه(های)مالیات در عنوان"
    first = out["items"][0]
    assert first["id"] == "14319859727897296242" and first["approved"] == "1405/07/11"
    assert first["approver"] == "سازمان امور مالیاتی" and "span" not in first["title"] and "repealed" not in first
    red = '<table><tr   class="red"  ><td>9</td><td><a href="/Law/TreeText/?IDS=5">x</a></td><td></td><td>y</td></tr>'
    row = search.parse_results("تعداد یافته ها</b> : 1" + red)["items"][0]
    assert row == {"id": "5", "title": "x", "approved": None, "approver": "y", "repealed": True}


async def test_qv_search_params_and_output(client, api):
    api["/"] = fixture("search_results.html")
    out = (
        await client.call_tool(
            "qv_search",
            {
                "query": "ماليات",
                "kind": "regulation",
                "approver_id": [130, 14],
                "status": "repealed",
                "approved_from": "۱۴۰۰/۰۱/۰۱",
                "limit": 3,
            },
        )
    ).structured_content
    assert out["total"] == 1545 and out["pages"] == 62 and len(out["items"]) == 3
    assert out["items"][0]["url"].endswith("/Law/TreeText/?IDS=14319859727897296242")
    assert out["filters"] == "واژه(های)مالیات در عنوان"
    call = api.calls[-1].url
    assert call.params.get_list("Approvers") == ["130", "14"]
    assert call.params["CAPTION"] == "مالیات" and call.params["_isRegulation"] == "true"
    assert call.params["LawStatus"] == "7" and call.params["fromApproveDate"] == "1400/01/01"
    assert (
        call.params["size"] == "25" and call.params["IsTitleSearch"] == "true" and call.params["SeachTextType"] == "1"
    )


async def test_qv_search_text_scope_and_page_size(client, api):
    api["/"] = fixture("search_results.html")
    await client.call_tool("qv_search", {"query": "خسارت", "in_text": True, "limit": 60, "page": 3, "sort": "title"})
    p = api.params()
    assert p["IsTextSearch"] == "true" and "IsTitleSearch" not in p
    assert (p["size"], p["PageNumber"], p["SortColumn"], p["SortDesc"]) == ("100", "3", "CAPTION", "False")


async def test_qv_search_without_filters_is_not_retried(client, api):
    api["/"] = fixture("search_results.html")
    await client.call_tool("qv_search", {})
    assert len(api.calls) == 1


async def test_qv_search_retries_when_site_ignores_filters(client, api, monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(search.asyncio, "sleep", no_sleep)
    ignored = fixture("search_results.html").replace("واژه(های)ماليات در عنوان", "")
    answers = [ignored, ignored, fixture("search_results.html")]
    api["/"] = lambda r: httpx.Response(200, text=answers.pop(0))
    out = (await client.call_tool("qv_search", {"query": "مالیات"})).structured_content
    assert out["filters"] and len(api.calls) == 3


async def test_qv_search_gives_up_when_filters_stay_ignored(client, api, monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(search.asyncio, "sleep", no_sleep)
    api["/"] = fixture("search_results.html").replace("واژه(های)ماليات در عنوان", "")
    result = await client.call_tool("qv_search", {"query": "مالیات"})
    assert result.is_error and "ignoring the search filters" in result.content[0].text


async def test_qv_search_empty_and_bad_input(client, api):
    api["/"] = fixture("search_empty.html")
    out = (await client.call_tool("qv_search", {"query": "zzzqqxx"})).structured_content
    assert out["total"] == 0 and out["items"] == []
    for args in ({"approved_from": "1405-7-1x"}, {"command_no": "12/5"}):
        result = await client.call_tool("qv_search", args)
        assert result.is_error, args


async def test_qv_lookup_orgs(client, api):
    api["/Law/getOrgs/"] = {
        "items": [{"id": 130, "text": "هيات وزيران(86030)", "count": 86030}],
        "page": 1,
        "size": 20,
        "pagecount": 25,
        "total_count": 482,
    }
    out = (await client.call_tool("qv_lookup", {"kind": "approver", "query": "هيات"})).structured_content
    assert out == {
        "total": 482,
        "page": 1,
        "pages": 25,
        "items": [{"id": 130, "name": "هیات وزیران", "count": 86030}],
    }
    assert api.params() == {"term": "هیات", "page": "1", "isApprover": "true"}


async def test_qv_lookup_subjects_and_static_lists(client, api):
    api["/Law/getTopics/"] = {
        "items": [{"id": 51, "text": " 409. بانکی و پولی(10046)", "code": "409     "}],
        "page": 1,
        "pagecount": 1,
        "total_count": 1,
    }
    out = (await client.call_tool("qv_lookup", {"kind": "subject", "query": "بانک"})).structured_content
    assert out["items"] == [{"id": 51, "code": "409", "name": "بانکی و پولی", "count": 10046}]
    statuses = (await client.call_tool("qv_lookup", {"kind": "status"})).structured_content
    assert {"id": 7, "name": "repealed (منسوخه)"} in statuses["items"]
    lists = (await client.call_tool("qv_lookup", {"kind": "list", "query": "آخرین"})).structured_content
    assert [i["id"] for i in lists["items"]] == [113, 114]
    assert len(api.calls) == 1  # static kinds make no request
