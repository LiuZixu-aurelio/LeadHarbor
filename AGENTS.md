# AGENTS.md — LeadHarbor 项目规范

> 本文件是给所有 AI agent（Cursor / Claude / Codex 等）和人类协作者的顶层契约。
> 任何修改代码的行为都必须遵守本文件；与本文件冲突时，以本文件为准。

## 1. 项目定位

LeadHarbor AI lead intelligence platform: discover buyers, score opportunities, and grow outreach.
Current stage focuses on **data collection subsystem** (multi-source, pluggable).

目标客户类型：海外经销商 / 批发商（distributor）。

## 2. 技术栈（不可随意替换）

- 后端：Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0
- 数据库：PostgreSQL 15+（JSONB + pgvector）
- 队列：Celery + Redis
- 采集：httpx（异步）/ Playwright（动态页）/ parsel
- 测试：pytest + pytest-asyncio
- 前端：Next.js（后续阶段）

## 3. 硬性规则（agent 必须遵守）

1. 任何外部数据先落 `lead_raw`（JSONB 存原始 payload），再进清洗管道。
2. 新增数据源 = 在 `app/collectors/sources/` 新增一个 `BaseCollector` 子类并在 `registry` 注册。禁止把采集逻辑写进 API 层。
3. 所有网络请求必须：限速、超时、可重试、遵守 robots.txt。
4. 数据库模型改动必须配 Alembic 迁移，禁止手改线上表。
5. 函数必须带类型注解；外部输入必须用 Pydantic 校验。
6. 提交前：`ruff check` 与 `pytest` 必须通过。
7. 不在代码里硬编码密钥/代理；一律走 `.env` + `app.core.config.settings`。
8. 采集/入库一律 async；长任务走 Celery，API 层不得阻塞。
9. 尊重合规：内建 `do_not_contact` 标记与退订机制，邮箱先校验后入库。

## 4. 分层与依赖方向（只允许单向依赖）

```
api → services → pipeline → collectors
core / models 可被任意层依赖，但 core 不依赖业务层。
```

- 禁止 `collectors` 直接 import `api`；禁止 `models` 反向依赖 `services`。
- 禁止循环 import。依赖通过参数注入，不用全局可变单例。

## 5. 目录职责

详见 `docs/ARCHITECTURE.md`。摘要：

- `app/core/`：配置、DB session、日志、异常（不依赖业务）
- `app/models/`：SQLAlchemy 模型
- `app/schemas/`：Pydantic DTO（Create / Update / Out / Internal 分离）
- `app/api/v1/`：路由层（薄，只做校验 + 调 service）
- `app/services/`：业务编排（组合 pipeline）
- `app/collectors/`：采集插件（`base.py` + `registry.py` + `sources/`）
- `app/pipeline/`：清洗管道（normalize / dedupe / enrich / score）
- `app/tasks/`：Celery 任务

## 6. 提交规范（Conventional Commits）

`feat: / fix: / refactor: / test: / docs: / chore:`
示例：`feat(collectors): add google places collector`
