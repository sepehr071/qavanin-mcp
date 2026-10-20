"""Search the law database and look up the ids its filters need."""

from __future__ import annotations

import asyncio
import html
import re
from typing import Annotated, Any, Literal

from pydantic import Field

from .http import BASE, ApiError, cached, get_json, get_page
from .registry import tool
from .text import ascii_digits, fa, one_line

# Verified ids: lwTypes and LawStatus are static <select> lists on the home page.
TYPES = {
    1: "مصوبات مجمع تشخیص مصلحت نظام",
    2: "اساسی",
    3: "مصوبات رهبری",
    4: "عادی",
    5: "مصوبات مجلس-مجمع تشخیص مصلحت نظام",
    6: "آیین نامه قانونی",
    7: "اساسنامه قانونی",
    66: "مقرره-تصمیم نامه",
    67: "مقرره-آیین نامه",
    68: "مقرره-اساسنامه",
    69: "مقرره-بخشنامه",
    70: "مقرره-موافقتنامه",
}
STATUSES = {"valid": 1, "trial": 3, "temporary": 4, "repealed": 7, "moot": 9, "enforced": 14, "extended": 15}
STATUS_NAMES = {
    "valid": "معتبر",
    "trial": "آزمایشی",
    "temporary": "موقت",
    "repealed": "منسوخه",
    "moot": "بااجرامنتفی می شود",
    "enforced": "تنفیذ",
    "extended": "تمدید",
}
LISTS = {
    1: "قوانین کاربردی",
    132: "سیاستهای کلی نظام",
    113: "آخرین قوانین",
    114: "آخرین مقررات",
    122: "معاهدات، کنوانسیونها و سازمانهای بین المللی",
    119: "موافقتنامه های بین المللی",
    118: "اساسنامه ها",
    117: "آیین نامه ها",
    120: "بخشنامه‌های قوه قضائیه",
    115: "آرای دیوان عالی کشور",
    116: "آرای دیوان عدالت اداری",
    125: "نظرات رییس مجلس شورای اسلامی",
    126: "نظرات مشورتی اداره کل حقوقی قوه قضائیه",
    121: "قوانین منسوخ",
    123: "مقررات منسوخ",
}
KINDS = {"law": "_isLaw", "regulation": "_isRegulation", "vote": "_IsVote", "opinion": "_isOpenion"}
MATCH = {"all_words": 1, "phrase": 2, "part_of_word": 3, "any_word": 4}
SORT = {"newest": ("APPROVEDATE", "True"), "oldest": ("APPROVEDATE", "False"), "title": ("CAPTION", "False")}
SIZES = (25, 50, 100)  # site whitelist is 25/50/100/200/500/1000; anything else is HTTP 500
DATE = re.compile(r"\d{4}/\d{2}/\d{2}")
TRIES = 4

