"""One law: full text, metadata, amendments, related documents."""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import Field

from .http import BASE, ApiError, cached, get_page
from .registry import tool
from .text import ascii_digits, fa, one_line, plain

IDS = Annotated[
    str,
    Field(pattern=r"^\d{1,20}$", description="Law id (IDS) from qv_search, digits only, e.g. '12021850837713548188'."),
]
STATUS = {"": None, "green": "amended", "red": "repealed", "brown": "opinion"}
STRUCTURE = re.compile(r"^(?:ماده|فصل|مبحث|باب|کتاب|قسمت|بخش|مقدمه)")
ATTRIBUTES = {
    "نوع قانون": "type",
    "مرجع تصویب": "approver",
    "تاریخ تصویب": "approved",
    "شماره ابلاغ": "notification_no",
    "مرجع ابلاغ": "notified_by",
    "تاریخ ابلاغ": "notified",
    "شماره روزنامه رسمی": "gazette_no",
    "تاریخ روزنامه رسمی": "gazette_date",
    "آخرین وضعیت": "last_status",
    "تاریخ اجرا": "effective",
    "تاریخ انتشار": "published",
    "طبقه بندی": "classification",
}
EMPTY = {"", "-", "ندارد", "0000/00/00"}

_TITLE = re.compile(r"""<h1 class=['"]mytitle[^>]*>(.*?)</h1>""", re.S)
_SUBTITLE = re.compile(r"""<h2 class=['"]Titr font-l[^>]*>(.*?)</h2>""", re.S)
_NODE_END = re.compile(r"<div id='share|<div class='w100'>|<fieldset")
_NODE = re.compile(r"""<p class=['"]SecTex ?(\w*)['"] id="(\d+)"[^>]*>(.*)""", re.S)
_LABEL = re.compile(r"""\s*<span class=['"]bold blue['"]>(.*?)</span>(.*)""", re.S)
_ARM = re.compile(r"<a [^>]*>\s*<img [^>]*arm\.gif[^>]*>\s*</a>", re.S)
_RELATED = re.compile(r"""href=['"]/Law/TreeText/\?IDS=(\d+)['"][^>]*>(.*?)</a>""", re.S)
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_LINK = re.compile(r'href="/Law/TreeText/\?IDS=(\d+)(?:#\d+)?"[^>]*>(.*?)</a>', re.S)


def _head(page: str) -> dict[str, Any]:
    title = _TITLE.search(page)
    sub = _SUBTITLE.search(page)
    out: dict[str, Any] = {"title": one_line(title[1]) if title else None}
    if sub and (m := re.search(r"مصوب\s+(\d{4}/\d\d/\d\d)\s*(.*)", one_line(sub[1]))):
        out["approved"], out["approver"] = m[1], m[2].strip() or None
    return out


async def _page(path: str, params: dict[str, Any]) -> str:
    return (await get_page(path, params))[1]


def parse_sections(page: str) -> list[dict[str, Any]]:
    """The flat list of articles, notes and headings of a TreeText page."""
    start = page.find('id="treeText"')
    if start < 0:
        raise ApiError("qavanin.ir returned a page without law text. Check the id with qv_search.")
    end = page.find('id="report-modal"', start)
    body = page[start : end if end > 0 else len(page)]
    nodes = []
    for chunk in re.split(r"(?=<p class=['\"]SecTex)", body):
        m = _NODE.match(chunk)
        if not m:  # the title block has no id
            continue
        # A node ends at its share/dropdown div, not at the first </p>: court votes nest <p> tags.
        end = _NODE_END.search(m[3])
        inner, rest = (m[3][: end.start()], m[3][end.start() :]) if end else (m[3], "")
        inner = re.sub(r"</p>\s*$", "", inner)
        if "rounddiv" in inner:  # the title block (title, approval date, "with later amendments"), also in the header
            continue
        node: dict[str, Any] = {"id": m[2]}
        if st := STATUS.get(m[1]):
            node["status"] = st
        if _ARM.search(inner):
            node["history"] = True
        inner = _ARM.sub("", inner)
        if lab := _LABEL.match(inner):
            node["label"] = one_line(lab[1])
            inner = lab[2]
        node["text"] = re.sub(r"^\s*-\s*", "", plain(inner))
        if rel := _RELATED.findall(rest):
            node["opinions"] = [{"id": i, "title": one_line(t)} for i, t in rel[:5]]
        nodes.append(node)
    return nodes


