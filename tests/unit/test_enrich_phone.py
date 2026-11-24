"""官网增强：电话/邮箱提取测试（无网络）。"""

from app.pipeline.enrich import extract_emails, extract_phone


def test_extract_phone_from_tel():
    html = '<a href="tel:+7 (701) 123-45-67">call</a>'
    phone = extract_phone(html)
    assert phone is not None
    assert phone.startswith("+")


def test_extract_phone_none():
    assert extract_phone("<div>no phone here</div>") is None


def test_extract_emails_still_works():
    assert extract_emails('mailto:Sales@Acme.KZ') == ["sales@acme.kz"]
