#!/usr/bin/env python3
"""End-to-end demo of the stock-research pipeline using a deterministic FakeLLM.

No network, no API key, no hermes. It wires a canned responder that returns
plausible JSON per stage so you can watch the four modules thread one
ResearchContext:

    strategy_compile -> deep_research (judge/retry) -> kline (placeholder) -> analysis

Run:
    python3 run_demo.py
"""

from __future__ import annotations

import json

from stock_agent import StockConfig, run_pipeline
from stock_agent.llm import FakeLLM


STRATEGY_TEXT = """
张大动量策略：牛市或震荡市里，个股回踩20日均线不破、MACD金叉、
成交量较5日均量放大超过50% 时买入；跌破10日线或MACD死叉卖出；
单笔止损 -8%，单一仓位不超过30%。熊市不适用。
"""


def responder(system: str, user: str) -> str:
    """Return stage-appropriate JSON keyed off unique text in each template."""
    # --- strategy compile ---
    if "compile trading strategies" in system or "严格" in user and "schema" in user.lower():
        return json.dumps({
            "name": "张大动量策略",
            "thesis": "牛市/震荡市中回踩确认后的动量追随",
            "entry_rules": ["回踩20日均线不破", "MACD金叉", "成交量较5日均量放大>50%"],
            "exit_rules": ["跌破10日线", "MACD死叉"],
            "risk_rules": ["单笔止损-8%", "单一仓位≤30%"],
            "indicators": ["MA20", "MA10", "MACD", "VOL"],
            "timeframe": "日线",
            "assumptions": ["适用牛市/震荡市，熊市失效"],
            "ambiguities": ["'放量'阈值原文未定，已设>50%"],
        }, ensure_ascii=False)

    # --- deep research producer (legacy single-shot engine) ---
    if "equity research analyst" in system and "digest" in user.lower() and "FUNDAMENTAL" not in user:
        return json.dumps({
            "digest": "苹果最新财报营收同比+8%，服务业务创新高；多家投行上调目标价；"
                      "近期无重大监管风险；估值处于历史中位偏上。",
            "sources": [
                {"title": "Q3 Earnings", "url": "https://example.com/earnings", "date": "2026-07"},
                {"title": "Analyst upgrade", "url": "https://example.com/upgrade", "date": "2026-07"},
            ],
        }, ensure_ascii=False)

    # --- ODR engine: research brief ---
    if "lead research planner" in system:
        return json.dumps({
            "brief": "评估 AAPL 未来 1-3 个月是否为买入时机，覆盖基本面、催化剂、"
                     "机构观点、情绪与风险。",
            "sub_questions": [
                "最新财报与业绩指引",
                "近期催化剂与重大事件",
                "分析师评级与目标价变化",
                "市场情绪与资金流向",
            ],
        }, ensure_ascii=False)

    # --- ODR engine: supervisor (round 1 delegates, round 2 completes) ---
    if "research supervisor" in system:
        first_round = "(暂无)" in user
        if first_round:
            return json.dumps({
                "reflection": "尚无任何发现，先并行铺开四个核心角度。",
                "complete": False,
                "sub_topics": [
                    {"topic": "AAPL 最新财报与业绩指引", "rationale": "基本面锚点"},
                    {"topic": "AAPL 近期催化剂与事件", "rationale": "价格驱动"},
                    {"topic": "投行评级与目标价变化", "rationale": "机构预期"},
                    {"topic": "资金流向与市场情绪", "rationale": "情绪面"},
                ],
            }, ensure_ascii=False)
        return json.dumps({
            "reflection": "四个角度均已覆盖，证据充分，可结稿。",
            "complete": True,
            "sub_topics": [],
        }, ensure_ascii=False)

    # --- ODR engine: sub-researcher ---
    if "focused sub-researcher" in system:
        return json.dumps({
            "notes": "该角度调研发现：相关数据积极，营收同比+8%，多家机构维持买入。",
            "sources": [
                {"title": "Q3 Earnings", "url": "https://example.com/earnings", "date": "2026-07"},
            ],
            "reflections": ["先查一手财报", "再核对机构观点，覆盖已足够"],
            "steps_used": 3,
        }, ensure_ascii=False)

    # --- ODR engine: compression ---
    if "compression specialist" in system:
        return json.dumps({
            "compressed": "营收+8%，服务业务创新高；多家投行维持/上调买入评级。",
            "sources": [
                {"title": "Q3 Earnings", "url": "https://example.com/earnings", "date": "2026-07"},
            ],
        }, ensure_ascii=False)

    # --- ODR engine: final report writer ---
    if "report writer" in system:
        return json.dumps({
            "digest": "综合各子研究：苹果最新财报营收同比+8%，服务业务创新高；多家投行"
                      "上调目标价；近期无重大监管风险；估值处于历史中位偏上。整体偏多，"
                      "但需结合技术面确认买点。",
            "sources": [
                {"title": "Q3 Earnings", "url": "https://example.com/earnings", "date": "2026-07"},
                {"title": "Analyst upgrade", "url": "https://example.com/upgrade", "date": "2026-07"},
            ],
        }, ensure_ascii=False)

    # --- research judge (score high so it accepts on attempt 1) ---
    if "research-quality judge" in system:
        return json.dumps({"score": 8.6, "reasons": "覆盖全面且有来源", "worst_gap": "情绪面略少"},
                          ensure_ascii=False)

    # --- analysis stages ---
    if "FUNDAMENTAL view" in user:
        return json.dumps({
            "bull_points": ["营收+8%", "服务业务创新高", "投行上调目标价"],
            "bear_points": ["估值偏上"],
            "catalysts": [{"event": "下季财报", "impact": "高", "direction": "未知"}],
            "risk_events": [], "confidence": 0.75,
            "evidence": [{"claim": "营收+8%", "source_idx": 0}, {"claim": "上调目标价", "source_idx": 1}],
        }, ensure_ascii=False)
    if "TECHNICAL view" in user:
        return json.dumps({"available": False})  # placeholder kline path anyway
    if "rule by rule" in user:
        return json.dumps({
            "entry": [
                {"rule": "回踩20日均线不破", "met": "partial", "basis": "缺失：K线数据不可用"},
                {"rule": "MACD金叉", "met": "partial", "basis": "缺失：K线数据不可用"},
            ],
            "exit": [], "risk": [{"rule": "单笔止损-8%", "met": True, "basis": "策略默认"}],
            "fit_score": 0.4,
            "blocking_violations": [],
        }, ensure_ascii=False)
    if "synthesis lead" in user:
        return json.dumps({
            "synthesis": {
                "agreements": ["基本面偏多"],
                "conflicts": ["技术面数据缺失，无法确认entry"],
                "net_bias": "偏多", "confidence": 0.5,
            },
            "decision_type": "timing",
        }, ensure_ascii=False)
    if "final VERDICT" in user:
        return json.dumps({
            "type": "timing", "action": "观望偏多", "rating": "B",
            "rationale": ["基本面偏多", "技术面entry未确认，等待K线数据"],
            "conditions": ["接入K线后确认回踩MA20+MACD金叉再进"],
        }, ensure_ascii=False)
    if "risk & execution officer" in user:
        return json.dumps({
            "position_pct": "≤30%（策略上限），当前建议观望0-10%试仓",
            "stop_loss": None,
            "invalidation": ["跌破10日线", "MACD死叉", "单笔亏损达-8%"],
            "uncertainty": "技术面数据缺失（K线占位），置信度打折",
            "disclaimer": "本结论为研究参考，非投资建议。",
        }, ensure_ascii=False)
    if "STRICT reviewer" in system or "STRICT reviewer" in user:
        return json.dumps({"score": 8.1, "reasons": "结论与证据一致，诚实标注缺数据",
                           "worst_gap": "技术面缺失"}, ensure_ascii=False)

    return "{}"


