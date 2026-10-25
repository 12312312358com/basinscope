from __future__ import annotations

import json
from pathlib import Path

from service.snapshot_facts import FACT_FILE, lookup_snapshot_fact


REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / "evaluation" / "qa_questions.jsonl"


def _normalize(value: object) -> str:
    text = str(value or "").lower()
    for char in (" ", ",", "%"):
        text = text.replace(char, "")
    return text


def test_snapshot_fact_lookup_covers_evaluation_questions() -> None:
    assert (REPO / FACT_FILE).is_file()
    questions = [
        json.loads(line)
        for line in QUESTIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    failures = []
    for question in questions:
        if question.get("manual_only"):
            continue
        answer = lookup_snapshot_fact(
            question["question"], basin=question.get("basin")
        )
        if answer is None:
            failures.append(f"{question['id']}: no deterministic answer")
            continue

        reply = _normalize(answer.get("reply", ""))
        missing = [
            fact
            for fact in question.get("expected_facts", [])
            if _normalize(fact) not in reply
        ]
        references = answer.get("references", [])
        source_ok = any(ref.get("file_path") == FACT_FILE for ref in references)
        if missing:
            failures.append(f"{question['id']}: missing {missing}")
        if not source_ok:
            failures.append(f"{question['id']}: missing snapshot source")

    assert not failures, "\n".join(failures)


def test_manual_scope_questions_have_direct_metadata_answers() -> None:
    questions = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in QUESTIONS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    for question_id in ("q28", "q29"):
        question = questions[question_id]
        answer = lookup_snapshot_fact(
            question["question"], basin=question.get("basin")
        )
        assert answer is not None
        for fact in question.get("expected_facts", []):
            assert _normalize(fact) in _normalize(answer["reply"])


def test_unrelated_generic_question_does_not_reuse_snapshot_fact() -> None:
    question = "\u5982\u4f55\u63d0\u9ad8\u70b9\u8d5e\uff1f"
    assert lookup_snapshot_fact(question) is None