def _article_range(nodes: list[dict[str, Any]], article: str) -> list[dict[str, Any]]:
    """The article with its notes (تبصره) up to the next article or heading."""
    num = re.search(r"\d+", ascii_digits(article))
    if not num:
        raise ApiError(f"article must contain a number, e.g. '10' or 'ماده 10 مکرر', got {article!r}.")
    again = "مکرر" in article
    pat = re.compile(rf"^ماده\s*{num[0]}(?!\d)")
    for i, n in enumerate(nodes):
        lab = n.get("label", "")
        if pat.match(lab) and ("مکرر" in lab) == again:
            j = i + 1
            while j < len(nodes) and not STRUCTURE.match(nodes[j].get("label", "")):
                j += 1
            return nodes[i:j]
    raise ApiError(f"Article {num[0]} was not found in this law ({len(nodes)} sections). Read it without `article`.")


@tool("Read a law's text")
async def qv_law(
    ids: IDS,
    article: Annotated[
        str | None,
        Field(max_length=40, description="Only this article with its notes, e.g. '10', 'ماده 10', '10 مکرر'."),
    ] = None,
    date: Annotated[
        str | None,
        Field(description="Jalali 'YYYY/MM/DD': the text as it stood on that date (before later amendments)."),
    ] = None,
    with_opinions: Annotated[
        bool, Field(description="Add interpretive opinions (نظر تفسیری) as extra sections.")
    ] = False,
    offset: Annotated[
        int, Field(ge=0, description="Skip this many sections (use next_offset from the last call).")
    ] = 0,
    max_chars: Annotated[int, Field(ge=500, le=100000, description="Text budget per call.")] = 15000,
) -> dict[str, Any]:
    """Read the full text of a law, regulation, court vote or opinion as sections (articles, notes, headings).

    Each section has `id`, `label` ('ماده 10', 'تبصره 1'), `text`, `status` ('amended', 'repealed', 'opinion'; absent
    when plain) and `history: true` when qv_article_history can show its amendments. Long laws are paged by
    `offset`/`next_offset` within `max_chars`; the civil code has about 1,500 sections and takes about 15 s to load
    the first time. Get the id from qv_search. Use `article` to answer "what does article N say".
    """
    if date:
        date = ascii_digits(date).strip().replace("-", "/")
        if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", date):
            raise ApiError(f"date must be a Jalali date like 1380/05/21, got {date!r}.")
    params = {"IDS": ids, **({"TextDate": date} if date else {}), **({"WithOpinion": "true"} if with_opinions else {})}

    async def make() -> dict[str, Any]:
        page = await _page("/Law/TreeText/", params)
        return {**_head(page), "sections": parse_sections(page)}

    law = await cached(("law", ids, date, with_opinions), 300, make)
    nodes = _article_range(law["sections"], article) if article else law["sections"]
    out: dict[str, Any] = {k: v for k, v in law.items() if k != "sections"} | {"id": ids, "sections_total": len(nodes)}
    out["url"] = f"{BASE}/Law/TreeText/?IDS={ids}"
    items: list[dict[str, Any]] = []
    used = 0
    for i in range(offset, len(nodes)):
        node = dict(nodes[i])
        room = max_chars - used
        if items and len(node["text"]) > room:
            out["next_offset"] = i
            break
        if len(node["text"]) > room:  # one section alone is over budget (court votes are a single section)
            node["text"] = node["text"][:room] + "…"
            out["cut"] = f"Section text cut at {max_chars} chars; raise max_chars (up to 100000) for the rest."
        used += len(node["text"])
        items.append(node)
    out["sections"] = items
    return out


