# 数据源策略与合规

> 本文档记录每个采集渠道的实现策略与合规要求。
> 新增采集源时必须同步补充本文件。

## 采集源总览

| 采集器 | 技术手段 | 产出 | 优先级 | 合规风险 |
| --- | --- | --- | --- | --- |
| `google_maps` | Google Places API（官方） | 商家名/地址/电话/官网 | 高（起步首选） | 低 |
| `b2b_directory` | httpx + parsel 解析目录页 | 公司+品类+国家 | 中 | 低 |
| `web_scraper` | 访问客户官网抓 mailto/contact 页 | 邮箱、业务描述 | 高（增强必用） | 低 |
| `customs` | 海关数据（需授权 API） | 真实采购记录 | 低（付费） | 中 |
| `linkedin` | 官方 API / 第三方数据商 | 决策人+职位 | 低（后期） | 高（反爬+ToS） |

当前优先跑通：**Google Places 找公司 + 官网抓取补邮箱**（合规、稳定、能形成闭环）。

## 已实现采集器：Google Places

实现文件：`app/collectors/sources/google_places.py`。

- 使用官方 Places API (New) Text Search，不爬取 Google Maps 页面。
- 环境变量：`GOOGLE_PLACES_API_KEY`。
- `query` 必填 `text_query`，可选 `region`（ISO 3166-1 alpha-2）、`language`、`max_items`（1–60）。
- 每页最多 20 条；Places 页 token 会等待后再继续请求。
- 返回商家名称、网站/域名、电话、国家、主类别，完整原始响应字段保留在 `lead_raw.payload`。
- API 计费/配额以 Google Cloud 项目启用情况为准；正式使用前确认 Places API 条款与成本。

示例：`{"text_query":"LED lighting distributor","region":"DE","max_items":20}`。

## 通用合规红线

- 遵守目标站 `robots.txt`（用 `urllib.robotparser` 判定）。
- 单域名限速（建议 1–2 req/s），全局并发上限通过 `CRAWLER_MAX_CONCURRENCY` 控制。
- 记录数据来源与抓取时间，保留可审计轨迹（写入 `lead_raw.source` / `fetched_at`）。
- 邮箱入库前先校验格式与 MX/有效性，无效的不进触达队列。
- 内建 `do_not_contact` 标记，退订永久屏蔽。
- 面向欧盟客户：邮件需符合 GDPR，必须带退订链接并记录 consent。
- LinkedIn：禁止硬爬，优先官方接口/数据商，避免账号封禁。

## 待补充（每个源的实现细节）

- [ ] `google_maps`：查询参数、配额、字段映射
- [ ] `b2b_directory`：目标目录清单、分页规则、解析选择器
- [ ] `web_scraper`：contact 页发现策略、邮箱提取正则、去噪
- [ ] `enrich`：AI 决策人邮箱推断规则

## 环境变量（相关）

```
GOOGLE_PLACES_API_KEY=
CRAWLER_USER_AGENT=LeadHarborBot/0.1 (+contact@example.com)
CRAWLER_MAX_CONCURRENCY=5
```

## 采集源：2GIS（双GIS）【新增】

实现文件：`app/collectors/sources/twogis.py`，注册名：`2gis`。

- 使用官方 Catalog API `https://catalog.api.2gis.com/3.0/items`，环境变量：`TWOGIS_API_KEY`。
- 适合市场：哈萨克斯坦（KZ）、乌兹别克斯坦（UZ）、吉尔吉斯斯坦（KG）、塔吉克斯坦（TJ）、土库曼斯坦（TM），以及俄罗斯（RU）。
- `query` 必填 `text_query`，可选 `region`（ISO 3166-1 alpha-2）、`region_id`、`max_items`（1–200）。
- 每页最多 50 条；通过 `page` 分页，复用通用 `RateLimiter`、`fetch_with_retry` 与 `crawler_timeout_seconds`。
- 返回公司名称、电话、官网、邮箱、国家代码、行业（rubrics），完整原始响应保留在 `lead_raw.payload`。
- 未配置 `TWOGIS_API_KEY` 时会抛出清晰报错，而非静默返回空结果。

### 示例请求

```bash
curl -X POST http://localhost:8000/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"source":"2gis","query":{"text_query":"LED distributor Almaty","region":"KZ"},"max_items":20}'
```

## 中亚市场采集建议

中亚国家的 Google Maps 覆盖较弱，**2GIS 才是主流地图与商家数据源**，建议优先使用 `2gis`，Google Places 作为补充：

| 渠道 | 优先级 | 适用场景 | 需密钥 |
| --- | --- | --- | --- |
| `2gis` | 高 | KZ / UZ / KG / TJ / TM / RU 公司、电话、官网 | `TWOGIS_API_KEY` |
| `google_places` | 中 | 英文/俄语区补充，国际品牌 | `GOOGLE_PLACES_API_KEY` |

## 环境变量（相关）

