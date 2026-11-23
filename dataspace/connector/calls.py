"""Summarise the connector's call log (CALL_LOG=1): one line per tool call, then totals.

  docker compose logs --no-log-prefix connector | python3 connector/calls.py

"gap" is the time between the end of one call and the start of the next: the agent thinking, or its own web searches.
A gap over GAP_S seconds starts a new block (probably a new question). Standard library only.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta

GAP_S = 120


def describe(e: dict) -> str:
    a = e.get("args", {})
    if e["tool"] == "call_source_operation":
        what = f"{a.get('dataset_id')}.{a.get('operation_id')} {json.dumps(a.get('params') or {}, ensure_ascii=False)}"
    elif e["tool"] == "vochub_search":
        what = repr(a.get("question")) + (f" tag={a['tag']}" if a.get("tag") else "")
    elif e["tool"] == "catalog_search":
        what = " ".join(f"{k}={v!r}" for k, v in a.items() if v)
    else:
        what = a.get("dataset_id") or a.get("id") or ""
    flags = [f"status {e['status']}" if e.get("status") else "", "TRUNCATED" if e.get("truncated") else "",
             f"error: {e['error']}" if e.get("error") else "", e.get("exception", "")]
    return " ".join(x for x in [what[:110], *flags] if x)


def main(lines) -> None:
    calls = []
    for line in lines:
        line = line.strip()
        if line.startswith("{") and '"call_log"' in line:
            e = json.loads(line)
            e["t0"] = datetime.fromisoformat(e["start"])
            e["t1"] = e["t0"] + timedelta(milliseconds=e["ms"])
            calls.append(e)
    if not calls:
        sys.exit("no call log lines found: set CALL_LOG=1 in dataspace/.env and restart the connector")
    calls.sort(key=lambda e: e["t0"])
    blocks, current = [], [calls[0]]
    for prev, e in zip(calls, calls[1:]):
        if (e["t0"] - prev["t1"]).total_seconds() > GAP_S:
            blocks.append(current)
            current = []
        current.append(e)
    blocks.append(current)

    for n, block in enumerate(blocks, 1):
        wall = (block[-1]["t1"] - block[0]["t0"]).total_seconds()
        in_tools = sum(e["ms"] for e in block) / 1000
        print(f"\n=== block {n}: {block[0]['t0']:%Y-%m-%d %H:%M:%S}, {len(block)} calls, {wall:.0f} s from first to last call, "
              f"{in_tools:.1f} s inside tools, {wall - in_tools:.0f} s between calls")
        print(f"{'#':>3} {'start':8} {'gap s':>6} {'ms':>6} {'chars':>6}  tool / what")
        prev = None
        for i, e in enumerate(block, 1):
            gap = f"{(e['t0'] - prev['t1']).total_seconds():.1f}" if prev else ""
            print(f"{i:>3} {e['t0']:%H:%M:%S} {gap:>6} {e['ms']:>6} {e.get('chars', ''):>6}  {e['tool']}: {describe(e)}")
            prev = e
        per_tool = defaultdict(lambda: [0, 0])
        for e in block:
            per_tool[e["tool"]][0] += 1
            per_tool[e["tool"]][1] += e["ms"]
        print("    per tool: " + ", ".join(f"{t} {c}x {ms / 1000:.1f} s" for t, (c, ms) in sorted(per_tool.items())))
        per_source = defaultdict(int)
        for e in block:
            if e["tool"] == "call_source_operation":
                per_source[f"{e['args'].get('dataset_id')}.{e['args'].get('operation_id')}"] += 1
        if per_source:
            print("    source calls: " + ", ".join(f"{k} {v}x" for k, v in sorted(per_source.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main(sys.stdin)
