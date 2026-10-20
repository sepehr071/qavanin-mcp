import pytest
from conftest import fixture

from qavanin_mcp import law

pytestmark = pytest.mark.anyio


def test_parse_sections_civil_excerpt():
    nodes = law.parse_sections(fixture("law_treetext_civil_excerpt.html"))
    assert len(nodes) == 6  # the title block is not a section
    art1 = next(n for n in nodes if n["id"] == "1030597")
    assert art1["label"] == "ماده 1 (اصلاحی 14ˏ08ˏ1370)" and art1["status"] == "amended" and art1["history"]
    assert art1["text"].startswith("مصوبات مجلس شورای اسلامی") and "arm.gif" not in art1["text"]
    assert [o["id"] for o in art1["opinions"]][0] == "4153979073585179551"
    assert "ي" not in art1["text"] and "ك" not in art1["text"]  # Arabic letters become Persian
    assert "status" not in nodes[-1] and nodes[-1]["label"] == "ماده 4"


def test_parse_sections_court_vote_keeps_nested_paragraphs():
    (node,) = law.parse_sections(fixture("law_treetext_vote.html"))
    assert node["text"].startswith("شماره 0302757") and "ابطال شد" in node["text"] and len(node["text"]) > 1000


async def test_qv_law_article_with_notes(client, api):
    api["/Law/TreeText/"] = fixture("law_treetext_civil_excerpt.html")
    out = (await client.call_tool("qv_law", {"ids": "12021850837713548188", "article": "ماده 1"})).structured_content
    assert out["title"] == "قانون مدنی" and out["approved"] == "1314/08/08" and out["approver"] == "مجلس شورای ملی"
    assert [s["label"].split()[0] for s in out["sections"]] == ["ماده", "تبصره"]
    assert all(s["label"] != "ماده 4" for s in out["sections"])
    assert api.params() == {"IDS": "12021850837713548188"}
    missing = await client.call_tool("qv_law", {"ids": "12021850837713548188", "article": "999"})
    assert missing.is_error and "Article 999 was not found" in missing.content[0].text
    assert len(api.calls) == 1  # the parsed law is cached


async def test_qv_law_paging_and_date(client, api):
    api["/Law/TreeText/"] = fixture("law_treetext_civil_excerpt.html")
    args = {"ids": "1", "date": "۱۳۱۴/۰۸/۰۸", "with_opinions": True, "max_chars": 500}
    first = (await client.call_tool("qv_law", args)).structured_content
    assert api.params() == {"IDS": "1", "TextDate": "1314/08/08", "WithOpinion": "true"}
    assert first["sections_total"] == 6 and 0 < len(first["sections"]) < 6 and "next_offset" in first
    rest = (await client.call_tool("qv_law", args | {"offset": first["next_offset"]})).structured_content
    assert rest["sections"][0]["id"] != first["sections"][0]["id"]


async def test_qv_law_single_long_section_is_cut(client, api):
    api["/Law/TreeText/"] = fixture("law_treetext_vote.html")
    out = (await client.call_tool("qv_law", {"ids": "1", "max_chars": 600})).structured_content
    (section,) = out["sections"]
    assert section["text"].endswith("…") and len(section["text"]) <= 601 and "max_chars" in out["cut"]


async def test_qv_law_bad_input(client, api):
    for args in ({"ids": "abc"}, {"ids": "1", "date": "1400-1"}, {"ids": "1", "article": "x"}):
        api["/Law/TreeText/"] = fixture("law_treetext_civil_excerpt.html")
        assert (await client.call_tool("qv_law", args)).is_error, args


async def test_qv_law_info(client, api):
    api["/Law/Attribute/"] = fixture("law_attribute_regulation.html")
    out = (await client.call_tool("qv_law_info", {"ids": "10231483372057062686"})).structured_content
    assert out["type"] == "مقرره" and out["approver"] and out["notification_no"]
    assert out["gazette_no"] and out["executors"]
    assert "0000/00/00" not in out.values() and "ندارد" not in out.values()


async def test_qv_amendments_and_article_history(client, api):
    api["/Law/StatusIndex/"] = fixture("law_statusindex.html")
    out = (await client.call_tool("qv_amendments", {"ids": "1", "limit": 2})).structured_content
    assert out["amended_by_total"] == 24 and len(out["amended_by"]) == 2 and out["amends"] == []
    art = out["articles"][0]
    assert art["section_id"] == "1030597" and art["label"] == "مقدمه>ماده 1" and art["changes"] == 3
    assert art["latest"]["date"] == "1370/08/14" and art["latest"]["type"] == "اصلاحی"
    api["/Law/SectionStatus/1030597"] = fixture("law_sectionstatus.html")
    hist = (await client.call_tool("qv_article_history", {"section_id": "1030597"})).structured_content
    assert [e["date"] for e in hist["events"]] == ["1358/09/12", "1361/10/08", "1370/08/14"]
    assert hist["events"][0]["by"]["title"] == "قانون اساسی جمهوری اسلامی ایران"
    assert hist["events"][0]["previous"] == "مقدمه>ماده 1" and "اصل اول" in hist["events"][0]["new_text"]


async def test_qv_related(client, api):
    api["/Law/RelatedIndex/"] = fixture("law_relatedindex_excerpt.html")
    out = (await client.call_tool("qv_related", {"ids": "1", "limit": 2})).structured_content
    assert out["laws"] == [] and out["others_total"] == 3 and len(out["others"]) == 2
    assert out["others"][0]["title"].startswith("رأی شماره 982061") and out["others"][0]["date"] == "1405/04/23"
