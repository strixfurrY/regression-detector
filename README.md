# Prompt Regression Detector

CI for LLM behavior. When a prompt or model changes, this system runs a human-labeled golden dataset through the feature, scores the outputs, diffs them against the last accepted run, and fails the pull request if quality dropped. Results are posted as a PR comment, an HTML diff report and (optionally) a Slack message.
The feature under test is a customer-support email classifier that returns a category (billing, technical, account, general) and a one-sentence summary.

## How it works

```
prompts/*.yaml  ->  runner (async)  ->  scoring  ->  compare vs baseline  ->  report + alerts  ->  CI gate
```

| Piece | File | Role |
|---|---|---|
| Interface contract | `src/schemas.py` | Pydantic models for prompt config and classifier output |
| Versioned prompts | `prompts/classifier_<version>.yaml` | The "code" under test: version, model, system prompt, few-shot examples |
| Feature | `src/classifier.py` | One function. Schema violations are recorded as failed results, never raised |
| Golden dataset | `data/cases.txt` -> `data/golden_v1.json` | Human-labeled cases with difficulty and edge-type tags |
| Runner | `src/runner.py` | Async, rate-limit aware. Scores category match, summary relevance (LLM judge, 1-5), latency, tokens |
| Comparison | `src/compare.py` | Pass-rate delta, per-category delta, regressions, improvements, status |
| Report | `src/report.py` | HTML: metadata, scorecard, regressed cases side by side, trend chart |
| Alerts | `src/alerts.py` | Slack webhook, slow-drift warning |
| CI entry point | `src/ci.py` | Runs the eval, compares to `baselines/main.json`, writes the PR comment, sets the exit code |
| Workflow | `.github/workflows/prompt-eval.yml` | Triggers on PRs that touch `prompts/` |

## Setup

Requires Python 3.11+ and a Gemini API key (free tier works).

```
git clone https://github.com/strixfurrY/regression-detector.git
cd regression-detector
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file (it is gitignored):

```
GEMINI_API_KEY=your-key
```

Smoke test: `python try.py` should print `category='account'` and `'error': None`.

## Everyday commands

```
python -m src.runner v1        # evaluate one prompt version, saves results/run_*.json
python -m src.compare          # diff the two most recent runs (console)
python -m src.check            # compare + HTML report + alerts + drift check
python -m src.ci v4            # what CI runs: evaluate v4 against baselines/main.json
```

## Adding test cases

Edit `data/cases.txt`, one case per line:

```
category | difficulty | edge_type | email | summary | notes
```

- `difficulty`: easy, medium, hard.
- `edge_type`: `-` for none, or ambiguous, very_short, typos, mixed_language, sarcastic.
- Do not use `|` inside an email.
- Write the label before you see what the model does. Do not relabel to match model output. A failing case is information.
- Write real reasoning in `notes`. It is shown next to the case in the diff report.
- Do not generate cases with an LLM. The dataset is only useful as human-verified ground truth.

Then regenerate and validate:

```
python -m src.build_dataset
python -m src.validate_dataset
```

`data/golden_v1.json` is generated. Never edit it by hand. When labels or cases change, bump `dataset_version` in `build_dataset.py` and re-record the baseline, because the eval bar has moved.

## Thresholds

Configured with environment variables. The same variables work locally, in CI and in Docker.

| Variable | Default | Meaning |
|---|---|---|
| `WARN_THRESHOLD` | 0.03 | Warning if pass rate drops by more than this |
| `CRITICAL_THRESHOLD` | 0.08 | Critical (fails CI) if the drop exceeds this |
| `DRIFT_WINDOW` | 7 | Runs in the moving average |
| `DRIFT_MIN_PASS_RATE` | 0.90 | Slow-drift warning if the average falls below this |
| `SLACK_WEBHOOK_URL` | unset | If unset, alerts are printed instead |

## CI behavior

On every PR that changes a file in `prompts/`, the workflow evaluates the changed prompt, compares it with `baselines/main.json`, comments on the PR, uploads `diff-report` as an artifact, and exits non-zero on CRITICAL. Make `eval` a required status check on `main` so the merge button is blocked.

Secrets (repository settings): `GEMINI_API_KEY`, and optionally `SLACK_WEBHOOK_URL`.

**Updating the baseline.** After a prompt change is intentionally accepted and merged, run the eval on `main` and copy the new run file to `baselines/main.json`. The baseline is "the last accepted behavior", not "the best ever".

## Docker

```
docker build -t regression-detector .
docker run --rm --env-file .env -v "${PWD}\reports:/app/reports" regression-detector v4
```

The image contains no secrets. The API key, webhook URL and thresholds come from the environment.

## Architecture decisions

**Golden dataset by hand, not by LLM.** Generated ground truth measures agreement with a model, not correctness.

**Schema violations are results, not exceptions.** A malformed output counts as a failed case. One bad generation must not abort the run, and the raw output is kept for the report.

**Status is driven by category pass rate, not summary score.** Category match is binary and reproducible. LLM-judge scores move by a point between runs on unchanged behavior, so they are reported but never gate a merge.

**Net pass rate decides the status, but every regression is listed.** In the v4 experiment one case improved and three regressed. The net drop (94% to 81%) triggered CRITICAL, and all three regressions appear by name in the PR comment, so improvements cannot hide a broken case.

**Slow drift is tracked separately from per-run regressions.** A moving average over several runs catches gradual degradation that no single diff would flag.

**Model versions are pinned.** `gemini-3.1-flash-lite` is set explicitly in every prompt file and in the judge. A floating alias such as `-latest` can change under you and make results shift for reasons unrelated to your prompt.

**Rate limiting is built into the runner.** Requests are paced to fit the free tier. A full run takes minutes, not seconds.

## Known limitations

- **The dataset is small (16 cases).** One flip is a 6% change, so the 3% and 8% thresholds are coarse. With 60 or more cases one flip is under 2% and the thresholds become meaningful. Growing the dataset is the first thing to do.
- **The judge is the same model family as the classifier,** so it may grade itself generously. A stronger, separate judge would be better.
- **CI evaluates only the first changed prompt file** in a PR.
- **Latency comparisons are unreliable on shared free-tier infrastructure.** Treat them as informational.