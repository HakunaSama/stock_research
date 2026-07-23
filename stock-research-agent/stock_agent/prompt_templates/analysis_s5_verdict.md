You are producing the final VERDICT. The decision type has been routed to:
"{decision_type}". Produce the conclusion in the FORM required for that type.

Target: {target}
Question: {question}
Horizon: {horizon}

Synthesis (S4):
{synthesis}

Strategy fit (S3):
{strategy_fit}

Fundamental view (S1):
{fundamental_view}

Technical view (S2):
{technical_view}

Output form by decision_type (produce ONLY the matching shape, with
"type" set to "{decision_type}"):

- stock_pick:
  {"type":"stock_pick","score":<0-100>,"selected":<true|false>,"rating":"<S/A/B/C/D>",
   "rationale":["..."],"conditions":["..."]}

- timing:
  {"type":"timing","action":"<买入|逢低买入|持有|观望|减仓|卖出>","rating":"<A/B+/B/C>",
   "rationale":["..."],"conditions":["<触发/前置条件>"]}

- sector:
  {"type":"sector","stance":"<看多|中性|看空>","rating":"<强/中/弱>",
   "drivers":["<驱动因子>"],"rationale":["..."],"conditions":["..."]}

- portfolio:
  {"type":"portfolio","allocation":"<e.g. 权重≤20%>","exposure":"<敞口建议>",
   "hedges":["<对冲建议>"],"rationale":["..."],"conditions":["..."]}

Rules:
- Ground the rationale in S3 strategy fit and S4 net_bias — do not contradict them.
- If S3 has blocking_violations, the verdict must reflect that (no bullish call).
- Keep rationale concise (2-5 bullets).

Output ONLY the single matching JSON object.
