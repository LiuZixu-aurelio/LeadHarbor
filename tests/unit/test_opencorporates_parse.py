"""OpenCorporates 解析测试（无网络）。"""

from app.collectors.sources.opencorporates import parse_opencorporates_response


def test_parse_opencorporates_response():
    leads = parse_opencorporates_response(
        {
            "results": {
                "companies": [
                    {
                        "company": {
                            "name": "Almaty Trade LLP",
                            "company_number": "12345",
                            "jurisdiction_code": "kz",
                            "opencorporates_url": "https://opencorporates.com/companies/kz/12345",
                            "website_url": "https://www.almatytrade.kz",
                            "industry_codes": [{"name": "Wholesale trade"}],
                        }
                    }
                ]
            }
        }
    )
    assert len(leads) == 1
    assert leads[0].name == "Almaty Trade LLP"
    assert leads[0].domain == "almatytrade.kz"
    assert leads[0].country == "KZ"
    assert leads[0].industry == "Wholesale trade"
    assert leads[0].raw["company_number"] == "12345"
