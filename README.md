<!-- mcp-name: io.github.sepehr071/digiato-mcp -->

<div align="center">

<img src="https://raw.githubusercontent.com/sepehr071/digiato-mcp/main/.github/banner.png" alt="digiato-mcp: unofficial Digiato (دیجیاتو) MCP server that reads Persian tech news, product reviews, categories, tags and full articles for Claude, Cursor and Copilot" width="100%">

# digiato-mcp: Digiato (دیجیاتو) tech news and reviews MCP server for AI agents

**digiato-mcp is an unofficial, read-only MCP server that lets an AI agent read the latest tech news, product reviews and full articles on Digiato (دیجیاتو, digiato.com), one of the biggest Persian tech news sites.**<br>
Its 8 tools list the newest articles, browse categories and tags, search by words, list device reviews (phones, laptops, tablets, TVs, wearables, cars) and read one article as plain text with title, author, summary, date, categories and tags.<br>
No API key or account is needed; it works in Claude, Cursor, Copilot and any other MCP client.

[![PyPI](https://img.shields.io/pypi/v/digiato-mcp?color=2563eb)](https://pypi.org/project/digiato-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/digiato-mcp)](https://pypi.org/project/digiato-mcp/)
[![CI](https://github.com/sepehr071/digiato-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sepehr071/digiato-mcp/actions/workflows/ci.yml)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-c2410c)](https://github.com/sepehr071/digiato-mcp/blob/main/LICENSE)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [Tools](#tools) · [Limits](#limits) · [فارسی](#فارسی)

</div>

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for digiato.com: newest articles, categories, tags, search, device reviews and full article text.
- **Install:** `uvx digiato-mcp` or `claude mcp add digiato -- uvx digiato-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none. Optional `DIGIATO_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot log in, comment or like, so no confirmation is needed before calling any tool.
- **Tools:** 8, all prefixed `dgt_`. Typical sequences: `dgt_latest` / `dgt_search` / `dgt_reviews` -> `dgt_article`; `dgt_categories` -> `dgt_category`; `dgt_tags` -> `dgt_tag` -> `dgt_article`.
- **Use when:** the user asks for recent tech, mobile, AI, security, car or science news from Iran's tech press, a Digiato review of a device, news about a company or product (Apple, Samsung, WWDC), or the text of a specific article.
- **Output:** compact JSON. Titles and article text are Persian; dates are Tehran time.

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

Claude Code:

```bash
claude mcp add digiato -- uvx digiato-mcp
```

Claude Desktop, Cursor, VS Code and other clients:

```json
{
  "mcpServers": {
    "digiato": { "command": "uvx", "args": ["digiato-mcp"] }
  }
}
```

Example prompts:

- "What is the latest Samsung news on Digiato?"
- "Is there a Digiato review of the iPhone Duo? Summarise it."
- "Show the newest artificial intelligence articles from Digiato."
- <span dir="rtl">آخرین اخبار سامسونگ در دیجیاتو چیست؟</span>
- <span dir="rtl">نقد و بررسی لپ‌تاپ‌های تازه دیجیاتو را فهرست کن.</span>

Real answer (18 Nov 2026): `dgt_tag(tag="samsung", limit=3)` returned 8,581 articles for the tag, newest first: article 1991704 (Samsung's One UI 9.5 beta for the Galaxy S26, 2026-11-18 13:05), then 1132601 (the phone buying guide) and 1895989 (best-selling phone prices in Iran).

## Tools

| Tool | What it returns |
|---|---|
| `dgt_latest` | Newest articles of any kind: id, title, date, url, categories |
| `dgt_categories` | Category tree with article counts and parent (tech, mobile, artificial-intelligence, car, ...) |
| `dgt_category` | Newest articles of one category, children included |
| `dgt_search` | Articles matching words in the title and text, best matches first |
| `dgt_article` | One article as plain text by id, URL or slug: title, author, summary, date, categories, tags, cover |
| `dgt_reviews` | Newest product reviews (نقد و بررسی), optionally of one device type |
| `dgt_tags` | Find tags (companies, products, topics) with article counts |
| `dgt_tag` | Newest articles carrying one tag |

## Limits

- Category and tag counts can drift from the real total by 1 to 200 (for example the game category showed 8,985 against 8,785 in the feed), so treat them as approximate.
- Search totals are capped at 10,000. A page past the end returns an empty list.
- `dgt_article` returns text only: figures, embeds and scripts are dropped, and the text is cut at `max_chars` (default 8,000; `truncated` says so). Author and summary are read from the article page and are left out if that page fails to load.
- Comments, user profiles and anything behind a login are not covered.
- Digiato answered both Iranian and foreign networks in testing; if your network is blocked, set `DIGIATO_MCP_PROXY`. The server ignores system proxy variables on purpose.

## فارسی

<div dir="rtl">

**digiato-mcp** یک سرور MCP غیررسمی و فقط&zwnj;خواندنی برای دیجیاتو (digiato.com) است. با آن یک عامل هوش مصنوعی می&zwnj;تواند تازه&zwnj;ترین اخبار فناوری را فهرست کند، دسته&zwnj;بندی&zwnj;ها و برچسب&zwnj;ها را ببیند، در مقاله&zwnj;ها جست&zwnj;وجو کند، نقد و بررسی موبایل، لپ&zwnj;تاپ، تبلت، تلویزیون و خودرو را پیدا کند و متن کامل یک مقاله را همراه با نویسنده، خلاصه و تاریخ بخواند. بدون حساب کاربری و کلید API کار می&zwnj;کند. نصب در Claude Code:

</div>

```bash
claude mcp add digiato -- uvx digiato-mcp
```

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q          # offline tests on recorded fixtures
uv run python -m pytest -m live -q  # live calls to digiato.com
```

Releases: bump the version in `pyproject.toml` and `server.json`, run `uv lock`, then push a `v*` tag; GitHub Actions publishes to PyPI.

## Disclaimer

Unofficial and not affiliated with or endorsed by Digiato. It is read-only and uses the public pages and API of digiato.com, which can change without notice.

## Author

Built and maintained by **Sepehr Radmard** (سپهر رادمرد). [LinkedIn](https://www.linkedin.com/in/sepehr-radmard) · [GitHub](https://github.com/sepehr071) · more servers in [iran-mcp](https://github.com/sepehr071/iran-mcp).

## مجوز استفاده (License)

<a href="https://www.linkedin.com/in/sepehr-radmard"><img src="https://raw.githubusercontent.com/sepehr071/iran-mcp/main/assets/license-banner.png" alt="استفادهٔ شخصی و غیرتجاری رایگان است؛ برای استفادهٔ تجاری با سپهر رادمرد تماس بگیرید. Free for personal and non-commercial use; commercial use needs a license." width="100%"></a>

**استفادهٔ شخصی و غیرتجاری رایگان است.** استفاده در شرکت، محصول پولی یا پروژهٔ مشتری به مجوز تجاری نیاز دارد؛ از راه [لینکدین](https://www.linkedin.com/in/sepehr-radmard) یا [گیت&zwnj;هاب](https://github.com/sepehr071) با سپهر رادمرد تماس بگیرید. متن کامل: [PolyForm Noncommercial 1.0.0](https://github.com/sepehr071/digiato-mcp/blob/main/LICENSE).

Free for personal and non-commercial use under the [PolyForm Noncommercial License 1.0.0](https://github.com/sepehr071/digiato-mcp/blob/main/LICENSE). Using it in a company, a paid product or a client project needs a commercial license: contact Sepehr Radmard on [LinkedIn](https://www.linkedin.com/in/sepehr-radmard) or [GitHub](https://github.com/sepehr071).
