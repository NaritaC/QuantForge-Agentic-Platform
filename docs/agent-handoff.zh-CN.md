# QuantForge Agentic Platform：新 Agent 从零接管手册

> 文档状态：可执行交接基线
>
> 核对日期：2026-08-29
>
> 当前代码基线：`main@f81b835`
>
> 远程仓库：<https://github.com/NaritaC/QuantForge-Agentic-Platform>
>
> 产品名称与包名：`QuantForge-Agentic-Platform` / `quantforge`

## 0. 这份文档解决什么问题

这份文档面向一个没有本对话上下文、没有项目记忆、甚至没有安装任何 Skill 或 MCP
的新 Agent。完成本手册后，它应当能够：

1. 理解产品目标、用户约束与不能改变的研究语义；
2. 在空环境中安装最低工具能力并安全获取仓库；
3. 复现离线数据闭环和真实 A 股数据闭环；
4. 判断运行是否真的成功，而不只看命令退出码；
5. 继续开发 AmazingData、多来源校验、PIT 财务数据、因子评价和学习材料；
6. 在任何阶段都不泄露密钥、不提交授权数据、不伪造市场事实。

“从零”默认指**新 Agent 的环境与上下文从零**，不是删除已验证代码重新造轮子。默认流程是：
克隆现有仓库 → 独立验收 → 继续开发。若用户明确要求 clean-room 重写，应在新目录或新分支完成，
不得覆盖、清空或重写当前 `main` 历史。

## 1. 新 Agent 首先必须读取的内容

按以下顺序读取，未读完前不要修改代码：

1. [`AGENTS.md`](../AGENTS.md)：最高优先级的产品边界、权限和研究协议；
2. 本文档：环境、复现、工具、当前状态与后续路线；
3. [`README.md`](../README.md)：用户入口和当前功能；
4. [`docs/data-contracts.md`](data-contracts.md)：数据与研究产物合同；
5. [`docs/quant-data-pitfalls.md`](quant-data-pitfalls.md)：本项目必须展示的数据问题；
6. [`docs/secrets.md`](secrets.md)：密钥规则；
7. [`docs/adr/`](adr/) 下全部 ADR：技术决策及其原因；
8. 与当前任务直接相关的源码和测试。

若需要读取 Obsidian Vault，必须先完整阅读 `E:\NaritaVault\AGENTS.md`、`SCHEMA.md`
和 `INDEX.md`。除非用户明确要求，不要修改 Vault。

## 2. 产品使命与用户工作约定

### 2.1 产品使命

QuantForge 是一个面向 A 股日频研究起步、长期扩展到国内期货、分钟/Tick、订单簿、
生产部署与低延迟路径的审计优先量化研究平台。它也是用户应聘量化策略研究员和量化数据
工程师的核心作品。

系统从下到上分为：

```text
Agent Layer
────────────────────────
Risk & Control
────────────────────────
Quant Research Core
────────────────────────
Data Foundation
```

关闭所有模型与 Agent 后，数据接入、清洗、质量检查、特征、因子、回测、组合、风控和报告
仍必须确定性运行。Agent 是受控协作者，不是市场事实来源，也不是质量门禁的替代品。

### 2.2 用户背景与协作偏好

- 数学本科，可以接受公式、统计、优化、时间序列和严格推导；
- 求职方向最初约为量化策略研究 70%、量化数据工程 30%；
- 近期学习重点是量化数据工程：术语、原理、公式、Python、SQL，C++ 次要；
- 用户每天通常最多投入 1 小时，主要工程代码由 Agent 完成；
- 学习材料要求中英双语，按 1 小时可完成的节奏组织；
- 用户需要能运行、能讲解、能展示、可追溯的作品，不接受只有规划或漂亮页面；
- 重大里程碑经测试后可以推送公开仓库；现有 `AGENTS.md` 已记录授权边界；
- 密钥只放本地 `.env`，不要要求用户把密钥发到聊天或命令行；
- 只有显著改变产品方向、引入付费服务、扩大外部权限或缺少关键业务选择时才停下确认。

