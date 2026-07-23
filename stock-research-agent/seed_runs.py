#!/usr/bin/env python3
"""Seed real ``context.json`` runs for the stock terminal's ODR panel.

Runs the *actual* judge/retry + ODR flow with a deterministic ``FakeLLM`` (no
network, no API key) for two tickers, so the frontend can fetch genuine backend
artifacts instead of hand-written mock:

- ``000100`` TCL科技 — clears the bar on attempt 1 (judge 8.6).
- ``002185`` 华天科技 — 6.2 -> re-run whole ODR -> 7.1 -> re-run -> 8.3 accepted,
  i.e. the "re-run the entire ODR flow when the final score is too low" loop.

Artifacts land under ``workdir`` (default ``~/.hermes/stock``); ``serve.py``
scans the same dir. Usage:

    python3 seed_runs.py [workdir]
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Dict, List

from stock_agent import StockConfig, build_researcher, run_deep_research
from stock_agent.context import ResearchContext
from stock_agent.kline import fetch_kline
from stock_agent.llm import FakeLLM


# ---- per-ticker canned research content (mirrors the frontend mock) --------

def _profile_000100() -> Dict[str, Any]:
    return {
        "target": "000100",
        "question": "未来 1-3 个月是否值得继续持有？",
        "horizon": "1-3 个月",
        "brief": "评估 TCL科技（000100）未来 1-3 个月是否值得继续持有：围绕面板价格"
                 "周期、公司产线稼动、资金面、机构预期与技术面结构展开。",
        "sub_questions": [
            "面板价格与行业景气度走向",
            "TCL 华星产线稼动与盈利弹性",
            "资金面（北向/龙虎榜/机构席位）",
            "机构评级、目标价与技术面结构",
        ],
        "topics": [
            {
                "topic": "面板价格与产线稼动率",
                "rationale": "基本面锚点：涨价周期是否确立",
                "notes": "群智咨询 7 月报：大尺寸面板价格环比 +5%，连续 3 个月上行；"
                         "TCL 华星 t7/t9 产线满产，稼动率维持 95%+。涨价周期确立。",
                "sources": [{"title": "群智咨询：7月面板价格月报", "url": "https://example.com/panel-price", "date": "2026-07-12"}],
                "reflections": ["先核对一手价格数据", "再确认公司产线是否吃到涨价，覆盖已足够"],
                "steps_used": 4,
                "compressed": "面板价 7 月 +5%（连涨 3 月），华星产线满产、稼动 95%+，涨价周期确立。",
            },
            {
                "topic": "资金面与龙虎榜",
                "rationale": "情绪面：增量资金是否进场",
                "notes": "北向资金近 3 日累计净买入约 3.1 亿元；7 月 14 日龙虎榜出现机构专用"
                         "席位买入居前，游资跟风。资金面偏强。",
                "sources": [{"title": "沪深港通北向资金流向", "url": "https://example.com/northbound", "date": "2026-07-15"}],
                "reflections": ["交叉验证北向与龙虎榜口径一致"],
                "steps_used": 3,
                "compressed": "北向近 3 日净买入约 3.1 亿；7/14 龙虎榜机构席位买入居前，资金面偏强。",
            },
            {
                "topic": "机构评级与目标价",
                "rationale": "机构预期：一致目标价与评级分布",
                "notes": "近两周 5 家机构上调 Q3 盈利预测，一致目标价升至 5.60（现价 4.95，"
                         "空间约 13%），评级以增持/买入为主。",
                "sources": [{"title": "TCL科技机构调研纪要", "url": "https://example.com/tcl-research", "date": "2026-07-14"}],
                "reflections": ["记录一致预期分布，避免单一机构偏差"],
                "steps_used": 3,
                "compressed": "5 家机构上调 Q3 预测，一致目标价 5.60（空间约 13%），评级偏买入。",
            },
            {
                "topic": "技术面结构",
                "rationale": "择时佐证：突破与量价配合",
                "notes": "放量突破 60 日新高，均线多头排列；量能较 5 日均量放大 1.8 倍，量价齐升。"
                         "回踩 4.72 为第一支撑。",
                "sources": [],
                "reflections": ["技术面作为佐证，不作为独立结论"],
                "steps_used": 2,
                "compressed": "放量突破 60 日新高、多头排列，量价齐升；回踩 4.72 为第一支撑。",
            },
        ],
        "digest": "综合各子研究：面板价格 7 月环比再涨 5%，TCL 华星大尺寸产线满产满销；"
                  "北向资金连续 3 日净买入、龙虎榜机构席位现身；多家机构上调 Q3 盈利预测，"
                  "一致目标价 5.60。技术面放量突破 60 日新高、多头排列。整体趋势与逻辑共振，"
                  "支持持仓者继续持有，回踩不破可加仓。",
        "digest_sources": [
            {"title": "群智咨询：7月面板价格月报", "url": "https://example.com/panel-price", "date": "2026-07-12"},
            {"title": "沪深港通北向资金流向", "url": "https://example.com/northbound", "date": "2026-07-15"},
            {"title": "TCL科技机构调研纪要", "url": "https://example.com/tcl-research", "date": "2026-07-14"},
        ],
        "judge": [
            {"score": 8.6, "reasons": "四角度覆盖全面、来源新且可追溯，结论与证据一致", "worst_gap": "情绪面样本略少"},
        ],
    }


def _profile_002185() -> Dict[str, Any]:
    return {
        "target": "002185",
        "question": "未来 1-3 个月是否为买入时机？",
        "horizon": "1-3 个月",
        "brief": "评估华天科技（002185）未来 1-3 个月是否为买入时机：围绕封测行业景气、"
                 "先进封装订单、公司产能利用率、机构评级与技术面结构展开。",
        "sub_questions": [
            "封测行业景气度与稼动率趋势",
            "先进封装订单与公司订单能见度",
            "公司产能利用率与盈利弹性",
            "机构评级、技术面与资金面",
        ],
        "topics": [
            {
                "topic": "封测行业景气度",
                "rationale": "周期定位：行业是否触底回升",
                "notes": "中国半导体行业协会：6 月封测景气度环比回升，预计三季度行业稼动率"
                         "回升至 85%。周期底部抬升信号明确。",
                "sources": [{"title": "中国半导体行业协会封测景气报告", "url": "https://example.com/atp-index", "date": "2026-07-13"}],
                "reflections": ["先定位行业周期位置", "确认稼动率口径为行业平均"],
                "steps_used": 4,
                "compressed": "6 月封测景气环比回升，Q3 行业稼动率有望回到 85%，周期底部抬升。",
            },
            {
                "topic": "先进封装订单",
                "rationale": "需求端：AI/HBM 拉动能见度",
                "notes": "产业链跟踪：AI/HBM 带动先进封装需求，华天先进封装产线订单排至四季度，"
                         "订单能见度提升。",
                "sources": [{"title": "先进封装产业链跟踪", "url": "https://example.com/adv-packaging", "date": "2026-07-14"}],
                "reflections": ["区分先进封装与传统封装贡献"],
                "steps_used": 3,
                "compressed": "AI/HBM 拉动先进封装，华天订单排至 Q4，能见度提升。",
            },
            {
                "topic": "产能利用率与评级",
                "rationale": "盈利弹性 + 机构预期",
                "notes": "投资者关系纪要：公司产能利用率环比提升，先进封装占比上行；分析师维持"
                         "增持评级，等待业绩拐点确认。",
                "sources": [{"title": "华天科技投资者关系纪要", "url": "https://example.com/htkj-ir", "date": "2026-07-11"}],
                "reflections": ["补齐上一轮缺失的产能数据"],
                "steps_used": 3,
                "compressed": "产能利用率环比提升、先进封装占比上行；分析师维持增持，等待业绩拐点。",
            },
            {
                "topic": "技术面与资金面",
                "rationale": "择时：回踩年线是否止跌",
                "notes": "股价回踩年线（约 12.30）缩量止跌，短均线走平；成交量较前期萎缩，"
                         "抛压减轻但增量资金不足，需放量站上 13.2 才确认方向。",
                "sources": [],
                "reflections": ["技术面作为择时佐证", "强调需放量确认，避免抢跑"],
                "steps_used": 2,
                "compressed": "回踩年线缩量止跌，需放量站上 13.2 确认；增量资金暂不足，宜轻仓试仓。",
            },
        ],
        "digest": "综合各子研究：先进封装订单回暖，华天产能利用率环比提升，行业协会预计三季度"
                  "封测稼动率回升至 85%；股价回踩年线缩量止跌，抛压减轻但增量资金不足，需放量"
                  "站上 13.2 确认。分析师维持增持、等待业绩拐点。结论：可轻仓试仓，等待放量确认再加。",
        "digest_sources": [
            {"title": "中国半导体行业协会封测景气报告", "url": "https://example.com/atp-index", "date": "2026-07-13"},
            {"title": "华天科技投资者关系纪要", "url": "https://example.com/htkj-ir", "date": "2026-07-11"},
            {"title": "先进封装产业链跟踪", "url": "https://example.com/adv-packaging", "date": "2026-07-14"},
        ],
        # Three attempts: below-threshold twice, then cleared — the re-run loop.
        "judge": [
            {"score": 6.2, "reasons": "订单回暖有据，但缺少产能利用率与资金面佐证，来源偏单一", "worst_gap": "产能与资金面缺口"},
            {"score": 7.1, "reasons": "补上产能利用率，评级面清晰，但技术面/资金面仍薄", "worst_gap": "技术面结构未覆盖"},
            {"score": 8.3, "reasons": "四角度齐备，技术面与基本面互证，结论审慎且可执行", "worst_gap": "业绩拐点仍需下季确认"},
        ],
    }


def _make_responder(profile: Dict[str, Any]) -> Callable[[str, str], str]:
    """Stateful (system,user) -> JSON responder driving one ticker's ODR run.

    The judge is called once per attempt; we pop successive scores so the outer
    loop retries until it clears the bar.
    """
    topics: List[Dict[str, Any]] = profile["topics"]
    judge_seq: List[Dict[str, Any]] = list(profile["judge"])
    state = {"judge_i": 0}

    def _topic_for(user: str) -> Dict[str, Any]:
        for t in topics:
            if t["topic"] in user:
                return t
        return topics[0]

    def responder(system: str, user: str) -> str:
        if "lead research planner" in system:
            return json.dumps({
                "brief": profile["brief"],
                "sub_questions": profile["sub_questions"],
            }, ensure_ascii=False)

        if "research supervisor" in system:
            first_round = "(暂无)" in user
            if first_round:
                return json.dumps({
                    "reflection": "尚无任何发现，先并行铺开核心角度。",
                    "complete": False,
                    "sub_topics": [
                        {"topic": t["topic"], "rationale": t["rationale"]} for t in topics
                    ],
                }, ensure_ascii=False)
            return json.dumps({
                "reflection": "各角度均已覆盖，证据充分，可结稿。",
                "complete": True,
                "sub_topics": [],
            }, ensure_ascii=False)

        if "focused sub-researcher" in system:
            t = _topic_for(user)
            return json.dumps({
                "notes": t["notes"],
                "sources": t["sources"],
                "reflections": t["reflections"],
                "steps_used": t["steps_used"],
            }, ensure_ascii=False)

        if "compression specialist" in system:
            t = _topic_for(user)
            return json.dumps({
                "compressed": t["compressed"],
                "sources": t["sources"],
            }, ensure_ascii=False)

        if "report writer" in system:
            return json.dumps({
                "digest": profile["digest"],
                "sources": profile["digest_sources"],
            }, ensure_ascii=False)

        if "research-quality judge" in system:
            i = min(state["judge_i"], len(judge_seq) - 1)
            state["judge_i"] += 1
            return json.dumps(judge_seq[i], ensure_ascii=False)

        return "{}"

    return responder


def _seed_one(profile: Dict[str, Any], config: StockConfig) -> ResearchContext:
    llm = FakeLLM(responder=_make_responder(profile))
    ctx = ResearchContext.new(
        target=profile["target"],
        question=profile["question"],
        horizon=profile["horizon"],
    )
    researcher = build_researcher(llm, config)
    run_deep_research(ctx, researcher, judge_llm=llm, config=config, persist=True)
    # Real K-line: pull live OHLCV via the vendored stocksdk + extract features
    # into ctx.kline, so the same run carries both research AND technicals. This
    # is a real network call; on failure fetch_kline degrades to a placeholder.
    fetch_kline(ctx, symbol=profile["target"], config=config)
    ctx.save(config.workdir)
    return ctx


def main() -> None:
    workdir = sys.argv[1] if len(sys.argv) > 1 else "~/.hermes/stock"
    config = StockConfig()
    config.workdir = workdir

    for profile in (_profile_000100(), _profile_002185()):
        ctx = _seed_one(profile, config)
        r = ctx.research
        arrow = " -> ".join(
            f"{h['score']:.1f}{'✓' if h['accepted'] else '✗'}" for h in r.history
        )
        print(f"[{profile['target']}] status={r.status} score={r.score} "
              f"attempts={r.attempts} threshold={r.threshold}  history: {arrow}")
        k = ctx.kline
        n_bars = k.range if k.status == "ok" else "-"
        print(f"          kline: status={k.status} bars={n_bars}"
              + (f" trend={k.features['trend']['direction']}" if k.status == "ok" and k.features else ""))
        print(f"          saved: {os.path.join(ctx.run_dir(config.workdir), 'context.json')}")


if __name__ == "__main__":
    main()
