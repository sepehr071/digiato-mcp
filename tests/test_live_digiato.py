import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_live_latest_and_article(client):
    r = (await client.call_tool("dgt_latest", {"limit": 3})).structured_content
    assert r["total"] > 100_000 and len(r["articles"]) == 3
    a = (await client.call_tool("dgt_article", {"article": str(r["articles"][0]["id"])})).structured_content
    assert a["title"] == r["articles"][0]["title"] and len(a["text"]) > 100 and a["author"]


async def test_live_categories_and_category(client):
    c = (await client.call_tool("dgt_categories", {})).structured_content
    assert {"tech", "mobile", "dgreview"} <= {x["slug"] for x in c["categories"]}
    r = (await client.call_tool("dgt_category", {"category": "artificial-intelligence", "limit": 3})).structured_content
    assert r["articles"] and all("هوش مصنوعی" in a["categories"] for a in r["articles"])


async def test_live_search_reviews_tags(client):
    s = (await client.call_tool("dgt_search", {"query": "سامسونگ", "limit": 3})).structured_content
    assert s["articles"]
    v = (await client.call_tool("dgt_reviews", {"kind": "mobile-review", "limit": 3})).structured_content
    assert v["articles"] and all("بررسی موبایل" in a["categories"] for a in v["articles"])
    t = (await client.call_tool("dgt_tags", {})).structured_content
    assert t["tags"][0]["count"] > 1000
    n = (await client.call_tool("dgt_tag", {"tag": "apple", "limit": 3})).structured_content
    assert n["total"] > 1000 and n["articles"]
