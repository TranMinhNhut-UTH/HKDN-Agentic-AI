import pytest
from shared.config import Settings
from shared.rss import RSSReader, normalize, deduplicate, filter_articles, canonical_url


def test_offline_sources_and_filter():
    reader = RSSReader(Settings())
    articles = reader.fetch("bbc")
    assert len(articles) == 2 and all(a.simulated for a in articles)
    assert len(filter_articles(articles, "giáo dục")) == 1
    assert filter_articles(articles, "quantumxyz") == []


def test_normalization_and_duplicates():
    a = normalize({"title": "<b>AI</b>", "link": "https://example.com/a?utm_source=x#hi", "summary": "a &amp; b"}, "test")
    b = normalize({"title": "ai", "link": "https://example.com/b"}, "test")
    assert str(a.url) == "https://example.com/a"
    assert a.excerpt == "a & b"
    assert len(deduplicate([a, a, b])) == 1


def test_no_live_fallback_and_invalid_urls():
    with pytest.raises(ValueError):
        Settings(mode="live")
    with pytest.raises(ValueError):
        canonical_url("javascript:alert(1)")
    with pytest.raises(ValueError):
        RSSReader(Settings()).fetch("https://localhost")
