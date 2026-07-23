# Stock Research Agent

A **stock-research add-on** for the [Nous Research hermes-agent](https://github.com/nousresearch/hermes-agent)
framework. It turns a raw trading strategy + market research + K-line into a
structured, traceable investment conclusion across four decision scenarios
(个股择时 / 选股筛选 / 板块研判 / 组合风险).

It runs in **two modes**:

- **Standalone** — pure Python, inject any `LLMClient` (a `FakeLLM` for tests, or
  an OpenAI-compatible endpoint). No hermes import required.
- **Inside hermes** — thin tool wrappers in `hermes_tools/` register a `stock`
  toolset; a `skills/stock/*` SKILL orchestrates them.

See [`../docs/stock-research-agent-design.md`](../docs/stock-research-agent-design.md) for the full design.

## Four modules

| Module | Code | What it does |
|---|---|---|
| 1. Strategy hot-plug | `stock_agent/strategy.py` | Compile a raw strategy (text or local `strategy.md`) into a strict schema + a rule-by-rule prompt block. Local files only — no URL/Git fetch. |
| 2. K-line fetch | `stock_agent/kline.py` + `stock_agent/kline_features.py` | Pulls **real A-share OHLCV** via the vendored `stocksdk` and extracts six technical features (`trend / ma_state / key_levels / patterns / volume_state / indicators`). Degrades gracefully to `status="placeholder"` (null features) when offline or disabled — see the [K-line section](#k-line-real-ohlcv-data-source) below. |
| 3. DeepResearch | `stock_agent/research.py` + `stock_agent/odr/` | Runs a research **producer** and gates it with an **independent judge**: accept when score ≥ threshold, else retry **without feedback** up to `max_attempts=8`. The default producer is a multi-agent **Open-Deep-Research** engine (a pure-Python port of langchain-ai/open_deep_research); a low final-report score re-runs the **whole ODR flow**. Set `research.engine="legacy"` for the old single-shot researcher. |
| 4. Analysis (centerpiece) | `stock_agent/analysis.py` | **6-stage pipeline**: S1 fundamental → S2 technical → S3 strategy-fit → S4 synthesis/route → S5 verdict → S6 risk&exec. Gating scheme B: fact stages self-validate/retry, final judge gates S4-S6. |

All four thread one `ResearchContext` (`stock_agent/context.py`), persisted to
`~/.hermes/stock/<run_id>/` (`context.json`, `research/attempt_N.json`, `analysis.json`).

## Quick start (standalone)

```bash
cd stock-research-agent
python3 run_demo.py
```

The demo uses a deterministic `FakeLLM` (no network/API key) to run the full
pipeline for AAPL and prints the verdict + risk block + quality score.

## Serving runs to the frontend (stock-terminal)

The [`stock-terminal`](../stock-terminal) UI has an **ODR research panel** that
can fetch a run's real `context.json` instead of its built-in mock. Two small
stdlib-only helpers wire this up (no FastAPI/Flask):

```bash
cd stock-research-agent
# 1) seed two runs with FakeLLM: 000100 clears on attempt 1; 002185 re-runs
#    the whole ODR flow 6.2 -> 7.1 -> 8.3 (the low-score-re-run loop).
#    Each run also pulls REAL K-line OHLCV (see below) into ctx.kline.
python3 seed_runs.py /tmp/stock-terminal-data
# 2) serve them read-only over HTTP (scans <workdir>/<run_id>/context.json).
python3 serve.py --workdir /tmp/stock-terminal-data --port 8787
```

Endpoints: `GET /api/runs`, `GET /api/research/<target>`,
`GET /api/kline/<target>`, `GET /api/context/<target>`, `GET /healthz`
(CORS open, read-only, local dev).

The frontend adapter ([`src/lib/api.ts`](../stock-terminal/src/lib/api.ts)) maps
`/api/research/<target>` onto its `ResearchRun` type and `/api/kline/<target>`
onto its `KlineData` type (candlestick chart + technical features). It's
**progressive enhancement**: if the bridge is down the panel falls back to the
local mock and tags itself "离线 mock", so the UI still demos offline. Point the
frontend at a different bridge with `VITE_RESEARCH_API`.

### K-line (real OHLCV) data source

[`stock_agent/kline.py`](stock_agent/kline.py) pulls real A-share OHLCV via the
**vendored** `stocksdk` (free tencent/eastmoney/sina sources, auto failover —
see [`vendor/NOTICE.md`](vendor/NOTICE.md)) and
[`kline_features.py`](stock_agent/kline_features.py) turns the bars into six
technical features (`trend / ma_state / key_levels / patterns / volume_state /
indicators`) written into `ctx.kline`. Everything degrades gracefully: if the
fetch fails (offline / non-A-share symbol) or `config.kline.enabled` is off, the
slot stays a `placeholder` with null features and no other module changes.
`vendor/stocksdk` is third-party code (`requests`-only); mind the license note
in `vendor/NOTICE.md` before redistributing.

To use a real model, build an `LLMClient` and call `run_pipeline`:

```python
from stock_agent import StockConfig, run_pipeline
from stock_agent.llm import OpenAICompatibleLLM

llm = OpenAICompatibleLLM(call_fn=my_openai_call, default_model="gpt-4o-mini")
ctx = run_pipeline(
    target="AAPL",
    question="当前是否是买入时机？",
    horizon="1-3 个月",
    decision_type=None,               # None => S4 auto-routes
    strategy_path="skills/stock/strategies/momentum_zhangda/strategy.md",
    strategy_source="bigv:张大",
    llm=llm,
    config=StockConfig(),
)
print(ctx.analysis["verdict"])
```

## Drop-in to hermes

1. **Put this package on hermes' import path.** Either `pip install -e .` a small
   packaging shim, or symlink `stock_agent/` next to hermes' modules so
   `import stock_agent` resolves.

2. **Register the tools.** Copy or symlink `hermes_tools/*.py` into hermes' `tools/`
   directory (or import them from a plugin entry point). Each module calls
   `registry.register(..., toolset="stock", ...)` at import time, which hermes'
   `discover_builtin_tools()` picks up.

3. **Add the `stock` toolset** in hermes' `toolsets.py`:

   ```python
   "stock": {
       "description": "Stock research: strategy compile, deep research, K-line, 6-stage analysis",
       "tools": [
           "stock_run_init",
           "strategy_compile",
           "deep_research",
           "kline_fetch",
           "analysis_run",
       ],
       "includes": [],
   },
   ```

4. **Install the skills.** Copy `skills/stock/` into hermes' skills dir
   (`~/.hermes/skills/` or the repo's skills root) so the orchestrator and
   strategy library are discoverable.

5. **(Optional) Configure** via the `stock:` section of `cli-config.yaml`:

   ```yaml
   stock:
     strategy:
       compile_model: null      # strategy compile model; null => cheap tier
     research:
       threshold: 8.0
       max_attempts: 8
       judge_model: null        # null => same as main; set to swap judge
       engine: odr              # "odr" (multi-agent, default) | "legacy" (single-shot)
       odr:
         clarify_enabled: false # ask user to clarify ambiguous requests; off => autonomous
         max_supervisor_iterations: 4
         max_researcher_iterations: 6
         max_concurrent_units: 4
         summarization_model: null   # per-stage model routing; null => research model
         research_model: null
         compression_model: null
         final_report_model: null
     analysis:
       model: null
       final_judge_enabled: true
       final_judge_threshold: 7.0
     workdir: ~/.hermes/stock
   ```

## Hermes tools (the `stock` toolset)

All tools after `stock_run_init` are **run_id-stateful**: they load the run's
`context.json`, mutate one slot, and save.

| Tool | Purpose |
|---|---|
| `stock_run_init` | Create a run; returns `run_id`. |
| `strategy_compile` | Compile a raw strategy into the context. |
| `deep_research` | Judge/retry research loop → context. |
| `kline_fetch` | K-line features (placeholder) → context. |
| `analysis_run` | 6-stage analysis pipeline → context. |

Typical order: `stock_run_init` → `strategy_compile` → `deep_research` →
`kline_fetch` → `analysis_run` (see the orchestrator SKILL).

## Adding a strategy

Drop a directory under `skills/stock/strategies/<name>/` with a `SKILL.md`
(frontmatter: author/tags) and a `strategy.md` (natural language / pseudocode /
condition list). The compiler turns vague phrasing into checkable rules and
records explicit assumptions + flagged ambiguities. See
`skills/stock/strategies/momentum_zhangda/` for an example.

## Wiring K-line data later

`stock_agent/kline.py::fetch_kline` has a `TODO(kline-data)` marker. When the
data doc arrives: fetch OHLCV, add a feature extractor that fills the six
`_FEATURE_KEYS` (trend / ma_state / key_levels / patterns / volume_state /
indicators), flip `status` to `"ok"`, and set `raw_ref`. No other module changes;
the analysis S2 stage automatically starts reading real features.

## Layout

```
stock-research-agent/
  stock_agent/
    context.py         # ResearchContext data contract + persistence
    config.py          # StockConfig (all configurable knobs)
    llm.py             # LLMClient protocol + FakeLLM / OpenAICompatibleLLM
    templates.py       # prompt-template loader
    strategy.py        # module 1: strategy compiler
    research.py        # module 3: judge/retry loop + producer selection (build_researcher)
    odr/               # module 3 engine: Open-Deep-Research (multi-agent) port
      state.py         #   dataclasses: brief / sub-topic / finding / note / result
      pipeline.py      #   OpenDeepResearcher: clarify→brief→supervisor→sub-research→compress→report
      retriever.py     #   Retriever protocol + LLMSubResearcher stub (injectable sub-research)
    kline.py           # module 2: K-line fetch (placeholder)
    analysis.py        # module 4: 6-stage analysis pipeline
    orchestrator.py    # chain all four modules
    hermes_bridge.py   # HermesLLM + config/context loaders (hermes-only)
    prompt_templates/  # strategy_compile / research_* / odr_* / analysis_* / *_judge
  hermes_tools/        # registry.register wrappers (the `stock` toolset)
                       #   + odr_retriever.py: DelegateRetriever (real web_search/web_extract sub-research)
  skills/stock/
    stock-research-orchestrator/SKILL.md
    strategies/momentum_zhangda/{SKILL.md,strategy.md}
  run_demo.py          # standalone end-to-end demo (FakeLLM)
```
