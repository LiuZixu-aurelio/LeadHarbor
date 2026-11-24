# 架构说明

## 1. 分层与依赖方向

```
┌─────────────────────────────────────────────┐
│  api/v1   （薄路由：参数校验 → 调 service）    │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│  services （业务编排：组合 pipeline / 采集）   │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│  pipeline （数据加工：normalize→dedupe→...)    │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│  collectors （取数：BaseCollector 插件）       │
└─────────────────────────────────────────────┘
```

`core/` 与 `models/` 是被所有层依赖的基础层，但 `core` 不得 import 任何业务层。

### 禁止事项

- API 层出现爬取 / 解析逻辑。
- collector 内直接写 `company` / `contact`（必须过 pipeline）。
- pipeline 内发起网络请求（enrich 的网络调用走注入的 client）。
- 循环 import。

## 2. 数据流（唯一合法路径）

```
collector.collect(query) 产出 RawLead
   → 写入 lead_raw（原始 payload 存 JSONB，便于追溯与重跑）
   → pipeline.normalize   字段标准化（域名/电话/国家/邮箱格式）
   → pipeline.dedupe      去重（domain 硬键 + 公司名 fuzzy 合并）
   → pipeline.enrich      补全（官网抓邮箱 / AI 推断决策人邮箱）
   → pipeline.score       AI 匹配打分（0-100）
   → 写入 company / contact（高分自动 qualified）
```

任何新增能力都应挂在这条链路的某个环节上，不得绕开。

## 3. 扩展点

- **新增数据源**：实现 `BaseCollector` 子类 → 在 `collectors/registry.py` 注册 → 在 `docs/DATA_SOURCES.md` 补充策略与合规说明。
- **新增清洗步骤**：在 `pipeline/` 新增模块 → 在对应 service 的管道顺序中插入。
- **新增对外接口**：在 `api/v1/` 加路由，只做校验与转发。

## 4. 关键实体（详见 models）

- `lead_raw`：原始线索池（source、payload JSONB、query JSONB、status、fetched_at）
- `company`：公司（domain 唯一键、ai_score、status、source）
- `contact`：联系人（email_verified、do_not_contact、company_id）
- `outreach`：触达记录（channel、template、sent/opened/replied 时间）

## 5. 运行时组件

- FastAPI：对外 API。
- Celery Worker + Beat：定时采集与长任务。
- PostgreSQL：持久化（JSONB + pgvector 做相似客户匹配）。
- Redis：队列 broker 与缓存。
