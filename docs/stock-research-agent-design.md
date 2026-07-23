# 股市调研智能体 —— 基于 Hermes Agent 的改造设计

> 状态：**架构设计 v0.3**，关键决策已锁定（见 §8）。DeepResearch 生产者已升级为 ODR 多 agent 引擎（见 §5.5）。
> 底座框架：Nous Research [hermes-agent](https://github.com/nousresearch/hermes-agent)（MIT，Python，本地已参考 clone 于 `/tmp/hermes-agent-ref`）。
> 参考项目：(1) 本仓库 autoresearch（Karpathy 的自主实验循环），借鉴其"打分—重试"闭环；(2) [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research)，DeepResearch 生产者对齐其多 agent 做法（纯 Python 移植，见 §5.5）。

---

## 0. TL;DR（一页看懂）

我们要把 hermes-agent 改造成一个**股市调研智能体**。它由一个"主控 agent"编排四类能力，最终产出一份可执行的调研结论：

| 模块 | 形态（在 hermes 里的落地方式） | 状态 |
|---|---|---|
| **1. 策略热插拔** | Skills 系统（`SKILL.md`）+ 一个"策略编译器"把用户/大V的原始策略规整成 LLM 友好的提示词 | 本期设计+实现 |
| **2. K线拉取** | 一个自定义 Tool（`registry.register`）+ 一个 skill，**先留占位**，等你给文档再补 | 本期只留 stub |
| **3. DeepResearch** | 一个 `delegate_task` 子 agent + **judge 打分/无反馈重试**闭环 | 本期设计+实现 |
| **4. 分析模块（重头戏）** | 一个多阶段子 agent，吃掉 search/K线/策略三路输入，分 6 个阶段产出结论 | 本期设计（阶段切分是本文重点） |

四个模块通过一个统一的 **调研任务上下文（`ResearchContext`）** 串起来：策略 → 资料 → K线 → 分析 → 结论。

---

## 1. 为什么选 hermes-agent 作为底座

先说清楚现状，避免误会：

- 本仓库 `autoresearch`（[train.py](file:///Users/bytedance/Desktop/autoresearch/autoresearch/train.py) / [program.md](file:///Users/bytedance/Desktop/autoresearch/autoresearch/program.md)）其实是 **LLM 预训练**的自主实验循环，**不是**通用 research agent。它值得借鉴的只有一点：`program.md` 里那个"跑一次 → 看指标 → 满意就 keep、不满意就 discard/重来"的**自主循环 + 质量门控**思路。这正好对应你要的 **deepresearch 打分重试**。
- 真正的 agent 底座是 hermes-agent。它天然具备我们需要的四块地基：

| 我们的需求 | hermes 现成机制 | 关键位置 |
|---|---|---|
| 策略热插拔 | **Skills 系统**：每个 skill 是一个带 YAML frontmatter 的 `SKILL.md` 目录，运行时被扫描成"索引"注入系统提示，模型按需 `skill_view` 读全文 | `agent/prompt_builder.py:1445` `build_skills_system_prompt`；`agent/system_prompt.py:292-322`；`tools/skills_hub.py`（安装/来源） |
| 子 agent（deepresearch / 分析） | **`delegate_task` 委派**：可给子 agent 独立的 system prompt、独立 toolset、独立模型；支持并行 tasks、同步/后台返回 | `tools/delegate_tool.py:3465`（注册）、`:1044`（`_build_child_agent`）、`:661`（子 prompt） |
| K线 / 自定义能力 | **Tool 注册表**：`registry.register(name, toolset, schema, handler, ...)`，import 时自动发现 | `tools/registry.py:356`；`toolsets.py:95`（TOOLSETS）、`:882`（自定义 toolset） |
| 拼装人设+记忆+策略 | **Prompt Builder**：SOUL.md + MEMORY.md + skills 索引 + 上下文文件 | `agent/system_prompt.py:145` `build_system_prompt_parts` |
| 已有金融/研究 skill 可参考 | `optional-skills/finance/stocks`（Yahoo 行情，stdlib，JSON 输出）、`optional-skills/research/*`（搜索/deep-research） | 直接当模板 |

**结论**：不重写框架，而是以"新增 skills + 新增 tools + 新增两个委派子 agent + 一个调研编排 skill"的方式，把 hermes 定制成股市调研智能体。改动集中、可回滚、跟着上游 rebase 也不痛。

---

## 2. 顶层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     主控 Agent (Orchestrator)                          │
│  由 SKILL: stock-research-orchestrator 驱动                            │
│  职责：接收用户请求(标的/问题) → 编排四模块 → 汇总产出结论               │
└───────┬───────────────┬────────────────┬───────────────┬─────────────┘
        │               │                │               │
        ▼               ▼                ▼               ▼
  ┌──────────┐   ┌─────────────┐   ┌───────────┐   ┌──────────────────┐
  │ 策略编译  │   │ K线拉取      │   │ DeepResearch│  │  分析子 Agent      │
  │ (skill+   │   │ (tool，占位) │   │ 子Agent     │  │ (多阶段，重头戏)   │
  │  tool)    │   │             │   │ +judge重试  │  │                   │
  └────┬─────┘   └──────┬──────┘   └─────┬───────┘   └────────┬─────────┘
       │                │                │                     │
       ▼                ▼                ▼                     │
  策略提示词块      K线特征JSON       市场资料摘要(合格)          │
       └────────────────┴────────────────┴─────────────────────┘
                                │
                    统一注入 ResearchContext
                                │
                                ▼
                        最终调研结论报告
```

### 2.1 统一数据契约：`ResearchContext`

四个模块之间不要口口相传，用一个结构化对象承接，落盘为 JSON（放 `~/.hermes/stock/<run_id>/context.json`），也便于调试和复现：

```jsonc
{
  "run_id": "2026-07-09-AAPL-x1",
  "query": { "target": "AAPL", "question": "近期是否值得买入", "horizon": "1-3个月" },
  "strategy": {
    "compiled_prompt": "……策略编译器产出的提示词块……",
    "source": "user | bigv:<name>",
    "raw_ref": "strategies/momentum_zhangda.md",
    "checks": ["需 MACD 金叉", "量能放大", "……"]   // 结构化断言，供分析阶段核对
  },
  "kline": { "status": "placeholder", "features": null },  // 本期占位
  "research": {
    "status": "accepted",
    "score": 8.7,
    "attempts": 3,
    "digest": "……合格的市场资料摘要……",
    "sources": [ {"title":"…","url":"…","date":"…"} ]
  },
  "analysis": { /* 分析子 agent 分阶段填充，见 §6 */ }
}
```

> 实现上，`ResearchContext` 用一个轻量 Python dataclass + JSON 序列化即可，不引入重依赖。

---

## 3. 模块一：策略热插拔（Strategy Hot-Plug）

### 3.1 用户视角

用户可以：(a) 自己写策略；(b) 从大V那里拿一段策略文本/文件丢进来。策略五花八门——有的是自然语言（"回踩20日线不破 + 放量")、有的是伪代码、有的是一堆指标条件。**不能直接把原文塞给大模型**，需要先"编译"成结构化、无歧义、LLM 好理解的提示词。

### 3.2 落地方式：Skill + 策略编译器 Tool

复用 hermes 的 skills 机制（策略天然就是"热插拔的领域知识"）：

```
skills/stock/strategies/                     # 策略库根目录（可配 external_dirs）
  momentum_zhangda/
    SKILL.md            # frontmatter: name/description/tags/author(大V名)
    strategy.md         # 策略原文（用户/大V提供）
  mean_reversion_user/
    SKILL.md
    strategy.md
```

新增一个 **策略编译器 tool**：`strategy_compile`（`tools/stock_strategy.py`，走 `registry.register`）。它做三件事：

1. **解析**：读入原始策略文本（`strategy.md` 或用户直接粘贴）。
2. **规整**：调一次 LLM（小模型即可），把原文转成固定 schema：
   ```jsonc
   {
     "name": "张大-动量策略",
     "thesis": "顺势而为，只做强势股回踩",
     "entry_rules":  ["回踩20日均线不破", "MACD 金叉", "成交量较5日均量放大>50%"],
     "exit_rules":   ["跌破10日线", "MACD 死叉"],
     "risk_rules":   ["单笔止损 -8%", "仓位≤30%"],
     "indicators":   ["MA20","MA10","MACD","VOL"],
     "timeframe":    "日线",
     "assumptions":  ["适用于牛市/震荡市，熊市失效"],
     "ambiguities":  ["'放量'的阈值原文未定义，已假设>50%"]  // 显式标注模糊点
   }
   ```
3. **渲染**：把 schema 渲染成一段**提示词块**（`compiled_prompt`），写回 `ResearchContext.strategy`。分析阶段用它，并用 `entry_rules/exit_rules/risk_rules` 作为可核对的**结构化断言**。

> 关键设计点：编译器把"模糊策略"显式转成"带假设声明 + 可核对断言"的结构。这样分析子 agent 不是"感觉符合策略"，而是**逐条核对**规则，结论可追溯。

### 3.3 评审要确认的点
- 策略编译用哪个模型？（建议：便宜快的模型，如 config 里 delegation.model 那一档）
- 策略库放本地目录还是也支持从 URL/Git 拉（hermes 的 `skills_hub` 支持）？

---

## 4. 模块二：K线拉取（占位）

**本期只留占位**，等你给拉取文档再实现。但接口先定好，免得后面返工：

- 新增 tool：`kline_fetch`（`tools/stock_kline.py`）。入参 `{symbol, timeframe, range}`，出参统一为 **K线特征 JSON**（不是原始 OHLCV 一大坨，而是给 LLM 消化过的特征）：
  ```jsonc
  {
    "status": "placeholder",   // 实现后改 "ok"
    "symbol": "AAPL", "timeframe": "1d", "range": "6mo",
    "features": {
      "trend": null,             // 例: "上升趋势/震荡/下降"
      "ma_state": null,          // 例: 均线多头排列
      "key_levels": null,        // 支撑/压力位
      "patterns": null,          // 形态: 头肩顶/旗形…
      "volume_state": null,      // 量能特征
      "indicators": null         // MACD/RSI/KDJ 数值+信号
    },
    "raw_ref": null              // 原始数据落盘路径，供画图/复核
  }
  ```
- 现在 handler 直接返回 `status: "placeholder"`，分析阶段遇到 placeholder 时跳过技术面细节、并在结论里标注"技术面数据缺失"。
- 你给文档后：在 handler 里接入真实数据源 + 一个"特征提取"函数（把 OHLCV 算成上面的 features），其余模块**零改动**。

---

## 5. 模块三：DeepResearch 子 Agent（含无反馈重试打分）

### 5.1 目标
搜集标的相关的市场信息（新闻、财报要点、公告、研报观点、舆情），产出一份**高质量的资料摘要 `digest`**，供分析阶段使用。

### 5.2 落地方式：委派子 agent + judge 闭环

用 `delegate_task` 起一个 **research 子 agent**（独立 system prompt + 只给它 `web_search`/`web_extract` 等检索类 toolset）。外面套一个 **judge 打分 + 无反馈重试**的循环——这正是借鉴 [program.md](file:///Users/bytedance/Desktop/autoresearch/autoresearch/program.md) 里 keep/discard 的思路：

```
attempt = 0
best = null
LOOP:
    attempt += 1
    digest = run_research_subagent(query)          # 子agent 检索+汇总
    score, reasons = judge(digest, query)          # judge 打分(0-10) + 打分理由(仅内部)
    if score >= THRESHOLD (如 8.0):
        accept(digest); break
    if score > best.score: best = (digest, score)   # 记住最好的
    if attempt >= MAX_ATTEMPTS (如 5):
        accept(best.digest 并标注"未达阈值，取最优"); break
    # 关键：重试时【不把 judge 的理由喂回去】，只是重跑
    continue
```

### 5.3 关键设计点（按你的要求）

- **judge 是独立的一次 LLM 调用**，用一套固定 rubric 打分（覆盖度、时效性、来源可信度、是否切题、有无幻觉/无出处断言）。judge 的 prompt 和 research 的 prompt **分离**，避免"自己判自己"过松。
- **重试不给 feedback**：judge 的理由只写进日志，**不回灌**给 research 子 agent。每次重试是"重新抽样"（可以靠调高 temperature / 换搜索词的随机性获得多样性），一直重试到达标或触顶。
  - 设计理由：无反馈重试是"多次独立采样取合格样本"，避免 agent 顺着 judge 的话把 digest 改得像"应试"而非真实提升质量。
- **兜底**：设 `MAX_ATTEMPTS` 上限（防止无限循环烧钱），触顶后取历史最佳并显式标注质量不足。
- **可复现**：每次 attempt 的 digest + score 落盘到 `~/.hermes/stock/<run_id>/research/attempt_N.json`。

### 5.4 评审要确认的点
- 阈值 THRESHOLD 和 MAX_ATTEMPTS 定多少？（建议 8.0 / 5 起步，可配）
- 重试的"多样性"从哪来：升温度？换 query 改写？还是两者都要？
- judge 用同一个大模型还是换一个"更严"的模型？

### 5.5 研究"生产者"引擎：Open-Deep-Research（v0.3 新增）

§5.2 的循环里，"跑一次调研产出 digest"这个**生产者是可插拔的**（`Researcher` 协议：`__call__(...) -> {digest, sources}`）。v0.3 把默认生产者从"单次 LLM 调用"升级成**对齐 langchain-ai/open_deep_research（ODR）的多 agent 引擎**（纯 Python 移植，不引入 LangGraph 依赖）。

**关键点：ODR 引擎与外层 judge 打分重试是正交组合的。**

```
run_deep_research（外层：judge 打分 + 无反馈重试，§5.2 不变）
  └── 每次 attempt 调用生产者 = OpenDeepResearcher（内层：完整 ODR 流程）
        clarify_with_user      # 可配置开关，默认关（自主运行，无人值守）
          → write_research_brief   # 把 query 收敛成研究简报 + 子问题
            → supervisor 循环（最多 max_supervisor_iterations 轮）：
                 supervisor 反思(think) → 委派 N 个子主题（并行）
                   → 每个子研究员跑有界 ReAct + think_tool 反思
                   → 压缩每份发现（compression 模型）
                   → 发现回灌 supervisor，决定继续或结稿
            → final_report_generation   # 汇总所有压缩笔记成最终报告
```

产出的**最终报告**即作为该 attempt 的 `digest` 交给独立 judge 打分。**若分数低于阈值 → 整个 ODR 流程重跑一遍**（下一个 attempt），直到达标或触顶 `MAX_ATTEMPTS`——这正是你要的"对 ODR 结果最终评分、过低则重新走 ODR 流程"。

**ODR 引擎 vs 旧单次引擎（对照）**

| 维度 | 旧 `LLMResearcher`（`engine="legacy"`） | ODR `OpenDeepResearcher`（`engine="odr"`，默认） |
|---|---|---|
| 架构 | 单次 LLM 调用 | 多 agent：supervisor 编排 + 并行子研究 |
| 多样性 | 角度轮换 + 升温（外层给） | 空间并行（一次铺开多个子主题）+ 反思 |
| 质量把关（内层） | 无 | supervisor 反思(think_tool) + 充分性判断 + 轮数上限 |
| 质量把关（外层） | 独立 judge 打分重试 | **同一套独立 judge 打分重试（复用）** |
| 产物 | 一段 digest | 研究简报 → 压缩笔记 → 最终报告 |
| 模型分档 | research/judge 两档 | summarization/research/compression/final_report 四档 |

**配置**（`config.research`）：

- `engine`: `"odr"`（默认）| `"legacy"`
- `odr.clarify_enabled`: 澄清反问开关，**默认 `false`**（自主运行）。交互式场景可开；开启且触发澄清时，`ODRResult.clarification_needed` 会带回要问用户的问题而非擅自假设。
- `odr.max_supervisor_iterations`（默认 4）/ `odr.max_researcher_iterations`（默认 6）/ `odr.max_concurrent_units`（默认 4）
- `odr.{summarization,research,compression,final_report}_model`: 四档模型路由（`None` 回退到 research 模型）。

**落地文件**：`stock_agent/odr/{state.py,pipeline.py,retriever.py,__init__.py}` + `prompt_templates/odr_{clarify,brief,supervisor,researcher,compress,final_report}.md`；生产者选择集中在 `research.build_researcher(llm, config, retriever=...)`，orchestrator 与 hermes `deep_research` 工具均经它选引擎。

**子研究检索接缝（可注入）**：每个子主题"怎么查"被抽象成 `odr/retriever.py` 的 `Retriever` 协议 `(topic, brief, horizon, temperature) -> SubFinding`：
- **standalone/测试**：默认 `LLMSubResearcher`——单次 LLM 调用（无实时 web，来源可能是示意性的）。
- **hermes 生产**：`hermes_tools/odr_retriever.py` 的 `DelegateRetriever`——用 `delegate_task` 起一个带 `web_search`/`web_extract` 的子 agent 做真实检索,再把自由文本结构化成 `SubFinding`。hermes 委派 API 的具体签名由 `resolve_delegate()` **运行时探测**（参考源码不可得时优雅回退到 LLM 桩，带 `TODO(hermes-delegate)` 标记），不硬编码臆测。`build_researcher(..., retriever=...)` 决定注入哪个;`deep_research` 工具在 hermes 内优先注入 `DelegateRetriever`,探测不到就回退。

**ODR trace 持久化（供前端消费）**：`ResearchSlot` 新增三处——`engine`（odr|legacy）、`history`（每次 attempt 的 `score/accepted/judge/supervisor_rounds/sub_topics`，即"5.0✗→...→8.5✓"重跑时间线）、`odr`（被接受/最优那次的完整 trace：`brief`/`sub_questions`/`findings`（含 topic/notes/sources/reflections）/`notes`（压缩笔记）/`supervisor_rounds`）。每次 attempt 的完整 trace 也落盘到 `<run>/research/attempt_N.json`。前端 `stock-terminal` 的 ODR 研究面板即消费 `ctx.research.{odr,history}`。

> 与 ODR 原版的差异（已知、有意为之）：(1) 无 LangGraph，改用 dataclass + 函数调用 + 线程池并行；(2) 生产环境的实时检索通过 `Retriever` 接缝走 hermes 的 `delegate_task` 子 agent（web_search/web_extract）注入，standalone/测试用单 LLM 桩；(3) 在 ODR 之上**额外**套了一层独立 judge 打分重试（ODR 原版运行时没有这层，只有离线评测用 LLM-judge）——这是本项目的核心增强。

---

## 6. 模块四：分析子 Agent（重头戏）—— 阶段切分设计

这是你最关心、也最需要我帮你切分的部分。分析要做的事太多（看资料、看K线、核对策略、还要面向选股/择时/板块/组合四类决策），单轮 prompt 塞不下也容易糊。所以拆成**6 个阶段（pipeline）**，每个阶段是一次带明确输入/输出契约的 LLM 调用，前一阶段的产出是后一阶段的输入。

### 6.1 为什么这么切（设计原则）

1. **认知顺序**：人类分析师也是"先分头看清楚各个面 → 再交叉验证 → 再下结论 → 再管风险"。阶段顺序模拟这个过程。
2. **单一职责**：每个阶段只干一件事，prompt 短、可评测、可单独重试。
3. **可追溯**：每阶段产出结构化 JSON，最终结论能回溯到"哪个证据/哪条规则"。
4. **面向你的四类决策场景**（选股筛选 / 个股择时 / 宏观板块 / 组合风险）——通过阶段 4 的"决策路由"分流，而不是为每类场景各写一套 pipeline。

### 6.2 六个阶段总览

| 阶段 | 名称 | 输入 | 输出 | 一句话职责 |
|---|---|---|---|---|
| S1 | **基本面/资料解读** | research.digest | `fundamental_view` | 从市场资料里提炼多空要点、催化剂、风险事件 |
| S2 | **技术面解读** | kline.features（本期多为 placeholder） | `technical_view` | 从K线特征读趋势/位置/量价/形态信号 |
| S3 | **策略符合度核对** | strategy.compiled + S1 + S2 | `strategy_fit` | 逐条核对策略 entry/exit/risk 规则是否满足 |
| S4 | **交叉验证 & 决策路由** | S1+S2+S3 | `synthesis` + `decision_type` | 三面互相印证/冲突识别；判定本次属于哪类决策场景 |
| S5 | **结论生成** | S4（按 decision_type 走对应子逻辑） | `verdict` | 给出方向/评级/理由（选股/择时/板块/组合各自的结论形态） |
| S6 | **风险与执行** | S5 + strategy.risk_rules | `risk_and_exec` | 仓位建议、止损位、失效条件、不确定性与免责 |

> S5 内部按 `decision_type` 分流（不是新开 pipeline，只是换 prompt 模板）：
> - `stock_pick`（选股筛选）→ 评分 + 是否入选 + 理由
> - `timing`（个股择时）→ 买入/卖出/观望 + 触发条件
> - `sector`（宏观板块）→ 看多/看空/中性 + 驱动因子
> - `portfolio`（组合风险）→ 配置权重/敞口/对冲建议

### 6.3 各阶段契约（关键 I/O）

**S1 基本面/资料解读**
```jsonc
"fundamental_view": {
  "bull_points": ["…"], "bear_points": ["…"],
  "catalysts": [{"event":"财报 7/25","impact":"高","direction":"未知"}],
  "risk_events": ["诉讼","监管"],
  "confidence": 0.0-1.0,
  "evidence": [{"claim":"…","source_idx":2}]   // 指向 research.sources
}
```

**S2 技术面解读**（placeholder 时输出 `"available": false`）
```jsonc
"technical_view": {
  "available": true,
  "trend":"上升", "position":"回踩MA20", "volume":"温和放量",
  "signals":[{"name":"MACD","state":"金叉在即"}],
  "key_levels":{"support":180,"resistance":205}, "confidence":0.6
}
```

**S3 策略符合度核对**（逐条打勾，最能体现"策略驱动"）
```jsonc
"strategy_fit": {
  "entry":[{"rule":"回踩20日线不破","met":true,"basis":"S2.position"},
           {"rule":"MACD金叉","met":"partial","basis":"S2.signals"}],
  "exit":[…], "risk":[…],
  "fit_score": 0.0-1.0,          // 综合符合度
  "blocking_violations": ["…"]   // 触发即否决的硬规则
}
```

**S4 交叉验证 & 决策路由**
```jsonc
"synthesis": {
  "agreements":["基本面偏多且技术面回踩确认"],
  "conflicts":["资料看多但量能不足"],
  "net_bias":"偏多/中性/偏空",
  "confidence":0.0-1.0
},
"decision_type": "timing"   // stock_pick|timing|sector|portfolio
```

**S5 结论**（以 timing 为例）
```jsonc
"verdict": {
  "type":"timing", "action":"逢低买入", "rating":"B+",
  "rationale":["策略entry满足3/3","净偏多","催化剂临近"],
  "conditions":["站稳MA20再进","财报前控制仓位"]
}
```

**S6 风险与执行**
```jsonc
"risk_and_exec": {
  "position_pct": "≤20%", "stop_loss": 178,
  "invalidation": ["跌破MA20且放量","财报暴雷"],
  "uncertainty":"技术面数据缺失，置信度打折",
  "disclaimer":"本结论为研究参考，非投资建议"
}
```

### 6.4 实现方式与两个可选项

- **落地**：分析子 agent 也用 `delegate_task` 起（或直接在 orchestrator skill 里按阶段串行调用 LLM）。每阶段一个 prompt 模板文件放 `skills/stock/analysis/prompts/S{n}_*.md`。
- **阶段间是否需要各自的质量门控？** 两个选项供你选：
  - **A（简单）**：只在最外层对最终 `verdict` 做一次 judge，不合格则整条 pipeline 重跑。
  - **B（稳健）**：S1/S2/S3 这类"事实提取"阶段各自带轻量校验（比如 S1 的每条 claim 必须有 source_idx，否则该阶段重试），S4-S6 只做一次终检。
  - 我的倾向是 **B**，因为事实层出错会污染后面所有阶段；但 B 更费 token。**这个请你拍板。**

### 6.5 评审要确认的点（分析模块）
1. 6 阶段的切分是否符合你的心智？是否要**合并**（如 S5+S6 合并）或**拆分**（如 S1 再拆"新闻/财报/研报观点"）？
2. `decision_type` 是让模型在 S4 自动判定，还是用户一开始就指定？
3. 阶段间质量门控选 A 还是 B（§6.4）？
4. 四类决策场景的**结论形态**（S5 各分支的字段）是否符合你的预期？

---

## 7. 落地文件清单（实现阶段将新增/改动）

> 均为"新增"为主，尽量不动 hermes 上游文件，便于后续 rebase。

```
skills/stock/
  stock-research-orchestrator/SKILL.md   # 主控编排：串起四模块
  strategies/<name>/SKILL.md + strategy.md# 策略库（热插拔）
  analysis/prompts/S1..S6_*.md           # 分析6阶段 prompt 模板
tools/
  stock_strategy.py                      # strategy_compile tool
  stock_kline.py                         # kline_fetch tool（占位）
  stock_research.py                      # deepresearch 委派+judge 闭环
  stock_analysis.py                      # 分析6阶段 pipeline 编排
  stock_context.py                       # ResearchContext dataclass + 落盘
toolsets.py                              # 注册一个 "stock" toolset(改1处)
docs/stock-research-agent-design.md      # 本文档
```

---

## 8. 已锁定的关键决策（汇总）

1. **策略编译**：模型可配置（缺省用便宜档）；策略库**只用本地目录**，不做 URL/Git 拉取。
2. **DeepResearch**：`THRESHOLD=8.0`、`MAX_ATTEMPTS=8`（可配）；judge 模型可配、缺省不换更严的；重试多样性用"query 改写 + 检索面轮换 + temperature 轻微上浮"的组合（§5.4）。
3. **分析阶段切分**：6 阶段不变；`decision_type` 用户可指定、否则 S4 自动判定；阶段门控用 **B**；四类结论形态已确认。
4. **K线**：本期只留 placeholder，接口先定死，等文档再接真实数据源。

**实现顺序**：`ResearchContext`（`stock_context.py`）→ 策略编译（`stock_strategy.py`）→ DeepResearch 闭环（`stock_research.py`）→ K线 stub（`stock_kline.py`）→ 分析 6 阶段 pipeline（`stock_analysis.py` + `analysis/prompts/S1..S6`）→ 编排 skill（`stock-research-orchestrator`）→ 注册 `stock` toolset。

---

*文档结束。评审通过后，我会据此进入实现，并优先搭 `ResearchContext` + 策略编译 + deepresearch 闭环，K线留 stub，分析 pipeline 按最终敲定的阶段切分实现。*
