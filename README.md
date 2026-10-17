# 宝可梦数据采集平台

一套完整的「爬虫 + 后端 API + 可视化前端」系统：从 [PokeAPI](https://pokeapi.co) 采集全量宝可梦数据，落库 SQLite，通过 FastAPI 提供查询、统计与导出接口，用 React 前端做列表筛选和图表分析。

```
PokeAPI ──► 爬虫层（httpx / Playwright）──► SQLite ──► FastAPI ──► React 前端
                  │                                                    │
            robots + 限速 + 重试                              列表筛选 / 六张图表
```

## 快速开始

### 1. 后端

```bash
cd backend

# 安装依赖（Python 3.13）
pip install -r requirements.txt
pip install -r requirements-playwright.txt   # 可选：动态渲染抓取器
python -m playwright install chromium        # 可选：下载浏览器内核（见「常见问题」）

# 初始化数据库
python scripts/init_db.py

# 试抓 5 条（不入库）
python scripts/crawl_once.py --limit 5 --dry-run

# 全量抓取 1351 条（1025 常规 + 326 形态，约 10 分钟）
python scripts/crawl_once.py --mode full --limit 1351

# P2 深度目标全量（物种 1025 / 进化链 540 / 招式 937 / 特性 374，合计约 10 分钟）
python scripts/crawl_once.py --target species --mode full --limit 100000
python scripts/crawl_once.py --target evolution --mode full --limit 100000
python scripts/crawl_once.py --target move-detail --mode full --limit 100000
python scripts/crawl_once.py --target ability-detail --mode full --limit 100000

# P2 数据验收（数量 / 锚点抽查 / 中文覆盖率）
python scripts/verify_p2.py

# 校验 httpx 与 playwright 两种抓取器输出一致
python scripts/verify_fetchers.py --ids 1,25,150

# 前端冒烟检查：真实加载 5 个页面 + 抽屉交互，断言有内容渲染且无运行时错误
# （可捕捉「HTTP 200 但页面空白」这类 curl 测不出的问题）
python scripts/smoke_frontend.py --base http://127.0.0.1:8000

# 启动服务
python run.py
```

服务启动后：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173
```

Vite 已配置 `/api` 代理到 `127.0.0.1:8000`，开发环境下前后端同源，无需处理跨域。

## 目录结构

```
backend/
├── app/
│   ├── api/v1/         health / pokemon / moves / stats / crawl / export 路由
│   ├── core/           数据库、ORM 模型、仓储、聚合、Pydantic 模型
│   ├── crawler/        抓取器抽象、robots、限速、httpx、Playwright、适配器、流水线、调度
│   ├── services/       任务服务、统计缓存、导出服务
│   └── utils/          时间与哈希工具
├── config/             配置（.env 驱动）与选择器示例
├── scripts/            init_db / crawl_once / export_cli / install_chromium / verify_fetchers /
│                       smoke_frontend / shot_zh / fetch_zh_names / backfill_zh /
│                       glossary_dump / glossary_merge / check_glossary
├── tests/              pytest 用例
└── data/               运行时生成：poke.db、日志、导出文件

frontend/
└── src/
    ├── api/            axios 客户端与接口封装
    ├── pages/          总览 / 数据列表 / 图表分析 / 爬取管理
    ├── components/     layout、通用组件、宝可梦组件、图表组件
    ├── hooks/          react-query 封装
    ├── store/          zustand 筛选状态
    └── utils/          属性配色与中英文映射
```

## 核心能力

### 双抓取引擎，配置切换

| 抓取器          | 适用场景           | 默认并发 | 默认速率               |
| ------------ | -------------- | ---- | ------------------ |
| `httpx`      | 静态页面 / JSON 接口 | 6    | 5 req/s，最小间隔 150ms |
| `playwright` | JS 动态渲染页面      | 2    | 2 req/s，最小间隔 500ms |

切换方式（优先级从低到高）：`.env` 的 `CRAWLER_FETCHER` → 接口 `POST /crawl/trigger` 的 `fetcher` 字段 → CLI `--fetcher`。  
未安装 Playwright 内核时会给出明确提示并降级，不影响 `httpx` 正常工作。

两者对同一批 id 的产物**逐字段一致**（含内容指纹），可用下面的命令验证：

```bash
python scripts/verify_fetchers.py --ids 1,25,150
# 结论： 两种抓取器输出完全一致 ✅
```

### 礼貌爬取

- 启动时主动拉取并解析 `robots.txt`，结果可通过 `GET /api/v1/crawl/robots` 查看
- 令牌桶限速 + 最小请求间隔 + 并发信号量
- 指数退避重试（0.5s → 1s → 2s → 4s → 8s，带抖动，上限 30s），429/503 优先遵循 `Retry-After`
- 显式 User-Agent，只保存图片 URL 不下载图片
- 幂等 upsert：按内容指纹判定，重复抓取只更新变化的数据

### 数据模型

主表 `pokemon` 以 PokeAPI 的 id 为主键；多值字段（属性 / 特性 / 种族值）**双写**：

- 主表 JSON 列 `types_json` / `abilities_json` / `stats_json` → 供列表展示与导出，零 JOIN
- 子表 `pokemon_type` / `pokemon_ability` / `pokemon_stat` → 供筛选与聚合，走索引

任务表 `crawl_job` 记录进度、断点游标、成功失败计数；`crawl_error` 保存失败项，支持 `retry_failed` 模式补抓。

### P2 深度表（物种档案 / 进化链 / 招式与特性明细）

`crawl_once.py --target`（或 `POST /crawl/trigger` 的 `target` 字段）支持五个目标，  
前四个与 `pokemon` 主表同源不同端点，各自独立适配器与写入函数：

| 目标               | 表                 | 内容                                                              |
| ---------------- | ----------------- | --------------------------------------------------------------- |
| `species`        | `pokemon_species` | 物种分类（genus 英/中）、捕获率、性别比、孵化周期、蛋组、栖息地、体色、体型、成长率、世代（1025 行）        |
| `evolution`      | `evolution_edge`  | 进化边扁平表：起止物种、触发条件、等级、道具、时段 + `detail_json` 完整条件（前端按 from/to 组装树） |
| `move-detail`    | `move_detail`     | 招式威力/命中/PP/优先级/类别 + 英文效果与描述（937 行，效果长文按策略不机翻）                   |
| `ability-detail` | `ability_detail`  | 特性英文效果与描述 + 世代/主线系列标记（374 行）                                    |

中文策略分三级：`genus_zh` 直接取 PokeAPI 官方 zh-hans 译名（缺失回落 `zh_genera.json` 手工补录）；  
蛋组/栖息地/体色/体型/成长率/进化触发条件六类封闭枚举进 `zh_glossary.json` 新命名空间；  
效果长文存英文，界面如实标注。深度表写入按 `content_hash` 增量（species 额外比对 `genus_zh`），  
重复抓取零写入。验收：`python scripts/verify_p2.py`。

## 接口一览（前缀 `/api/v1`）

| 方法   | 路径                               | 说明                                                                                                                                                                                                                |
| ---- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET  | `/health`                        | 健康检查（含 DB、调度器、活跃任务）                                                                                                                                                                                               |
| GET  | `/pokemon`                       | 列表：`q` `type`(可重复) `type_any` `ability` `min_total` `max_total` `min_height` `max_height` `min_weight` `max_weight` `genus` `egg_group` `habitat` `color` `shape` `growth_rate` `sort` `order` `page` `page_size` |
| GET  | `/pokemon/{id 或名称}`              | 详情（额外返回 `moves` 招式明细，带 `name_zh`；列表接口不返回以控 payload）                                                                                                                                                               |
| GET  | `/pokemon/meta/types`            | 18 属性配色与中文名                                                                                                                                                                                                       |
| GET  | `/pokemon/meta/abilities`        | 特性字典（`name` 英文 slug + `name_zh` 中文 + 出现次数）                                                                                                                                                                        |
| GET  | `/pokemon/filter-options`        | 物种分类筛选项：genus/蛋组/栖息地/体色/体型/成长率（含中文名与形态级计数）                                                                                                                                                                        |
| GET  | `/pokemon/{id 或名称}/evolution`    | 进化链：扁平边表组装为树（支持分支/合流，节点带代表形态 id 与触发条件）                                                                                                                                                                            |
| GET  | `/moves`                         | 招式图鉴：`q`(中/英) `type_name` `damage_class` `generation` `names`(批量,不分页) `sort`(power/accuracy/pp/priority/name) `order` 分页                                                                                          |
| GET  | `/moves/{name}`                  | 招式详情：效果/描述（英文原文）+ 可学会宝可梦数                                                                                                                                                                                         |
| GET  | `/abilities`                     | 特性列表：`q` `names`(批量) 分页                                                                                                                                                                                           |
| GET  | `/abilities/{name}`              | 特性详情：效果（英文原文）+ 持有宝可梦数                                                                                                                                                                                             |
| GET  | `/stats/overview`                | 总量、均值、最近采集                                                                                                                                                                                                        |
| GET  | `/stats/type-distribution`       | 属性分布（含六维均值）                                                                                                                                                                                                       |
| GET  | `/stats/type-matrix`             | 双属性组合热力图数据                                                                                                                                                                                                        |
| GET  | `/stats/ability-top`             | 特性出现次数 TOP N（含 `ability_zh`）                                                                                                                                                                                      |
| GET  | `/stats/height-weight`           | `mode=scatter\|hist` 身高体重分布                                                                                                                                                                                       |
| GET  | `/stats/ranking`                 | `metric` 可切换的排行榜                                                                                                                                                                                                  |
| GET  | `/stats/radar`                   | `ids=1,4,7` 多只六维对比                                                                                                                                                                                                |
| GET  | `/stats/crawl-trend`             | 每日任务趋势                                                                                                                                                                                                            |
| POST | `/crawl/trigger`                 | 触发抓取，返回 `job_id`（有任务在跑时返回 409）；`target` 可选 `pokemon`/`species`/`evolution`/`move-detail`/`ability-detail`                                                                                                         |
| GET  | `/crawl/jobs`、`/crawl/jobs/{id}` | 任务列表与详情（含进度与 ETA）                                                                                                                                                                                                 |
| POST | `/crawl/jobs/{id}/cancel`        | 取消任务                                                                                                                                                                                                              |
| GET  | `/crawl/scheduler`               | 定时任务状态                                                                                                                                                                                                            |
| POST | `/crawl/scheduler/{id}/run-now`  | 立即执行一次                                                                                                                                                                                                            |
| GET  | `/crawl/robots`                  | robots.txt 判定结果                                                                                                                                                                                                   |
| GET  | `/export?format=csv\|json`       | 导出（复用列表的全部筛选参数；含 `name_zh` 与 `abilities_zh`）                                                                                                                                                                      |

## 配置

复制 `.env.example` 为 `backend/.env` 后修改，常用项：

| 变量                           | 默认值     | 说明                         |
| ---------------------------- | ------- | -------------------------- |
| `CRAWLER_FETCHER`            | `httpx` | 抓取器：`httpx` / `playwright` |
| `CRAWLER_CONCURRENCY`        | `6`     | 并发数                        |
| `CRAWLER_RATE_PER_SEC`       | `5.0`   | 令牌桶速率                      |
| `CRAWLER_MIN_INTERVAL_MS`    | `150`   | 请求最小间隔                     |
| `RESPECT_ROBOTS`             | `true`  | 是否校验 robots.txt            |
| `STORE_RAW_JSON`             | `false` | 是否保存原始报文                   |
| `SCHEDULER_ENABLED`          | `true`  | 定时调度总开关                    |
| `SCHEDULER_INCREMENTAL_HOUR` | `3`     | 每日增量时间（UTC）                |
| `SCHEDULER_FULL_DAY_OF_WEEK` | `sun`   | 每周全量时间                     |

## 常见问题

**Playwright 启动报 `NotImplementedError`**  
Playwright 靠子进程启动它的 Node 驱动，而在 Windows 上**只有 Proactor 事件循环支持创建子进程**；  
若策略是 `WindowsSelectorEventLoopPolicy`，会在 `loop.subprocess_exec()` 处抛 `NotImplementedError`。  
本项目已封装在 `app/core/loop.py`，`run.py` / `app/main.py` / 脚本 / 测试统一调用它。自己写脚本时：

```python
from app.core.loop import setup_event_loop_policy
setup_event_loop_policy()   # 必须在创建任何事件循环之前
```

**下载 Chromium 太慢或一直 0 字节**  
先换镜像源：

```bash
set PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
python -m playwright install chromium
```

若安装器仍然卡住（本机曾遇到下载 26 分钟仍是 0 字节），可手动分片下载后解压：

```bash
# 1. 用任意下载工具取回两个 zip（镜像地址见 `playwright install --dry-run chromium`）
#    chrome-win64.zip                  -> ~207 MB
#    chrome-headless-shell-win64.zip   -> ~124 MB

# 2. 解压到 ms-playwright 约定目录并打标记
python scripts/install_chromium.py \
    --chromium /path/to/chrome-win64.zip \
    --shell    /path/to/chrome-headless-shell-win64.zip \
    --revision 1248
```

脚本会创建 `chromium-1248/` 与 `chromium_headless_shell-1248/` 并写入 `INSTALLATION_COMPLETE` 标记。  
单连接慢时可对同一个 zip 并发发多个 HTTP Range 请求再拼接，实测可从 ~240 KB/s 提到 ~780 KB/s。

**Playwright 任务抓完了却卡在收尾**  
`browser.close()` 在本环境（Windows + Proactor）下，只要页面导航过就会无限等待（>60s）。  
实测：单独 launch 关闭 1.7s、加 context 2.0s、一旦 `page.goto` 过就挂死，且与启动参数无关。  
因此 `PlaywrightFetcher.aclose()` **不调用 `browser.close()`**，直接由 `pw.stop()` 收尾（约 32s，  
浏览器进程 3 → 0 全部回收）。关闭步骤都带超时兜底，不会拖死任务。

**列表/详情里的官方图鉴图片不显示**  
官方图托管在 `raw.githubusercontent.com`，国内网络常不可达。后端已在**读出口径**（API / 统计 / 导出）把图片与叫声外链统一改写为 jsDelivr CDN 镜像（`https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/...`、`.../cries@main/...`），数据库仍忠实保存 PokeAPI 原始 URL（存量数据不动）。镜像在个别网络仍不可达时，前端降级为「属性主色 + 首字母」圆形占位，不影响数据浏览。  
如需切换镜像或关闭改写，在 `backend/.env` 配置 `MEDIA_CDN_TEMPLATE`（留空 = 关闭；备选：`https://cdn.statically.io/gh/{owner}/{repo}/{ref}/{path}`）。

**端口被占用**

```bash
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

**导出 CSV 用 Excel 打开乱码**  
已使用 `utf-8-sig` 编码（带 BOM），Excel 可直接打开。

**`uvicorn --reload` 下定时任务重复执行**  
本项目 `run.py` 默认关闭 reload；如自行开启，请在 `.env` 设 `SCHEDULER_ENABLED=false`。

## 测试

```bash
cd backend
pytest -q
```

覆盖：限速器、robots 判定、PokeAPI 字段映射（校验 bulbasaur 种族值总和 = 318）、CSS 选择器解析、  
仓储幂等 upsert、API 冒烟、中文词典降级/热重载/词条规范、`*_zh` 接口契约与 CSV 表头列数对齐、  
P3 分类筛选/进化链组装/招式图鉴/特性明细的接口契约。

验收脚本：`scripts/verify_p1.py`（前端 DOM 18 项）、`scripts/verify_p2.py`（深度数据 42 项）、  
`scripts/verify_p3.py`（数据消费接口 43 项，ASGI 直跑真实库只读断言）。

前端另有视觉验收脚本 `scripts/shot_zh.py`（Playwright 截图列表页 / 详情抽屉 / 招式悬停 /  
进化链大图 / 招式图鉴 / 特性下拉）。

## 数据来源

[PokeAPI](https://pokeapi.co) — 免费的宝可梦 REST API，无需鉴权。本项目遵循其公平使用原则：限速、缓存友好、不下载图片资源。

### 中文译名

PokeAPI **不提供简体中文**（只有 ja / fr / de 等 12 种语言），因此宝可梦中文名  
取自 [Wikidata](https://www.wikidata.org)（CC0）：用属性  
[P1685](https://www.wikidata.org/wiki/Property:P1685)（Pokémon index）定位图鉴条目，  
再取 `zh-cn / zh-hans` 标签，得到官方译名（妙蛙种子、喷火龙、皮卡丘…）。

生成结果落盘在 `backend/app/data/zh_names.json`，**随仓库提交**，运行期不再访问外网：

```bash
python scripts/fetch_zh_names.py    # 重新生成映射（仅数据过时需要）
python scripts/backfill_zh.py       # 回填到已有数据（新抓取会自动写入）
```

中文译名是**物种级**的：`charizard-mega-x` 与 `charizard` 共用「喷火龙」。

### 特性与招式译名（离线词典）

特性名与招式名没有可用的公开中文数据源（PokeAPI 无 zh-Hans、Wikidata 无对应实体、  
52poke 需登录且被 Cloudflare 拦截、Bulbapedia 返回 403），因此由 AI 按**官方简体译名口径**  
离线产出，落盘为 `backend/app/data/zh_glossary.json`（1146 条：特性 313 + 招式 833）。

不同于宝可梦名，这部分**不入库**，只在读取/序列化时按英文 slug 查表附加 `*_zh`：

| 项      | 做法                                                                                                     |
| ------ | ------------------------------------------------------------------------------------------------------ |
| 权威 key | 始终是英文 slug（`overgrow`），筛选、URL 参数、旧接口契约都不受影响                                                            |
| 中文     | 并列新增字段 `name_zh` / `ability_zh`，查不到时为 `null`，前端回落英文                                                    |
| 为何不入库  | `content_hash` 只覆盖原始 payload，重爬时存量记录判为 skipped，写库反而拿不到译文；且 `pokemon_move` 近 10 万行，加列会让每次 upsert 白搬静态数据 |
| 热重载    | 改完 JSON 调 `zh_glossary.reload_glossary()` 或重启即可，无需迁移与回填                                                |

```bash
python scripts/glossary_dump.py --out data/glossary_src   # 1 导出待译清单（只读）
# 2 分片写入 app/data/glossary_parts/*.json
python scripts/glossary_merge.py                          # 3 校验+合并（冲突即中止）
python scripts/check_glossary.py --strict                 # 4 覆盖率必须 100%
```


````

> 注：译名为 AI 生成、非官方授权数据，个别冷门招式可能与官方译名有出入；
> 修正方式是把新的分片加入 `glossary_parts/` 后重跑 merge，不要手改 `zh_glossary.json`。

---

## 仓库留存说明

本仓库为**全量快照**提交，有意包含以下通常不入库的大文件，保证 `git clone` 后可直接运行：

| 资产 | 体积 | 说明 |
|---|---|---|
| `backend/data/poke.db` | ~9.7MB | SQLite 全量数据（1351 条：1025 图鉴物种 + 326 特殊形态） |
| `frontend/dist/` | ~2.5MB | 前端生产构建产物，由后端直接托管，免去云端 `npm run build` |

`.gitignore` 只排除私有/运行时内容：`.workbuddy/`（私有工作区）、`backend/data/{shots,logs,exports}/`、
`backend/data/test.db`、`__pycache__`、`node_modules`、`.env`。

### 克隆后运行

```bash
git clone https://github.com/Shifeng-Del/pokecrawler.git
cd pokecrawler/backend
pip install -r requirements.txt
python run.py        # 默认监听 127.0.0.1:8000（见 config/settings.py 与 .env.example）
````

### 重新构建前端（修改 `frontend/src` 后）

```bash
cd frontend
npm install
npm run build        # 产物落到 frontend/dist/，后端无需改动
```

> 注意：`start.bat` 含作者本机 Python 路径，换机器请使用上面的命令启动。
