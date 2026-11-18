import html
import sys
import webbrowser
from pathlib import Path

from .compare import compare, latest_runs, load_run

COLORS = {"OK": "#1a7f37", "WARNING": "#b7791f", "CRITICAL": "#c53030"}

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#222}
h1{margin-bottom:4px}
.badge{display:inline-block;padding:4px 12px;border-radius:12px;color:#fff;font-weight:bold}
table{border-collapse:collapse;width:100%;margin:12px 0}
th,td{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top;font-size:14px}
th{background:#f4f4f4}
.old{background:#f0fff4}
.new{background:#fff5f5}
.muted{color:#666;font-size:13px}
"""


def esc(x):
    return html.escape("" if x is None else str(x))


def pct(x):
    return f"{x:.0%}"


def signed(x):
    return "n/a" if x is None else f"{x:+.2f}"


def trend_svg(paths):
    pts = []
    for p in paths:
        r = load_run(p)
        pts.append((r["metadata"]["prompt_version"], r["summary"]["pass_rate"]))
    if len(pts) < 2:
        return "<p class='muted'>Not enough runs for a trend yet.</p>"

    w, h, pad = 700, 220, 40
    step = (w - 2 * pad) / (len(pts) - 1)
    coords = []
    for i, (_, rate) in enumerate(pts):
        coords.append((pad + i * step, h - pad - rate * (h - 2 * pad)))

    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    marks = ""
    for i, ((x, y), (ver, rate)) in enumerate(zip(coords, pts), 1):
        marks += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#2b6cb0"/>'
        marks += f'<text x="{x:.1f}" y="{y - 10:.1f}" font-size="11" text-anchor="middle">{rate:.0%}</text>'
        marks += f'<text x="{x:.1f}" y="{h - pad + 16:.1f}" font-size="11" text-anchor="middle">#{i} {esc(ver)}</text>'
    axis = f'<line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" stroke="#999"/>'
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%">{axis}'
        f'<polyline points="{line}" fill="none" stroke="#2b6cb0" stroke-width="2"/>{marks}</svg>'
    )


def build_report(base_path, new_path, history_n=10, out="reports/report.html"):
    base, new = load_run(base_path), load_run(new_path)
    c = compare(base, new)
    bm, nm, bs, ns = c["baseline"], c["new"], base["summary"], new["summary"]
    color = COLORS[c["status"]]

    reg_rows = ""
    for r in c["regressions"]:
        reg_rows += (
            "<tr>"
            f"<td>{esc(r['id'])}</td>"
            f"<td>{esc(r['expected'])}</td>"
            f"<td class='old'>{esc(r['old_predicted'])}<br><span class='muted'>{esc(r['old_summary'])}</span></td>"
            f"<td class='new'>{esc(r['new_predicted'])}<br><span class='muted'>{esc(r['new_summary'])}</span></td>"
            "</tr>"
        )
    if not reg_rows:
        reg_rows = "<tr><td colspan='4'>No regressions detected.</td></tr>"

    imp_items = "".join(
        f"<li>{esc(r['id'])}: expected {esc(r['expected'])}, was {esc(r['old_predicted'])}, now {esc(r['new_predicted'])}</li>"
        for r in c["improvements"]
    ) or "<li>None</li>"

    cat_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{v:+.0%}</td></tr>"
        for k, v in sorted(c["category_deltas"].items())
    )

    score_rows = (
        f"<tr><td>Category pass rate</td><td>{pct(c['baseline_pass_rate'])}</td>"
        f"<td>{pct(c['new_pass_rate'])}</td><td>{c['pass_rate_delta']:+.0%}</td></tr>"
        f"<tr><td>Avg summary score (1-5)</td><td>{esc(bs['avg_summary_score'])}</td>"
        f"<td>{esc(ns['avg_summary_score'])}</td><td>{signed(c['summary_score_delta'])}</td></tr>"
        f"<tr><td>Avg latency (s)</td><td>{esc(bs['avg_latency_s'])}</td>"
        f"<td>{esc(ns['avg_latency_s'])}</td><td>{signed(c['latency_delta_s'])}</td></tr>"
        f"<tr><td>Total tokens</td><td>{esc(bs['total_tokens'])}</td>"
        f"<td>{esc(ns['total_tokens'])}</td><td>{esc(c['tokens_delta'])}</td></tr>"
    )

    meta_rows = (
        f"<tr><td>Prompt version</td><td>{esc(bm['prompt_version'])}</td><td>{esc(nm['prompt_version'])}</td></tr>"
        f"<tr><td>Model</td><td>{esc(bm['model'])}</td><td>{esc(nm['model'])}</td></tr>"
        f"<tr><td>Timestamp (UTC)</td><td>{esc(bm['timestamp'])}</td><td>{esc(nm['timestamp'])}</td></tr>"
        f"<tr><td>Dataset version</td><td>{esc(bm['dataset_version'])}</td><td>{esc(nm['dataset_version'])}</td></tr>"
    )

    history = sorted(Path("results").glob("run_*.json"))[-history_n:]

    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Prompt regression report</title><style>" + CSS + "</style></head><body>"
        "<h1>Prompt regression report</h1>"
        f"<span class='badge' style='background:{color}'>{c['status']}</span> "
        f"<span class='muted'>warn above a {c['thresholds']['warn']:.0%} drop, "
        f"critical above {c['thresholds']['critical']:.0%} ({c['cases_compared']} cases compared)</span>"
        "<h2>Run metadata</h2>"
        f"<table><tr><th></th><th>Baseline</th><th>New</th></tr>{meta_rows}</table>"
        "<h2>Scorecard</h2>"
        f"<table><tr><th>Metric</th><th>Baseline</th><th>New</th><th>Change</th></tr>{score_rows}</table>"
        "<h2>Accuracy change by category</h2>"
        f"<table><tr><th>Category</th><th>Change</th></tr>{cat_rows}</table>"
        f"<h2>Regressed cases ({len(c['regressions'])})</h2>"
        f"<table><tr><th>Case</th><th>Expected</th><th>Baseline output</th><th>New output</th></tr>{reg_rows}</table>"
        f"<h2>Improved cases ({len(c['improvements'])})</h2><ul>{imp_items}</ul>"
        f"<h2>Pass rate over the last {len(history)} runs</h2>{trend_svg(history)}"
        "</body></html>"
    )

    out_path = Path(out)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return c, out_path


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        base_path, new_path = args
    else:
        files = latest_runs(2)
        if len(files) < 2:
            raise SystemExit("Need at least 2 runs in results/. Run python -m src.runner first.")
        base_path, new_path = files
    c, out_path = build_report(base_path, new_path)
    print(f"Status: {c['status']}")
    print(f"Report saved to {out_path}")
    webbrowser.open(out_path.resolve().as_uri())