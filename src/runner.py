import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import openai

from .classifier import classify_email
from .judge import judge_summary
from .loader import load_prompt

MIN_INTERVAL_S = 4.5   # free tier is about 15 requests per minute
MAX_RETRIES = 5
MAX_CONCURRENT = 3


class Pacer:
    """Makes sure requests start at least MIN_INTERVAL_S apart."""

    def __init__(self, interval):
        self.interval = interval
        self.lock = asyncio.Lock()
        self.next_time = 0.0

    async def wait(self):
        async with self.lock:
            now = time.monotonic()
            delay = self.next_time - now
            if delay > 0:
                await asyncio.sleep(delay)
            self.next_time = max(now, self.next_time) + self.interval


async def call_paced(fn, pacer, *args):
    for _ in range(MAX_RETRIES):
        await pacer.wait()
        try:
            return await asyncio.to_thread(fn, *args)
        except openai.RateLimitError:
            await asyncio.sleep(20)
    raise RuntimeError("rate_limited")


async def run_case(case, cfg, pacer, sem):
    async with sem:
        try:
            r = await call_paced(classify_email, pacer, case["input"], cfg)
        except Exception as e:
            r = {"output": None, "raw": None, "error": f"api_error: {e}",
                 "latency_s": None, "prompt_tokens": None, "completion_tokens": None}

        judge = {"score": None, "reason": None}
        if r["output"]:
            try:
                judge = await call_paced(
                    judge_summary, pacer,
                    case["input"], case["expected_summary"], r["output"].summary,
                )
            except Exception as e:
                judge = {"score": None, "reason": f"judge_error: {e}"}

    predicted = r["output"].category if r["output"] else None
    result = {
        "id": case["id"],
        "difficulty": case["difficulty"],
        "edge_type": case["edge_type"],
        "expected_category": case["expected_category"],
        "predicted_category": predicted,
        "category_match": predicted == case["expected_category"],
        "predicted_summary": r["output"].summary if r["output"] else None,
        "expected_summary": case["expected_summary"],
        "summary_score": judge["score"],
        "judge_reason": judge["reason"],
        "raw": r["raw"],
        "error": r["error"],
        "latency_s": r["latency_s"],
        "prompt_tokens": r["prompt_tokens"],
        "completion_tokens": r["completion_tokens"],
    }
    mark = "PASS" if result["category_match"] else "FAIL"
    print(f"  {mark}  {case['id']:<10} expected={case['expected_category']:<10} "
          f"got={predicted!s:<10} summary={judge['score']}")
    return result


async def run_eval(prompt_version, dataset_path="data/golden_v1.json"):
    cfg = load_prompt(prompt_version)
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    cases = dataset["cases"]

    print(f"Running {len(cases)} cases with prompt {cfg.version} on {cfg.model}...")
    pacer = Pacer(MIN_INTERVAL_S)
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results = await asyncio.gather(*(run_case(c, cfg, pacer, sem) for c in cases))
    results = sorted(results, key=lambda r: r["id"])

    passed = sum(r["category_match"] for r in results)
    latencies = [r["latency_s"] for r in results if r["latency_s"] is not None]
    scores = [r["summary_score"] for r in results if r["summary_score"] is not None]
    summary = {
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4),
        "errors": sum(1 for r in results if r["error"]),
        "avg_summary_score": round(sum(scores) / len(scores), 2) if scores else None,
        "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "total_tokens": sum((r["prompt_tokens"] or 0) + (r["completion_tokens"] or 0) for r in results),
    }

    run = {
        "metadata": {
            "prompt_version": cfg.version,
            "model": cfg.model,
            "dataset_version": dataset["dataset_version"],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "summary": summary,
        "results": results,
    }

    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"run_{stamp}_{cfg.version}.json"
    out_path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nPass rate: {passed}/{len(results)} = {summary['pass_rate']:.0%}")
    print(f"Avg summary score: {summary['avg_summary_score']}/5")
    print(f"Average latency: {summary['avg_latency_s']}s | Errors: {summary['errors']}")
    print(f"Saved to {out_path}")
    return run


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    asyncio.run(run_eval(version))