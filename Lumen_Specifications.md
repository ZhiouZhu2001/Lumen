# Lumen 项目规格说明

Oct 1, 2026 · @ZhiouZhu

## 1. 概述

Lumen 是一个 AI 选书助手：用户描述想看的题材，Lumen 返回 5–10 本**真实存在**的英文或西语书，并告诉用户在西班牙去哪里买或读。

**目标用户**：住在西班牙、读英文或西语书、知道想看什么类型但不知道具体看哪本的读者。

**项目定位**：作品集项目，按真实可用的标准来做，4 周内上线。

**核心卖点**（区别于直接问 ChatGPT）：

- 每本书都来自真实书目数据库，AI 只能从检索到的候选书里挑选，不能凭空生成书名
- 每本书附带购买和阅读渠道：纸质书店、Kindle、Apple Books、免费公版
- 每本书展示出版方简介、真实来源的评分（标注来源），以及 AI 根据用户需求写的推荐理由

**MVP 不做的事**：用户登录、个性化推荐、中文书、实时价格抓取、AI 打分、多轮对话。

## 2. 功能范围

用户只需一次输入，就能在 15 秒内看到第一本推荐书，结果逐本流式出现。

**用户流程**

1. 在页面顶部选择书籍语言：English 或 Español（界面语言随之切换）
2. 在文本框输入需求，例如“节奏快、有反转的西班牙悬疑小说”
3. 可选筛选：类型、出版年代、篇幅（短 / 中 / 长）、只看免费
4. 点击搜索，页面显示进度：正在理解需求 → 找到 N 本候选 → 正在挑选
5. 推荐卡片逐本出现

**每张推荐卡片包含**

| 字段 | 来源 |
| --- | --- |
| 封面、书名、作者、出版年、页数 | Google Books / Open Library |
| 格式标签：纸质 / Kindle / Apple Books / 免费公版 | 数据源字段 + 链接规则推断 |
| 出版方简介（原文，可折叠） | Google Books |
| 评分 + 评分人数 + 来源名称；没有则显示“暂无评分” | Google Books / Open Library |
| 为什么推荐给你（2–3 句） | AI，仅基于该书真实数据 |
| 购买与阅读按钮 | 书店链接规则 |

**双语界面**：用 next-intl 实现 `en` 和 `es` 两套文案，书籍语言偏好和界面语言保存在 localStorage 和 Zustand 中，刷新后保持。

## 3. 系统架构

&#91;embedded content: Lumen 系统架构 · 5 个容器，5 个外部服务\]

浏览器只和 Caddy 通信；所有外部 API 和 AI 调用都集中在后端，密钥不会暴露给前端。

**技术栈分工**

| 层 | 技术 | 负责 |
| --- | --- | --- |
| 前端 | Next.js（App Router）、TypeScript、shadcn、Zustand、next-intl | 页面、接收 SSE、保存语言偏好 |
| 后端 | FastAPI、Pydantic、httpx（异步） | 接口、参数校验、调用外部 API |
| AI 编排 | LangGraph；LangChain 只用于模型封装和结构化输出 | 搜索流程 |
| 数据 | PostgreSQL、SQLAlchemy、Alembic | 书籍和搜索记录 |
| 缓存 | Redis | 缓存、限流 |
| 部署 | Docker Compose、Caddy、GitHub Actions | 运行和持续集成 |

**仓库结构**

```text
lumen/
├── frontend/
│   ├── app/[locale]/        # 页面，按语言路由
│   ├── components/          # 书籍卡片、搜索框、筛选器
│   ├── stores/              # Zustand：语言偏好、搜索状态
│   ├── lib/sse.ts           # SSE 客户端
│   └── messages/            # en.json、es.json
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI 路由
│   │   ├── graph/           # LangGraph 状态、节点、图定义
│   │   ├── sources/         # Google Books、Open Library、Gutendex、iTunes 客户端
│   │   ├── stores.yaml      # 书店链接规则
│   │   ├── models.py        # SQLAlchemy 模型
│   │   └── cache.py         # Redis 缓存和限流
│   ├── alembic/
│   ├── evals/               # 评测查询和检查脚本
│   └── tests/
├── docker-compose.yml
├── Caddyfile
├── Makefile                 # make dev / make test / make eval
└── README.md
```

## 4. LangGraph 流程

这是一张固定的图，不是自由 agent：只有“候选是否足够”这一处分支，最多重试 2 次，成本和行为都可预测。

&#91;embedded content: LangGraph 搜索图 · 6 个节点，1 个重试循环\]