def main() -> None:
    llm = FakeLLM(responder=responder)
    config = StockConfig()
    config.workdir = "/tmp/stock-demo"

    ctx = run_pipeline(
        target="AAPL",
        question="当前是否是买入时机？",
        horizon="1-3 个月",
        decision_type=None,           # let S4 route (will pick timing)
        strategy_text=STRATEGY_TEXT,
        strategy_source="bigv:张大",
        llm=llm,
        config=config,
    )

    print("=" * 60)
    print(f"run_id: {ctx.run_id}")
    print(f"strategy: {ctx.strategy.schema.get('name')} (source={ctx.strategy.source})")
    print(f"research engine: {config.research.engine} (clarify={config.research.odr.clarify_enabled})")
    print(f"research: status={ctx.research.status} score={ctx.research.score} attempts={ctx.research.attempts}")
    odr = ctx.research.odr or {}
    if odr:
        print(f"  ODR brief: {odr.get('brief', '')[:60]}...")
        print(f"  ODR supervisor rounds: {odr.get('supervisor_rounds')}")
        print(f"  ODR sub-research ({len(odr.get('findings', []))}): "
              + " | ".join(f.get("topic", "") for f in odr.get("findings", [])))
        print(f"  ODR attempt history: "
              + " -> ".join(f"{h['score']:.1f}{'✓' if h['accepted'] else '✗'}"
                            for h in ctx.research.history))
    print(f"kline: status={ctx.kline.status} (features all null={all(v is None for v in (ctx.kline.features or {}).values())})")
    print(f"decision_type: {ctx.analysis['decision_type']}")
    print(f"verdict: {json.dumps(ctx.analysis['verdict'], ensure_ascii=False)}")
    print(f"risk: {json.dumps(ctx.analysis['risk_and_exec'], ensure_ascii=False)}")
    print(f"quality: {json.dumps(ctx.analysis['quality'], ensure_ascii=False)}")
    print("=" * 60)
    print(f"artifacts saved under: {config.workdir}/{ctx.run_id}/")


if __name__ == "__main__":
    main()
