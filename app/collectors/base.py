"""采集器抽象基类：新增渠道只需继承并实现 `collect`。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from app.schemas.lead import RawLead


class BaseCollector(ABC):
    """所有采集器的统一接口。

    约定：
    - `collect` 是异步生成器，边采边产出，便于流式入库与限流。
    - query 的结构由各采集器自行约定，见 `docs/DATA_SOURCES.md`。
    - 采集器只负责「取数 + 解析」，不做去重/打分（交给 pipeline）。
    """

    source_name: ClassVar[str]
    # 面向用户展示的名称
    label: ClassVar[str] = ""
    # 需要的环境变量密钥名（为空表示无需密钥）
    requires_key: ClassVar[str] = ""
    # 默认区域（ISO 3166-1 alpha-2）
    default_region: ClassVar[str] = "KZ"
    # 支持的区域列表（ISO 3166-1 alpha-2）
    supported_regions: ClassVar[list[str]] = []

    @abstractmethod
    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        raise NotImplementedError
