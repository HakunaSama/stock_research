# 知势 Cheese · 投研智能体 + 量化终端

> 一个**自主股票研究**的全栈实验：纯 Python 的多智能体研究引擎 + 一个深色系量化决策终端前端。
> 底座沿用了 [@karpathy 的 autoresearch](#-appendix-the-original-autoresearch-llm-training-playground) 自主研究理念，把它从"AI 自己训练 LLM"迁移到"AI 自己做投研"。

<p align="center">
  <img src="https://copilot-cn.bytedance.net/api/ide/v1/text_to_image?prompt=dark%20themed%20quantitative%20trading%20terminal%20dashboard%2C%20candlestick%20chart%20with%20red%20and%20green%20candles%2C%20moving%20average%20lines%2C%20volume%20bars%2C%20research%20panel%20with%20score%20gauges%2C%20cyberpunk%20fintech%20UI%2C%20deep%20navy%20background%2C%20neon%20accents%2C%20highly%20detailed%2C%20professional%20product%20screenshot&image_size=landscape_16_9" alt="Stock Terminal preview" width="82%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/backend-pure%20Python-3776AB?logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/frontend-React%20%2B%20TS%20%2B%20Vite-61DAFB?logo=react&logoColor=black" alt="react" />
  <img src="https://img.shields.io/badge/deps-stdlib%20%2B%20requests-brightgreen" alt="deps" />
  <img src="https://img.shields.io/badge/K--line-real%20A--share%20OHLCV-ff5b5b" alt="kline" />
</p>

---

## ✨ 这是什么

给一个 AI 智能体一套**真实但小巧的投研工作流**，让它自己跑：读策略 → 联网做深度研究 → 拉真实 K 线提技术特征 → 六阶段分析 → 出带评分、可回溯的投资结论。整套后端**零重依赖**（标准库 + `requests`），前端是一个**手绘 SVG、零图表库**的量化决策终端。

| 你会得到 | 说明 |
|---|---|
| 🧠 **多智能体研究引擎** | langchain-ai/open_deep_research 的纯 Python 复刻：生产者产出研究，独立裁判打分，低分**整体重跑**（无反馈重试，最多 8 次） |
| 📈 **真实 K 线 + 技术特征** | 通过 vendored `stocksdk` 拉 A 股真实 OHLCV，纯 Python 算 MA / RSI / MACD / 关键价位 / 量比 / 蜡烛形态 |
| 🎛️ **量化决策终端前端** | React + TS + Vite，深色主题、A 股涨红跌绿、手绘蜡烛图、ODR 研究面板、评分闭环时间线 |
| 🔌 **全真实数据终端** | 实时指数/报价/K线/个股资讯全部来自真实行情源（多源故障转移）；研究结论/评分/来源全部读后端真实产物，前端零 mock |
| 🤖 **可插拔真实大模型** | 一个 `urllib` 写的 OpenAI 兼容适配器，换 `.env` 三个值即可驱动火山方舟 / OpenAI / DeepSeek / 通义 等；`FakeLLM` 仍可零 key 离线跑 |

---

## 🗂️ 仓库结构

```
autoresearch/
├── stock-research-agent/     # 后端：纯 Python 投研智能体
│   ├── stock_agent/          #   策略热插拔 · K线特征 · ODR 研究引擎 · 6阶段分析
│   ├── vendor/stocksdk/      #   vendored 的 A股行情 SDK（见 vendor/NOTICE.md）
│   ├── hermes_tools/         #   hermes 框架工具封装（standalone 时为 no-op）
│   ├── serve.py              #   stdlib HTTP bridge：暴露 run 的 context / K线
│   ├── run_demo.py           #   FakeLLM 离线跑通全流程（无需 key）
│   ├── run_live.py           #   真实大模型跑全流程（读 .env）
│   ├── .env.example          #   大模型端点配置模板（火山方舟/OpenAI/DeepSeek...）
│   └── seed_runs.py          #   产出两只股票的样例 run（含真实 K线）
├── stock-terminal/           # 前端：React + TS + Vite 量化决策终端
│   └── src/                  #   蜡烛图 · 特征卡 · ODR 研究面板 · api 适配层
├── docs/                     # 设计文档
└── (train.py / prepare.py / program.md ...)  # ↓ 原 karpathy autoresearch 训练底座
```

---

## 🚀 快速开始

### 1) 后端：跑一次完整投研（无需 API key）

```bash
cd stock-research-agent
python3 run_demo.py
```

用确定性的 `FakeLLM`（不联网、不需要 key）跑完整条 pipeline，打印结论 + 风险块 + 质量评分。

### 2) 前后端联动（真实行情 + 真实研究产物）

```bash
# 后端：产出样例 run 并起 FastAPI（鉴权/行情/任务队列都在这）
cd stock-research-agent
pip install -r requirements.txt
python3 seed_runs.py /tmp/stock-terminal-data     # 000100 / 002185，含真实日K
STOCK_DATA_DIR=/tmp/stock-terminal-data python3 -m uvicorn webapp.app:app --port 8000

# 前端：另开一个终端（dev server 自动把 /api 反代到 127.0.0.1:8000，同源无 CORS）
cd stock-terminal
pnpm install        # 或 npm install
pnpm dev
```

注册登录后即是完整终端：顶栏实时指数、自选池实时报价（5s 轮询）、任意标的实时
K 线（日/周/月/60分）、个股真实资讯、已研究标的的 AI 结论卡与完整研究过程抽屉。
后端地址可用环境变量 `BACKEND_ORIGIN` 覆盖（默认 `http://127.0.0.1:8000`）。

### 3) 接真实大模型跑全流程（可选）

`run_demo.py` 用的是确定性 `FakeLLM`（不联网）。想让**真实大模型**驱动整条链路（策略编译 → ODR 深度研究 → 真实 K 线 → 六阶段分析），用 [`run_live.py`](stock-research-agent/run_live.py)：

```bash
cd stock-research-agent
cp .env.example .env        # 然后填入 base_url / api_key / model（.env 已被 .gitignore 忽略）
python3 run_live.py                       # 默认标的 600519 贵州茅台
python3 run_live.py 000100 "华星光电 1-3 个月是否值得布局？"
```

适配器 [`stock_agent/live_llm.py`](stock-research-agent/stock_agent/live_llm.py) 只讲 OpenAI 标准的 `/chat/completions`，用标准库 `urllib` 发请求（**零重依赖**），因此**任何 OpenAI 兼容端点**都能用——换 `.env` 里三个值即可切换：

| 提供商 | `STOCK_LLM_BASE_URL` | `STOCK_LLM_MODEL` |
|---|---|---|
| 火山方舟 / Ark | `https://ark.cn-beijing.volces.com/api/v3` | `ep-xxxx`（推理接入点）或 `doubao-...` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |

> 🔑 **凭据只从环境变量 / 本地 `.env` 读取，绝不写进代码**。`.env` 已被 `.gitignore` 挡住，不会被提交。
> ⏱️ 推理型模型（带思维链）单次响应较慢，`run_live.py` 已调小 ODR 并行度/轮数让首次跑通更快；想更快可换非推理的快模型或继续调低这些值。

---

## 🧩 后端四大模块

线程一个 `ResearchContext` 贯穿始终，落盘到 `~/.hermes/stock/<run_id>/`。

| # | 模块 | 代码 | 做什么 |
|---|---|---|---|
| 1 | 策略热插拔 | `stock_agent/strategy.py` | 把裸策略（文本或本地 `strategy.md`）编译成严格 schema + 逐条规则的 prompt 块（仅本地文件，不抓 URL/Git） |
| 2 | K 线特征 | `stock_agent/kline.py` + `kline_features.py` | 拉真实 A 股 OHLCV，提六个技术特征（趋势/均线/关键价位/形态/量能/指标），离线时优雅退回 placeholder |
| 3 | 深度研究 | `stock_agent/research.py` + `odr/` | 生产者产研究，独立裁判打分：≥阈值接受，否则**整体无反馈重跑**（默认 ODR 多智能体引擎） |
| 4 | 分析（核心） | `stock_agent/analysis.py` | **6 阶段**：基本面→技术面→策略契合→综合定线→结论→风险&执行；事实阶段自校验重试，终裁把关 S4-S6 |

> 完整设计见 [`docs/stock-research-agent-design.md`](docs/stock-research-agent-design.md)。

---

## 📈 K 线数据源（真实 OHLCV）

[`stock_agent/kline.py`](stock-research-agent/stock_agent/kline.py) 通过 **vendored 的 `stocksdk`**（腾讯/东财/新浪多源自动故障转移，仅依赖 `requests`）拉真实 A 股 OHLCV，[`kline_features.py`](stock-research-agent/stock_agent/kline_features.py) 把 K 线算成六个技术特征写进 `ctx.kline`。全链路优雅降级：拉取失败（离线 / 非 A 股代码）或 `config.kline.enabled=False` 时，槽位保持 `placeholder`、特征全 null，**其它模块零改动**。

> ⚠️ `vendor/stocksdk` 是第三方代码，来源与许可见 [`stock-research-agent/vendor/NOTICE.md`](stock-research-agent/vendor/NOTICE.md)。上游仓库未声明开源协议，公开分发前请先获授权或替换实现。

---

## 🎨 前端亮点

- **全真实数据**：指数/报价/K线/资讯/全市场榜单（涨幅/跌幅/成交额）全部来自真实行情源（腾讯/东财/新浪，多源故障转移），前端无任何硬编码行情。
- **Ant Design 组件体系**：暗色主题定制；Tabs / Card / Segmented / Drawer / AutoComplete / Form / Dropdown 等通用组件承载主交互。
- **竞品级交互**：左侧「自选 + 全市场榜单」动态股票池（搜索/榜单一键加自选，本地持久化）；顶栏全局搜索（代码/名称/拼音）；5s 行情轮询；K 线周期切换 + 悬停十字线。
- **零图表依赖**：蜡烛图、均线、成交量柱、支撑/压力标线全部手绘 SVG。
- **A 股配色**：涨红跌绿，石墨蓝 + 终端金的深色量化风。
- **可回溯**：ODR 研究面板展示子研究、评分闭环时间线、重试历史；未研究标的可一键发起真实多智能体研究（对接点数计费）。

---

## 📎 Appendix — the original `autoresearch` (LLM training playground)

本仓库的底座是 [@karpathy](https://x.com/karpathy/status/2029701092347630069) 的 **autoresearch**：给 AI 智能体一套小而真实的 LLM 训练环境，让它整夜自主实验——改代码、训 5 分钟、看指标是否变好、保留或丢弃、循环往复。核心思路是你不直接改 Python，而是编写 `program.md` 这类 Markdown"研究组织程序"来给智能体提供上下文。

保留下来的相关文件：

```
prepare.py      — 常量、数据准备 + 运行时工具（不修改）
train.py        — 模型、优化器、训练循环（智能体修改此文件）
program.md      — 智能体指令
pyproject.toml  — 依赖
```

**Quick start（训练底座）**：需要单张 NVIDIA GPU（在 H100 上测试）、Python 3.10+、[uv](https://docs.astral.sh/uv/)。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # 安装 uv
uv sync                                           # 装依赖
uv run prepare.py                                 # 一次性下数据 + 训 tokenizer
uv run train.py                                   # 跑一次 5 分钟训练实验
```

指标是 **val_bpb**（越低越好）。更多背景与调小模型的建议参见原项目说明与 [nanochat](https://github.com/karpathy/nanochat)。

---

## 📄 License

- 训练底座（`train.py` / `prepare.py` / `program.md` 等）沿用原 autoresearch 的 **MIT** 许可。
- `stock-research-agent/vendor/stocksdk` 为第三方代码，许可状态见其 `NOTICE.md`——**再分发前需单独确认**。