原始“一周面试 MVP”时限来自 2026-08-25。新 Agent 接管时应重新确认面试日期是否仍有效，
但不得用重新确认作为停止工程工作的理由。

## 3. 唯一可信的工程位置与仓库

- GitHub：<https://github.com/NaritaC/QuantForge-Agentic-Platform>
- 当前本机规范目录：`E:\QuantForge-Agentic-Platform`
- Python 包：`src/quantforge`
- 默认分支：`main`
- 本交接基线：`f81b835 feat: run closed loop on real A-share data`

早期说明中的 `E:\QuantForge-Platform` 已被产品重命名取代。不要在旧目录创建第二份权威工程，
也不要让两个目录同时演进。

所有真实数据和运行产物留在本机，并由 `.gitignore` 排除。公开仓库只包含代码、配置、文档、
测试和极小脱敏 Fixture。

## 4. 新 Agent 需要具备的能力

Skill、MCP 和 Python 依赖是三类不同东西：

- **Skill**：规定 Agent 如何完成某类工作；
- **MCP/工具连接**：让 Agent 能访问文件、GitHub、浏览器等外部系统；
- **项目依赖**：让 QuantForge 代码本身可以运行。

缺失某个 Skill 时，可以按本文档的等价流程继续；缺失文件系统、终端或 Git 能力时，不能承担
工程实现任务。

### 4.1 必备底层能力

| 能力 | 最低验收 | 权限原则 |
|---|---|---|
| 工作区文件读写 | 能读取、补丁式编辑、搜索仓库文件 | 仅授权项目目录；保留用户已有修改 |
| PowerShell/终端 | 能运行 Python、pytest、ruff、Git 和长任务 | 不把密钥写进参数；不执行破坏性历史操作 |
| Git | 能看 diff/status/log、提交并推送 | 测试通过后才推送；不 `reset --hard` |
| Python 3.12 | `python --version` 为 3.12.x | 使用隔离虚拟环境 |
| 网络与一手资料核验 | 能访问数据商、交易所和官方仓库 | 事实以官方文档/源码为先 |
| PDF 阅读 | 能读取并按页验证开发手册或财报 | 不把授权 PDF 提交仓库 |
| 本地浏览器测试 | 能打开并检查 Streamlit 页面 | 测试自己创建的会话；不扰动用户标签页 |
| 长任务管理 | 网络下载超过 30 秒时能轮询并汇报 | 不因暂时无输出就重复启动同一任务 |

### 4.2 Skill 最低清单与增强清单

以下名称来自当前 Codex 环境；不同 Agent 产品可安装同名 Skill，或提供满足“必须行为”的等价
Skill。对一个没有项目上下文的新 Agent，P0 是最低清单，P1/P2 按任务启用。先审阅每个
`SKILL.md` 和权限，再启用。

| 优先级 | Skill | 用途 | 必须行为 |
|---|---|---|---|
| P0 | `grilling`（旧名/别名 `grill-me`） | 新产品决策或研究协议存在歧义时追问 | 不重复追问本文已冻结的决定 |
| P0 | `web-access` | 数据源、交易规则、库版本、招聘要求等联网核验 | 优先一手来源；记录访问日期；不凭记忆写市场规则 |
| P0 | `pdf:pdf` | AmazingData 手册、财报、公告 PDF | 结合文本和页面渲染；保留页码/来源定位 |
| P0 | `data-analytics:analyze-data-quality` | 数据质量、覆盖率、异常与跨源差异 | 输出证据、严重级别、影响行和处置状态 |
| P0 | `webapp-testing` | 本地 Research Ledger 验收 | 检查真实数据、追溯链接和空状态，不只检查 HTTP 200 |
| P1 | `data-analytics:jupyter-notebooks` | 探索、教学、SQL/Python 演示 | Notebook 不得成为生产唯一实现 |
| P1 | `doc-coauthoring` | ADR、研究协议、交接和学习文档 | 面向无上下文读者测试完整性 |
| P1 | `data-analytics:build-dashboard` / `visualize-data` | 扩展证据控制台 | 图表必须来自确定性产物，不在 UI 重算另一套结果 |
| P1 | `claude-mem` 或等价长期记忆 | 跨会话保存已确认决策 | 记忆不是事实源；仓库文档仍是最终依据 |
| P2 | `sn-deep-research` | 多数据源、框架或岗位系统调研 | 调研必须转化为 ADR、代码或明确否决理由 |
| P2 | `frontend-design` | UI 信息架构确需升级时 | 前端美观低于闭环、质量和可追溯性优先级 |