已重试 2 次仍然没有候选时，直接推送 `no_results`；有候选但不足 5 本时，就用现有候选继续挑选。

**图的状态**

```python
class SearchState(TypedDict):
    query: str
    language: Literal["en", "es"]
    filters: Filters
    parsed: ParsedQuery | None   # parse_query / broaden 的输出
    candidates: list[Book]       # merge 后的候选，按 ISBN 去重
    retries: int                 # 已重试次数，上限 2
    picks: list[Pick]            # [{isbn13, rank, reason}]
    results: list[BookCard]      # 带购买链接的最终卡片
```

**规则**

- 只有 `parse_query`、`broaden`、`rank_and_explain` 三个节点调用 AI，全部用 Pydantic 结构化输出；其余节点是普通 Python 代码
- `rank_and_explain` 的提示词里只提供候选书的 ISBN、书名、作者和简介，最多 30 本；返回后代码过滤掉不在候选里的 ISBN
- 推荐理由只能引用简介里的信息，用用户界面的语言书写
- 用 LangGraph 的 `astream` 把节点进度转成 SSE 的 `status` 事件
- 每个节点的耗时和 AI 用量都写进结构化日志，并带上 `search_id`
- 模型名放在环境变量里，换模型不用改代码

## 5. 数据源与购买渠道

书目数据只来自公开 API，书店只负责“去哪买”，通过 ISBN 生成链接，MVP 不抓取价格。

**书目数据源**

| 数据源 | 用途 | 关键字段 |
| --- | --- | --- |
| Google Books API | 主检索源，支持 `langRestrict=en/es` | ISBN、简介、封面、页数、`averageRating`、`saleInfo.isEbook` |
| Open Library API | 补充检索和评分 | ISBN、work id、评分（ratings 接口） |
| Gutendex（Project Gutenberg 的 API） | 判断是否有免费公版 | 下载链接 |
| iTunes Search API（`media=ebook`） | 判断 Apple Books 是否有该书 | 商品链接 |

合并规则：以 ISBN-13 为主键去重；没有 ISBN 的书直接丢弃，保证每本书可追溯。

**书店链接规则**（`backend/app/stores.yaml`，加一家店只加一条配置）

| 书店 | 语言 | 题材 | 格式 | 链接方式 |
| --- | --- | --- | --- | --- |
| Amazon.es | en, es | 全部 | 纸质 + Kindle | 按 ISBN 搜索的 URL 模板 |
| Apple Books | en, es | 全部 | 电子书 | iTunes Search API 返回的链接，查不到则不显示 |
| Project Gutenberg | en, es | 全部 | 免费公版 | Gutendex 返回的链接，查不到则不显示 |
| Casa del Libro | es | 全部 | 纸质 + 电子书 | 按 ISBN 搜索的 URL 模板 |
| Abacus | es | 全部 | 纸质 | 按 ISBN 搜索的 URL 模板 |
| Norma Comics | es | 漫画、日漫、图像小说 | 纸质 | 按 ISBN 或书名搜索的 URL 模板 |

