"""Yandex / Wikidata 解析测试（无网络）。"""

from app.collectors.sources.wikidata import parse_wikidata_bindings
from app.collectors.sources.yandex_maps import parse_yandex_response


def test_parse_yandex_response():
    leads = parse_yandex_response(
        {
            "features": [
                {
                    "properties": {
                        "CompanyMetaData": {
                            "name": "Almaty Lighting LLP",
                            "url": "https://almaty-lighting.kz",
                            "Phones": [{"formatted": "+7 727 000 1111"}],
                            "Categories": [{"name": "Светотехника"}],
                        }
                    }
                }
            ]
        },
        "KZ",
    )
    assert len(leads) == 1
    assert leads[0].name == "Almaty Lighting LLP"
    assert leads[0].domain == "almaty-lighting.kz"
    assert leads[0].phone == "+7 727 000 1111"
    assert leads[0].country == "KZ"


def test_parse_wikidata_bindings():
    leads = parse_wikidata_bindings(
        [
            {
                "itemLabel": {"value": "KazMunayGas"},
                "website": {"value": "https://kmg.kz"},
                "industryLabel": {"value": "energy industry"},
                "inception": {"value": "2002"},
            }
        ],
        "KZ",
    )
    assert len(leads) == 1
    assert leads[0].name == "KazMunayGas"
    assert leads[0].domain == "kmg.kz"
    assert leads[0].country == "KZ"
