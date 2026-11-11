# -*- coding: utf-8 -*-
"""Create a review-only MySQL database and load schema plus synthetic demo data."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from build_rich_review_demo import build as build_rich_review_demo


ROOT = Path(__file__).resolve().parents[1]
_DASHBOARD_GEN = ROOT / "src" / "dashboard_gen"
if str(_DASHBOARD_GEN) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_GEN))
from build_reviewer_video_demo import build as build_reviewer_video_demo


def statements(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    for item in text.split(";"):
        sql = item.strip()
        if sql:
            yield sql


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(ROOT / ".env.reviewer"))
    parser.add_argument("--database", default=None)
    parser.add_argument("--schema", default=str(ROOT / "sql" / "schema.sql"))
    parser.add_argument("--seed", default=str(ROOT / "sql" / "demo_seed.sql"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    load_dotenv(args.env_file)
    database = args.database or os.getenv("DB_NAME", "db_weibo_basin_review")
    if database == "db_weibo_basin" and not args.force:
        raise SystemExit("Refusing to reset the production DB. Use a review DB name or pass --force explicitly.")

    connection_args = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
    )
    admin = pymysql.connect(**connection_args)
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s",
                (database,),
            )
            if cur.fetchone() is None:
                cur.execute(
                    f"CREATE DATABASE `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
    finally:
        admin.close()

    conn = pymysql.connect(database=database, **connection_args)
    try:
        with conn.cursor() as cur:
            for sql in statements(Path(args.schema)):
                cur.execute(sql)
            for sql in statements(Path(args.seed)):
                cur.execute(sql)
            build_rich_review_demo(conn)
            os.environ["DB_NAME"] = database
            build_reviewer_video_demo()
            cur.execute("SELECT COUNT(*) FROM t_basin_article")
            article_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM t_basin_comment")
            comment_count = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"Review database ready: {database}")
    print(f"t_basin_article={article_count}, t_basin_comment={comment_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())