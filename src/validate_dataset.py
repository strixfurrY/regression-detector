import json
import sys
from collections import Counter
from pathlib import Path

CATEGORIES = {"billing", "technical", "account", "general"}
DIFFICULTIES = {"easy", "medium", "hard"}
EDGE_TYPES = {None, "ambiguous", "very_short", "typos", "mixed_language", "sarcastic"}
REQUIRED = {"id", "input", "expected_category", "expected_summary",
            "difficulty", "edge_type", "notes"}

def validate(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data["cases"]
    errors = []

    ids = Counter(c.get("id") for c in cases)
    inputs = Counter(c.get("input", "").strip().lower() for c in cases)

    for c in cases:
        cid = c.get("id", "<missing id>")
        missing = REQUIRED - c.keys()
        if missing:
            errors.append(f"{cid}: missing fields {sorted(missing)}")
            continue
        if ids[cid] > 1:
            errors.append(f"{cid}: duplicate id")
        if inputs[c["input"].strip().lower()] > 1:
            errors.append(f"{cid}: duplicate input text")
        if c["expected_category"] not in CATEGORIES:
            errors.append(f"{cid}: bad category {c['expected_category']!r}")
        if c["difficulty"] not in DIFFICULTIES:
            errors.append(f"{cid}: bad difficulty {c['difficulty']!r}")
        if c["edge_type"] not in EDGE_TYPES:
            errors.append(f"{cid}: bad edge_type {c['edge_type']!r}")
        if c["difficulty"] == "hard" and not c["notes"].strip():
            errors.append(f"{cid}: hard cases need a notes explanation")

    print(f"{len(cases)} cases (target 50-100)")
    print("by category:", dict(Counter(c["expected_category"] for c in cases)))
    print("by difficulty:", dict(Counter(c["difficulty"] for c in cases)))
    print("by edge_type:", dict(Counter(c["edge_type"] for c in cases)))

    if errors:
        print(f"\n{len(errors)} problems:")
        for e in errors:
            print(" -", e)
        return 1
    print("\nOK")
    return 0

if __name__ == "__main__":
    sys.exit(validate(sys.argv[1] if len(sys.argv) > 1 else "data/golden_v1.json"))