同一任务只启用最小 Skill 集；不要让工具说明淹没项目上下文。

Skill 安装流程与具体 Agent 产品有关，交接时按以下步骤执行：

1. 优先通过目标客户端的官方 Skill/Plugin 管理器安装 P0 项；
2. 安装后枚举实际可用 Skill，并完整阅读每个 `SKILL.md`，不能只凭名称推断行为；
3. 没有管理器时，从经审计的来源复制**完整 Skill 目录**，不要只复制一个说明片段；
4. `web-access` 的当前来源记录为 <https://github.com/eze-is/web-access>；
5. `pdf:pdf` 来自当前 OpenAI bundled runtime，`data-analytics:*` 来自 Data Analytics 插件；
6. `grilling`、`webapp-testing` 是当前机器上的本地 Skill，迁移前需一并复制目录并复核许可证；
7. 某个包不可获得时，按表中的“必须行为”执行等价流程，不能因此跳过质量或来源核验。

### 4.3 MCP 最低清单与替代关系

对“运行 QuantForge”而言，没有量化专用 MCP 是硬依赖；行情通过可测试的 Python Adapter/SDK
进入，SQL 由 DuckDB 执行。若新 Agent 没有任何内置工具，Filesystem、GitHub、Playwright 是
最低 MCP 组合；若它已有等价的工作区、Git/远端和浏览器工具，则不要重复安装。

| MCP | 级别 | 作用 | 安全配置 |
|---|---|---|---|
| [GitHub 官方 MCP Server](https://github.com/github/github-mcp-server) | 无等价远端工具时必需 | 查看仓库、Issue、PR、Actions 和远端状态 | 初始只读；仅开放当前仓库；认证放系统密钥存储或 OAuth |
| [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) | 无等价浏览器工具时必需 | 测试本地 Streamlit、官方网页和交互流程 | 默认隔离浏览器；需要用户登录态时再请求授权 |
| [Filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | 无内置工作区工具时必需 | 读取、搜索和补丁式修改项目文件 | Roots 只允许项目目录，禁止整个磁盘/用户主目录 |

Playwright MCP 的通用 Codex 安装命令是：

```powershell
codex mcp add playwright npx "@playwright/mcp@latest"
```

首次验证后应记录实际解析版本，避免未来环境无意漂移。若 Agent 已有可靠的内置浏览器控制，
不要重复安装功能等价的 MCP。

Filesystem MCP 的 Windows 配置必须把最后一个参数限制到项目目录，例如：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "E:\\QuantForge-Agentic-Platform"
      ]
    }
  }
}
```

不要安装 DuckDB/PostgreSQL/交易所“万能 MCP”来绕过数据合同。不要把券商账号、Token 或 `.env`
通过 MCP 上下文暴露给模型。

### 4.4 暂不需要的能力

Kafka、Kubernetes、ClickHouse、复杂多 Agent 编排、C++ 低延迟、自动下单、云部署、完整 MLOps
均不是当前复现前置条件。只有实测负载或下一阶段需求证明必要时，才通过 ADR 引入。

## 5. 从空环境复现当前项目

### 5.1 系统前置

必须安装：

- Git；
- Python 3.12；
- 能创建虚拟环境的 Python 安装；
- Windows PowerShell 7（当前开发环境）或能等价执行命令的 shell。

建议安装：

- Node.js 20+：Playwright/Filesystem MCP；若使用现有 `web-access` CDP Skill，使用 Node.js 22+；
- Chrome/Chromium：本地 UI 测试；
- C++ 编译器：仅后续学习或性能模块需要，不阻塞当前平台；
- Docker：当前 CI/运行不依赖，未来部署再启用。

### 5.2 克隆与安装

```powershell
Set-Location E:\
git clone https://github.com/NaritaC/QuantForge-Agentic-Platform.git
Set-Location E:\QuantForge-Agentic-Platform
git switch main
git pull --ff-only origin main

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ui,baostock]"
```

若目标目录已有文件，先只读检查，不要覆盖或删除。若必须进行独立 clean-room 重写，使用
`E:\QuantForge-Agentic-Platform-Rebuild` 或独立分支，并保留当前仓库作为行为基线。

### 5.3 本地密钥文件

```powershell
Copy-Item .env.example .env
```

`.env` 只能在本机编辑，不提交、不截图、不回显值。当前变量名为：

```dotenv
QUANTFORGE_TUSHARE_TOKEN=
QUANTFORGE_AMAZINGDATA_SDK_PATH=
QUANTFORGE_AMAZINGDATA_USERNAME=
QUANTFORGE_AMAZINGDATA_PASSWORD=
QUANTFORGE_AMAZINGDATA_HOST=
QUANTFORGE_AMAZINGDATA_PORT=
```

BaoStock 不需要密钥，因此即使这些变量都为空，也可以完成当前真实数据闭环。

### 5.4 第一层验收：代码质量

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=quantforge --cov-report=term-missing
```

