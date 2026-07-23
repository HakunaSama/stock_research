---
name: stock-research-orchestrator
description: 股市调研主控。串起四模块——策略热插拔编译、DeepResearch(打分/无反馈重试)、K线拉取(占位)、6阶段分析子agent——对一只标的/板块/组合给出可追溯的调研结论。当用户要调研个股买卖时机、选股筛选、板块趋势或组合风险时使用。
version: 0.1.0
author: Hermes Stock Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Stock, Research, Analysis, Strategy, Investing]
    category: finance
    related_skills: [momentum-zhangda, stocks]
---

# 股市调研主控（Orchestrator）

把一次股市调研拆成四个模块，串成一条可追溯的流水线。每一步产出都写进同一个
`ResearchContext`（落盘于 `~/.hermes/stock/<run_id>/`），最终给出结构化结论。

## 何时使用

- 个股**买卖时机**判断（timing）
- **选股/标的筛选**（stock_pick）
- **宏观/板块**趋势研判（sector）
- **组合/风险**管理（portfolio）

## 四个工具（stock toolset）

1. `strategy_compile` — 把用户或大V的原始策略（文本或本地 `strategy.md`）编译成
   严格 schema + 可逐条核对的提示词块。**仅本地文件，不从 URL/Git 拉取。**
2. `deep_research` — 收集市场资料并由独立 judge 打分；不达阈值就**无反馈重试**
   （换检索角度 + 轻微升温），最多 8 次，仍不达标则取历史最优并标注质量不足。
3. `kline_fetch` — 拉取K线技术特征。**当前为占位**：返回 `status=placeholder`、
   特征全 null；分析阶段会据此跳过技术面细节并在结论里标注"技术面数据缺失"。
4. `analysis_run` — 6 阶段分析子 agent（重头戏）：
   S1 基本面 → S2 技术面 → S3 策略符合度 → S4 交叉验证&决策路由 →
   S5 结论 → S6 风险与执行。

## 推荐编排流程

按顺序调用工具，让每一步产出进入同一个 run 的上下文：

```
# 1) 编译策略（可选，但强烈建议——分析阶段会逐条核对）
strategy_compile strategy_path=~/.hermes/skills/stock/strategies/momentum_zhangda/strategy.md source=bigv:张大

# 2) 深度调研（judge 打分 + 无反馈重试到满意）
deep_research run_id=<run_id> target=AAPL question="当前是否是买入时机" horizon="1-3个月"

# 3) 拉K线（占位，接入真实数据源后自动生效）
kline_fetch symbol=AAPL timeframe=1d range=6mo

# 4) 6阶段分析，产出最终结论
analysis_run run_id=<run_id>
```

> `decision_type`（stock_pick|timing|sector|portfolio）用户可在提问时指定；
> 不指定则由 S4 自动判定。

## 结论形态（按 decision_type）

- `timing`：action(买入/逢低买入/持有/观望/减仓/卖出) + rating + 触发条件
- `stock_pick`：score(0-100) + selected + rating + 理由
- `sector`：stance(看多/中性/看空) + 驱动因子
- `portfolio`：配置权重/敞口/对冲建议

每次结论都带 `risk_and_exec`（仓位/止损/失效条件/免责声明）与 `quality`（终检打分）。

## 产物

`~/.hermes/stock/<run_id>/`：
- `context.json` — 贯穿四模块的完整上下文
- `research/attempt_N.json` — 每次调研尝试的 digest + judge 打分（可复现）
- `analysis.json` — 6 阶段结构化结论

## 配置（`cli-config.yaml` 的 `stock:` 段）

```yaml
stock:
  strategy:
    compile_model: null        # 策略编译模型，缺省用便宜档
  research:
    threshold: 8.0             # 调研达标分
    max_attempts: 8            # 无反馈重试上限
    judge_model: null          # judge 模型，缺省不换更严的
  analysis:
    model: null
    final_judge_enabled: true
    final_judge_threshold: 7.0
  workdir: ~/.hermes/stock
```
