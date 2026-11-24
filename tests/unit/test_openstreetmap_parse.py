"""OpenStreetMap 解析测试（无网络）。"""

from app.collectors.sources.openstreetmap import parse_overpass_response


def test_parse_overpass_response():
    leads = parse_overpass_response(
        {
            "elements": [
                {
                    "type": "node",
                    "id": 1,
                    "tags": {
                        "name": "Almaty Lighting",
                        "website": "https://almaty-lighting.kz",
                        "contact:email": "sales@almaty-lighting.kz",
                        "contact:phone": "+7 727 123 4567",
                        "shop": "lighting",
                    },
                },
                {"type": "node", "id": 2, "tags": {"shop": "hardware"}},
            ]
        },
        "KZ",
    )
    assert len(leads) == 1
    assert leads[0].name == "Almaty Lighting"
    assert leads[0].domain == "almaty-lighting.kz"
    assert leads[0].email == "sales@almaty-lighting.kz"
    assert leads[0].country == "KZ"
    assert leads[0].industry == "lighting"