在 `f81b835` 基线上，本地证据为 44 项测试通过、总覆盖率约 89%。未来测试数量可以增加；
验收标准是全部通过且没有通过降低门槛来“修复”测试。

### 5.5 第二层验收：完全离线数据流水线

```powershell
python -m quantforge pipeline --config configs/mvp.yaml
python -m quantforge experiment --config configs/research-demo.yaml
```

必须验证，而不是只看退出码：

- `data/raw/` 出现按 SHA-256 寻址的原始 Fixture；
- `data/staging/` 与 `data/curated/` 出现不可变 Parquet 快照；
- `artifacts/runs/latest.json` 的状态成功；
- 质量检查明确列出 passed/warning/failed；
- 研究运行生成 `universe/factors/signals/orders/fills/holdings/nav` 七类 Parquet；
- `experiment.json` 记录参数、输入快照、Git commit、限制和 `baseline_comparison=deferred`；
- 合成数据被标记为功能证据，不得称作真实研究结论。

### 5.6 第三层验收：真实 A 股数据闭环

先做小请求：

```powershell
python -m quantforge pipeline --config configs/baostock-smoke.yaml
```

再运行固定真实样本：

```powershell
python -m quantforge experiment --config configs/real-data-research.yaml
```

基线请求为 12 只长期上市 A 股、2022-01-04 至 2025-12-31、未复权日线
`adjustflag=3`。在 2026-08-25 的成功运行中得到：

- 11,628 行真实日线、12 只证券；
- 11 项日线质量检查全部通过、0 violations；
- 504 条动态样本、432 条因子、180 条信号；
- 187 条订单尝试、186 次成交、3,554 条持仓、711 个 NAV 日期；
- 一笔 `000333.SZ` 买单在 2024-10-08 因涨停保守阻止，次日重试成交；
- 连续两次采集的 Raw 校验和、Curated snapshot ID 和七类研究产物校验和一致。

这些数字是复现参考，不是强制伪造的断言。若数据商修订历史数据或网络返回不同，保留新 Raw，
比较字段、范围、单位和校验和，并把差异写入质量报告；不得为了匹配旧数字篡改数据。

### 5.7 第四层验收：本地证据控制台

```powershell
python -m quantforge dashboard --port 8765
```

打开 <http://localhost:8765/>。验收至少包括：