@tool("Law metadata")
async def qv_law_info(ids: IDS) -> dict[str, Any]:
    """Metadata of a law: type, approving body, approval, notification and gazette dates and numbers, last status,
    effective date, executing bodies and recipients of the copy.

    Use after qv_search to cite a law ("approved 1318/..., published in gazette no. ...") or to check its
    type. Court votes and opinions carry almost no metadata. Dates are Jalali.
    """
    page = await _page("/Law/Attribute/", {"IDS": ids})
    out: dict[str, Any] = {"id": ids} | _head(page)
    for label, value in re.findall(
        r'<span class="text-primary">\s*([^<]*?)\s*</span></div>\s*<div><span class="text-left">\s*([\s\S]*?)</span>',
        page,
    ):
        key = ATTRIBUTES.get(fa(label.strip().rstrip(":")))
        value = re.sub(r"\s*-\s*$", "", one_line(value))
        if key and key not in out and value not in EMPTY:
            out[key] = value
    for heading, items in re.findall(
        r'<h4 class="Titr"[^>]*>(.*?)</h4>\s*</div>\s*<div[^>]*scrollbar1[^>]*>\s*<ul>(.*?)</ul>', page, re.S
    ):
        names = [one_line(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", items, re.S)]
        key = "executors" if "مجری" in heading else "copy_to" if "رونوشت" in heading else None
        if key and names:
            out[key] = names[:30]
    out["url"] = f"{BASE}/Law/TreeText/?IDS={ids}"
    return out


def parse_events(fragment: str) -> list[dict[str, Any]]:
    """Amendment events of one article from SectionStatus markup."""
    events = []
    for chunk in fragment.split('<div class="Box1">')[1:]:
        head, _, tail = chunk.partition("</div>")
        by = _LINK.search(head)
        ev: dict[str, Any] = {}
        if m := re.search(r"نوع وضعیت :</b>\s*(.*?)\s*<b>", head, re.S):
            ev["type"] = one_line(m[1])
        if by:
            ev["by"] = {"id": by[1], "title": one_line(by[2])}
        if m := re.search(r"تاریخ :</b>\s*(\d{4}/\d\d/\d\d)", head):
            ev["date"] = m[1]
        if m := re.search(r"متن قبلی :</b>(.*?)<br", tail, re.S):
            ev["previous"] = one_line(m[1])
        if m := re.search(r"متن اثرگذار/تغییر یافته :</b>(.*?)(?:<hr|$)", tail, re.S):
            ev["new_text"] = plain(m[1])[:1500]
        events.append(ev)
    return events


@tool("Amendments of a law")
async def qv_amendments(
    ids: IDS,
    limit: Annotated[int, Field(ge=1, le=100, description="Max amending/amended laws listed per direction.")] = 30,
) -> dict[str, Any]:
    """Which laws amended this one, which this one amends, and which of its articles were amended.

    Returns `amended_by` and `amends` (id, title, approval date) and `articles`: section id, label, number of
    changes and the latest change. Read one article's full history with qv_article_history(section_id).
    """
    page = await _page("/Law/StatusIndex/", {"IDS": ids})
    out: dict[str, Any] = {"id": ids}
    tables = [m for m in re.findall(r'<table class="slwTable">(.*?)</table>', page, re.S)]
    for key, table in zip(("amended_by", "amends"), tables[:2], strict=False):
        rows = []
        for row in _ROW.findall(table):
            if (m := _LINK.search(row)) and (cells := re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)):
                rows.append({"id": m[1], "title": one_line(m[2]), "approved": one_line(cells[2]) or None})
        out[key] = rows[:limit]
        out[f"{key}_total"] = len(rows)
    articles = []
    for pid, label, body in re.findall(
        r'<div class="panel panel-default" id="(\d+)">.*?<a role="button"[^>]*>(.*?)</a>(.*?)(?=<div class="panel panel-default"|\Z)',
        page,
        re.S,
    ):
        events = parse_events(body)
        art: dict[str, Any] = {"section_id": pid, "label": one_line(label), "changes": len(events)}
        if events:
            art["latest"] = {k: v for k, v in events[-1].items() if k in ("type", "date", "by")}
        articles.append(art)
    out["articles"] = articles
    return out


@tool("History of one article")
async def qv_article_history(
    section_id: Annotated[
        str, Field(pattern=r"^\d{1,12}$", description="Section id from qv_law (items marked history) or qv_amendments.")
    ],
) -> dict[str, Any]:
    """Every amendment of one article: type (اصلاحی...), date, the amending law and the replacing text.

    Use after qv_law or qv_amendments when asked how an article changed. Oldest change first. An article that
    was never amended returns an empty list.
    """
    page = await _page(f"/Law/SectionStatus/{section_id}", {})
    return {"section_id": section_id, "events": parse_events(page)}


@tool("Related regulations, votes and opinions")
async def qv_related(
    ids: IDS,
    limit: Annotated[int, Field(ge=1, le=200, description="Max related documents returned per group.")] = 30,
) -> dict[str, Any]:
    """Documents related to a law: other laws, and regulations, court votes and legal opinions that cite or
    interpret it (hundreds for the civil code, newest first).

    Returns `laws` and `others`, each with id, title and date; read any with qv_law. Votes of the
    Administrative Justice Court and opinions are listed by title only.
    """
    page = await _page("/Law/RelatedIndex/", {"IDS": ids})
    out: dict[str, Any] = {"id": ids}
    for col in re.split(r'<h2 class="Titr', page)[1:]:
        # The first h2.Titr on the page is the law subtitle; the two columns are told apart by their headings.
        key = "others" if "مقررات" in col[: col.find("</h2>")] else "laws" if "قوانین مرتبط" in col[:60] else None
        if not key:
            continue
        rows = []
        for row in _ROW.findall(col):
            if m := _LINK.search(row):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
                rows.append({"id": m[1], "title": one_line(m[2]), "date": one_line(cells[-1]) or None})
        out[key] = rows[:limit]
        out[f"{key}_total"] = len(rows)
    return out
