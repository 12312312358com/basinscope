# -*- coding: utf-8 -*-
"""Verify the BasinScope synthetic reviewer demo.

The default mode checks the committed synthetic SQL fixture without requiring a
database. Optional modes validate a running review database and HTTP endpoints.

Exit codes:
    0  all requested checks passed
    1  one or more checks failed
    2  invalid invocation or missing review files
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


BASIN = "\u6d41\u57df"
TOPIC = "\u8bae\u9898"
PLATFORM = "\u5e73\u53f0"
YELLOW = "\u9ec4\u6cb3"
TOPIC_ECO = "\u751f\u6001\u6cbb\u7406"
TOPIC_TOURISM = "\u6587\u65c5"
TOPIC_HEALTH = "\u533b\u60a3\u77db\u76fe"

REQUIRED_TABLES = {
    "t_user",
    "t_article",
    "t_comment",
    "t_article_safe",
    "t_comment_safe",
    "t_basin_article",
    "t_basin_comment",
    "t_xhs_article",
    "t_xhs_comment",
    "t_zhihu_article",
    "t_zhihu_comment",
    "t_douyin_article",
    "t_douyin_comment",
}

EXPECTED_TOTAL_COUNTS = {
    "t_user": 1,
    "t_article": 210,
    "t_comment": 210,
    "t_basin_article": 210,
    "t_basin_comment": 210,
    "t_xhs_article": 70,
    "t_xhs_comment": 190,
    "t_zhihu_article": 70,
    "t_zhihu_comment": 190,
    "t_douyin_article": 18,
    "t_douyin_comment": 18,
}

EXPECTED_YELLOW_COUNTS = {
    "t_basin_article": 120,
    "t_basin_comment": 120,
    "t_xhs_article": 50,
    "t_xhs_comment": 100,
    "t_zhihu_article": 50,
    "t_zhihu_comment": 100,
    "t_douyin_article": 12,
    "t_douyin_comment": 12,
}

EXPECTED_YELLOW_TOPICS = {
    "t_basin_article": {TOPIC_ECO: 40, TOPIC_TOURISM: 40, TOPIC_HEALTH: 40},
    "t_basin_comment": {TOPIC_ECO: 40, TOPIC_TOURISM: 40, TOPIC_HEALTH: 40},
    "t_xhs_article": {TOPIC_ECO: 25, TOPIC_HEALTH: 25},
    "t_xhs_comment": {TOPIC_ECO: 50, TOPIC_HEALTH: 50},
    "t_zhihu_article": {TOPIC_ECO: 25, TOPIC_HEALTH: 25},
    "t_zhihu_comment": {TOPIC_ECO: 50, TOPIC_HEALTH: 50},
    "t_douyin_article": {TOPIC_TOURISM: 6, TOPIC_ECO: 6},
    "t_douyin_comment": {TOPIC_TOURISM: 6, TOPIC_ECO: 6},
}

REQUIRED_REVIEW_DEPENDENCIES = {
    "Flask",
    "Werkzeug",
    "Jinja2",
    "PyMySQL",
    "SQLAlchemy",
    "cryptography",
    "numpy",
    "scikit-learn",
    "jieba",
    "snownlp",
    "Pillow",
    "python-dotenv",
}


def fail(message: str) -> None:
    raise ValueError(message)


def parse_insert_rows(seed_path: Path) -> list[tuple[str, dict[str, str]]]:
    """Parse the single-row INSERT statements used by demo_seed.sql."""
    rows: list[tuple[str, dict[str, str]]] = []
    pattern = re.compile(
        r"INSERT INTO `([^`]+)` \((.*?)\) VALUES \((.*)\);\s*$"
    )
    for line_number, line in enumerate(
        seed_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        match = pattern.match(line.strip())
        if not match:
            continue
        table, columns_text, values_text = match.groups()
        columns = [item.strip().strip("`") for item in columns_text.split(",")]
        values = next(
            csv.reader(
                [values_text],
                delimiter=",",
                quotechar="'",
                escapechar="\\",
                skipinitialspace=True,
            )
        )
        if len(columns) != len(values):
            fail(
                f"{seed_path.name}:{line_number}: column/value count mismatch "
                f"for {table}: {len(columns)} != {len(values)}"
            )
        rows.append((table, dict(zip(columns, values))))
    return rows


def discover_repo_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[1]
    if not (root / "sql" / "demo_seed.sql").is_file():
        fail(f"demo_seed.sql not found under repository root: {root}")
    return root


def check_required_files(root: Path) -> list[str]:
    required = [
        "Dockerfile",
        "docker-compose.yml",
        ".env.reviewer.example",
        "requirements-review.txt",
        "sql/schema.sql",
        "sql/demo_seed.sql",
        "docs/REVIEWER_GUIDE.md",
        "scripts/init_demo_db.py",
        "tests/test_smoke.py",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        fail("missing reviewer files: " + ", ".join(missing))
    return required


def check_schema(root: Path) -> list[str]:
    schema = (root / "sql" / "schema.sql").read_text(encoding="utf-8-sig")
    seed = (root / "sql" / "demo_seed.sql").read_text(encoding="utf-8-sig")
    created = set(
        re.findall(r"CREATE TABLE(?: IF NOT EXISTS)? `?([^`\s(]+)`?", schema + "\n" + seed, re.I)
    )
    missing = sorted(REQUIRED_TABLES - created)
    if missing:
        fail("schema and demo seed are missing required tables: " + ", ".join(missing))
    return sorted(REQUIRED_TABLES)


def check_review_dependencies(root: Path) -> list[str]:
    text = (root / "requirements-review.txt").read_text(encoding="utf-8-sig")
    packages = {
        match.group(1).lower()
        for match in re.finditer(r"^\s*([A-Za-z0-9_.-]+)\s*(?:==|>=|<=|~=|$)", text, re.M)
    }
    missing = sorted(
        package for package in REQUIRED_REVIEW_DEPENDENCIES if package.lower() not in packages
    )
    if missing:
        fail("requirements-review.txt is missing: " + ", ".join(missing))
    return sorted(REQUIRED_REVIEW_DEPENDENCIES)


def check_seed_fixture(root: Path) -> dict[str, Any]:
    seed_path = root / "sql" / "demo_seed.sql"
    rows = parse_insert_rows(seed_path)
    total = Counter(table for table, _ in rows)

    for table, expected in EXPECTED_TOTAL_COUNTS.items():
        actual = total.get(table, 0)
        if actual != expected:
            fail(f"seed count mismatch for {table}: expected {expected}, got {actual}")

    yellow_counts: dict[str, int] = {}
    yellow_topics: dict[str, dict[str, int]] = {}
    for table, expected_count in EXPECTED_YELLOW_COUNTS.items():
        table_rows = [row for name, row in rows if name == table]
        yellow_rows = [row for row in table_rows if row.get(BASIN) == YELLOW]
        yellow_counts[table] = len(yellow_rows)
        if len(yellow_rows) != expected_count:
            fail(
                f"Yellow River count mismatch for {table}: "
                f"expected {expected_count}, got {len(yellow_rows)}"
            )
        actual_topics = dict(Counter(row.get(TOPIC, "") for row in yellow_rows))
        expected_topics = EXPECTED_YELLOW_TOPICS[table]
        if actual_topics != expected_topics:
            fail(
                f"Yellow River topic counts mismatch for {table}: "
                f"expected {expected_topics}, got {actual_topics}"
            )
        yellow_topics[table] = actual_topics

    seed_text = seed_path.read_text(encoding="utf-8-sig")
    urls = re.findall(r"https?://[^\s'\"<>]+", seed_text)
    invalid_urls = sorted({url for url in urls if "example.invalid" not in url})
    if invalid_urls:
        fail("seed contains non-synthetic URLs: " + ", ".join(invalid_urls[:10]))

    sentinel_checks = {
        "synthetic_fixture": "Synthetic" in seed_text,
        "no_real_platform_url": not invalid_urls,
        "yellow_basin": YELLOW in seed_text,
    }
    return {
        "seed_file": str(seed_path),
        "row_count": len(rows),
        "total_counts": dict(sorted(total.items())),
        "yellow_counts": yellow_counts,
        "yellow_topics": yellow_topics,
        "synthetic_urls_only": not invalid_urls,
        "checks": sentinel_checks,
    }


def db_counts(env_file: str | None, repo_root: Path) -> dict[str, Any]:
    try:
        import pymysql
        from dotenv import load_dotenv
    except Exception as exc:
        fail(f"database mode requires pymysql and python-dotenv: {type(exc).__name__}")

    path = Path(env_file) if env_file else repo_root / ".env.reviewer"
    if env_file and not path.is_file():
        fail(f"reviewer environment file not found: {path}")
    if path.is_file():
        load_dotenv(path)
    elif not os.getenv("DB_HOST") and not os.getenv("DB_NAME"):
        fail(f"reviewer environment file not found and DB environment variables are not set: {path}")
    connection_args = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "db_weibo_basin_review"),
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=10,
    )
    conn = pymysql.connect(**connection_args)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            existing = {row[0] for row in cur.fetchall()}
            missing = sorted(REQUIRED_TABLES - existing)
            if missing:
                fail("database is missing required tables: " + ", ".join(missing))

            counts: dict[str, int] = {}
            for table, expected in EXPECTED_TOTAL_COUNTS.items():
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                actual = int(cur.fetchone()[0])
                counts[table] = actual
                if actual != expected:
                    fail(f"database count mismatch for {table}: expected {expected}, got {actual}")

            for table, expected in EXPECTED_YELLOW_COUNTS.items():
                cur.execute(
                    f"SELECT COUNT(*) FROM `{table}` WHERE `{BASIN}`=%s",
                    (YELLOW,),
                )
                actual = int(cur.fetchone()[0])
                if actual != expected:
                    fail(
                        f"database Yellow River count mismatch for {table}: "
                        f"expected {expected}, got {actual}"
                    )
        return {
            "database": connection_args["database"],
            "counts": counts,
            "yellow_counts": EXPECTED_YELLOW_COUNTS,
        }
    finally:
        conn.close()


def url_json(url: str, timeout: int = 10) -> tuple[int, dict[str, Any] | None]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read()
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = None
        return int(response.status), payload


def http_checks(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    health_status, health = url_json(base + "/healthz")
    if health_status != 200 or not health or health.get("status") != "ok":
        fail(f"healthz failed: HTTP {health_status}, payload={health}")

    ready_status, ready = url_json(base + "/readyz")
    if ready_status != 200 or not ready or ready.get("database") != "ok":
        fail(f"readyz failed: HTTP {ready_status}, payload={ready}")
    if int(ready.get("article_count", -1)) != 120:
        fail(f"readyz article_count expected 120, got {ready.get('article_count')}")
    if int(ready.get("comment_count", -1)) != 120:
        fail(f"readyz comment_count expected 120, got {ready.get('comment_count')}")

    with urllib.request.urlopen(base + "/page/dashboard", timeout=600) as response:
        status = int(response.status)
        body = response.read()
    if status != 200:
        fail(f"dashboard returned HTTP {status}")
    if len(body) < 50_000:
        fail(f"dashboard output is too small: {len(body)} bytes")
    html = body.decode("utf-8", errors="replace")
    if "\u9ec4\u6cb3\u6d41\u57df" not in html:
        fail("dashboard HTML does not contain the Yellow River marker")

    return {
        "base_url": base,
        "healthz": health,
        "readyz": ready,
        "dashboard_bytes": len(body),
        "dashboard_marker": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--db", action="store_true", help="validate the review database")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--url", default="", help="validate HTTP endpoints")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    try:
        root = discover_repo_root(args.repo_root)
        report: dict[str, Any] = {
            "repo_root": str(root),
            "files": check_required_files(root),
            "schema_tables": check_schema(root),
            "review_dependencies": check_review_dependencies(root),
            "seed": check_seed_fixture(root),
        }
        if args.db:
            report["database"] = db_counts(args.env_file, root)
        if args.url:
            report["http"] = http_checks(args.url)
        report["status"] = "passed"
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("REVIEWER DEMO CHECK PASSED")
            print(f"repository: {root}")
            print(f"synthetic rows: {report['seed']['row_count']}")
            print(f"Yellow articles: {report['seed']['yellow_counts']['t_basin_article']}")
            print(f"Yellow comments: {report['seed']['yellow_counts']['t_basin_comment']}")
            if args.db:
                print(f"database: {report['database']['database']}")
            if args.url:
                print(f"dashboard bytes: {report['http']['dashboard_bytes']}")
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print("REVIEWER DEMO CHECK FAILED", file=sys.stderr)
            print(f" - {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


