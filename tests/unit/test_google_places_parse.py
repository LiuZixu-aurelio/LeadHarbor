"""google_places 解析测试（无网络，喂固定 payload）。"""

from app.collectors.sources.google_places import extract_domain, parse_places_response

SAMPLE = {
    "places": [
        {
            "id": "abc123",
            "displayName": {"text": "Acme Lighting GmbH", "languageCode": "de"},
            "formattedAddress": "Musterstr. 1, 10115 Berlin, Germany",
            "websiteUri": "https://www.acme-lighting.de/",
            "internationalPhoneNumber": "+49 30 123456",
            "addressComponents": [
                {"longText": "Germany", "shortText": "DE", "types": ["country"]},
                {"longText": "Berlin", "shortText": "BE", "types": ["administrative_area_level_1"]},
            ],
            "primaryTypeDisplayName": {"text": "Lighting store"},
        },
        {
            "id": "def456",
            "displayName": {"text": "No Website Co"},
            "addressComponents": [
                {"longText": "France", "shortText": "FR", "types": ["country"]},
            ],
        },
    ],
    "nextPageToken": "tok",
}


def test_extract_domain():
    assert extract_domain("https://www.acme.de/x") == "acme.de"
    assert extract_domain("http://acme.de") == "acme.de"
    assert extract_domain(None) is None


def test_parse_places_response():
    leads = parse_places_response(SAMPLE)
    assert len(leads) == 2

    first = leads[0]
    assert first.source == "google_places"
    assert first.name == "Acme Lighting GmbH"
    assert first.domain == "acme-lighting.de"
    assert first.website == "https://www.acme-lighting.de/"
    assert first.phone == "+49 30 123456"
    assert first.country == "DE"
    assert first.industry == "Lighting store"
    assert first.raw["id"] == "abc123"

    second = leads[1]
    assert second.name == "No Website Co"
    assert second.domain is None
    assert second.country == "FR"
