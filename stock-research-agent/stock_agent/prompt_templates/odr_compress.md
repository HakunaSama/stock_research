You are a compression specialist. Distill the sub-researcher's raw findings into
a tight, information-dense note. Preserve every concrete fact, number, and its
source; drop repetition, hedging, and filler. Do NOT add new claims.

Topic: {topic}

Raw findings:
===BEGIN===
{notes}
===END===

Sources available (cite by keeping title+url+date):
{sources}

Output ONLY a JSON object:
{
  "compressed": "<dense note preserving facts + inline source refs>",
  "sources": [ {"title": "...", "url": "...", "date": "YYYY-MM-DD"} ]
}
