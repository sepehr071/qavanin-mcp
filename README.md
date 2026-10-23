<!-- mcp-name: io.github.sepehr071/qavanin-mcp -->

# qavanin-mcp: Iranian laws and regulations MCP server for AI agents

**Let your AI agent read Iranian law (قوانین و مقررات ایران).**<br>
An unofficial, read-only MCP server for [qavanin.ir](https://qavanin.ir) (سامانه ملی قوانین و مقررات جمهوری اسلامی ایران), the national database of Iranian laws, regulations, court votes and legal opinions.<br>
Search about 168,000 documents by title or full text, read a law or a single article, see how an article was amended, and follow the regulations and court votes that cite it, all from Claude, Cursor or Copilot.

[![PyPI](https://img.shields.io/pypi/v/qavanin-mcp?color=2563eb)](https://pypi.org/project/qavanin-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/qavanin-mcp)](https://pypi.org/project/qavanin-mcp/)
[![CI](https://github.com/sepehr071/qavanin-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sepehr071/qavanin-mcp/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-io.github.sepehr071%2Fqavanin--mcp-7c3aed)](https://registry.modelcontextprotocol.io/?q=qavanin-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/qavanin-mcp/blob/main/LICENSE)

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_qavanin--mcp-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=qavanin&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22qavanin-mcp%22%5D%7D)

[For AI agents](#for-ai-agents) · [Why](#why) · [What it can do](#what-it-can-do) · [Quick start](#quick-start) · [Tools](#tools) · [How it works](#how-it-works) · [Good to know](#good-to-know) · [FAQ](#faq) · [Configuration](#configuration) · [فارسی](#فارسی) · [Development](#development) · [Related](#related-servers) · [Disclaimer](#disclaimer) · [License](#license)

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for qavanin.ir, Iran's national laws and regulations database. Queries work in Persian (Arabic ي/ك and Persian ی/ک are equivalent); dates are Jalali `YYYY/MM/DD`.
- **Install:** `uvx qavanin-mcp` or `claude mcp add qavanin -- uvx qavanin-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `QAVANIN_MCP_PROXY` (HTTP proxy URL, or a comma-separated list tried in turn); system proxy settings are ignored.
- **Access:** read-only. No login, subscription or purchase calls exist, so no confirmation is needed before calling any tool.
- **Tools:** 7, all prefixed `qv_`. Typical sequence: `qv_search` -> `qv_law` (with `article`) -> `qv_amendments` -> `qv_article_history`.
- **Units:** dates are Jalali strings (`1405/07/22`); document ids (`id`, the site's `IDS`) are 20-digit strings, keep them as strings; text uses Persian ی/ک.
- **Use when:** looking up what an Iranian law, regulation, court ruling or legal opinion says, when it was approved and published, whether it was amended or repealed, and what cites it.
- **Do not use when:** the user needs legal advice or a binding interpretation. The site is a reference database; always say which version and status you read. Sections marked `repealed` or `amended` are not current text.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/qavanin-mcp/blob/main/server.json) and the
  [iran-mcp catalog](https://github.com/sepehr071/iran-mcp) (`TOOLS.md`, `servers.json`, `llms.txt`).

## Why

Iranian legislation is spread over thousands of laws, by-laws, court votes and opinions, and a law's current text depends on later amendments. Answering "what does article 10 of the civil code say, was it ever amended, and which regulations cite it?" means a lot of searching on a slow, server-rendered site. With `qavanin-mcp` an agent does it in a few calls and returns only the relevant article instead of an 892 KB law.

> **You:** ماده ۱۰ قانون مدنی چه می&zwnj;گوید؟
>
> **Agent:** *calls* `qv_search(query="قانون مدنی", kind="law")` -> `qv_law(ids=..., article="10")`
>
> It finds the civil code, reads just article 10 with its notes, and can follow up with `qv_article_history` to show whether that article was changed.

## What it can do

- **Search** about 168,000 laws, regulations, court votes and legal opinions by title or full text, with filters for kind, approving body, executor, subject, document type, status, dates and gazette numbers
- **Read** a law as sections, a single article with its notes, or the text as of a past date
- **Check status**: approval, notification and gazette numbers and dates, last status, executors
- **Trace amendments**: which laws amended this one, which it amends, and every amendment of one article with its replacing text
- **Follow citations**: regulations, court votes and legal opinions related to a law
- **Look up filter ids**: approving bodies, executing bodies, subjects, document types, statuses and curated lists
- **Read-only by design**: no login, no comments, no subscriptions, no purchases

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add qavanin -- uvx qavanin-mcp
```
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "qavanin": { "command": "uvx", "args": ["qavanin-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Cursor</b></summary>

Add the Claude Desktop block to `~/.cursor/mcp.json`.
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

Click **Install in VS Code** above, or add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "qavanin": { "type": "stdio", "command": "uvx", "args": ["qavanin-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex mcp add qavanin -- uvx qavanin-mcp
```

Or in `~/.codex/config.toml`:

```toml
[mcp_servers.qavanin]
command = "uvx"
args = ["qavanin-mcp"]
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "qavanin": { "command": "uvx", "args": ["qavanin-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Windsurf</b></summary>

Add the Claude Desktop block to `~/.codeium/windsurf/mcp_config.json`.
</details>

<details>
<summary><b>Anything else</b></summary>

It's a standard stdio MCP server: run `uvx qavanin-mcp`, or `pip install qavanin-mcp` and run `qavanin-mcp`.
</details>

Then just ask:

- "What does article 10 of the Iranian civil code say?"
- "Was article 1 of this law ever amended? Show the amendment history."
- "Find the latest laws approved by the Majlis and list their gazette numbers."
- "Which regulations and court votes are related to the Iranian Commercial Code?"
- "Show the text of this law as it was on 1400/01/01."
- <span dir="rtl">ماده ۱۰ قانون مدنی چه می&zwnj;گوید؟</span>
- <span dir="rtl">آیا ماده ۱ این قانون اصلاح شده است؟ تاریخچه اصلاحات را نشان بده.</span>
- <span dir="rtl">آیین&zwnj;نامه&zwnj;ها و آرای مرتبط با قانون تجارت کدام&zwnj;اند؟</span>

## Tools

All tools return compact JSON. Document ids from `qv_search` go to the other tools; `qv_lookup` finds the ids that `qv_search` filters take.

| Tool | What it does |
|---|---|
| `qv_search` | Search titles or full text, with filters for kind, approving body, executor, subject, type, status, dates and gazette numbers |
| `qv_lookup` | Find the ids the search filters take: approving bodies, executing bodies, subjects, document types, statuses, curated lists |
| `qv_law` | Read the text of a law as sections, one article with its notes, or the text as of a past date |
| `qv_law_info` | Metadata: type, approver, approval, notification and gazette numbers and dates, last status, executors |
| `qv_amendments` | Which laws amended this one, which it amends, and which of its articles were amended |
| `qv_article_history` | Every amendment of one article: type, date, amending law, replacing text |
| `qv_related` | Regulations, court votes and legal opinions related to a law |

All 7 tools are annotated `readOnlyHint: true`.

## How it works

```text
  AI agent  (Claude, Cursor, Copilot, ...)
      │
      │  MCP over stdio
      ▼
  qavanin-mcp  (runs on your machine)
      │
      │  HTTPS
      └──────▶  qavanin.ir   laws, regulations, court votes, opinions
```

`qavanin-mcp` runs locally and reads the same pages the qavanin.ir website serves (server-rendered HTML plus two small JSON lookups). There is no hosted server in between and no API key. The site's bot-check cookie is solved in Python, so no browser is needed.

## Good to know

- **The site is slow:** 1-15 s per call. The civil code takes about 15 s on first read; it is cached for 5 minutes, so paging through it is fast.
- **Dates are Jalali** (`1405/07/22`), ids stay strings (20-digit), and text is normalised to Persian ی/ک. Placeholder dates such as `0000/00/00` are dropped.
- **Status matters:** sections marked `repealed` or `amended` are not current text. Say which version and status you read.
- **Full-text search shows no snippet.** With `in_text` it finds words inside the law text, so open candidates with `qv_law(article=...)`.
- **The site sometimes ignores search filters** and answers with the whole database; the server detects that and retries.
- **Sorting by date has ties,** so paging a long list can repeat or skip a row: narrow the filters instead of paging deep.
- **Not covered:** comments, subscriptions, purchases and any account feature. It is a research aid, not legal advice.

## FAQ

<details>
<summary><b>Is there an MCP server or API for Iranian laws (qavanin.ir)?</b></summary>

Yes: `qavanin-mcp` is an unofficial MCP server with 7 read-only tools for searching and reading laws, regulations, court votes and legal opinions on qavanin.ir. It reads the same pages as the website; no API key is needed.
</details>

<details>
<summary><b>How do I use it with Claude, Cursor or Copilot?</b></summary>

Add the server with `claude mcp add qavanin -- uvx qavanin-mcp` (or the matching config in [Quick start](#quick-start)), then ask in plain language, in Persian or English.
</details>

<details>
<summary><b>Is it official, safe and free?</b></summary>

It is unofficial and not affiliated with qavanin.ir or the Iranian government. It is read-only, runs on your machine, and is free under the MIT license.
</details>

<details>
<summary><b>Is the text legally binding or up to date?</b></summary>

No. It shows what the site shows. Check each document's status and amendments (`qv_law_info`, `qv_amendments`) before relying on it, and consult a lawyer for legal advice.
</details>

<details>
<summary><b>Can I search with Arabic letters (ي/ك)?</b></summary>

Yes. The site stores Arabic ي/ك, and queries in either form match. Output is normalised to Persian ی/ک.
</details>

<details>
<summary><b>Why is it slow on the first read of a big law?</b></summary>

The site returns a whole law in one response (the civil code is about 892 KB). The server caches it for 5 minutes, so reading further articles is fast.
</details>

<details>
<summary><b>Can it log in, comment or subscribe?</b></summary>

No. It has no login and never calls comment, subscription or purchase endpoints.
</details>

<details>
<summary><b>I get a bot-check or connection error</b></summary>

The server solves qavanin.ir's cookie challenge itself. If your network still cannot reach the site, set `QAVANIN_MCP_PROXY` to an HTTP proxy that can. System proxy variables are ignored on purpose.
</details>

<details>
<summary><b>Claude Desktop says <code>uvx</code> is not found</b></summary>

Use the full path to `uvx` (`where uvx` on Windows, `which uvx` on macOS/Linux) as `command`.
</details>

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `QAVANIN_MCP_PROXY` | unset | Optional HTTP proxy URL, or a comma-separated list tried in turn, for qavanin.ir; system proxies are ignored |

<a id="فارسی"></a>

## فارسی

<div dir="rtl">

### سرور MCP قوانین و مقررات ایران برای دستیار هوش مصنوعی

**qavanin-mcp** یک سرور MCP غیررسمی و فقط&zwnj;خواندنی برای سامانه ملی قوانین و مقررات جمهوری اسلامی ایران ([qavanin.ir](https://qavanin.ir)) است. دستیار هوش مصنوعی شما (Claude، Cursor، Copilot و ...) با آن می&zwnj;تواند در حدود ۱۶۸ هزار سند شامل قوانین، مقررات، آرای قضایی و نظرات حقوقی جستجو کند.

**چه کارهایی می&zwnj;کند**

- **جستجو** در عنوان یا متن اسناد، با فیلتر نوع سند، مرجع تصویب&zwnj;کننده، دستگاه اجرایی، موضوع، وضعیت، تاریخ و شماره روزنامه رسمی.
- **خواندن متن قانون**، یک ماده با تبصره&zwnj;هایش، یا متن قانون در یک تاریخ گذشته.
- **اطلاعات سند**: تاریخ تصویب و ابلاغ، شماره روزنامه رسمی، آخرین وضعیت و دستگاه&zwnj;های اجرایی.
- **اصلاحات**: کدام قوانین این قانون را اصلاح کرده&zwnj;اند و تاریخچهٔ اصلاح هر ماده.
- **مقررات و آرای مرتبط**: آیین&zwnj;نامه&zwnj;ها، آرای دادگاه&zwnj;ها و نظرات مرتبط با هر قانون.

**نکته&zwnj;ها**

- فقط خواندنی است: وارد حساب نمی&zwnj;شود، اشتراک یا خرید ندارد.
- تاریخ&zwnj;ها شمسی (مثل `1405/07/22`) هستند و حروف عربی «ي» و «ك» در جستجو با «ی» و «ک» یکی حساب می&zwnj;شوند.
- سایت کند است (۱ تا ۱۵ ثانیه برای هر درخواست). این ابزار مشاوره حقوقی نیست؛ وضعیت و اصلاحات هر متن را بررسی کنید.
- روی سیستم خود شما اجرا می&zwnj;شود و کلید API لازم ندارد.

**کلیدواژه&zwnj;ها:** قوانین و مقررات ایران، سامانه ملی قوانین و مقررات، قوانین کشور، متن قانون، قانون مدنی، آرای قضایی، نظرات مشورتی، اصلاحات قانون، سرور MCP قوانین.

**نصب** (اول [uv](https://docs.astral.sh/uv/getting-started/installation/) را نصب کنید). در Claude Code:

</div>

```bash
claude mcp add qavanin -- uvx qavanin-mcp
```

<div dir="rtl">

در Claude Desktop، Cursor و بقیه برنامه&zwnj;ها همان تنظیم بخش [Quick start](#quick-start) را بگذارید.

**نمونه پرسش&zwnj;ها**

- «ماده ۱۰ قانون مدنی چه می&zwnj;گوید؟»
- «آیا ماده ۱ این قانون اصلاح شده است؟»
- «آیین&zwnj;نامه&zwnj;های مرتبط با قانون تجارت را فهرست کن.»
- «متن این قانون در تاریخ ۱۴۰۰/۰۱/۰۱ چه بود؟»

</div>

## Development

```bash
git clone https://github.com/sepehr071/qavanin-mcp && cd qavanin-mcp
uv sync
uv run python -m pytest            # offline, against recorded responses
uv run python -m pytest -m live    # real site, slow
uv run ruff check .
```

Tools live in `src/qavanin_mcp/search.py` and `law.py`; each is a typed async function with a docstring that tells the agent when to use it. Issues and PRs are welcome.

Releases: bump the version in `pyproject.toml` and `server.json`, then push a `v*` tag. GitHub Actions tests, publishes to PyPI and the [MCP Registry](https://registry.modelcontextprotocol.io), and creates the GitHub Release.

## Related servers

- [Iran Tax MCP server](https://github.com/sepehr071/iran-tax-mcp) for Iranian tax and Codal data
- [Paziresh24 MCP server](https://github.com/sepehr071/paziresh24-mcp) for doctors and appointments
- [Iran News MCP server](https://github.com/sepehr071/iran-news-mcp) for Iranian news
- [Iran Apps MCP server](https://github.com/sepehr071/iran-apps-mcp) for Iranian apps
- [iran-mcp](https://github.com/sepehr071/iran-mcp): catalog of all Iranian-service MCP servers

## Disclaimer

Unofficial and not affiliated with or endorsed by qavanin.ir or the Iranian government. It reads the pages of the qavanin.ir website, which can change without notice, and it is a research aid, not legal advice. Please keep request rates reasonable.

## Author

<a href="https://www.linkedin.com/in/sepehr-radmard"><img src="https://raw.githubusercontent.com/sepehr071/iran-mcp/main/assets/author-banner.png" alt="Sepehr Radmard: open-source MCP servers for the Iranian web. LinkedIn: linkedin.com/in/sepehr-radmard" width="100%"></a>

Built and maintained by **Sepehr Radmard** (سپهر رادمرد). Connect on [LinkedIn](https://www.linkedin.com/in/sepehr-radmard) or follow [@sepehr071 on GitHub](https://github.com/sepehr071) for more MCP servers for Iranian websites, all listed in [iran-mcp](https://github.com/sepehr071/iran-mcp). If this saves you time, a star on the repo helps other people find it.

## License

[MIT](https://github.com/sepehr071/qavanin-mcp/blob/main/LICENSE)

If this saves you time, a star helps others find it.
