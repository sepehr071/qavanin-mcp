import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]

CIVIL = "12021850837713548188"


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_qv_search(client):
    data = await call(client, "qv_search", {"query": "مالیات بر ارزش افزوده", "kind": "law", "limit": 10})
    assert 0 < data["total"] < 5000 and len(data["items"]) >= 1
    assert all(i["id"].isdigit() and i["title"] for i in data["items"])


async def test_qv_search_filters_by_status_and_date(client):
    data = await call(client, "qv_search", {"status": "repealed", "approved_from": "1390/01/01", "limit": 25})
    assert 0 < data["total"] < 100000 and data["items"] and all(i.get("repealed") for i in data["items"])


async def test_qv_lookup(client):
    orgs = await call(client, "qv_lookup", {"kind": "approver", "query": "مجلس"})
    assert orgs["total"] >= 1 and orgs["items"][0]["id"]
    subjects = await call(client, "qv_lookup", {"kind": "subject", "query": "بانک"})
    assert subjects["items"] and subjects["items"][0]["code"]


async def test_qv_law_article(client):
    data = await call(client, "qv_law", {"ids": CIVIL, "article": "10"})
    assert data["title"] == "قانون مدنی" and data["sections"][0]["label"].startswith("ماده 10")
    assert "قراردادهای خصوصی" in data["sections"][0]["text"]


async def test_qv_law_info(client):
    data = await call(client, "qv_law_info", {"ids": CIVIL})
    assert data["type"] == "قانون" and data["approved"] == "1314/08/08"


async def test_qv_amendments_and_history(client):
    data = await call(client, "qv_amendments", {"ids": CIVIL, "limit": 5})
    assert data["amended_by_total"] > 10 and data["articles"]
    first = next(a for a in data["articles"] if a["changes"])
    hist = await call(client, "qv_article_history", {"section_id": first["section_id"]})
    assert hist["events"] and hist["events"][0]["date"]


async def test_qv_related(client):
    data = await call(client, "qv_related", {"ids": CIVIL, "limit": 5})
    assert data["others_total"] > 5 and len(data["others"]) == 5
