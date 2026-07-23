You are a STRICT reviewer of an investment analysis conclusion. Score it 0-10.
An 8+ means the verdict is coherent, well-grounded, and internally consistent.

Target: {target}
Question: {question}

Synthesis (S4):
{synthesis}

Verdict (S5):
{verdict}

Risk & execution (S6):
{risk_and_exec}

Check for:
- Consistency: does the verdict follow from the net_bias and strategy fit? Any
  contradiction (e.g. bullish verdict despite blocking_violations)?
- Completeness: does it answer the question and match the decision_type form?
- Risk discipline: are stop-loss / invalidation / position sizing sensible?
- Honesty: does it acknowledge missing data (e.g. absent K-line) instead of
  overstating confidence?

Output ONLY a JSON object:
{
  "score": <number 0-10>,
  "reasons": "<short rationale>",
  "worst_gap": "<the single biggest weakness>"
}
