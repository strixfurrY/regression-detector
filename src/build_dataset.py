import json
from collections import Counter
from pathlib import Path

PREFIX = {"billing": "bill", "technical": "tech", "account": "acct", "general": "gen"}

def build(src="data/cases.txt", out="data/golden_v1.json"):
    cases, counts = [], Counter()
    for n, line in enumerate(Path(src).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6:
            raise SystemExit(f"Line {n}: expected 6 parts separated by |, found {len(parts)}")
        category, difficulty, edge, email, summary, notes = parts
        if category not in PREFIX:
            raise SystemExit(f"Line {n}: unknown category {category!r}")
        counts[category] += 1
        cases.append({
            "id": f"{PREFIX[category]}-{counts[category]:03d}",
            "input": email,
            "expected_category": category,
            "expected_summary": summary,
            "difficulty": difficulty,
            "edge_type": None if edge == "-" else edge,
            "notes": notes,
        })
    data = {"dataset_version": "1.0.0", "cases": cases}
    Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {out}")

if __name__ == "__main__":
    build()