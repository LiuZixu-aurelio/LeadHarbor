"""AI 网页提取解析测试（无网络）。"""

from app.collectors.sources.ai_extractor import (
    html_to_text,
    parse_ai_extractor_response,
)


def test_parse_plain_json_array():
    text = '[{"name":"Acme","website":"https://acme.kz","email":"a@acme.kz","phone":"+7701","address":"Almaty","industry":"Lighting"}]'
    leads = parse_ai_extractor_response(text)
    assert len(leads) == 1
    assert leads[0].name == "Acme"
    assert leads[0].domain == "acme.kz"
    assert leads[0].email == "a@acme.kz"


def test_parse_fenced_json():
    text = '```json\n[{"name":"Beta LLC"}]\n```'
    leads = parse_ai_extractor_response(text)
    assert len(leads) == 1
    assert leads[0].name == "Beta LLC"


def test_parse_skips_items_without_name():
    leads = parse_ai_extractor_response('[{"email":"x@y.z"},{"name":"Gamma"}]')
    assert [lead.name for lead in leads] == ["Gamma"]


def test_parse_garbage_returns_empty():
    assert parse_ai_extractor_response("sorry, no structured data") == []


def test_html_to_text_strips_tags():
    text = html_to_text("<html><body><h1>Acme</h1><p>phone +7701</p></body></html>")
    assert "Acme" in text and "+7701" in text
