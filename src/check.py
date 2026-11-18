import os
import sys

from .alerts import drift_check, send_drift, send_status
from .compare import latest_runs, print_report
from .report import build_report


def main():
    files = latest_runs(2)
    if len(files) < 2:
        raise SystemExit("Need at least 2 runs in results/. Run python -m src.runner first.")
    base_path, new_path = files

    c, out_path = build_report(base_path, new_path)
    report_url = os.environ.get("REPORT_URL", out_path.resolve().as_uri())

    print_report(c)
    print(f"\nHTML report: {out_path}")

    send_status(c, report_url)

    drift = drift_check()
    if drift is None:
        print("Drift check: not enough runs yet for the moving average.")
    elif drift["drifting"]:
        print(f"Drift check: WARNING, {drift['window']}-run average is {drift['average']:.0%}")
        send_drift(drift, report_url)
    else:
        print(f"Drift check: OK, {drift['window']}-run average is {drift['average']:.0%}")

    # A non-zero exit code is what lets CI block a merge on critical regressions
    if c["status"] == "CRITICAL":
        sys.exit(1)


if __name__ == "__main__":
    main()