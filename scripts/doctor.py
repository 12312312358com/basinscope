# -*- coding: utf-8 -*-
"""Check the review environment before starting the Flask application."""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "t_user", "t_article", "t_comment", "t_article_safe", "t_comment_safe",
    "t_basin_article", "t_basin_comment",
    "t_xhs_article", "t_xhs_comment", "t_zhihu_article", "t_zhihu_comment",
    "t_douyin_article", "t_douyin_comment",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(ROOT / ".env.reviewer"))
    parser.add_argument("--url", default="")
    args = parser.parse_args()
    load_dotenv(args.env_file)

    errors = []
    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "db_weibo_basin_review"),
            charset="utf8mb4",
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            existing = {row[0] for row in cur.fetchall()}
            missing = [name for name in TABLES if name not in existing]
            if missing:
                errors.append("missing tables: " + ", ".join(missing))
            else:
                cur.execute("SELECT COUNT(*) FROM t_basin_article")
                articles = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM t_basin_comment")
                comments = cur.fetchone()[0]
                print(f"database=ok articles={articles} comments={comments}")
                if articles == 0:
                    errors.append("t_basin_article is empty")
        conn.close()
    except Exception as exc:
        errors.append("database unavailable: " + type(exc).__name__)

    if args.url:
        for endpoint in ("/healthz", "/readyz"):
            try:
                with urllib.request.urlopen(args.url.rstrip("/") + endpoint, timeout=10) as resp:
                    print(f"{endpoint}=HTTP {resp.status}")
                    if resp.status != 200:
                        errors.append(f"{endpoint} returned {resp.status}")
            except urllib.error.HTTPError as exc:
                errors.append(f"{endpoint} returned HTTP {exc.code}")
            except Exception as exc:
                errors.append(f"{endpoint} failed: {type(exc).__name__}")

    if errors:
        print("REVIEW CHECK FAILED")
        for error in errors:
            print(" -", error)
        return 1
    print("REVIEW CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())