```
TARGET_COUNTRIES=KZ,UZ,KG,TJ,TM
DEFAULT_REGION=KZ
TWOGIS_API_KEY=
GOOGLE_PLACES_API_KEY=
CRAWLER_USER_AGENT=LeadHarborBot/0.1 (+contact@example.com)
CRAWLER_MAX_CONCURRENCY=5
CRAWLER_REQUESTS_PER_SECOND=2
```

合规红线同前：遵守 `robots.txt`、单域名限速、记录来源与抓取时间、邮箱校验后入库、建立 `do_not_contact` 机制。

## 采集源：Google 搜索（直接 Google）【新增】

实现文件：`app/collectors/sources/google_search.py`，注册名：`google_search`。

- 使用官方 **Google Programmable Search / Custom Search JSON API**（非网页硬爬）。
- 环境变量：`GOOGLE_SEARCH_API_KEY` + `GOOGLE_SEARCH_CX`（搜索引擎 ID）。
- `query` 必填 `text_query`，可选 `region`（`gl` 国家）、`language`（`hl`）、`max_items`。
- 每页 10 条，最多翻到第 91 条；返回标题、落地链接、域名。
- 典型打法：先用 `google_search` 找到公司官网 → 再把官网 URL 交给 `website` 采集器抓邮箱/电话。

示例：

```bash
curl -X POST http://localhost:8000/api/v1/collect -H "Content-Type: application/json" \
  -d '{"source":"google_search","query":{"text_query":"LED lighting distributor Almaty","region":"KZ"},"max_items":10}'
```

## 采集源：官网/主页抓取器【新增】

实现文件：`app/collectors/sources/website.py`，注册名：`website`（无需密钥）。

- `query` 提供 `urls`（列表）或 `url`（单个），可加 `max_pages_per_site`（默认 2）。
- 抓首页 + 自动发现 contact/контакты/aloqa 等联系页；用 parsel 解析。
- 提取：公司名（og:site_name / title）、邮箱（正文正则 + mailto）、电话（tel: + 正则）。
- **严格遵守 robots.txt**（can_fetch），复用全局限速与超时。
- 可用于公司官网，也可用于你能合法访问的社媒公开主页 URL（Facebook/Instagram/Telegram 公开页等）。

示例：

```bash
curl -X POST http://localhost:8000/api/v1/collect -H "Content-Type: application/json" \
  -d '{"source":"website","query":{"urls":["acme.kz","https://partner.uz/contact"]},"max_items":20}'
```

## 社媒采集合规（重要）

| 渠道 | 建议做法 | 说明 |
| --- | --- | --- |
| LinkedIn | **禁止硬爬**，仅用官方合作伙伴 API / 合规数据商 | 反爬 + ToS 风险高 |
| Telegram | 公开频道/主页经 `website` 抓取；私域需官方 Bot/API | 中亚 B2B 重要渠道，优先做可授权的 |
| Facebook / Instagram | Graph API（需商业账号授权） | 硬爬会封号 |
| VK | 官方 API | 俄语区补充 |

结论：**优先官方 API（google_search / google_places / 2gis）+ robots 合规的 website 抓取**；社媒硬爬不纳入默认能力。

## 环境变量（新增）

```
GOOGLE_SEARCH_API_KEY=
GOOGLE_SEARCH_CX=
```

## 采集源：OpenStreetMap Overpass（免费）【新增】

实现文件：`app/collectors/sources/openstreetmap.py`，注册名：`openstreetmap`。

- 无需 API key，使用 OpenStreetMap 的开放数据与 Overpass API。
- 可补充中亚本地商店、批发市场、办公室、工业设施等，适合作为 2GIS/Google 的免费补充。
- 环境变量：`OVERPASS_URL`，默认 `https://overpass-api.de/api/interpreter`。
- 支持 `KZ / UZ / KG / TJ / TM / RU` 等区域，按 `region` 的 ISO 代码查询。
- 返回 OSM 中的名称、官网、邮箱、电话、行业标签和完整原始 tags。
- 公共 Overpass 实例有频率和资源限制；正式大规模使用建议自建 Overpass 实例或购买商业 OSM 服务。

示例：

```bash
curl -X POST http://localhost:8000/api/v1/collect \\
  -H "Content-Type: application/json" \\
  -d '{"source":"openstreetmap","query":{"text_query":"lighting","region":"KZ"},"max_items":20}'
```

## 渠道组合建议

| 目的 | 推荐渠道 | 成本 |
| --- | --- | --- |
| 中亚商家基础覆盖 | 2GIS + OpenStreetMap | 2GIS 按套餐；OSM 免费 |
| 找官网 | Google Search / Google Places | Google 按额度 |
| 补邮箱电话 | `website` + contact 页 | 免费，受 robots 限制 |
| AI 研究与分类 | 先采集，再用 OpenAI/兼容模型做摘要、行业归类、线索评分 | 按 token |
| 社媒 | 官方 API（Telegram Bot、Meta Graph、VK API） | 通常免费额度 + 平台限制 |

