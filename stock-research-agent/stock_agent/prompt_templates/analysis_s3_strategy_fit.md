You are checking whether the market situation satisfies a specific TRADING
STRATEGY, rule by rule. This is the strategy-driven core — be precise and honest
about which rules are met, partially met, or unmet.

Target: {target}
Horizon: {horizon}

Compiled strategy (entry/exit/risk rules + assumptions):
===BEGIN STRATEGY===
{strategy}
===END STRATEGY===

Fundamental view (S1):
{fundamental_view}

Technical view (S2):
{technical_view}

Rules:
- For EACH strategy rule, decide met = true | false | "partial".
- "basis" must point to where the evidence comes from (e.g. "S2.position",
  "S1.catalysts", or "缺失：K线数据不可用").
- If the technical view is unavailable, technical rules should be "partial" or
  false with basis noting the missing data — never assume they are met.
- "blocking_violations" lists any HARD rule whose violation should veto a
  bullish conclusion.

Output ONLY a JSON object:
{
  "entry": [{"rule": "<rule text>", "met": <true|false|"partial">, "basis": "<where>"}],
  "exit":  [{"rule": "<rule text>", "met": <true|false|"partial">, "basis": "<where>"}],
  "risk":  [{"rule": "<rule text>", "met": <true|false|"partial">, "basis": "<where>"}],
  "fit_score": <0.0-1.0>,
  "blocking_violations": ["<hard-rule violation>", ...]
}
