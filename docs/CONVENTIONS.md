# 编码规范

## 通用

- Python 3.11+，全量类型注解；对外函数标注返回类型。
- 格式化 / 检查：ruff（line-length = 100）。禁止裸 `except:`。
- 命名：模块 `snake_case`；类 `PascalCase`；常量 `UPPER_SNAKE`。
- 禁止循环 import；用依赖注入而非全局可变单例。

## 异步与并发

- 采集 / IO 一律 async，复用 `httpx.AsyncClient`（不每次新建）。
- 采集器内必须做并发控制（`asyncio.Semaphore`），禁止无上限 `gather`。
- 长任务走 Celery，API 层不得阻塞。

## 数据模型

- 公司 / 联系人 / 触达记录三层分离，不合并。
- 灵活字段用 JSONB，但高频查询字段单独成列并建索引。
- 去重硬键：`company.domain`（唯一索引）。

## Schema 分层

- `app/schemas/` 区分 `Create` / `Update` / `Out` / `Internal`，不复用一个模型到处用。

## 日志与错误

- 统一走 `app.core.logging`；禁止 `print`。
- 网络请求失败要记录 URL + 状态码 + 重试次数。

## 测试

- 采集器解析逻辑必须有单测（喂 HTML fixture，断言解析结果）。
- 清洗管道（去重 / 标准化）必须有单测。
- 外部网络请求在测试中必须 mock，不真连网。
- 运行：`pytest`（`asyncio_mode = auto`）。

## 提交规范（Conventional Commits）

`feat: / fix: / refactor: / test: / docs: / chore:`
示例：`feat(collectors): add google places collector`

## 提交前检查

```bash
ruff check .
pytest
```
