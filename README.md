# LeadHarbor — AI Lead Intelligence Platform

采集潜在买家 → AI 清洗/打分 → CRM 沉淀 → 自动化外联。
当前阶段聚焦 **数据采集子系统**（多渠道、可插拔），目标客户为海外经销商 / 批发商。

## 技术栈

- Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0
- PostgreSQL 15+（JSONB + pgvector）/ Celery + Redis
- 采集：httpx（异步）/ Playwright / parsel

## 快速开始（Docker Compose，推荐）

一键拉起 API + PostgreSQL(pgvector) + Redis + Celery worker，并自动执行数据库迁移。

```bash
# 1. 准备环境变量（务必修改 POSTGRES_PASSWORD）
cp .env.example .env

# 2. 构建并启动全部服务
docker compose up -d --build

# 3. 查看日志 / 服务状态
docker compose ps
docker compose logs -f api

# 4. 访问 API 文档
open http://localhost:8000/docs
```

说明：
- `migrate` 服务会在 DB 健康后自动 `alembic upgrade head`；`api` / `worker` 等它成功后再启动。
- 数据持久化在 Docker 卷 `pgdata`、`redisdata` 中，重启容器不丢。
- Postgres / Redis 仅在 `127.0.0.1` 暴露端口，供本机工具连接，不对外网开放。
- 迁移到新服务器时，复制项目 + `.env`，`docker compose up -d --build` 即可；已有数据通过 `pg_dump`/`pg_restore` 备份恢复。

常用运维：

```bash
docker compose down            # 停止（保留数据卷）
docker compose down -v         # 停止并删除数据卷（清空数据，慎用）
docker compose run --rm migrate alembic revision --autogenerate -m "msg"  # 生成迁移
docker compose exec db psql -U ${POSTGRES_USER:-leadharbor} -d ${POSTGRES_DB:-leadharbor}   # 进数据库
```

## 前端开发

前端位于 `frontend/`，使用 Next.js App Router。先启动后端 API（默认 `http://localhost:8000`），再运行：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000`。开发服务器会将 `/api/backend/*` 请求代理到本机 FastAPI；后端不可用时，概览会展示演示数据。视觉令牌、组件约束和响应式规则见 [`frontend/DESIGN_SYSTEM.md`](./frontend/DESIGN_SYSTEM.md)。

## 本地开发（可选，不用容器跑应用）

若只想用本机 Python 跑应用、仅用容器跑 DB/Redis：

```bash
# 用 uv 管理项目 Python（不改系统 Python）
uv sync --extra dev

# 仅启动数据库与缓存
docker compose up -d db redis

# 首次建表
uv run alembic upgrade head

# 启动 API（自动重载）
uv run uvicorn app.main:app --reload

# 测试 / lint
uv run pytest
uv run ruff check .
```


## 接口速览

- `GET  /health` — 健康检查
- `GET  /api/v1/collectors` — 可用采集器
- `POST /api/v1/collect` — 触发一次采集（示例见下）
- `GET  /api/v1/companies?min_score=60` — 客户列表（按 AI 分排序）
- `GET  /api/v1/leads` — 原始线索列表
- `GET  /api/v1/stats` — 统计

触发采集示例：

```bash
curl -X POST http://localhost:8000/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"source":"google_places","query":{"text_query":"LED lighting distributor","region":"DE"},"max_items":20}'
```

> 长批量采集建议走 Celery：`app.tasks.crawl.run_collection_task`。


## 项目结构

```
app/
├── core/        # 配置、DB、日志、异常
├── models/      # SQLAlchemy 模型
├── schemas/     # Pydantic DTO
├── api/v1/      # 路由层
├── services/    # 业务编排
├── collectors/  # ★ 采集插件（base + registry + sources）
├── pipeline/    # ★ 清洗管道（normalize/dedupe/enrich/score）
└── tasks/       # Celery 任务
docs/            # 架构、规范、数据源说明
```

## 开发规范

所有协作者（人类和 AI agent）必须遵守：

- 顶层规则：[`AGENTS.md`](./AGENTS.md)
- 架构与数据流：[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- 编码规范：[`docs/CONVENTIONS.md`](./docs/CONVENTIONS.md)
- 数据源与合规：[`docs/DATA_SOURCES.md`](./docs/DATA_SOURCES.md)

## 数据流

```
collector.collect() → lead_raw(JSONB) → normalize → dedupe → enrich → score → company/contact
```