- 最新运行和历史运行可选择；
- 数据来源、请求参数、日期范围、行数和证券数可见；
- Raw → Staging → Curated 的处理步骤、字段映射、校验和和代码位置可追溯；
- 质量检查同时显示通过项和问题项；
- 股票池、因子、信号、订单、成交、持仓、NAV、指标和限制均来自同一运行；
- 旧运行缺少新产物时显示诚实空状态，不生成占位数据；
- 中文与英文显示同一事实。

HTTP 200 只能证明服务存活，不能证明以上内容正确。

## 6. 当前架构与代码地图

### 6.1 已实现闭环

```text
Fixture / Synthetic / BaoStock
  → AdapterBatch
  → content-addressed Raw + request manifest
  → canonical Staging normalization
  → deterministic quality gate
  → immutable Curated Parquet snapshot
  → DuckDB direct query
  → PIT-style dynamic universe
  → 12-1 momentum + 60-day low volatility
  → MAD winsorization + cross-sectional z-score
  → equal-weight target signals
  → next-open orders and fills
  → fees/slippage/board lots/suspension/price-limit retry
  → holdings + NAV + metrics
  → checksummed experiment manifest
  → read-only bilingual Research Ledger
```

### 6.2 关键模块

| 路径 | 职责 |
|---|---|
| `src/quantforge/config.py` | YAML 配置、目录解析、阻止 YAML 内联密钥 |
| `src/quantforge/settings.py` | 加载 `.env`，环境变量优先 |
| `src/quantforge/data/adapters/base.py` | AdapterBatch 合同 |
| `src/quantforge/data/adapters/fixture.py` | 离线可复现入口 |
| `src/quantforge/data/adapters/synthetic.py` | 完整研究闭环的确定性功能数据 |
| `src/quantforge/data/adapters/baostock.py` | 真实未复权日线、交易日历、证券主数据、超时/EOF 保护 |
| `src/quantforge/data/normalize.py` | 证券 ID、类型、状态和字段语义统一 |
| `src/quantforge/data/price_limits.py` | 带版本的 A 股历史涨跌停规则推导 |
| `src/quantforge/data/quality.py` | 日线质量门禁 |
| `src/quantforge/data/reference.py` | 交易日历与证券主数据标准化/质量 |
| `src/quantforge/data/storage.py` | Raw 内容寻址和 Parquet 快照 |
| `src/quantforge/data/lineage.py` | 字段级与步骤级血缘 |
| `src/quantforge/pipeline.py` | Raw → Staging → Curated 主流程 |
| `src/quantforge/research/universe.py` | 按调仓时点重建动态股票池 |
| `src/quantforge/research/factors.py` | 价格因子、截面处理、目标权重 |
| `src/quantforge/research/backtest.py` | 次日开盘执行与组合会计 |
| `src/quantforge/experiment.py` | 一键研究运行和产物清单 |
| `src/quantforge/ui/data.py` | 有界查询和 UI 只读模型 |
| `src/quantforge/ui/app.py` | 双语 Research Ledger |
| `tests/unit/` / `tests/integration/` | 单元、合同、持久化和闭环回归测试 |

## 7. 不能破坏的研究与数据语义

### 7.1 数据分层

- Raw：原始字节、来源、请求、获取时间、校验和、Adapter 版本；只追加、不覆盖；
- Staging：字段名、类型、时间、供应商枚举的可追溯标准化；
- Curated：通过质量门禁的标准快照；
- Research artifacts：股票池、因子、信号、订单、成交、持仓、NAV 和指标；
- UI：只读取这些产物，不维护第二份事实或偷偷纠错。

### 7.2 时间与防泄漏

- 月末收盘形成信号，最早在下一交易日开盘尝试执行；
- 财务报告期不等于信息可用时间；只有公告/来源可用后才能进入 as-of 查询；
- 修订值创建新版本，不能覆盖过去已知版本；
- 今日指数成分股不能回填历史股票池；
- 最终 OOS 区间不得用于调参；带未来收益标签的切分必须有 purge 边界。

### 7.3 交易约束

