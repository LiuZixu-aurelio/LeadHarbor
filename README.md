# LeadHarbor — AI Lead Intelligence Platform

采集潜在买家 → AI 清洗/打分 → CRM 沉淀 → 多渠道补全联系方式。
Collect potential buyers → AI clean/score → store in CRM → enrich contacts across channels.

**中文** | [English](#english)

---

## 中文

LeadHarbor 是一个面向外贸 / B2B 出海的**线索采集与客户管理平台**，当前聚焦数据采集子系统：多渠道、可插拔的采集器 + 统一清洗入库 + 客户详情多渠道补全。

### 功能特性

- **多数据源采集**：2GIS、Google Places、Google Search、Yandex Maps、OpenStreetMap、Wikidata、OpenCorporates、官网抓取、AI 网页提取、AI 研究员。
- **批量采集 + 轮次**：按国家批量，可设置采集轮次，每轮自动翻页抓取不同结果并去重。
- **AI 一键采集**：关键词 → Google 搜索发现页面 → AI 抽取 → 自动入库。
- **官网优先深度补全**：详情页「官网优先深度补全」会爬取官网最多 20 页（联系/关于/支持优先，且同域普通页面），从任意页面文本识别邮箱与电话格式，并合并多邮箱、多电话为联系人。
- **多渠道补全**：官网 + Google Search/Places + 2GIS + Yandex + OSM，单渠道失败不影响其他渠道。
- **数据管理**：客户列表/详情、生命周期状态、CSV 导入导出、原始线索查看。
- **可插拔采集器**：在 `app/collectors/registry.py` 注册即可扩展。
- **前端**：Next.js App Router 管理台，含采集、客户库、设置页（运行时配置密钥并测试连通性）。

### 采集渠道

| 采集器 | 标识 | 需要密钥 | 说明 |
|---|---|---|---|
| 2GIS | `2gis` | `TWOGIS_API_KEY` | 中亚 / 俄语区地图商家 |
| Google Places | `google_places` | `GOOGLE_PLACES_API_KEY` | Places (New) Text Search |
| Google Search | `google_search` | `GOOGLE_SEARCH_API_KEY` / `GOOGLE_SEARCH_CX` | 按关键词发现官网 |
| Yandex Maps | `yandex_maps` | `YANDEX_GEOSEARCH_API_KEY` | 俄语区 / 中亚商家 |
| OpenStreetMap | `openstreetmap` | 无 | Overpass，公共实例限流 |
| Wikidata | `wikidata` | 无 | 公开公司实体 |
| OpenCorporates | `opencorporates` | `OPENCORPORATES_API_TOKEN` | 公司注册数据 |
| 官网抓取 | `website` | 无 | 站点多页抓邮箱/电话 |
| AI 网页提取 | `ai_extractor` | `OPENAI_API_KEY`（+ 搜索密钥） | LLM 结构化抽取网页线索 |
| AI 研究员 | `ai_researcher` | `OPENAI_API_KEY` | LLM 生成候选公司名单（需核实） |

> AI 模型支持任意 OpenAI 兼容接口（如 DeepSeek）：配置 `OPENAI_BASE_URL` + `OPENAI_MODEL` 即可。

### 技术栈

- Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0 / asyncpg
- PostgreSQL 15+（JSONB）/ Celery + Redis
- 采集：httpx（异步）/ parsel / Playwright
- 前端：Next.js (App Router) / TypeScript

### 快速开始（Docker Compose，推荐）

```bash
# 1. 准备环境变量（务必修改 POSTGRES_PASSWORD 与各项密钥）
cp .env.example .env

# 2. 构建并启动（自动执行数据库迁移）
docker compose up -d --build

# 3. 查看状态 / 日志
docker compose ps
docker compose logs -f api

# 4. 打开 API 文档
open http://localhost:8000/docs
```

前端（Next.js）：

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

开发服务器会把 `/api/backend/*` 代理到本机 FastAPI。

### 本地开发（不用容器跑应用）

```bash
uv sync --extra dev
docker compose up -d db redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 测试 / lint
uv run pytest
uv run ruff check app alembic tests
```

### 主要接口

- `GET  /health` — 健康检查
- `GET  /api/v1/collect/config` — 采集器元数据与模板
- `POST /api/v1/collect` — 单次采集
- `POST /api/v1/collect/batch` — 同步按国家批量
- `POST /api/v1/collect/batch/async` — 异步批量（Celery，返回任务轮询）
- `GET  /api/v1/collect/jobs` / `/{id}` — 批量任务进度
- `POST /api/v1/collect/ai-pipeline` — AI 搜索 → 抽取 → 入库
- `GET  /api/v1/companies` — 客户列表（按 AI 分排序）
- `GET  /api/v1/companies/{id}` — 客户详情（含联系人）
- `PATCH /api/v1/companies/{id}` — 更新生命周期状态
- `POST /api/v1/companies/{id}/enrich` — 多渠道补全联系方式
- `GET  /api/v1/companies/export` / `POST /api/v1/companies/import` — CSV 导出 / 导入
- `GET  /api/v1/leads` — 原始线索
- `GET  /api/v1/stats` — 统计
- `GET/PUT /api/v1/settings/keys`、`POST /api/v1/settings/test` — 运行时密钥配置与连通性测试

采集示例：

```bash
curl -X POST http://localhost:8000/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"source":"google_places","query":{"text_query":"LED lighting distributor","region":"DE"},"max_items":20}'
```

### 项目结构

```
app/
├── core/        # 配置、DB、日志、异常
├── models/      # SQLAlchemy 模型
├── schemas/     # Pydantic DTO
├── api/v1/      # 路由层（collectors / leads / settings）
├── services/    # 业务编排（ingest / 补全 / 导入导出）
├── collectors/  # ★ 采集插件（base + registry + sources）
├── pipeline/    # ★ 清洗管道（normalize / dedupe / enrich / score）
└── tasks/       # Celery 任务
frontend/        # Next.js 管理台
docs/            # 架构、规范、数据源说明
```

### 数据流

```
collector.collect() → lead_raw(JSONB) → normalize → dedupe → enrich → score → company / contact
```

### 合规提示

- 所有网络请求限速、超时、可重试，并遵守目标站 `robots.txt`。
- 使用第三方数据源请遵守其服务条款与额度限制。
- AI 生成 / 抽取的结果存在误差，触达前请人工核实。

### 开发规范

- 顶层规则：[`AGENTS.md`](./AGENTS.md)
- 架构与数据流：[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- 编码规范：[`docs/CONVENTIONS.md`](./docs/CONVENTIONS.md)
- 数据源与合规：[`docs/DATA_SOURCES.md`](./docs/DATA_SOURCES.md)

---

## English

LeadHarbor is a **lead collection and CRM platform** for B2B / export teams. The current focus is the data-collection subsystem: pluggable multi-source collectors, a unified ingest pipeline, and multi-channel contact enrichment on the company detail page.

### Features

- **Multi-source collection**: 2GIS, Google Places, Google Search, Yandex Maps, OpenStreetMap, Wikidata, OpenCorporates, website crawler, AI extractor, AI researcher.
- **Batch + rounds**: collect per country with configurable rounds; each round pages deeper and de-duplicates.
- **One-click AI pipeline**: keyword → Google Search discovers pages → AI extracts structured leads → auto-ingest.
- **Website-first deep enrichment**: crawls up to 20 pages of a company site (contact/about/support first, plus other same-domain pages), extracts emails/phones from any page text, and stores multiple emails/phones as contacts.
- **Multi-channel enrichment**: website + Google Search/Places + 2GIS + Yandex + OSM; a failing channel never blocks the others.
- **Data management**: company list/detail, lifecycle status, CSV import/export, raw lead inspection.
- **Pluggable collectors**: register in `app/collectors/registry.py` to extend.
- **Frontend**: Next.js admin console with collection, customer library, and a settings page for runtime keys + connectivity tests.

### Collectors

| Collector | name | Key required | Notes |
|---|---|---|---|
| 2GIS | `2gis` | `TWOGIS_API_KEY` | Central Asia / CIS maps |
| Google Places | `google_places` | `GOOGLE_PLACES_API_KEY` | Places (New) Text Search |
| Google Search | `google_search` | `GOOGLE_SEARCH_API_KEY` / `GOOGLE_SEARCH_CX` | Discover sites by keyword |
| Yandex Maps | `yandex_maps` | `YANDEX_GEOSEARCH_API_KEY` | CIS / Central Asia |
| OpenStreetMap | `openstreetmap` | none | Overpass, public rate limits |
| Wikidata | `wikidata` | none | Public company entities |
| OpenCorporates | `opencorporates` | `OPENCORPORATES_API_TOKEN` | Company registry data |
| Website | `website` | none | Multi-page email/phone crawl |
| AI extractor | `ai_extractor` | `OPENAI_API_KEY` (+ search key) | LLM structured extraction |
| AI researcher | `ai_researcher` | `OPENAI_API_KEY` | LLM-suggested names (verify) |

> Any OpenAI-compatible provider (e.g. DeepSeek) works: set `OPENAI_BASE_URL` + `OPENAI_MODEL`.

### Stack

- Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0 / asyncpg
- PostgreSQL 15+ (JSONB) / Celery + Redis
- Scraping: httpx (async) / parsel / Playwright
- Frontend: Next.js (App Router) / TypeScript

### Quick start (Docker Compose, recommended)

```bash
cp .env.example .env            # then edit POSTGRES_PASSWORD and API keys
docker compose up -d --build    # runs DB migrations automatically
docker compose ps
open http://localhost:8000/docs
```

Frontend:

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

The dev server proxies `/api/backend/*` to the local FastAPI app.

### Local development (run the app outside containers)

```bash
uv sync --extra dev
docker compose up -d db redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

uv run pytest
uv run ruff check app alembic tests
```

### API overview

- `GET  /health`
- `GET  /api/v1/collect/config` — collector metadata and templates
- `POST /api/v1/collect` — single collection
- `POST /api/v1/collect/batch` — synchronous per-country batch
- `POST /api/v1/collect/batch/async` — async batch (Celery, pollable job)
- `GET  /api/v1/collect/jobs` / `/{id}` — batch job progress
- `POST /api/v1/collect/ai-pipeline` — AI search → extract → ingest
- `GET  /api/v1/companies` / `/{id}` / `PATCH /{id}`
- `POST /api/v1/companies/{id}/enrich` — multi-channel contact enrichment
- `GET  /api/v1/companies/export` / `POST /api/v1/companies/import`
- `GET  /api/v1/leads`, `GET /api/v1/stats`
- `GET/PUT /api/v1/settings/keys`, `POST /api/v1/settings/test`

Example:

```bash
curl -X POST http://localhost:8000/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"source":"google_places","query":{"text_query":"LED lighting distributor","region":"DE"},"max_items":20}'
```

### Project structure

```
app/
├── core/        # config, DB, logging, errors
├── models/      # SQLAlchemy models
├── schemas/     # Pydantic DTOs
├── api/v1/      # routers (collectors / leads / settings)
├── services/    # orchestration (ingest / enrichment / import-export)
├── collectors/  # ★ plugins (base + registry + sources)
├── pipeline/    # ★ normalize / dedupe / enrich / score
└── tasks/       # Celery tasks
frontend/        # Next.js admin console
docs/            # architecture, conventions, data sources
```

### Data flow

```
collector.collect() → lead_raw(JSONB) → normalize → dedupe → enrich → score → company / contact
```

### Compliance

- All requests are rate-limited, time-limited, retried, and respect `robots.txt`.
- Follow each third-party source's terms of service and quotas.
- AI-generated/extracted data may be inaccurate — verify before outreach.

### Docs

- [`AGENTS.md`](./AGENTS.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- [`docs/CONVENTIONS.md`](./docs/CONVENTIONS.md)
- [`docs/DATA_SOURCES.md`](./docs/DATA_SOURCES.md)

---

## License

Released under the [MIT License](./LICENSE).
