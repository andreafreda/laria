#!/usr/bin/env python3
"""Render the triggering probe progress log as a standalone HTML report.

Reads probe_progress.log (one "[PASS|FAIL] f/r expected=Bool: query" line per
query) so it works on partial, in-progress data, and writes probe_report.html.
"""
import re
import sys
import webbrowser
from pathlib import Path

ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
log = (ws / "probe_progress.log").read_text(encoding="utf-8", errors="replace")

row_re = re.compile(r"^\[(PASS|FAIL)\] (\d+)/(\d+) expected=(True|False): (.*)$")
rows = []
for line in log.splitlines():
    m = row_re.match(line.strip())
    if m:
        status, fires, runs, expected, query = m.groups()
        rows.append({
            "ok": status == "PASS",
            "fires": int(fires), "runs": int(runs),
            "should": expected == "True",
            "query": query,
        })

pos = [r for r in rows if r["should"]]
neg = [r for r in rows if not r["should"]]


def pct(num, den):
    """Percent string, or n/a when nothing of that class has been scored yet."""
    return f"{num / den:.0%}" if den else "n/a"


recall_s = pct(sum(r["ok"] for r in pos), len(pos))
spec_s = pct(sum(r["ok"] for r in neg), len(neg))
acc_s = pct(sum(r["ok"] for r in rows), len(rows))
TOTAL = 20


def card(label, value, sub):
    return (f'<div class="card"><div class="v">{value}</div>'
            f'<div class="l">{label}</div><div class="s">{sub}</div></div>')


def tr(r):
    cls = "pass" if r["ok"] else "fail"
    badge = "PASS" if r["ok"] else "FAIL"
    want = "should trigger" if r["should"] else "should NOT trigger"
    rate = f'{r["fires"]}/{r["runs"]}'
    return (f'<tr class="{cls}"><td class="b">{badge}</td>'
            f'<td>{want}</td><td class="rate">{rate}</td>'
            f'<td class="q">{r["query"]}</td></tr>')


html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>codecraft triggering probe</title><style>
:root {{ color-scheme: light dark; }}
body {{ font: 15px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 980px;
  padding: 0 1rem; color: #1a1a1a; background: #fafafa; }}
h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
.note {{ color: #666; margin: 0 0 1.5rem; }}
.cards {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.card {{ background: #fff; border: 1px solid #e3e3e3; border-radius: 10px;
  padding: 1rem 1.25rem; min-width: 130px; }}
.card .v {{ font-size: 1.9rem; font-weight: 700; }}
.card .l {{ font-weight: 600; margin-top: .2rem; }}
.card .s {{ color: #777; font-size: .85rem; }}
table {{ width: 100%; border-collapse: collapse; background: #fff;
  border: 1px solid #e3e3e3; border-radius: 10px; overflow: hidden; }}
th, td {{ text-align: left; padding: .6rem .75rem; border-bottom: 1px solid #eee; }}
th {{ background: #f3f3f3; font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; }}
td.b {{ font-weight: 700; }}
tr.pass td.b {{ color: #137333; }}
tr.fail td.b {{ color: #c5221f; }}
tr.fail {{ background: #fff5f5; }}
.rate {{ font-variant-numeric: tabular-nums; }}
.q {{ color: #333; }}
</style></head><body>
<h1>codecraft triggering probe</h1>
<p class="note">Real installed skill, headless, user settings excluded (no caveman).
{len(rows)}/{TOTAL} queries scored{' (in progress)' if len(rows) < TOTAL else ''}.
Positives are scored first, so specificity stays n/a until negatives are reached.
Trigger = a Skill call to codecraft or a read of a codecraft file. Pass threshold 0.5.</p>
<div class="cards">
{card("Recall", recall_s, f"{sum(r['ok'] for r in pos)}/{len(pos)} should-trigger caught")}
{card("Specificity", spec_s, f"{sum(r['ok'] for r in neg)}/{len(neg)} negatives held")}
{card("Accuracy", acc_s, f"{sum(r['ok'] for r in rows)}/{len(rows)} scored")}
</div>
<table><thead><tr><th>Result</th><th>Expectation</th><th>Fired</th><th>Query</th></tr></thead>
<tbody>{''.join(tr(r) for r in rows)}</tbody></table>
</body></html>"""

out = ws / "probe_report.html"
out.write_text(html, encoding="utf-8")
print(str(out))
try:
    webbrowser.open(out.as_uri())
except Exception:
    pass
