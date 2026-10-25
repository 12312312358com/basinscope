from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_reviewer_demo_fixture() -> None:
    repo = Path(os.environ.get("BASINSCOPE_REPO", Path(__file__).resolve().parents[1]))
    script = Path(
        os.environ.get(
            "BASINSCOPE_VERIFY_SCRIPT",
            repo / "scripts" / "verify_reviewer_demo.py",
        )
    )
    completed = subprocess.run(
        [sys.executable, str(script), "--repo-root", str(repo), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "passed"
    assert payload["seed"]["total_counts"]["t_basin_article"] == 210
    assert payload["seed"]["yellow_counts"]["t_basin_article"] == 120
    assert payload["seed"]["yellow_counts"]["t_basin_comment"] == 120
    assert payload["seed"]["synthetic_urls_only"] is True
