"""[REPRO] Merge eval/global_human results of jobs that each ran a subset of videos.

Upstream launch.py writes one line per video to <out>/_error_log_0.txt and reports the n_human-
weighted mean over all lines (extract_metrics / calculate_averages in eval/global_human/utils.py).
We concatenate the per-video lines of all parts and apply the SAME upstream functions, so the result
equals a single run over all videos (up to the order of lines). Also checks coverage: every expected
video exactly once, and no OOM / exception lines (REPRO_NOTES G12).

Usage: python repro/merge_global_human.py --out DIR [--expect N] PART_DIR [PART_DIR ...]
"""
import argparse
import os
import re
import sys

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
from eval.global_human.utils import extract_metrics, get_summary_log  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--out", required=True)
p.add_argument("--expect", type=int, default=None, help="expected number of videos")
p.add_argument("parts", nargs="+")
a = p.parse_args()

lines, problems, seen = [], [], {}
for d in a.parts:
    f = os.path.join(d, "_error_log_0.txt")
    for l in open(f):
        if " |  n_human: " in l:
            key = l.split(" |  n_human: ")[0].strip()
            if key in seen:
                problems.append(f"duplicate {key} in {d} and {seen[key]}")
            seen[key] = d
            lines.append(l if l.endswith("\n") else l + "\n")
        elif re.search(r"OOM|Exception|error", l, re.I):
            problems.append(f"{d}: {l.strip()}")

n = len(lines)
if a.expect is not None and n != a.expect:
    problems.append(f"expected {a.expect} videos, found {n}")

os.makedirs(a.out, exist_ok=True)
merged = os.path.join(a.out, "_merged_videos.txt")
with open(merged, "w") as f:
    f.writelines(lines)
summary = extract_metrics(merged)          # upstream: n_human-weighted mean over the lines
log = get_summary_log(summary)
with open(os.path.join(a.out, "_error_log.txt"), "w") as f:
    f.write(f"[merged from {len(a.parts)} parts: {', '.join(a.parts)}; {n} videos]\n")
    f.writelines(lines)
    f.write(log)
print(f"videos: {n}")
print(log.strip())
if problems:
    print("PROBLEMS:\n  " + "\n  ".join(problems))
    sys.exit(1)
