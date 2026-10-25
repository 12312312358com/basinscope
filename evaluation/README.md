# QA Evaluation

This directory contains a reproducible manual audit set for the BasinScope
question-answering path. The questions cover numeric facts, event monitoring,
cross-platform comparisons, risk scores, evidence gaps, scope rejection, and
source traceability.

## Files

- `qa_questions.jsonl`: 30 evaluation questions.
- `qa_results.jsonl`: generated replies and references.
- `qa_results.csv`: spreadsheet-friendly result table with manual score fields.

The generated result files are intentionally not committed until an evaluation
run has been completed.

## Dry run

The question file can be validated without starting the application or using an
API key:

```powershell
python scripts/run_qa_eval.py --dry-run
```

## Full run

Start the application with the configured QA service first, then run:

```powershell
python scripts/run_qa_eval.py `
  --base-url http://127.0.0.1:5001 `
  --output-dir evaluation
```

The runner sends:

```json
{
  "message": "question text",
  "basin": "黄河",
  "mode": "strict"
}
```

to `/page/chat` and records both `reply` and `references`.

## Manual scoring

Automatic status is only a screening result. A reviewer must inspect each answer:

- `1`: correct and supported by the returned references;
- `0.5`: partially correct or incompletely sourced;
- `0`: incorrect, unsupported, or an out-of-scope question answered instead of
  being rejected.

Do not report answer accuracy in the manuscript until the manual scores have
been completed.

## Scope of the evaluation

The dataset includes 30 questions:

- 8 numeric factual questions;
- 5 event or risk questions;
- 5 cross-platform questions;
- 4 evidence-gap questions;
- 4 out-of-scope questions;
- 4 scope or traceability questions.

The questions refer to the current snapshot and do not constitute a population
estimate or a substitute for professional evaluation of the language model.

## Short-video validation

The 33-case short-video subset is checked separately:

```powershell
python scripts/verify_video_subset.py --json
```

The check requires a matching l2 feature record, at least one keyframe, ASR
status `ok`, and a non-empty transcript for each selected l3 Yellow River case.
## Resume an interrupted run

Results are saved after every question. If a run is interrupted, continue from
the existing `qa_results.jsonl` without repeating completed questions:

```powershell
python scripts\run_qa_eval.py `
  --base-url http://127.0.0.1:5001 `
  --output-dir evaluation `
  --resume
```

Only rows whose question text still matches `qa_questions.jsonl` are reused.
Start a clean run by omitting `--resume`.