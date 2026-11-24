"""2GIS meta 错误检测测试（无网络）。"""

import pytest

from app.collectors.sources.twogis import check_twogis_meta


def test_twogis_meta_ok():
    check_twogis_meta({"meta": {"code": 200}, "result": {"items": []}})


def test_twogis_meta_error_raises():
    with pytest.raises(RuntimeError) as exc:
        check_twogis_meta(
            {"meta": {"code": 403, "error": {"message": "Authorization error"}}}
        )
    assert "403" in str(exc.value)
    assert "Authorization" in str(exc.value)
