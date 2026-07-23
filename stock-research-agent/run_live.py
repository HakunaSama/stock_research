#!/usr/bin/env python3
"""End-to-end run of the stock-research pipeline against a REAL LLM.

Same four-module flow as ``run_demo.py`` (strategy -> deep research -> K-line
-> analysis), but instead of the deterministic ``FakeLLM`` it drives a real
OpenAI-compatible endpoint (OpenAI / 火山方舟 / DeepSeek / 通义 ...). The target
defaults to a real A-share code so the K-line module hits its live path too.

Setup:
    cp .env.example .env      # then fill STOCK_LLM_BASE_URL / _API_KEY / _MODEL
    python3 run_live.py                       # default target 600519 贵州茅台
    python3 run_live.py 000100 "华星光电 1-3 个月是否值得布局？"

Credentials are read from the environment / local .env only — never hard-coded.
"""

from __future__ import annotations

import json
import sys

from stock_agent import StockConfig, run_pipeline
from stock_agent.live_llm import LiveLLMError, build_live_llm, load_dotenv


STRATEGY_TEXT = """
张大动量策略：牛市或震荡市里，个股回踩20日均线不破、MACD金叉、
成交量较5日均量放大超过50% 时买入；跌破10日线或MACD死叉卖出；
单笔止损 -8%，单一仓位不超过30%。熊市不适用。
"""


def main() -> None:
    load_dotenv()  # pull STOCK_LLM_* from a local .env if present

    target = sys.argv[1] if len(sys.argv) > 1 else "600519"
    question = sys.argv[2] if len(sys.argv) > 2 else "当前是否是买入时机？"

    try:
        llm = build_live_llm()
    except LiveLLMError as e:
        print(f"[config error] {e}")
        print("→ 复制 .env.example 为 .env 并填入 base_url / api_key / model 后重试。")
        sys.exit(1)

    config = StockConfig()
    config.workdir = "/tmp/stock-live"
    # DeepSeek-class reasoning models are slow per call; keep the first live
    # run lean so it finishes in a sensible time. Bump these back up once you
    # know your endpoint's latency/throughput.
    config.research.odr.max_supervisor_iterations = 2
    config.research.odr.max_concurrent_units = 2
    config.research.odr.max_researcher_iterations = 3
    config.research.max_attempts = 2

    print(f"→ target={target}  question={question!r}")
    print(f"→ engine={config.research.engine}  (真实 LLM + 真实 K线)\n")

    try:
        ctx = run_pipeline(
            target=target,
            question=question,
            horizon="1-3 个月",
            decision_type=None,          # let S4 route
            strategy_text=STRATEGY_TEXT,
            strategy_source="bigv:张大",
            llm=llm,
            config=config,
        )
    except LiveLLMError as e:
        print(f"[llm error] {e}")
        sys.exit(2)

    print("=" * 60)
    print(f"run_id: {ctx.run_id}")
    print(f"strategy: {ctx.strategy.schema.get('name')} (source={ctx.strategy.source})")
    print(f"research: status={ctx.research.status} score={ctx.research.score} attempts={ctx.research.attempts}")
    odr = ctx.research.odr or {}
    if odr:
        print(f"  ODR brief: {odr.get('brief', '')[:70]}...")
        print(f"  ODR sub-research ({len(odr.get('findings', []))}): "
              + " | ".join(f.get("topic", "") for f in odr.get("findings", [])))
        if ctx.research.history:
            print("  ODR attempt history: "
                  + " -> ".join(f"{h['score']:.1f}{'✓' if h['accepted'] else '✗'}"
                                for h in ctx.research.history))
    kf = ctx.kline.features or {}
    print(f"kline: status={ctx.kline.status} range={ctx.kline.range} "
          f"trend={(kf.get('trend') or {}).get('direction') if kf else None}")
    print(f"decision_type: {ctx.analysis['decision_type']}")
    print(f"verdict: {json.dumps(ctx.analysis['verdict'], ensure_ascii=False)}")
    print(f"risk: {json.dumps(ctx.analysis['risk_and_exec'], ensure_ascii=False)}")
    print(f"quality: {json.dumps(ctx.analysis['quality'], ensure_ascii=False)}")
    print("=" * 60)
    print(f"artifacts saved under: {config.workdir}/{ctx.run_id}/")


if __name__ == "__main__":
    main()
