import json
import os
import urllib.request
from pathlib import Path

DRIFT_WINDOW = int(os.environ.get("DRIFT_WINDOW", "7"))
DRIFT_MIN_PASS_RATE = float(os.environ.get("DRIFT_MIN_PASS_RATE", "0.90"))

STATUS_LABEL = {"OK": "PASS", "WARNING": "WARN", "CRITICAL": "FAIL"}
STATUS_COLOR = {"OK": "#1a7f37", "WARNING": "#b7791f", "CRITICAL": "#c53030"}


def drift_check():
    """Moving average of pass rate over the last DRIFT_WINDOW runs."""
    files = sorted(Path("results").glob("run_*.json"))
    if len(files) < DRIFT_WINDOW:
        return None
    rates = [
        json.loads(p.read_text(encoding="utf-8"))["summary"]["pass_rate"]
        for p in files[-DRIFT_WINDOW:]
    ]
    avg = sum(rates) / len(rates)
    return {
        "window": DRIFT_WINDOW,
        "average": avg,
        "threshold": DRIFT_MIN_PASS_RATE,
        "drifting": avg < DRIFT_MIN_PASS_RATE,
    }


def build_headline(c):
    old, new = c["baseline_pass_rate"], c["new_pass_rate"]
    n = len(c["regressions"])
    if n:
        return f"{n} regression(s) detected, accuracy went from {old:.0%} to {new:.0%}"
    return f"No regressions detected, accuracy {old:.0%} to {new:.0%}"


def post(payload, label):
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print(f"\n[Slack not configured, printing instead] {label}")
        for att in payload["attachments"]:
            print(att["title"])
            print(att["text"])
        return
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print(f"Slack: sent {label}")
    except Exception as e:
        print(f"Slack: failed to send {label}: {e}")


def send_status(c, report_url):
    bm, nm = c["baseline"], c["new"]
    text = (
        f"{build_headline(c)}\n"
        f"Prompt {bm['prompt_version']} -> {nm['prompt_version']} on {nm['model']}\n"
        f"Report: {report_url}"
    )
    payload = {"attachments": [{
        "color": STATUS_COLOR[c["status"]],
        "title": f"Prompt regression check: {STATUS_LABEL[c['status']]}",
        "text": text,
    }]}
    post(payload, "status alert")


def send_drift(d, report_url):
    text = (
        f"The {d['window']}-run moving average of the pass rate is {d['average']:.0%}, "
        f"below the {d['threshold']:.0%} threshold, although no single run triggered an alert.\n"
        f"Report: {report_url}"
    )
    payload = {"attachments": [{
        "color": STATUS_COLOR["WARNING"],
        "title": "Slow drift warning",
        "text": text,
    }]}
    post(payload, "drift warning")