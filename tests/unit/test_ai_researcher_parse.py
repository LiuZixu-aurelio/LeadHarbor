"""AI 研究员响应解析测试（无 API 调用）。"""

from app.collectors.sources.ai_researcher import parse_ai_researcher_response


def test_parse_ai_researcher_response():
    leads = parse_ai_researcher_response(
        '[{"name":"Almaty Solar LLP","website":"https://www.almatysolar.kz",'
        '"industry":"Solar","description":"光伏经销商","confidence":75}]'
    )
    assert len(leads) == 1
    assert leads[0].source == "ai_researcher"
    assert leads[0].domain == "almatysolar.kz"
    assert leads[0].raw["ai_generated"] is True


def test_parse_ai_researcher_invalid_json():
    assert parse_ai_researcher_response("not json") == []
