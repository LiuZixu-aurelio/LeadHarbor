"""normalize 纯函数测试。"""

from app.pipeline.normalize import (
    is_valid_email,
    normalize_country,
    normalize_domain,
    normalize_email,
    normalize_lead,
    normalize_phone,
)
from app.schemas.lead import RawLead


def test_normalize_domain_from_url_and_bare():
    assert normalize_domain("https://www.Example.com/about") == "example.com"
    assert normalize_domain("Example.COM/path") == "example.com"
    assert normalize_domain("www.foo.io:8080") == "foo.io"
    assert normalize_domain(None) is None


def test_normalize_email():
    assert normalize_email("  Foo@Bar.COM ") == "foo@bar.com"
    assert normalize_email("not-an-email") is None
    assert is_valid_email("a@b.co") is True
    assert is_valid_email("bad") is False


def test_normalize_phone():
    assert normalize_phone("+49 (0) 30 1234-5678") == "+4903012345678"
    assert normalize_phone("0049 30 123") == "+4930123"
    assert normalize_phone(None) is None


def test_normalize_country():
    assert normalize_country("Germany") == "DE"
    assert normalize_country("de") == "DE"
    assert normalize_country("united states") == "US"
    assert normalize_country(None) is None


def test_normalize_lead_full():
    lead = RawLead(
        source="google_places",
        name="  Acme GmbH ",
        website="https://www.acme.de/contact",
        email="Info@Acme.DE",
        phone="0049 30 123",
        country="germany",
        industry=" Lighting ",
    )
    out = normalize_lead(lead)
    assert out.name == "Acme GmbH"
    assert out.domain == "acme.de"
    assert out.email == "info@acme.de"
    assert out.country == "DE"
    assert out.industry == "Lighting"
    assert out.phone == "+4930123"
