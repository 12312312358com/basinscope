# -*- coding: utf-8 -*-
"""Verify the 33-case Yellow River short-video evaluation subset."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


YELLOW = "\u9ec4\u6cb3"
DOUYIN = "dy"
TOURISM = "\u6587\u65c5"
ECOLOGY = "\u751f\u6001\u6cbb\u7406"
STATUS = "\u72b6\u6001"
TRANSCRIPT = "\u8f6c\u5199\u6587\u672c"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root)
    vf = root / "video_features"
    l2 = load_jsonl(vf / "l2_features.jsonl")
    l3 = load_jsonl(vf / "l3_features.jsonl")
    l2_map = {
        row["content_id"]: row
        for row in l2
        if row.get("basin") == YELLOW and row.get("platform") == DOUYIN
    }
    selected = [row for row in l3 if row.get("basin") == YELLOW]
    errors: list[str] = []
    topic_counts = Counter(row.get("topic") for row in selected)
    if len(selected) != 33:
        errors.append(f"expected 33 Yellow River l3 cases, got {len(selected)}")
    if topic_counts != Counter({TOURISM: 17, ECOLOGY: 16}):
        errors.append(f"unexpected topic counts: {dict(topic_counts)}")
    for row in selected:
        cid = row.get("content_id", "")
        l2row = l2_map.get(cid)
        if l2row is None:
            errors.append(f"{cid}: missing l2 record")
            continue
        if int(l2row.get("frames_count") or 0) <= 0:
            errors.append(f"{cid}: no keyframes")
        asr = ((row.get("features") or {}).get("asr") or {}).get("kv") or {}
        if asr.get(STATUS) != "ok":
            errors.append(f"{cid}: ASR status is {asr.get(STATUS)!r}")
        if not str(asr.get(TRANSCRIPT) or "").strip():
            errors.append(f"{cid}: empty transcript")
    result = {
        "status": "passed" if not errors else "failed",
        "l3_cases": len(selected),
        "topics": dict(topic_counts),
        "l2_yellow_cases": len(l2_map),
        "missing_l2": sum(1 for row in selected if row.get("content_id") not in l2_map),
        "no_keyframes": sum(1 for row in selected if int((l2_map.get(row.get("content_id")) or {}).get("frames_count") or 0) <= 0),
        "asr_non_ok": sum(1 for row in selected if (((row.get("features") or {}).get("asr") or {}).get("kv") or {}).get(STATUS) != "ok"),
        "empty_transcripts": sum(1 for row in selected if not str((((row.get("features") or {}).get("asr") or {}).get("kv") or {}).get(TRANSCRIPT) or "").strip()),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
