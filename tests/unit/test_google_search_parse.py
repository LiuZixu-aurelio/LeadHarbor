"""google_search 解析测试（无网络，喂固定 payload）。"""

from app.collectors.sources.google_search import (
    _clean_title,
    parse_google_search_response,
)

SAMPLE = {
    "items": [
        {
            "title": "Almaty Lighting | Официальный сайт",
            "link": "https://www.almaty-lighting.kz/",
            "snippet": "LED lighting distributor in Kazakhstan",
        },
        {
            "title": "Tashkent Trade Co - Wholesale supplier",
            "link": "http://tashkenttrade.uz",
        },
    ]
}


def test_clean_title():
    assert _clean_title("Acme | Official") == "Acme"
    assert _clean_title("Foo - Bar") == "Foo"
    assert _clean_title(None) is None


def test_parse_google_search_response():
    leads = parse_google_search_response(SAMPLE)
    assert len(leads) == 2

    first = leads[0]
    assert first.source == "google_search"
    assert first.name == "Almaty Lighting"
    assert first.domain == "almaty-lighting.kz"
    assert first.website == "https://www.almaty-lighting.kz/"

    second = leads[1]
    assert second.name == "Tashkent Trade Co"
    assert second.domain == "tashkenttrade.uz"
