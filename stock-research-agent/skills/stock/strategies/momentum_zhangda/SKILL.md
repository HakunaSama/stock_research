---
name: momentum-zhangda
description: 张大的动量策略 — 顺势做强势股回踩，放量金叉进场。示例策略，可替换为你自己的或大V的策略。
version: 0.1.0
author: "bigv:张大"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Stock, Strategy, Momentum, Trading]
    category: stock-strategy
---

# 张大-动量策略（示例）

这是一个**热插拔策略**示例。策略原文放在同目录的 `strategy.md`。

## 用法

调研某只标的时，让 agent 用 `strategy_compile` 工具把 `strategy.md` 编译成结构化提示词块，注入本次调研的 ResearchContext，供分析阶段逐条核对。

```
strategy_compile strategy_path=~/.hermes/skills/stock/strategies/momentum_zhangda/strategy.md source=bigv:张大
```

## 如何新增自己的策略

在 `skills/stock/strategies/` 下新建一个目录，放一个 `SKILL.md`（frontmatter 写清 author/tags）和一个 `strategy.md`（策略原文，自然语言/伪代码/条件列表均可）。编译器会自动把模糊表述转成带假设声明的可核对规则。
