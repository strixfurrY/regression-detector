import asyncio
import json
import os
import sys
from pathlib import Path

from .alerts import send_status
from .report import build_report
from .runner import run_eval

BASELINE = "baselines/main.json"


def pct(x):
    return f"{x:.0%}"


def build_comment(c, report_url):
    bm, nm = c["baseline"], c["new"]
    lines = [
        f"## Prompt regression check: {c['status']}",
        "",
        f"Prompt `{bm['prompt_version']}` (baseline) vs `{nm['prompt_version']}` (this PR) "
        f"on `{nm['model']}`, {c['cases_compared']} cases.",
        "",
        f"- Pass rate: {pct(c['baseline_pass_rate'])} -> {pct(c['new_pass_rate'])} ({c['pass_rate_delta']:+.0%})",
        f"- Summary score change: {c['summary_score_delta']}",
        f"- Token change: {c['tokens_delta']}",
        f"- Thresholds: warning above a {c['thresholds']['warn']:.0%} drop, "
        f"critical above {c['thresholds']['critical']:.0%}",
        "",
    ]
    if c["regressions"]:
        lines += [f"### Regressions ({len(c['regressions'])})", "",
                  "| Case | Expected | Baseline | This PR |", "|---|---|---|---|"]
        for r in c["regressions"]:
            lines.append(f"| {r['id']} | {r['expected']} | {r['old_predicted']} | {r['new_predicted']} |")
        lines.append("")
    if c["improvements"]:
        lines += [f"### Improvements ({len(c['improvements'])})", ""]
        for r in c["improvements"]:
            lines.append(f"- {r['id']}: expected {r['expected']}, was {r['old_predicted']}, now {r['new_predicted']}")
        lines.append("")
    lines.append(f"[Run page with the full HTML report]({report_url}) "
                 "(download the `diff-report` artifact at the bottom of the page)")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m src.ci <prompt_version>")
    version = sys.argv[1]

    run = asyncio.run(run_eval(version))
    Path("ci").mkdir(exist_ok=True)
    new_path = Path("ci/new_run.json")
    new_path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")

    c, report_path = build_report(BASELINE, str(new_path))
    report_url = os.environ.get("REPORT_URL", report_path.resolve().as_uri())

    comment = build_comment(c, report_url)
    Path("ci/comment.md").write_text(comment, encoding="utf-8")
    print("\n" + comment)

    send_status(c, report_url)

    # A non-zero exit code makes the check fail, which blocks the merge
    if c["status"] == "CRITICAL":
        sys.exit(1)


if __name__ == "__main__":
    main()