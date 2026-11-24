"""website 解析测试（无网络，喂固定 HTML）。"""

from app.collectors.sources.website import parse_website_html

SAMPLE_HTML = """
<html>
  <head>
    <title>Acme Home | Welcome</title>
    <meta property="og:site_name" content="Acme Distribution" />
  </head>
  <body>
    <p>Contact us: sales@acme.kz or support@acme.kz</p>
    <a href="mailto:info@acme.kz">Email</a>
    <a href="tel:+7 727 123 4567">Call</a>
    <a href="/contacts">Контакты</a>
  </body>
</html>
"""


def test_parse_website_html():
    parsed = parse_website_html(SAMPLE_HTML, "https://acme.kz/")
    assert parsed["name"] == "Acme Distribution"
    assert "sales@acme.kz" in parsed["emails"]
    assert "info@acme.kz" in parsed["emails"]
    assert parsed["phones"][0].startswith("+7")
    assert any(link == "https://acme.kz/contacts" for link in parsed["contact_links"])


def test_parse_extracts_plain_text_phone_without_tel_link():
    html = "<html><body><p>Call +7 701 123 4567 or +7 701 999 8877</p></body></html>"
    parsed = parse_website_html(html, "https://acme.kz")
    assert len(parsed["phones"]) >= 2


def test_parse_collects_all_links_for_deep_crawl():
    html = """<html><body>
      <a href="/contact">Contact</a><a href="/services">Services</a>
      <a href="/policy.pdf">Policy</a><a href="mailto:x@y.kz">mail</a>
    </body></html>"""
    parsed = parse_website_html(html, "https://acme.kz")
    assert any("contact" in link for link in parsed["contact_links"])
    assert any("services" in link for link in parsed["all_links"])
    assert not any("mailto" in link for link in parsed["all_links"])
