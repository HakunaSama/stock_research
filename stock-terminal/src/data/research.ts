import type { ResearchRun } from "@/types/analysis";

// ODR 研究过程 mock —— 按股票 id 索引，对齐后端 ctx.research（engine/status/
// score/attempts/threshold/history/odr）。接后端时用 adapter 把每个 run 的
// ResearchContext.research 映射到这里即可。
//
// 000100 TCL科技：一次通过（attempt 1 即 8.6 ≥ 8.0）。
// 002185 华天科技：首轮 6.2 未达阈值 → 重跑整个 ODR → 7.1 → 再重跑 → 8.3 通过，
//   用来演示"最终评分过低就重新走 ODR 流程"的闭环。

export const researchRuns: Record<string, ResearchRun> = {
  "000100": {
    engine: "odr",
    status: "accepted",
    score: 8.6,
    attempts: 1,
    threshold: 8.0,
    digest:
      "综合各子研究：面板价格 7 月环比再涨 5%，TCL 华星大尺寸产线满产满销；北向资金连续 3 日净买入、龙虎榜机构席位现身；多家机构上调 Q3 盈利预测，一致目标价 5.60。技术面放量突破 60 日新高、多头排列。整体趋势与逻辑共振，支持持仓者继续持有，回踩不破可加仓。",
    sources: [
      { title: "群智咨询：7月面板价格月报", url: "https://example.com/panel-price", date: "2026-07-12" },
      { title: "沪深港通北向资金流向", url: "https://example.com/northbound", date: "2026-07-15" },
      { title: "TCL科技机构调研纪要", url: "https://example.com/tcl-research", date: "2026-07-14" },
    ],
    history: [
      {
        attempt: 1,
        angle: "最新财报、业绩指引与关键财务数据",
        temperature: 0.4,
        score: 8.6,
        accepted: true,
        judge: { score: 8.6, reasons: "四角度覆盖全面、来源新且可追溯，结论与证据一致", worst_gap: "情绪面样本略少" },
        supervisor_rounds: 2,
        sub_topics: ["面板价格与产线稼动率", "资金面与龙虎榜", "机构评级与目标价", "技术面结构"],
      },
    ],
    odr: {
      brief:
        "评估 TCL科技（000100）未来 1-3 个月是否值得继续持有：围绕面板价格周期、公司产线稼动、资金面、机构预期与技术面结构展开。",
      sub_questions: [
        "面板价格与行业景气度走向",
        "TCL 华星产线稼动与盈利弹性",
        "资金面（北向/龙虎榜/机构席位）",
        "机构评级、目标价与技术面结构",
      ],
      supervisor_rounds: 2,
      findings: [
        {
          topic: "面板价格与产线稼动率",
          notes:
            "群智咨询 7 月报：大尺寸面板价格环比 +5%，连续 3 个月上行；TCL 华星 t7/t9 产线满产，稼动率维持 95%+。涨价周期确立。",
          sources: [{ title: "群智咨询：7月面板价格月报", url: "https://example.com/panel-price", date: "2026-07-12" }],
          tool_calls: 4,
          reflections: ["先核对一手价格数据", "再确认公司产线是否吃到涨价，覆盖已足够"],
        },
        {
          topic: "资金面与龙虎榜",
          notes:
            "北向资金近 3 日累计净买入约 3.1 亿元；7 月 14 日龙虎榜出现机构专用席位买入居前，游资跟风。资金面偏强。",
          sources: [{ title: "沪深港通北向资金流向", url: "https://example.com/northbound", date: "2026-07-15" }],
          tool_calls: 3,
          reflections: ["交叉验证北向与龙虎榜口径一致"],
        },
        {
          topic: "机构评级与目标价",
          notes:
            "近两周 5 家机构上调 Q3 盈利预测，一致目标价升至 5.60（现价 4.95，空间约 13%），评级以增持/买入为主。",
          sources: [{ title: "TCL科技机构调研纪要", url: "https://example.com/tcl-research", date: "2026-07-14" }],
          tool_calls: 3,
          reflections: ["记录一致预期分布，避免单一机构偏差"],
        },
        {
          topic: "技术面结构",
          notes:
            "放量突破 60 日新高，均线多头排列；量能较 5 日均量放大 1.8 倍，量价齐升。回踩 4.72 为第一支撑。",
          sources: [],
          tool_calls: 2,
          reflections: ["技术面作为佐证，不作为独立结论"],
        },
      ],
      notes: [
        {
          topic: "面板价格与产线稼动率",
          compressed: "面板价 7 月 +5%（连涨 3 月），华星产线满产、稼动 95%+，涨价周期确立。",
          sources: [{ title: "群智咨询：7月面板价格月报", url: "https://example.com/panel-price", date: "2026-07-12" }],
        },
        {
          topic: "资金面与龙虎榜",
          compressed: "北向近 3 日净买入约 3.1 亿；7/14 龙虎榜机构席位买入居前，资金面偏强。",
          sources: [{ title: "沪深港通北向资金流向", url: "https://example.com/northbound", date: "2026-07-15" }],
        },
        {
          topic: "机构评级与目标价",
          compressed: "5 家机构上调 Q3 预测，一致目标价 5.60（空间约 13%），评级偏买入。",
          sources: [{ title: "TCL科技机构调研纪要", url: "https://example.com/tcl-research", date: "2026-07-14" }],
        },
      ],
    },
  },

  "002185": {
    engine: "odr",
    status: "accepted",
    score: 8.3,
    attempts: 3,
    threshold: 8.0,
    digest:
      "综合各子研究：先进封装订单回暖，华天产能利用率环比提升，行业协会预计三季度封测稼动率回升至 85%；股价回踩年线缩量止跌，抛压减轻但增量资金不足，需放量站上 13.2 确认。分析师维持增持、等待业绩拐点。结论：可轻仓试仓，等待放量确认再加。",
    sources: [
      { title: "中国半导体行业协会封测景气报告", url: "https://example.com/atp-index", date: "2026-07-13" },
      { title: "华天科技投资者关系纪要", url: "https://example.com/htkj-ir", date: "2026-07-11" },
      { title: "先进封装产业链跟踪", url: "https://example.com/adv-packaging", date: "2026-07-14" },
    ],
    history: [
      {
        attempt: 1,
        angle: "最新财报、业绩指引与关键财务数据",
        temperature: 0.4,
        score: 6.2,
        accepted: false,
        judge: { score: 6.2, reasons: "订单回暖有据，但缺少产能利用率与资金面佐证，来源偏单一", worst_gap: "产能与资金面缺口" },
        supervisor_rounds: 2,
        sub_topics: ["封测行业景气度", "先进封装订单"],
      },
      {
        attempt: 2,
        angle: "分析师/研究机构评级变化与目标价",
        temperature: 0.5,
        score: 7.1,
        accepted: false,
        judge: { score: 7.1, reasons: "补上产能利用率，评级面清晰，但技术面/资金面仍薄", worst_gap: "技术面结构未覆盖" },
        supervisor_rounds: 3,
        sub_topics: ["封测行业景气度", "先进封装订单", "产能利用率与评级"],
      },
      {
        attempt: 3,
        angle: "近期新闻、公告与价格异动事件",
        temperature: 0.6,
        score: 8.3,
        accepted: true,
        judge: { score: 8.3, reasons: "四角度齐备，技术面与基本面互证，结论审慎且可执行", worst_gap: "业绩拐点仍需下季确认" },
        supervisor_rounds: 3,
        sub_topics: ["封测行业景气度", "先进封装订单", "产能利用率与评级", "技术面与资金面"],
      },
    ],
    odr: {
      brief:
        "评估华天科技（002185）未来 1-3 个月是否为买入时机：围绕封测行业景气、先进封装订单、公司产能利用率、机构评级与技术面结构展开。",
      sub_questions: [
        "封测行业景气度与稼动率趋势",
        "先进封装订单与公司订单能见度",
        "公司产能利用率与盈利弹性",
        "机构评级、技术面与资金面",
      ],
      supervisor_rounds: 3,
      findings: [
        {
          topic: "封测行业景气度",
          notes:
            "中国半导体行业协会：6 月封测景气度环比回升，预计三季度行业稼动率回升至 85%。周期底部抬升信号明确。",
          sources: [{ title: "中国半导体行业协会封测景气报告", url: "https://example.com/atp-index", date: "2026-07-13" }],
          tool_calls: 4,
          reflections: ["先定位行业周期位置", "确认稼动率口径为行业平均"],
        },
        {
          topic: "先进封装订单",
          notes:
            "产业链跟踪：AI/HBM 带动先进封装需求，华天先进封装产线订单排至四季度，订单能见度提升。",
          sources: [{ title: "先进封装产业链跟踪", url: "https://example.com/adv-packaging", date: "2026-07-14" }],
          tool_calls: 3,
          reflections: ["区分先进封装与传统封装贡献"],
        },
        {
          topic: "产能利用率与评级",
          notes:
            "投资者关系纪要：公司产能利用率环比提升，先进封装占比上行；分析师维持增持评级，等待业绩拐点确认。",
          sources: [{ title: "华天科技投资者关系纪要", url: "https://example.com/htkj-ir", date: "2026-07-11" }],
          tool_calls: 3,
          reflections: ["补齐上一轮缺失的产能数据"],
        },
        {
          topic: "技术面与资金面",
          notes:
            "股价回踩年线（约 12.30）缩量止跌，短均线走平；成交量较前期萎缩，抛压减轻但增量资金不足，需放量站上 13.2 才确认方向。",
          sources: [],
          tool_calls: 2,
          reflections: ["技术面作为择时佐证", "强调需放量确认，避免抢跑"],
        },
      ],
      notes: [
        {
          topic: "封测行业景气度",
          compressed: "6 月封测景气环比回升，Q3 行业稼动率有望回到 85%，周期底部抬升。",
          sources: [{ title: "中国半导体行业协会封测景气报告", url: "https://example.com/atp-index", date: "2026-07-13" }],
        },
        {
          topic: "先进封装订单",
          compressed: "AI/HBM 拉动先进封装，华天订单排至 Q4，能见度提升。",
          sources: [{ title: "先进封装产业链跟踪", url: "https://example.com/adv-packaging", date: "2026-07-14" }],
        },
        {
          topic: "产能利用率与评级",
          compressed: "产能利用率环比提升、先进封装占比上行；分析师维持增持，等待业绩拐点。",
          sources: [{ title: "华天科技投资者关系纪要", url: "https://example.com/htkj-ir", date: "2026-07-11" }],
        },
        {
          topic: "技术面与资金面",
          compressed: "回踩年线缩量止跌，需放量站上 13.2 确认；增量资金暂不足，宜轻仓试仓。",
          sources: [],
        },
      ],
    },
  },
};