每个 URL 模板在第 3 周手动验证一次，并写进测试脚本。Casa del Libro 在 Awin 上有联盟计划（基础佣金 5%），上线后可以申请，把链接换成联盟链接。[来源](https://ui.awin.com/merchant-profile-terms/21491)

## 6. 数据库设计

MVP 只需要 3 张表，全部用 Alembic 迁移创建；书籍数据按 ISBN 缓存，搜索记录匿名保存，留给第二阶段的个性化推荐使用。

**books**：每本见过的书一行

| 列 | 类型 | 说明 |
| --- | --- | --- |
| isbn13 | char(13) PK | 主键，入库前校验格式 |
| title, authors | text, text\[\] | 非空 |
| language | char(2) | `en` 或 `es`，CHECK 约束 |
| description | text | 出版方简介 |
| cover\_url | text | 可空 |
| page\_count, published\_year | int | 可空 |
| genres | text\[\] | 用于匹配 Norma Comics 等题材规则 |
| rating\_value, rating\_count, rating\_source | numeric(2,1), int, text | 三者同时为空或同时有值（CHECK） |
| formats | text\[\] | `paper` / `kindle` / `apple_books` / `free` |
| raw | jsonb | 原始 API 返回，方便排查 |
| fetched\_at | timestamptz | 超过 30 天重新拉取 |

**searches**：每次搜索一行

| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid PK |  |
| query\_text | text | 用户原始输入 |
| parsed\_query | jsonb | AI 解析后的结构化查询 |
| language | char(2) |  |
| filters | jsonb |  |
| candidate\_count, retries | int | 检索到多少候选、重试了几次 |
| duration\_ms | int | 用于观察性能 |
| created\_at | timestamptz | 索引 |

不保存 IP 等可识别身份的信息。

**search\_results**：每次搜索推荐了哪些书

| 列 | 类型 | 说明 |
| --- | --- | --- |
| search\_id | uuid FK → searches |  |
| isbn13 | char(13) FK → books |  |
| rank | smallint | 展示顺序 |
| reason | text | AI 写的推荐理由 |

主键为 (search\_id, isbn13)。外键约束在数据库层面保证“推荐的书一定在 books 表里”，这是防止编造的最后一道保险。

## 7. API 接口

后端只暴露 3 个端点，核心是一个返回 SSE 流的搜索接口。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/search` | 接收需求，返回 `text/event-stream` |
| GET | `/api/books/{isbn13}` | 单本书详情（分享链接用） |
| GET | `/api/health` | 检查 Postgres 和 Redis 连通性，供部署监控使用 |

**`POST /api/search` 请求体**（Pydantic 校验）

```json
{
  "query": "fast-paced Spanish thriller with twists",
  "language": "es",
  "filters": { "genre": "thriller", "era": "2000s", "length": "medium", "free_only": false }
}
```

`query` 长度限制为 3–300 个字符；`language` 只能是 `en` 或 `es`。

**SSE 事件**（按顺序推送）

| 事件 | 数据 | 前端表现 |
| --- | --- | --- |
| `status` | `{stage: "parsing" \| "searching" \| "ranking"}` | 进度提示 |
| `candidates` | `{count: 34}` | “找到 34 本候选” |
| `book` | 一本书的完整卡片数据 + `reason` + `links` | 追加一张卡片 |
| `done` | `{search_id, total}` | 结束加载状态 |
| `error` | `{code, message}` | 友好的错误提示 |

错误码统一定义：`rate_limited`（429）、`no_results`、`upstream_unavailable`、`llm_failed`。所有错误都写结构化日志，并带上 `search_id`。

## 8. 缓存与限流

Redis 有两个作用：让相同的请求不重复花钱，以及防止有人刷掉你的 AI 额度。

| 键 | 内容 | TTL |
| --- | --- | --- |
| `parse:{sha256(query+language+filters)}` | AI 解析后的结构化查询 | 7 天 |
| `gbooks:{sha256(params)}` | Google Books 原始返回 | 24 小时 |
| `olib:{sha256(params)}` | Open Library 原始返回 | 24 小时 |
| `result:{sha256(query+language+filters)}` | 整次搜索的最终结果 | 6 小时 |
| `rl:{ip}:{yyyymmddhh}` | 该 IP 本小时的搜索次数 | 1 小时 |

**限流规则**：每个 IP 每小时最多 20 次搜索，超过返回 429。IP 只存在 Redis 里，1 小时后自动过期，不写入 PostgreSQL。

**全局保险**：在环境变量里设置每日 AI 调用上限，超过后搜索接口返回维护提示。这样即使限流被绕过，月度花费也有上限。

命中 `result:` 缓存时，依然用 SSE 逐本推送结果，前端不需要区分两种情况。

## 9. 测试与质量

每次修改提示词或检索逻辑后，运行一次 `make eval`；6 项检查必须全部通过才能合并。

**评测查询集**：`backend/evals/queries.yaml`，共 20 条，英文和西语各 10 条，覆盖：

- 宽泛的题材（“fantasy with dragons”）
- 带限制条件的需求（“短篇、2010 年以后、西班牙作者”）
- 漫画类（用于验证 Norma Comics 链接规则）
- 只看免费（用于验证 Gutenberg 链接）
- 冷门需求（用于验证重试分支）
- 2 条无意义输入（应返回 `no_results`，而不是编造书）

**自动检查**

| 检查项 | 通过标准 |
| --- | --- |
| 真实性 | 每本推荐书的 ISBN 都在本次检索的候选列表里 |
| 语言正确 | 每本书的 `language` 与请求一致 |
| 数量 | 正常查询返回 5–10 本；无意义输入返回 0 本 |
| 链接规则 | 西语书没有英文专属渠道；非漫画书没有 Norma Comics 链接 |
| 推荐理由 | 非空，且不出现 `description` 和书名之外的专有名词（简单启发式检查） |
| 耗时 | 第一本书在 15 秒内推送 |

**单元测试**（pytest）只测有逻辑的地方：ISBN 合并去重、书店规则匹配、限流计数、重试条件判断。外部 API 用录制好的返回数据做测试替身，不在单元测试里真实联网。

## 10. 部署

一台 VPS 用 Docker Compose 跑起全部 5 个服务，本地开发和线上用同一份 compose 文件，只是环境变量不同。

| 服务 | 镜像 | 说明 |
| --- | --- | --- |
| caddy | caddy:2 | 反向代理，自动 HTTPS；`/api/*` 转发给 backend，其余转发给 frontend |
| frontend | 自建（Next.js standalone 构建） | 端口 3000 |
| backend | 自建（FastAPI + uvicorn） | 端口 8000；启动前执行 `alembic upgrade head` |
| postgres | postgres:16 | 数据卷持久化，每天用 `pg_dump` 备份 |
| redis | redis:7 | 不需要持久化，丢了只是缓存失效 |

**要点**

- SSE 经过 Caddy 时要关闭响应缓冲，否则流式效果会失效
- 密钥（AI API key、Google Books key、数据库密码）放在 VPS 上的 `.env` 文件里，不提交进仓库；仓库里提供 `.env.example`
- 用 GitHub Actions 在每次推送时跑 lint、单元测试和类型检查；部署先手动执行 `git pull && docker compose up -d --build`，稳定后再自动化
- 买一个域名（每年约 10 欧），README 里放线上地址

## 11. 四周计划

每周 6 天、每天 3–4 小时，约 21 小时；每周末必须有一个能演示的版本，做不完就砍功能，不延期。

### 第 1 周：不用 AI，先跑通检索

- [ ] 建 monorepo，`docker compose up` 能起 Postgres、Redis、backend、frontend
- [ ] Alembic 建 3 张表
- [ ] 实现 Google Books 和 Open Library 客户端，按 ISBN 合并去重
- [ ] `POST /api/search` 先用关键词直接检索，普通 JSON 返回
- [ ] 前端：语言切换、搜索框、书籍卡片列表（shadcn）
- [ ] 合并去重的单元测试

**完成标准**：输入英文关键词，能看到真实的书。

### 第 2 周：接入 AI 和流式返回

- [ ] 封装模型调用层（LangChain，结构化输出）
- [ ] LangGraph 搭好 5 个节点和重试分支
- [ ] 挑选节点只能输出候选列表里的 ISBN，并在代码里再校验一次
- [ ] 改成 SSE，前端逐本显示卡片和进度提示
- [ ] next-intl 双语界面

**完成标准**：用一句自然语言描述，能流式看到带推荐理由的结果。

### 第 3 周：渠道、缓存、质量

- [ ] `stores.yaml` 链接规则，以及 Gutendex、iTunes Search 查询
- [ ] 手动验证每个书店的 URL 模板
- [ ] Redis 缓存和 IP 限流，以及每日 AI 调用上限
- [ ] 20 条评测查询和 `make eval` 脚本，跑到全部通过
- [ ] 筛选条件生效

**完成标准**：`make eval` 6 项检查全部通过。

### 第 4 周：上线和包装

- [ ] 租 VPS、买域名，配置 Caddy，完成部署
- [ ] GitHub Actions 跑测试
- [ ] 打磨界面：加载骨架屏、空状态、错误提示、移动端适配
- [ ] README：解决什么问题、截图和 GIF、架构图、技术取舍、如何本地运行
- [ ] 录 2 分钟演示视频
- [ ] 让 3 个朋友试用，记录反馈

**完成标准**：陌生人打开链接就能用，README 讲得清楚为什么这样设计。

## 12. 后续阶段与风险

MVP 上线后再考虑第二阶段：用户账号、“读过 / 喜欢”标记、基于历史的个性化推荐（已经保存的 `searches` 和 `search_results` 可以直接复用），以及申请 Casa del Libro 的联盟链接。

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Google Books 对西语书覆盖不足 | 西语结果偏少 | 用 Open Library 补充；评测集里西语查询单独统计；必要时放宽重试条件 |
| 书店改版导致 URL 模板失效 | 链接 404 | 每个模板都有评测用例；失效时只隐藏该渠道，不影响整张卡片 |
| AI 写的推荐理由夸大或编造情节 | 损害“真实”卖点 | 提示词限定只用简介内容；评测里做启发式检查；页面标注“理由由 AI 生成” |
| 外部 API 限额或宕机 | 搜索失败 | Redis 缓存；返回 `upstream_unavailable` 并给出友好提示 |
| AI 费用失控 | 超出预算 | IP 限流 + 每日调用上限 |
| 范围蔓延 | 4 周做不完 | 每周末必须有可演示版本；新想法一律写进第二阶段清单 |
