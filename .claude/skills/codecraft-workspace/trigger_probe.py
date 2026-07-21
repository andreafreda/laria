#!/usr/bin/env python3
"""Custom triggering probe for the REAL installed codecraft skill.

Why this instead of skill-creator's run_eval: that harness injects a temporary
renamed slash-command and checks whether the model invokes that exact name. Here
codecraft is really installed in the project, so the model invokes the real
skill, which the harness would miss. It also let the active `caveman` plugin win
the Skill call. This probe runs each query against the real skill with user-level
settings excluded (so caveman is gone) and detects a genuine codecraft trigger:
a Skill tool call with skill == codecraft, or a Read of a codecraft skill file.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT = r"C:\projects\laria"
MODEL = "claude-opus-4-8"
RUNS_PER_QUERY = 2
TIMEOUT = 120  # safety cap; we early-exit as soon as the trigger is seen

eval_set = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))


def is_trigger_line(line: str) -> bool:
    """A stream line that shows codecraft was consulted (Skill call or file read)."""
    low = line.lower()
    if '"skill":"codecraft"' in line or '"skill": "codecraft"' in line:
        return True
    if '"name":"read"' in low and "codecraft" in low and "skill.md" in low:
        return True
    return False


def run_one(query: str) -> bool:
    """Run one headless query; return True as soon as codecraft is consulted.

    The Skill call comes early, before tool execution, so we stream and break
    on first sight instead of waiting for the model's exploration to finish
    (which can be slow and would otherwise cause timeout false-negatives).
    """
    cmd = [
        "claude", "-p", query,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--model", MODEL,
        "--setting-sources", "project,local",  # drop user settings => no caveman
    ]
    proc = subprocess.Popen(
        cmd, cwd=PROJECT, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    triggered = False
    start = time.time()
    try:
        for line in proc.stdout:
            if is_trigger_line(line):
                triggered = True
                break
            if time.time() - start > TIMEOUT:
                break
    finally:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    return triggered


results = []
for item in eval_set:
    q = item["query"]
    fires = sum(run_one(q) for _ in range(RUNS_PER_QUERY))
    rate = fires / RUNS_PER_QUERY
    should = item["should_trigger"]
    ok = (rate >= 0.5) if should else (rate < 0.5)
    results.append({"query": q, "should_trigger": should, "rate": rate,
                    "fires": fires, "runs": RUNS_PER_QUERY, "pass": ok})
    print(f"[{'PASS' if ok else 'FAIL'}] {fires}/{RUNS_PER_QUERY} expected={should}: {q[:65]}",
          file=sys.stderr, flush=True)

pos = [r for r in results if r["should_trigger"]]
neg = [r for r in results if not r["should_trigger"]]
recall = sum(r["pass"] for r in pos) / len(pos) if pos else 0
specificity = sum(r["pass"] for r in neg) / len(neg) if neg else 0
acc = sum(r["pass"] for r in results) / len(results)
summary = {"total": len(results), "passed": sum(r["pass"] for r in results),
           "recall": round(recall, 3), "specificity": round(specificity, 3),
           "accuracy": round(acc, 3)}
print(json.dumps({"summary": summary, "results": results}, indent=2))
