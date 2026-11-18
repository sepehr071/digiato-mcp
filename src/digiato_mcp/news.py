"""Digiato news, reviews, categories and tags, read from the site's WordPress REST API (post type digi_posts)."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from typing import Annotated, Any
from urllib.parse import unquote, urlparse

from pydantic import Field

from .http import API, ApiError, fetch, fetch_html
from .registry import tool

POSTS = f"{API}/digi_posts"
LIST_FIELDS = "id,date,slug,link,title,categories,images"
REVIEWS = "dgreview"  # parent category of all reviews (نقد و بررسی)

Page = Annotated[int, Field(description="Page number, 1-based.", ge=1)]
Limit = Annotated[int, Field(description="Articles per page.", ge=1, le=30)]
Cat = Annotated[
    str, Field(description="Category slug (e.g. mobile, artificial-intelligence) or numeric id; see dgt_categories.")
]
TagRef = Annotated[str, Field(description="Tag slug (e.g. apple) or numeric id; see dgt_tags.")]


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _text(s: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


class _Plain(HTMLParser):
    """Article HTML to plain text: paragraphs and headings on their own lines, lists as '- ', no scripts or embeds."""

    SKIP = {"script", "style", "noscript", "svg", "iframe", "figure", "form", "button"}
    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "blockquote", "ul", "ol", "table"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def _plain(markup: str) -> str:
    p = _Plain()
    p.feed(markup)
    p.close()
    lines = (re.sub(r"[ \t ]+", " ", ln).strip() for ln in "".join(p.out).splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


_LD = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)


async def _page_meta(url: str) -> dict:
    """Author and summary live only in the article page (JSON-LD NewsArticle); best effort, {} on any failure."""
    try:
        page = await fetch_html(url)
    except ApiError:
        return {}
    for m in _LD.finditer(page):
        try:
            ld = json.loads(m.group(1))
        except ValueError:
            continue
        for d in ld if isinstance(ld, list) else [ld]:
            if isinstance(d, dict) and d.get("@type") == "NewsArticle":
                a = d.get("author")
                a = a[0] if isinstance(a, list) and a else a
                return {
                    "author": a.get("name") if isinstance(a, dict) else None,
                    "summary": _text(d.get("description")),
                }
    return {}


async def _categories() -> list[dict]:
    """All categories (about 80, one request, cached briefly)."""
    out: list[dict] = []
    for page in range(1, 6):
        rows, meta = await fetch(
            f"{API}/categories", {"per_page": 100, "page": page, "_fields": "id,name,slug,count,parent,link"}
        )
        out += rows
        if page >= meta.get("pages", 1):
            break
    return out


async def _category_id(ref: str) -> int:
    ref = ref.strip().strip("/").translate(_DIGITS)
    cats = await _categories()
    if ref.isdigit() and any(c["id"] == int(ref) for c in cats):
        return int(ref)
    ref = unquote(ref.rsplit("/", 1)[-1])
    for c in cats:
        if ref in (c["slug"], c["name"]):
            return c["id"]
    raise ApiError(f"No category '{ref}'. Call dgt_categories for the valid slugs.", 404)


async def _tag_id(ref: str) -> int:
    ref = ref.strip().strip("/").translate(_DIGITS)
    if ref.isdigit():
        return int(ref)
    ref = unquote(ref.rsplit("/", 1)[-1])
    by_slug = {"slug": ref, "_fields": "id"}
    by_name = {"search": ref, "per_page": 10, "orderby": "count", "order": "desc", "_fields": "id,name"}
    if ref.isascii():  # a Persian name also matches junk tags whose slug is the escaped name: search first
        rows, _ = await fetch(f"{API}/tags", by_slug)
        if not rows:
            rows, _ = await fetch(f"{API}/tags", by_name)
    else:
        rows, _ = await fetch(f"{API}/tags", by_name)
        rows = [t for t in rows if _text(t["name"]) == ref] or rows
    if not rows:
        raise ApiError(f"No tag '{ref}'. Call dgt_tags with query to find one.", 404)
    return rows[0]["id"]


def _item(p: dict, cats: dict[int, str]) -> dict:
    return {
        "id": p["id"],
        "title": _text(p["title"]["rendered"]),
        "date": p["date"].replace("T", " ")[:16],
        "url": p["link"],
        "categories": [cats[c] for c in p.get("categories", []) if c in cats],
        "image": (p.get("images") or {}).get("cover_large"),
    }


async def _list(params: dict[str, Any], page: int, limit: int) -> dict:
    (rows, meta), cats = (
        await fetch(POSTS, {"per_page": limit, "page": page, "_fields": LIST_FIELDS, **params}),
        await _categories(),
    )
    names = {c["id"]: c["name"] for c in cats}
    return {
        "total": meta.get("total", len(rows)),
        "page": page,
        "pages": meta.get("pages", 1),
        "articles": [_item(p, names) for p in rows],
    }


async def _page_list(params: dict[str, Any], page: int, limit: int) -> dict:
    """A page past the end is a 400 upstream; report it as an empty page."""
    try:
        return await _list(params, page, limit)
    except ApiError as e:
        if e.status == 400:
            return {"total": 0, "page": page, "pages": 0, "articles": []}
        raise


@tool("Latest news")
async def dgt_latest(page: Page = 1, limit: Limit = 10) -> dict:
    """Latest Digiato articles (news, reviews, guides), newest first.

    Each article has id, title, date (Tehran time), url and category names. Next: dgt_article with the id or url.
    """
    return await _page_list({}, page, limit)


@tool("Categories")
async def dgt_categories(
    parent: Annotated[
        str | None, Field(description="Only children of this category slug or id (e.g. tech, car).")
    ] = None,
) -> dict:
    """List Digiato categories with article counts and parent, e.g. tech > mobile, artificial-intelligence, security.

    Counts of a parent include its children. Use the slug with dgt_category.
    """
    cats = await _categories()
    pid = await _category_id(parent) if parent else None
    by_id = {c["id"]: c["slug"] for c in cats}
    rows = [c for c in cats if pid is None or c["parent"] == pid]
    rows.sort(key=lambda c: -c["count"])
    return {
        "count": len(rows),
        "categories": [
            {"slug": c["slug"], "name": c["name"], "articles": c["count"], "parent": by_id.get(c["parent"])}
            for c in rows
        ],
    }


@tool("News by category")
async def dgt_category(category: Cat, page: Page = 1, limit: Limit = 10) -> dict:
    """Newest articles of one category (children included), e.g. mobile, artificial-intelligence, car-news, security.

    Next: dgt_article for the full text.
    """
    cid = await _category_id(category)
    return {"category": category, **await _page_list({"categories": cid}, page, limit)}


@tool("Search articles")
async def dgt_search(
    query: Annotated[
        str, Field(description="Words to search for, Persian or English (e.g. آیفون, Galaxy S26).", min_length=1)
    ],
    page: Page = 1,
    limit: Limit = 10,
) -> dict:
    """Search Digiato articles by words in the title and text, best matches first.

    Next: dgt_article for the full text.
    """
    if not query.strip():
        raise ApiError("Give some words to search for.")
    return {"query": query, **await _page_list({"search": query.strip()}, page, limit)}


@tool("Reviews")
async def dgt_reviews(
    kind: Annotated[
        str | None,
        Field(
            description="Review type slug: mobile-review, laptop-review, tablet-review, tv-review, wearable-review, "
            "speaker-review, hardware-review, or introduction-review-of-car. Omit for all reviews and comparisons."
        ),
    ] = None,
    page: Page = 1,
    limit: Limit = 10,
) -> dict:
    """Newest Digiato product reviews (نقد و بررسی), optionally of one device type.

    Next: dgt_article for the full review text.
    """
    cid = await _category_id(kind or REVIEWS)
    return {"kind": kind or REVIEWS, **await _page_list({"categories": cid}, page, limit)}


@tool("Tags")
async def dgt_tags(
    query: Annotated[
        str | None, Field(description="Part of a tag name (e.g. اپل, WWDC). Omit for the most used tags.")
    ] = None,
    limit: Annotated[int, Field(description="Tags to return.", ge=1, le=50)] = 20,
) -> dict:
    """Find Digiato tags (companies, products, topics) with article counts, most used first.

    Next: dgt_tag with the slug.
    """
    params: dict[str, Any] = {"per_page": limit, "orderby": "count", "order": "desc", "_fields": "id,name,slug,count"}
    if query:
        params["search"] = query
    rows, meta = await fetch(f"{API}/tags", params)
    return {"total": meta.get("total", len(rows)), "tags": [{**t, "name": _text(t["name"])} for t in rows]}


@tool("News by tag")
async def dgt_tag(tag: TagRef, page: Page = 1, limit: Limit = 10) -> dict:
    """Newest articles carrying one tag, e.g. apple, samsung, google, mobile.

    Next: dgt_article for the full text.
    """
    tid = await _tag_id(tag)
    return {"tag": tag, **await _page_list({"tags": tid}, page, limit)}


@tool("Read article")
async def dgt_article(
    article: Annotated[
        str, Field(description="Article id, URL (https://digiato.com/mobile/...) or slug, from a list or search tool.")
    ],
    max_chars: Annotated[int, Field(description="Cut the text after this many characters.", ge=500, le=40000)] = 8000,
) -> dict:
    """Read one Digiato article as plain text with title, author, summary, date, categories, tags and cover.

    Use after dgt_latest, dgt_search or dgt_reviews. Long texts are cut at max_chars; `truncated` says so.
    """
    ref = article.strip().translate(_DIGITS)
    fields = "id,date,modified,slug,link,title,content,categories,tags,images"
    if ref.isdigit():
        post, _ = await fetch(f"{POSTS}/{ref}", {"_fields": fields})
    else:
        slug = unquote(urlparse(ref).path.strip("/").rsplit("/", 1)[-1]) if "/" in ref else unquote(ref)
        rows, _ = await fetch(POSTS, {"slug": slug, "_fields": fields})
        if not rows:
            raise ApiError(f"No article with slug '{slug}'. Search with dgt_search.", 404)
        post = rows[0]
    names = {c["id"]: c["name"] for c in await _categories()}
    tags: list[str] = []
    if post.get("tags"):
        rows, _ = await fetch(
            f"{API}/tags", {"include": ",".join(map(str, post["tags"])), "per_page": 100, "_fields": "name"}
        )
        tags = [_text(t["name"]) for t in rows]
    body = _plain(post["content"]["rendered"])
    return {
        **_item(post, names),
        **await _page_meta(post["link"]),
        "modified": post["modified"].replace("T", " ")[:16],
        "tags": tags,
        "chars": len(body),
        "truncated": len(body) > max_chars,
        "text": body[:max_chars],
    }