_ROW = re.compile(r"<tr\s[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_IDS = re.compile(r"IDS=(\d+)")


def _date(value: str | None, name: str) -> str | None:
    if not value:
        return None
    v = ascii_digits(value.strip()).replace("-", "/")
    if not DATE.fullmatch(v):
        raise ApiError(f"{name} must be a Jalali date like 1403/05/21, got {value!r}.")
    return v


def _digits(value: str | None, name: str) -> str | None:
    v = ascii_digits(value or "").strip()
    if v and not v.isdigit():
        raise ApiError(f"{name} must be digits only (no '/' or letters), got {value!r}.")
    return v or None


def parse_results(page: str) -> dict[str, Any]:
    """Count, description, pages and rows of a result page; repealed rows are `<tr class="red">`."""
    count = re.search(r"تعداد یافته ها</b>\s*:\s*(\d+)", page)
    desc = re.search(r"توصیف جستجو</b>\s*:(.*?)<br", page, re.S)
    pages = re.search(r"</select>\s*از\s*(\d+)", page[page.find('id="PageNumber"') :])
    if not count:
        raise ApiError("qavanin.ir returned an unexpected page (no result count). Try again in a moment.")
    items = []
    for row in _ROW.finditer(page):
        ids = _IDS.search(row[1])
        cells = _CELL.findall(row[1])
        if not ids or len(cells) < 4:
            continue
        item: dict[str, Any] = {
            "id": ids[1],
            "title": one_line(cells[1]),
            "approved": one_line(cells[2]) or None,
            "approver": one_line(cells[3]) or None,
        }
        if "red" in row[0]:
            item["repealed"] = True
        items.append(item)
    return {
        "total": int(count[1]),
        "pages": int(pages[1]) if pages else 0,
        "description": one_line(desc[1]) if desc else "",
        "items": items,
    }


async def _corpus_total() -> int:
    """Hit count of an unfiltered search; the site sometimes answers a filtered query with exactly this."""

    async def make() -> int:
        return parse_results((await get_page("/", {"size": 25}))[1])["total"]

    return await cached("corpus_total", 3600, make)


async def _search(params: dict[str, Any], filtered: bool, has_query: bool) -> dict[str, Any]:
    """GET the home page; about 30 % of answers silently ignore every filter, so detect and repeat those."""
    for attempt in range(TRIES):
        out = parse_results((await get_page("/", params))[1])
        if not filtered:
            return out
        blank = not out["description"]
        if not (blank and (has_query or out["total"] >= await _corpus_total())):
            return out
        if attempt + 1 < TRIES:
            await asyncio.sleep(1)
    raise ApiError("qavanin.ir keeps ignoring the search filters right now. Try again in a minute.")


@tool("Search laws and regulations")
async def qv_search(
    query: Annotated[
        str | None,
        Field(max_length=200, description="Words to find, Persian or Arabic letters, e.g. 'مالیات بر ارزش افزوده'."),
    ] = None,
    in_text: Annotated[bool, Field(description="Search the full text of every law, not only the titles.")] = False,
    match: Annotated[
        Literal["all_words", "phrase", "part_of_word", "any_word"],
        Field(
            description="'all_words' every word as a whole word, 'phrase' words adjacent, 'part_of_word' substring "
            "match (the site default, widest), 'any_word' at least one whole word."
        ),
    ] = "all_words",
    kind: Annotated[
        Literal["law", "regulation", "vote", "opinion"] | None,
        Field(description="'law' (Majlis statutes), 'regulation', 'vote' (court rulings), 'opinion' (legal opinions)."),
    ] = None,
    approver_id: Annotated[
        list[int] | None,
        Field(max_length=10, description="Approving body ids from qv_lookup(kind='approver'); several are OR-ed."),
    ] = None,
    executor_id: Annotated[
        list[int] | None, Field(max_length=10, description="Executing body ids from qv_lookup(kind='executor').")
    ] = None,
    subject_id: Annotated[
        list[int] | None, Field(max_length=10, description="Subject ids from qv_lookup(kind='subject').")
    ] = None,
    type_id: Annotated[
        list[int] | None, Field(max_length=10, description="Document type ids from qv_lookup(kind='type').")
    ] = None,
    status: Annotated[
        Literal["valid", "trial", "temporary", "repealed", "moot", "enforced", "extended"] | None,
        Field(description="Legal status. 'repealed' = منسوخه; 'moot' = بااجرامنتفی می شود. 'valid' undercounts."),
    ] = None,
    list_id: Annotated[
        int | None, Field(description="A curated list id from qv_lookup(kind='list'), e.g. 113 for the latest laws.")
    ] = None,
    approved_from: Annotated[str | None, Field(description="Approval date from, Jalali 'YYYY/MM/DD'.")] = None,
    approved_to: Annotated[str | None, Field(description="Approval date to, Jalali 'YYYY/MM/DD'.")] = None,
    command_no: Annotated[
        str | None, Field(description="Notification number (شماره ابلاغ), digits, substring.")
    ] = None,
    newspaper_no: Annotated[
        str | None, Field(description="Official gazette number (شماره روزنامه رسمی), digits, substring.")
    ] = None,
    sort: Annotated[
        Literal["newest", "oldest", "title"],
        Field(description="By approval date, or 'title' (alphabetical by database collation; stable for paging)."),
    ] = "newest",
    page: Annotated[int, Field(ge=1, le=10000, description="Page number, from 1.")] = 1,
    limit: Annotated[int, Field(ge=1, le=100, description="Results per page.")] = 25,
) -> dict[str, Any]:
    """Search the Iranian law and regulation database (qavanin.ir, 168,000 documents) and list matching titles.

    Returns total hits, page count and items with `id` (the IDS to give qv_law, qv_law_info, qv_amendments and
    qv_related), title, approval date (Jalali), approving body and `repealed` for repealed ones. Text search shows
    no snippets. Use for "which law covers X", "all regulations of body Y in a date range" and "latest laws".
    Sorting by date has many ties, so paging a long list may repeat or skip a row; narrow the filters instead.
    """
    size = next(s for s in SIZES if limit <= s)
    sort_col, desc = SORT[sort]
    params: dict[str, Any] = {"size": size, "PageNumber": page, "SortColumn": sort_col, "SortDesc": desc}
    q = fa(query or "").strip()
    if q:
        params["CAPTION"] = q
        params["IsTextSearch" if in_text else "IsTitleSearch"] = "true"
        params["SeachTextType"] = MATCH[match]
    if kind:
        params[KINDS[kind]] = "true"
    for key, ids in (
        ("Approvers", approver_id),
        ("Executors", executor_id),
        ("Subjects", subject_id),
        ("lwTypes", type_id),
    ):
        if ids:
            params[key] = ids
    if status:
        params["LawStatus"] = STATUSES[status]
    if list_id:
        params["Report_ID"] = list_id
    for key, value in (
        ("fromApproveDate", _date(approved_from, "approved_from")),
        ("APPROVEDATE", _date(approved_to, "approved_to")),
        ("COMMANDNO", _digits(command_no, "command_no")),
        ("NEWSPAPERNO", _digits(newspaper_no, "newspaper_no")),
    ):
        if value:
            params[key] = value
    filtered = any(k not in ("size", "PageNumber", "SortColumn", "SortDesc") for k in params)
    out = await _search(params, filtered, bool(q))
    items = out["items"][:limit]
    for item in items:
        item["url"] = f"{BASE}/Law/TreeText/?IDS={item['id']}"
    res: dict[str, Any] = {"total": out["total"], "page": page, "pages": out["pages"], "items": items}
    if out["description"]:
        res["filters"] = out["description"]
    return res


async def _paged(path: str, term: str, page: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return await get_json(path, {"term": fa(term), "page": page, **(extra or {})})


@tool("Look up filter ids")
async def qv_lookup(
    kind: Annotated[
        Literal["approver", "executor", "subject", "type", "status", "list"],
        Field(
            description="'approver' (مرجع تصویب), 'executor' (دستگاه مجری), 'subject' (موضوع), 'type' (نوع مصوبه), "
            "'status' (وضعیت) or 'list' (curated lists)."
        ),
    ],
    query: Annotated[
        str | None,
        Field(max_length=100, description="Name fragment, e.g. 'دیوان' or 'بانک'. Empty lists the most used."),
    ] = None,
    page: Annotated[int, Field(ge=1, le=100, description="Page of 20 for approver, executor and subject.")] = 1,
) -> dict[str, Any]:
    """Find the ids that qv_search filters take: approving bodies, executing bodies, subjects, types, statuses, lists.

    Returns items with `id` and name; approvers, executors and subjects also have `count` (documents) and are
    paged by 20. Example: kind='approver', query='مجلس' gives the Majlis id to pass as approver_id.
    """
    term = fa(query or "").strip()
    if kind in ("approver", "executor"):
        data = await _paged("/Law/getOrgs/", term, page, {"isApprover": "true" if kind == "approver" else "false"})
        items = [
            {"id": i["id"], "name": fa(re.sub(r"\(\d+\)$", "", i["text"]).strip()), "count": i["count"]}
            for i in data["items"]
        ]
    elif kind == "subject":
        data = await _paged("/Law/getTopics/", term, page)
        items = []
        for i in data["items"]:
            m = re.fullmatch(r"\s*\S+?\.\s*(.*?)\((\d+)\)\s*", html.unescape(i["text"]), re.S)
            items.append(
                {"id": i["id"], "code": i["code"].strip(), "name": fa(m[1].strip() if m else i["text"].strip())}
                | ({"count": int(m[2])} if m else {})
            )
    else:
        table = {
            "type": TYPES,
            "status": {STATUSES[k]: f"{k} ({STATUS_NAMES[k]})" for k in STATUSES},
            "list": LISTS,
        }[kind]
        items = [{"id": k, "name": v} for k, v in table.items() if not term or fa(term) in fa(v) or term in str(k)]
        return {"total": len(items), "items": items}
    return {"total": data["total_count"], "page": data["page"], "pages": data["pagecount"], "items": items}