- 日频数据不等于日频调仓；当前基线为月频，周频仅做敏感性测试；
- A 股整手、佣金最低收费、卖出印花税、滑点均进入成交；
- 停牌、缺失报价、涨跌停和缺失涨跌停价是不同状态；
- 目标组合不等于成交组合；失败订单保留原因并有限重试；
- 当前涨跌停推导可用于功能闭环，但异常交易日最终应由供应商快照字段替换或验证。

### 7.4 研究结论

- 当前真实运行是固定 12 股的集成样本，有幸存者/选择偏差；
- 当前只有价格动量与低波动两个因子；PIT ROA 尚未接入；
- 买入持有、网格、定投比较仍明确记录为 `deferred`；
- 任何收益、Sharpe 或回撤只是流水线输出，不是盈利承诺；
- 不允许按输出表现选择参数后再把同一段数据称作样本外。

## 8. 数据源与密钥交接

### 8.1 BaoStock

- 已接入并真实跑通；
- 不需要账号或 Token；
- 使用未复权日线；
- 可获取历史 ST、交易状态、交易日历和证券基础信息；
- 日线接口不直接提供每日涨跌停价，当前使用版本化交易所规则推导；
- 网络 SDK 已增加 socket deadline 与 EOF 防死循环，但全市场下载仍需断点续传和批次重试。

### 8.2 Tushare

- 用户此前约有 123 积分，预计只有基础权限；接管时重新调用最小接口确认，不凭积分数字猜权限；
- Token 只放 `QUANTFORGE_TUSHARE_TOKEN`；
- 首要用途是抽样交叉验证收盘价、证券元数据和可访问字段，不应成为唯一真相源；
- 权限不足必须产生明确 availability 状态，不能用假数据补齐。

### 8.3 中国银河 AmazingData

用户提供的是一个月试用，后续若使用效果好，可能按券商条件转正式版。用户告知的能力包括
历史日 K、3 秒 Level-1 快照、实时订阅、Linux 部署，以及正式版 2 Mbps 带宽限制、无调用次数
限制。这些商务与权限事实在正式采购前需要重新确认。

本地手册（不在仓库中）：

```text
E:\NaritaVault\00 Inbox\AmazingData开发手册.pdf
```

已从手册确认的 SDK 形态：

- 登录需要 username、password、host、port；
- `BaseData.get_calendar()` 提供交易日历；
- `BaseData.get_stock_basic(code_list)` 提供证券基础信息；
- `MarketData(calendar).query_kline(...)` 返回按代码分组的 DataFrame 字典；
- `query_snapshot(...)` 的快照字段包含 `pre_close`、`high_limited`、`low_limited`、
  `trading_phase_code` 等；
- 日 K 本身只有 OHLC、volume、amount 等，供应商原始涨跌停价需要从快照补充。

AmazingData 仍未实现正式 Adapter。下一位 Agent 的实现要求：

1. SDK 动态加载，公开仓库不包含 wheel、手册或供应商数据；
2. 配置只保存环境变量名，实际值由 `.env` 读取；
3. 登录前检查五个变量是否配置，只返回 presence，不回显值；
4. 会话必须可靠 logout，并对超时、空响应、部分代码失败给出可恢复错误；
5. 历史日 K 与收盘附近的小窗口快照分开请求，避免下载整日 3 秒快照；
6. 供应商代码、日期、时间、成交量单位和停牌枚举必须有显式映射；
7. 用 BaoStock 的历史 ST/交易状态补充或交叉验证时，记录字段级 authority；
8. 冲突先统一单位、复权和时间语义，再按字段权威与容差裁决；未解决差异进入 quarantine；
9. 使用 Fake SDK 写完整单元测试；只有本地凭据存在时才运行 live smoke；
10. 供应商 Raw 与运行产物始终留在 Git ignore 路径。

### 8.4 AKShare、交易所和 CNINFO

- AKShare 是补充/兜底源；多个接口若共享同一上游网站，不算独立交叉验证；
- 交易所用于交易规则、证券身份和官方市场文件；
- CNINFO 用于公告、财报元数据和原文；
- 每个新来源先写 source contract、许可边界、频率、单位、复权和 PIT 语义，再写 Adapter。

