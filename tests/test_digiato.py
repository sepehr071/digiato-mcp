from urllib.parse import urlparse

import httpx
import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

WP = "/wp-json/wp/v2"
ARTICLE_HTML = (
    '<html><script type="application/ld+json">{"@type":"NewsArticle","description":"Sum &amp; text",'
    '"author":{"@type":"Person","name":"پویا بهرامی"}}</script>'
    '<script type="application/ld+json">{"@type":"BreadcrumbList"}</script></html>'
)


def counted(body, total, pages):
    return lambda request: httpx.Response(
        200, json=body, headers={"x-wp-total": str(total), "x-wp-totalpages": str(pages)}
    )


def posts_q(routes):
    """Query of the last digi_posts list call (a categories call may follow it)."""
    return next(r for r in reversed(routes.calls) if r.url.path.endswith("/digi_posts")).url.params


@pytest.fixture
def site(api):
    api[f"{WP}/categories"] = fixture("categories.json")
    api[f"{WP}/digi_posts"] = counted(fixture("posts.json"), 164724, 54908)
    api[f"{WP}/tags"] = fixture("tags.json")
    return api


async def test_tools_are_registered_and_read_only(client):
    tools = (await client.list_tools()).tools
    names = {t.name for t in tools}
    assert names == {
        "dgt_latest",
        "dgt_categories",
        "dgt_category",
        "dgt_search",
        "dgt_article",
        "dgt_reviews",
        "dgt_tags",
        "dgt_tag",
    }
    assert all(t.annotations.read_only_hint for t in tools)


async def test_latest_maps_items(client, site):
    r = (await client.call_tool("dgt_latest", {"limit": 3})).structured_content
    assert r["total"] == 164724 and r["pages"] == 54908 and len(r["articles"]) == 3
    a = r["articles"][0]
    assert a["url"].startswith("https://digiato.com/") and a["date"].count(":") == 1 and "T" not in a["date"]
    assert all(isinstance(c, str) for c in a["categories"]) and a["categories"]
    q = posts_q(site)
    assert q["per_page"] == "3" and "content" not in q["_fields"]


async def test_category_resolves_slug_and_rejects_unknown(client, site):
    r = (await client.call_tool("dgt_category", {"category": "mobile"})).structured_content
    assert r["articles"] and posts_q(site)["categories"] == "30"
    bad = await client.call_tool("dgt_category", {"category": "nope"})
    assert bad.is_error


async def test_reviews_default_to_the_review_parent(client, site):
    await client.call_tool("dgt_reviews", {})
    assert posts_q(site)["categories"] == "172"
    await client.call_tool("dgt_reviews", {"kind": "laptop-review"})
    assert posts_q(site)["categories"] == "93019"


async def test_categories_children_and_parent_slug(client, site):
    r = (await client.call_tool("dgt_categories", {"parent": "tech"})).structured_content
    assert r["count"] > 5 and {c["parent"] for c in r["categories"]} == {"tech"}
    assert r["categories"] == sorted(r["categories"], key=lambda c: -c["articles"])


async def test_search_and_past_the_end_page(client, site):
    await client.call_tool("dgt_search", {"query": "آیفون"})
    assert posts_q(site)["search"] == "آیفون"
    site[f"{WP}/digi_posts"] = lambda request: httpx.Response(400, json={"code": "rest_post_invalid_page_number"})
    r = (await client.call_tool("dgt_search", {"query": "x", "page": 99999})).structured_content
    assert r["articles"] == [] and r["pages"] == 0


async def test_tags_and_tag_by_slug(client, site):
    r = (await client.call_tool("dgt_tags", {"query": "اپل"})).structured_content
    assert r["tags"][0]["slug"] and "count" in r["tags"][0]
    site[f"{WP}/tags"] = [{"id": 111}]
    t = (await client.call_tool("dgt_tag", {"tag": "apple"})).structured_content
    assert t["articles"] and posts_q(site)["tags"] == "111"


async def test_article_by_url_is_plain_text_and_truncates(client, site):
    site[f"{WP}/digi_posts"] = fixture("article.json")
    site[f"{WP}/tags"] = fixture("tags_article.json")
    url = fixture("article.json")[0]["link"]
    site[urlparse(url).path] = lambda request: httpx.Response(200, text=ARTICLE_HTML)
    r = (await client.call_tool("dgt_article", {"article": url, "max_chars": 500})).structured_content
    assert posts_q(site)["slug"] == url.rsplit("/", 1)[-1]
    assert "<" not in r["text"] and "&#" not in r["text"] and len(r["text"]) == 500
    assert r["truncated"] and r["chars"] > 500 and r["tags"] and r["modified"].startswith("2026")
    assert r["author"] == "پویا بهرامی" and r["summary"]


async def test_article_survives_a_missing_page(client, site):
    """Author/summary come from the HTML page; if it fails the article still returns."""
    site[f"{WP}/digi_posts/1991612"] = fixture("article.json")[0]
    site.pop("/car-news/" + fixture("article.json")[0]["slug"], None)
    r = (await client.call_tool("dgt_article", {"article": "1991612"})).structured_content
    assert r["id"] == 1991612 and "author" not in r


async def test_article_by_id_and_missing_slug(client, site):
    site[f"{WP}/digi_posts/1991612"] = fixture("article.json")[0]
    r = (await client.call_tool("dgt_article", {"article": "1991612"})).structured_content
    assert r["id"] == 1991612
    site[f"{WP}/digi_posts"] = []
    assert (await client.call_tool("dgt_article", {"article": "no-such-slug"})).is_error


async def test_plain_text_handles_lists_and_skips_embeds():
    from digiato_mcp.news import _plain

    out = _plain(
        "<p>One &amp; two</p><ul><li>a</li><li>b</li></ul><script>x()</script><figure><img></figure><h2>H</h2>"
    )
    assert out == "One & two\n\n- a\n- b\n\nH"


async def test_request_headers_match_the_sites_frontend(site):
    from digiato_mcp import http

    await http.fetch(f"{http.API}/tags")
    h = site.calls[-1].headers
    assert h["accept"] == "*/*" and h["referer"] == "https://digiato.com/" and "origin" not in h
    assert (h["sec-fetch-site"], h["sec-fetch-mode"], h["sec-fetch-dest"]) == ("same-origin", "cors", "empty")
    assert h["accept-language"].startswith("fa-IR")


async def test_persian_digits_blank_search_and_persian_tag_name(client, site):
    site[f"{WP}/digi_posts/1991612"] = fixture("article.json")[0]
    r = (await client.call_tool("dgt_article", {"article": "۱۹۹۱۶۱۲"})).structured_content
    assert r["id"] == 1991612
    assert (await client.call_tool("dgt_search", {"query": "   "})).is_error
    # Persian name: search by name, exact match wins over the first (most used) hit
    apple = "اپل"
    site[f"{WP}/tags"] = [{"id": 5, "name": apple + " واچ"}, {"id": 111, "name": apple}]
    await client.call_tool("dgt_tag", {"tag": apple})
    assert posts_q(site)["tags"] == "111"
