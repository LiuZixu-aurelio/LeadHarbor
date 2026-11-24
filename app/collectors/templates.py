"""采集关键词模板：按行业给出可直接用的搜索词，配合按国家批量采集。

这些只是「预设关键词」，采集器仍按各自的 query 解释（text_query）。
中亚市场建议英文/俄文关键词，必要时可在前端手动改写。
"""

from __future__ import annotations

COLLECT_TEMPLATES: list[dict[str, str]] = [
    {
        "key": "led",
        "label": "LED 照明",
        "keyword": "LED lighting distributor",
        "description": "照明经销/批发商，中亚需求稳定",
    },
    {
        "key": "solar",
        "label": "光伏/储能",
        "keyword": "solar energy equipment distributor",
        "description": "太阳能、储能设备经销商",
    },
    {
        "key": "hvac",
        "label": "暖通空调",
        "keyword": "HVAC equipment distributor",
        "description": "空调、通风、制冷批发商",
    },
    {
        "key": "furniture",
        "label": "家具批发",
        "keyword": "furniture wholesale distributor",
        "description": "家具、家居用品批发",
    },
    {
        "key": "autoparts",
        "label": "汽车配件",
        "keyword": "auto parts distributor",
        "description": "汽配经销商，中亚市场活跃",
    },
    {
        "key": "electronics",
        "label": "消费电子",
        "keyword": "consumer electronics distributor",
        "description": "电子、小家电批发商",
    },
    {
        "key": "building",
        "label": "建材",
        "keyword": "building materials distributor",
        "description": "建材、五金批发",
    },
    {
        "key": "machinery",
        "label": "工业机械",
        "keyword": "industrial machinery supplier",
        "description": "工业设备与机械供应商",
    },
]