## 9. 当前未完成事项与建议路线

### P0：把真实数据底座从“固定样本”升级到“研究可用”

1. 实现 AmazingData Adapter 与 Fake SDK 测试；
2. 建立全市场历史证券发现、分批下载、断点续传和失败重跑；
3. 建立 BaoStock/AmazingData/Tushare 的字段级交叉验证与 quarantine；
4. 接入供应商原始每日涨跌停价，验证并逐步替代推导值；
5. 增加覆盖率、延迟、新鲜度、重复、缺口、单位和跨源差异监控；
6. 记录数据许可、试用截止日期和不可公开字段。

### P1：Point-in-Time 财务与财报

1. 建立 financial facts 的版本化表和 as-of 查询；
2. 接入公告时间、实际来源可用时间和修订版本；
3. 实现 PDF/HTML 校验、文本层检测、页码定位、表格/章节抽取和质量评分；
4. 接入 PIT ROA TTM，恢复冻结的三因子生产协议；
5. 所有模型抽取必须保留原文定位、Schema、Prompt/模型版本和确定性校验。

### P2：因子评价与基线

数据底座通过 P0/P1 后再实现：覆盖率、Rank IC、ICIR、分组收益、衰减、换手、相关性、
walk-forward、purge、成本前后、因子消融，以及买入持有/网格/定投在相同资金与成本假设下的
比较。不要以当前 12 股样本选择参数。

### P3：工程化与展示

- 为网络采集增加 checkpoint、backoff、可恢复清单和增量更新；
- 让 Research Ledger 展示字段 authority、跨源差异、quarantine 和数据新鲜度；
- 补 Day 01、Day 04 以后中英双语学习材料，继续 Python/SQL 为主；
- 生成五分钟项目介绍、十五分钟技术讲解、失败案例和面试追问题库；
- 只有出现多用户、长任务或独立部署需求后，才评估 API 服务、PostgreSQL 或调度器。

## 10. 每个里程碑的工程工作流

1. 读取 `AGENTS.md` 和相关合同/ADR；
2. 检查 `git status`，区分用户已有修改；
3. 写最小失败测试或验收用例；
4. 实现一个可运行的纵向切片；
5. 运行相关单测，再运行完整 pytest、ruff lint、ruff format check；
6. 实际运行离线闭环；涉及真实数据时再运行最小 live smoke；
7. 检查行数、日期、唯一键、质量报告、校验和、研究产物和 UI；
8. 检查 `.env`、数据、PDF、数据库、日志和授权产物未进入 staged diff；
9. 更新 README、合同或 ADR，并写明限制；
10. 小而有意义地提交；确认 `origin/main` 可快进后推送；
11. 向用户报告实际运行证据，而不是只报告改了哪些文件。

推荐的提交前检查：

```powershell
git status --short
git diff --check
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=quantforge --cov-report=term-missing
git diff --cached --stat
```

禁止：跳过测试后声称完成、为过测试而降低合同、提交真实数据、在聊天/日志打印密钥、覆盖 Raw、
静默填充市场事实、破坏性重写 Git 历史、未经用户确认引入付费服务或自动交易。

## 11. 故障处理原则

- **数据商无响应**：有限超时，记录请求，保留已完成批次；不要无限重试；
- **数据为空**：区分无权限、无数据、停牌、非交易日、代码错误和网络失败；
- **跨源冲突**：先对齐代码、日期、单位、复权和时间戳，再比较；不做多数表决；
- **质量失败**：Raw 保留，Curated 阻断；修复规则必须可解释、可测试、可追溯；
- **测试与真实数据不一致**：优先暴露 Fixture 没覆盖的语义，不把真实异常硬改成 Fixture；
- **UI 与清单不一致**：清单/Parquet 是事实源，修复 UI 读取，不在 UI 生成替代数字；
- **本地有未提交修改**：判断归属并绕开；无法安全合并时再询问用户；
- **需要密钥**：要求用户在 `.env` 填写变量，不要求其发送值；
- **需要付费或扩大权限**：停止并明确成本、用途和替代方案，等待授权。

