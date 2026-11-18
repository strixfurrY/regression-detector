import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Configurable through environment variables (the Docker container will use them too)
WARN_THRESHOLD = float(os.environ.get("WARN_THRESHOLD", "0.03"))
CRITICAL_THRESHOLD = float(os.environ.get("CRITICAL_THRESHOLD", "0.08"))


def load_run(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def latest_runs(n=2):
    return sorted(Path("results").glob("run_*.json"))[-n:]


def accuracy_by_category(results):
    totals, hits = defaultdict(int), defaultdict(int)
    for r in results:
        totals[r["expected_category"]] += 1
        hits[r["expected_category"]] += bool(r["category_match"])
    return {c: hits[c] / totals[c] for c in totals}


def compare(baseline, new, warn=WARN_THRESHOLD, critical=CRITICAL_THRESHOLD):
    b = {r["id"]: r for r in baseline["results"]}
    n = {r["id"]: r for r in new["results"]}
    shared = sorted(set(b) & set(n))
    if not shared:
        raise SystemExit("The two runs have no case ids in common.")

    regressions, improvements = [], []
    for cid in shared:
        was, now = b[cid]["category_match"], n[cid]["category_match"]
        flip = {
            "id": cid,
            "expected": b[cid]["expected_category"],
            "old_predicted": b[cid]["predicted_category"],
            "new_predicted": n[cid]["predicted_category"],
            "old_summary": b[cid]["predicted_summary"],
            "new_summary": n[cid]["predicted_summary"],
        }
        if was and not now:
            regressions.append(flip)
        elif not was and now:
            improvements.append(flip)

    b_rate = sum(b[c]["category_match"] for c in shared) / len(shared)
    n_rate = sum(n[c]["category_match"] for c in shared) / len(shared)
    delta = n_rate - b_rate

    b_cat = accuracy_by_category([b[c] for c in shared])
    n_cat = accuracy_by_category([n[c] for c in shared])
    category_deltas = {c: n_cat[c] - b_cat[c] for c in b_cat}

    drop = -delta
    if drop > critical:
        status = "CRITICAL"
    elif drop > warn:
        status = "WARNING"
    else:
        status = "OK"

    bs, ns = baseline["summary"], new["summary"]

    def diff(key):
        if bs.get(key) is None or ns.get(key) is None:
            return None
        return round(ns[key] - bs[key], 3)

    return {
        "status": status,
        "thresholds": {"warn": warn, "critical": critical},
        "baseline": baseline["metadata"],
        "new": new["metadata"],
        "cases_compared": len(shared),
        "baseline_pass_rate": b_rate,
        "new_pass_rate": n_rate,
        "pass_rate_delta": delta,
        "category_deltas": category_deltas,
        "regressions": regressions,
        "improvements": improvements,
        "summary_score_delta": diff("avg_summary_score"),
        "latency_delta_s": diff("avg_latency_s"),
        "tokens_delta": diff("total_tokens"),
        "same_dataset_version": (
            baseline["metadata"]["dataset_version"] == new["metadata"]["dataset_version"]
        ),
    }


def print_report(c):
    bm, nm = c["baseline"], c["new"]
    print(f"\nBaseline: prompt {bm['prompt_version']} ({bm['model']})")
    print(f"New:      prompt {nm['prompt_version']} ({nm['model']})")
    if not c["same_dataset_version"]:
        print("WARNING: the two runs used different dataset versions.")
    print(f"Cases compared: {c['cases_compared']}")
    print(f"\nSTATUS: {c['status']}   "
          f"(warn > {c['thresholds']['warn']:.0%} drop, critical > {c['thresholds']['critical']:.0%} drop)")
    print(f"Pass rate: {c['baseline_pass_rate']:.0%} -> {c['new_pass_rate']:.0%} "
          f"({c['pass_rate_delta']:+.0%})")

    print("\nAccuracy by category:")
    for cat, d in sorted(c["category_deltas"].items()):
        print(f"  {cat:<10} {d:+.0%}")

    print(f"\nRegressions (pass -> fail): {len(c['regressions'])}")
    for r in c["regressions"]:
        print(f"  {r['id']}: expected {r['expected']}, was {r['old_predicted']}, now {r['new_predicted']}")
    print(f"Improvements (fail -> pass): {len(c['improvements'])}")
    for r in c["improvements"]:
        print(f"  {r['id']}: expected {r['expected']}, was {r['old_predicted']}, now {r['new_predicted']}")

    print(f"\nSummary score change: {c['summary_score_delta']}")
    print(f"Latency change (s):   {c['latency_delta_s']}")
    print(f"Token change:         {c['tokens_delta']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        base_path, new_path = args
    else:
        files = latest_runs(2)
        if len(files) < 2:
            raise SystemExit("Need at least 2 runs in results/. Run python -m src.runner first.")
        base_path, new_path = files
    print(f"Baseline file: {base_path}")
    print(f"New file:      {new_path}")
    print_report(compare(load_run(base_path), load_run(new_path)))