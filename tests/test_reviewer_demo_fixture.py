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

def test_yellow_map_scope() -> None:
    repo = Path(os.environ.get("BASINSCOPE_REPO", Path(__file__).resolve().parents[1]))
    geo = json.loads(
        (repo / "dashboard_gen" / "basin_geo_map.json").read_text(encoding="utf-8")
    )
    analytical = set(geo["meta"]["data"]["yl"])
    displayed = set(geo["meta"]["yl"])
    expected = {
        "\u9752\u6d77",
        "\u7518\u8083",
        "\u5b81\u590f",
        "\u5185\u8499\u53e4",
        "\u9655\u897f",
        "\u5c71\u897f",
        "\u6cb3\u5357",
        "\u5c71\u4e1c",
    }
    assert analytical == expected
    assert displayed - analytical == {"\u56db\u5ddd"}
