"""运行时配置服务单测（无 DB）。"""

from app.services.settings_service import _mask, status_list


def test_mask():
    assert _mask("") == ""
    assert _mask("abc") == "••••"
    assert _mask("sk-1234567890abcd") == "••••abcd"


def test_status_list_shape():
    items = status_list()
    names = {item["name"] for item in items}
    assert "TWOGIS_API_KEY" in names
    assert "AI_RESEARCHER_ENABLED" in names
    for item in items:
        assert set(item) >= {"name", "label", "group", "secret", "configured"}
