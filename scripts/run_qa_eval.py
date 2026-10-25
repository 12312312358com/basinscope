# -*- coding: utf-8 -*-
"""Run the BasinScope QA evaluation set and record replies and references."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_questions(path: Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        missing = [key for key in ("id", "type", "basin", "question") if key not in row]
        if missing:
            raise ValueError(f"{path}:{line_no}: missing keys: {', '.join(missing)}")
        row.setdefault("expected_facts", [])
        row.setdefault("expected_source_terms", [])
        row.setdefault("out_of_scope", False)
        rows.append(row)
    return rows


def normalize(text: object) -> str:
    text = str(text or "").lower()
    text = text.replace(",", "").replace("，", "").replace(" ", "")
    text = text.replace("%", "").replace("％", "")
    return text


def fact_hit(answer: str, facts: list[str]) -> bool:
    if not facts:
        return True
    answer_n = normalize(answer)
    return all(normalize(fact) in answer_n for fact in facts)


def source_hit(references: list[dict], source_terms: list[str]) -> bool:
    if not source_terms:
        return True
    blob = normalize(json.dumps(references, ensure_ascii=False))
    return any(normalize(term) in blob for term in source_terms)


def refusal_hit(answer: str) -> bool:
    text = answer.lower()
    markers = (
        "证据不足", "无法", "不能", "没有", "不包含", "超出",
        "仅限", "范围外", "not enough", "insufficient", "cannot",
        "outside", "not available", "no evidence",
    )
    return any(marker in text for marker in markers)


def call_chat(base_url: str, question: dict, timeout: int) -> dict:
    url = base_url.rstrip("/") + "/page/chat"
    payload = json.dumps(
        {
            "message": question["question"],
            "basin": question["basin"],
            "mode": "strict",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return {
            "http_status": int(exc.code),
            "reply": exc.read().decode("utf-8", errors="replace"),
            "references": [],
            "error": f"HTTP {exc.code}",
        }
    except Exception as exc:
        return {
            "http_status": 0,
            "reply": "",
            "references": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        data = json.loads(body)
    except Exception:
        return {
            "http_status": status,
            "reply": body,
            "references": [],
            "error": "response was not JSON",
        }
    return {
        "http_status": status,
        "reply": str(data.get("reply") or data.get("answer") or ""),
        "references": data.get("references") or [],
        "error": "",
    }


def automatic_status(question: dict, response: dict) -> str:
    reply = response.get("reply", "")
    if response.get("error"):
        return "error"
    if question.get("out_of_scope"):
        return "auto_pass" if refusal_hit(reply) else "manual_review"
    if question.get("type") == "evidence_gap" and refusal_hit(reply):
        return "auto_pass"
    if fact_hit(reply, question.get("expected_facts", [])) and source_hit(
        response.get("references", []), question.get("expected_source_terms", [])
    ):
        return "auto_pass"
    return "manual_review"


def write_outputs(rows: list[dict], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "qa_results.jsonl"
    csv_path = output_dir / "qa_results.csv"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    columns = [
        "id", "type", "question", "reply", "reference_count", "auto_status",
        "manual_score", "manual_notes", "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})
    return jsonl_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="evaluation/qa_questions.jsonl")
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--output-dir", default="evaluation")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    questions_path = Path(args.questions)
    if not questions_path.is_absolute():
        questions_path = root / questions_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    questions = load_questions(questions_path)
    if args.dry_run:
        print(json.dumps({"status": "passed", "questions": len(questions), "path": str(questions_path)}, ensure_ascii=False, indent=2))
        return 0

    results = []
    for question in questions:
        if question.get("manual_only"):
            item = {
                **question,
                "reply": "",
                "references": [],
                "reference_count": 0,
                "auto_status": "manual_only",
                "manual_score": "",
                "manual_notes": question.get("manual_reason", ""),
                "error": "",
            }
            results.append(item)
            print(f"[{item['id']}] manual_only")
            continue
        response = call_chat(args.base_url, question, args.timeout)
        item = {
            **question,
            "reply": response.get("reply", ""),
            "references": response.get("references", []),
            "reference_count": len(response.get("references", [])),
            "auto_status": automatic_status(question, response),
            "manual_score": "",
            "manual_notes": "",
            "error": response.get("error", ""),
        }
        results.append(item)
        print(f"[{item['id']}] {item['auto_status']} refs={item['reference_count']}")
    jsonl_path, csv_path = write_outputs(results, output_dir)
    counts = {key: sum(1 for row in results if row["auto_status"] == key) for key in ("auto_pass", "manual_review", "manual_only", "error")}
    print(json.dumps({"status": "completed", "questions": len(results), "counts": counts, "jsonl": str(jsonl_path), "csv": str(csv_path)}, ensure_ascii=False, indent=2))
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())