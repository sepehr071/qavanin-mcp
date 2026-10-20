<!-- mcp-name: io.github.sepehr071/qavanin-mcp -->

# qavanin-mcp: Iranian laws and regulations MCP server for AI agents ⚖️

**Unofficial, read-only MCP server for [qavanin.ir](https://qavanin.ir) (سامانه ملی قوانین و مقررات جمهوری اسلامی ایران), the national database of Iranian laws, regulations, court votes and legal opinions.**<br>
Search about 168,000 documents by title or full text, read a law or a single article, see how an article was amended, and follow the regulations and court votes that cite it, all from Claude, Cursor or Copilot.

[Quick start](#quick-start) · [For AI agents](#for-ai-agents) · [Tools](#tools) · [Notes](#notes) · [فارسی](#فارسی)

---

## For AI agents

- **What:** unofficial MCP server for qavanin.ir. Queries work in Persian (Arabic ي/ك and Persian ی/ک are equivalent); dates are Jalali `YYYY/MM/DD`.
- **Install:** `claude mcp add qavanin -- uvx qavanin-mcp` (stdio transport, needs [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10+).
- **Auth:** none. Optional `QAVANIN_MCP_PROXY` sets an HTTP proxy for requests to qavanin.ir.
- **Access:** read-only. No login, subscription or purchase calls exist.
- **Tools:** 7, all prefixed `qv_`. Typical sequence: `qv_search` → `qv_law` (with `article`) → `qv_amendments` → `qv_article_history`.
- **Use when:** looking up what an Iranian law, regulation, court ruling or legal opinion says, when it was approved and published, whether it was amended or repealed, and what cites it.
- **Do not use when:** the user needs legal advice or a binding interpretation. The site is a reference database; always say which version and status you read.
- **Output:** compact JSON. Document ids (`id`, the site's `IDS`) are 20-digit strings: keep them as strings. Output uses Persian letters. Sections marked `repealed` or `amended` are not current text.
- **Machine-readable:** [`server.json`](server.json), and the catalog of all Iranian MCP servers at [awesome-iran-mcp](https://github.com/sepehr071/awesome-iran-mcp).

## Quick start

```bash
claude mcp add qavanin -- uvx qavanin-mcp
```

```json
{ "mcpServers": { "qavanin": { "command": "uvx", "args": ["qavanin-mcp"] } } }
```

Example: «ماده ۱۰ قانون مدنی چه می‌گوید؟» → `qv_search(query="قانون مدنی", kind="law")` → `qv_law(ids=..., article="10")`.

## Tools

| Tool | What it does |
|---|---|
| `qv_search` | Search titles or full text, with filters for kind, approving body, executor, subject, type, status, dates and gazette numbers |
| `qv_lookup` | Find the ids the search filters take: approving bodies, executing bodies, subjects, document types, statuses, curated lists |
| `qv_law` | Read the text of a law as sections, one article with its notes, or the text as of a past date |
| `qv_law_info` | Metadata: type, approver, approval, notification and gazette numbers and dates, last status, executors |
| `qv_amendments` | Which laws amended this one, which it amends, and which of its articles were amended |
| `qv_article_history` | Every amendment of one article: type, date, amending law, replacing text |
| `qv_related` | Regulations, court votes and legal opinions related to a law |

## Notes

- The site is slow: 1-15 s per call, the civil code about 15 s on first read (it is cached for 5 minutes, so paging through it is fast).
- The site sometimes ignores search filters and answers with the whole database; the server detects and retries that.
- Sorting by date has many ties, so paging a long list can repeat or skip a row: narrow the filters instead of paging deep.
- A bot-check cookie (ArvanCloud) is solved in Python; no browser is needed.

## فارسی

سرور MCP غیررسمی و فقط‌خواندنی برای سامانه ملی قوانین و مقررات (qavanin.ir): جستجو در عنوان یا متن حدود ۱۶۸ هزار سند، خواندن متن قانون یا یک ماده، تاریخچهٔ اصلاحات هر ماده و مقررات، آرا و نظرات مرتبط. نصب: `claude mcp add qavanin -- uvx qavanin-mcp`

## License

MIT. Not affiliated with qavanin.ir or the Iranian government.