## 12. 新 Agent 接管验收清单

新 Agent 只有在以下项目全部完成后，才算“接管成功”：

- [ ] 已读取 `AGENTS.md`、本文、README、数据合同、陷阱和 ADR；
- [ ] 能说清楚确定性核心与 Agent 层的边界；
- [ ] 已核对规范仓库、目录、分支和 Git 基线；
- [ ] 已安装 Python 3.12 项目依赖；
- [ ] 已运行 lint、format check 和完整测试；
- [ ] 已跑通离线 pipeline；
- [ ] 已跑通离线 experiment，并核对七类研究产物；
- [ ] 已跑通 BaoStock smoke；
- [ ] 网络允许时已跑通真实数据 experiment；
- [ ] 已打开并实际检查 Research Ledger；
- [ ] 已确认 `.env`、数据和授权资料没有进入 Git；
- [ ] 已向用户报告当前事实、限制和下一项 P0 工作；
- [ ] 未重新讨论或改写已经冻结的核心协议。

## 13. 可直接交给新 Agent 的启动 Prompt

```text
你现在接管 QuantForge-Agentic-Platform。

远程仓库：
https://github.com/NaritaC/QuantForge-Agentic-Platform

规范本地目录：
E:\QuantForge-Agentic-Platform

第一步不要写代码。先完整阅读：
1. AGENTS.md
2. docs/agent-handoff.zh-CN.md
3. README.md
4. docs/data-contracts.md
5. docs/quant-data-pitfalls.md
6. docs/secrets.md
7. docs/adr/ 下全部 ADR

然后完成接管验收：
- 检查 Git 状态、main 分支和远端；
- 创建 Python 3.12 虚拟环境并安装 .[dev,ui,baostock]；
- 运行 ruff lint、ruff format check 和 pytest coverage；
- 运行 configs/mvp.yaml 的离线 pipeline；
- 运行 configs/research-demo.yaml 的离线 experiment；
- 运行 configs/baostock-smoke.yaml；
- 网络可用时运行 configs/real-data-research.yaml；
- 启动 8765 端口的 dashboard，并核对数据、质量、血缘、研究产物和限制。

你必须遵守：
- 模型关闭后确定性核心仍能运行；
- Raw 只追加、不覆盖；
- 不伪造、不静默填充市场事实；
- 不泄露或提交密钥、真实数据、PDF、Parquet、数据库和授权产物；
- 信号在收盘形成，最早次日开盘成交；
- 不使用今日成分股回填历史；
- 当前 12 股真实运行只是集成样本，不是策略有效性证据；
- PIT ROA 和基线比较尚未完成，不得伪装成已完成；
- 每个里程碑必须经过测试、真实运行核验、secret/data exclusion 检查后才能推送。

用户每天通常最多投入 1 小时，主要工程代码由你完成。解释以 Python/SQL 为主，学习材料中英双语。
除非方向、付费、密钥或外部权限会发生实质变化，否则自行推进，不要停留在规划。

完成验收后，先向用户报告：
1. 你实际跑通了什么；
2. 测试和数据证据；
3. 当前限制；
4. 你建议立即开始的一个 P0 纵向切片。
```

## 14. 冷启动读者应能回答的问题

如果新 Agent 读完本文仍无法正确回答以下问题，说明交接尚不完整，应先补文档而不是靠口头记忆：

1. 哪个目录和远程仓库才是唯一权威工程？
2. 为什么不直接把今天下载的前复权序列当作历史事实？
3. Raw、Staging、Curated 和 Research artifacts 分别负责什么？
4. 为什么月末信号不能按同一收盘价成交？
5. 固定 12 股真实数据运行为什么仍不能证明策略有效？
6. 涨跌停价来自哪里，当前有什么限制？
7. AmazingData Adapter 还缺什么，密钥应放在哪里？
8. 哪些 Skill/MCP 真正必要，哪些只是效率增强？
9. 一个里程碑在什么证据齐全后才能推送？
10. 接下来最优先的工程切片是什么？