AI 本身不是稳定的原始数据源。建议保留原始来源，再让 AI 对已采集的官网/商家信息做归类、摘要和优先级评分，避免把模型猜测当成事实。

## 采集源：OpenCorporates【新增】

实现文件：`app/collectors/sources/opencorporates.py`，注册名：`opencorporates`。

- 公司注册信息 API，适合补充公司法定名称、注册号、注册辖区、成立日期、公司类型、注册地址和行业代码。
- 可注册免费额度；生产使用建议配置 `OPENCORPORATES_API_TOKEN`。
- 支持 KZ、UZ、KG、TJ、TM、RU 等辖区（实际返回取决于 OpenCorporates 覆盖）。
- 不保证有官网、邮箱和电话，建议后续接 `website` 做联系方式补全。

## 采集源：AI 研究员【新增】

实现文件：`app/collectors/sources/ai_researcher.py`，注册名：`ai_researcher`。

- 使用 OpenAI 兼容 API 按 token 生成公司/经销商候选名单。
- 配置 `OPENAI_API_KEY` 和 `AI_RESEARCHER_ENABLED=true` 后启用，模型由 `AI_RESEARCHER_MODEL` 控制。
- 输出公司名、官网候选、行业、简介、置信度，并标记 `ai_generated=true`。
- AI 结果可能存在幻觉，不能直接视为事实；建议把返回官网交给 `website` 二次验证，再进入触达流程。

相关环境变量：

```
OVERPASS_URL=https://overpass-api.de/api/interpreter
OPENCORPORATES_API_TOKEN=
AI_RESEARCHER_ENABLED=false
AI_RESEARCHER_MODEL=gpt-4o-mini
OPENAI_API_KEY=
```

## 采集源：Yandex 地图（Geosearch 官方 API）【新增】

实现文件：`app/collectors/sources/yandex_maps.py`，注册名：`yandex_maps`。

- Yandex 在俄语区和中亚（尤其是哈萨克斯坦、乌兹别克斯坦、吉尔吉斯斯坦）有较好覆盖。
- 使用官方 Geosearch JSON API，不抓取 Yandex 页面，合规风险较低。
- 环境变量：`YANDEX_GEOSEARCH_API_KEY`（免费额度，后续按量计费）。
- 按 `region` 的 ISO 代码定位城市中心点，返回商家名称、官网、电话、行业类别。
- 环境变量：

```
YANDEX_GEOSEARCH_API_KEY=
YANDEX_GEOSEARCH_URL=https://search-maps.yandex.ru/v1/
```

## 采集源：Wikidata（完全免费）【新增】

实现文件：`app/collectors/sources/wikidata.py`，注册名：`wikidata`。

- 完全免费，无 API key，依赖公共 Wikidata Query Service（WDQS）。
- 按国家（P17）+ 关键词（公司名称别名）查询公司/组织实体，返回名称、官网、行业（P452）、成立日期。
- 公共 WDQS 有严格限速（建议每秒不超过 1 次，采集器内置 0.5 req/s），适合小批量种子数据；大规模使用建议自建 Wikidata 镜像。

这些渠道可以和已有能力组合：

| 渠道 | 成本 | 中亚覆盖 | 适合场景 |
| --- | --- | --- | --- |
| `openstreetmap` | 免费 | 较好 | 本地商店、批发市场、办公室 |
| `wikidata` | 免费 | 中等 | 公司法定名称、行业、成立日期 |
| `opencorporates` | 免费额度 + token | 中等 | 公司注册信息、注册辖区 |
| `yandex_maps` | 免费额度 + api key | 好 | 俄语区商家搜索 |
| `ai_researcher` | 按 OpenAI token | 通用 | 无结构化名单时用 AI 构造种子 |
| `website` | 免费（受 robots 限制） | 取决于目标站 | 补邮箱电话 |

## 采集源：AI 网页提取（OpenAI）【新增】

实现文件：`app/collectors/sources/ai_extractor.py`，注册名：`ai_extractor`。

- 适合「目录页/黄页/公司列表/关于我们/联系我们」等含多家公司或联系方式的页面。
- 抓取页面 HTML → 转纯文本 → OpenAI 按 token 抽取 {name, website, email, phone, address, industry} → 入库。
- 仅抽取文本中真实出现的信息，不会编造；结果建议人工核实后再触达。
- 输入：`query["urls"]`（网址列表）或 `query["url"]`（单个网址），可加 `max_items`（默认 20）。
- 支持环境变量：`OPENAI_API_KEY`（必填）、`OPENAI_MODEL`（可选，默认 gpt-4o-mini）。

示例：

```bash
curl -X POST http://localhost:8000/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"source":"ai_extractor","query":{"urls":["https://example-dir.kz/companies"],"max_items":20}}'
```

用法建议：先用 `google_search` / `website` 找到包含公司列表的页面 URL，再交给 `ai_extractor` 把页面里的公司名和联系方式抽出，最后接一次 `website` 抓取补全邮箱/电话。

相关环境变量：

```
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```
