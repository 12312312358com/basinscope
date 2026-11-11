# -*- coding: utf-8 -*-
"""Build a clearly labelled synthetic short-video demo product for reviewers.

This fallback is used only for a reviewer database name ending in ``_review``
when the optional model-produced ``video_insight.json`` is unavailable.  It
uses the committed synthetic Douyin rows, generates placeholder keyframes, and
writes the same JSON schema consumed by ``build_unified_page.py``.
"""
from __future__ import annotations

import collections
import json
import os
import time
from pathlib import Path

import pymysql
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
PRJ = BASE.parent
FRAMES = PRJ / "video_features" / "frames"
DST = BASE / "video_topic_data.json"

ARTICLE_ID = "\u89c6\u9891ID"
TOPIC = "\u8bae\u9898"
LIKES = "\u70b9\u8d5e\u6570"
COMMENTS = "\u8bc4\u8bba\u6570"
FAVOURITES = "\u6536\u85cf\u6570"
SHARES = "\u5206\u4eab\u6570"
REGION = "\u53d1\u5e03\u5730\u533a"
DURATION = "\u65f6\u957f\u79d2"
RESOLUTION = "\u5206\u8fa8\u7387"
BASIN = "\u6d41\u57df"
YELLOW = "\u9ec4\u6cb3"
ECO = "\u751f\u6001\u6cbb\u7406"
TOURISM = "\u6587\u65c5"


def _connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "db_weibo_basin_review"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _font(size):
    path = Path(r"C:\Windows\Fonts\arial.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def _frame(path: Path, index: int, topic: str, region: str) -> None:
    colors = [("#1d4ed8", "#93c5fd"), ("#047857", "#a7f3d0"),
              ("#b45309", "#fde68a"), ("#7c3aed", "#ddd6fe")]
    c1, c2 = colors[(index - 1) % len(colors)]
    image = Image.new("RGB", (480, 270), c1)
    draw = ImageDraw.Draw(image)
    for y in range(270):
        t = y / 269
        rgb = tuple(int(int(c1[j:j + 2], 16) * (1 - t) + int(c2[j:j + 2], 16) * t)
                    for j in (1, 3, 5))
        draw.line((0, y, 480, y), fill=rgb)
    draw.rounded_rectangle((22, 22, 458, 248), radius=18, outline=(255, 255, 255), width=2)
    draw.text((40, 72), "SYNTHETIC", font=_font(24), fill=(255, 255, 255))
    draw.text((40, 108), "SHORT-VIDEO DEMO", font=_font(24), fill=(255, 255, 255))
    draw.text((40, 155), f"{topic}  |  Record {index:02d}", font=_font(17), fill=(255, 255, 255))
    draw.text((40, 190), region, font=_font(17), fill=(255, 255, 255))
    image.save(path, quality=88, optimize=True)


def build():
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM t_douyin_article WHERE `{BASIN}`=%s ORDER BY `{ARTICLE_ID}`",
                (YELLOW,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return None

    FRAMES.mkdir(parents=True, exist_ok=True)
    cards = []
    for index, row in enumerate(rows, 1):
        cid = row[ARTICLE_ID]
        topic = "Ecological Governance" if row[TOPIC] == ECO else "Cultural Tourism"
        _frame(FRAMES / f"{cid}.jpg", index, topic, row[REGION])
        likes = int(row[LIKES] or 0)
        comments = int(row[COMMENTS] or 0)
        favourites = int(row[FAVOURITES] or 0)
        shares = int(row[SHARES] or 0)
        interactions = likes + comments + favourites + shares
        claim = ("Visitor experience and service quality are the main reported concerns; "
                 "verify pricing and complaint evidence before use."
                 if topic == "Cultural Tourism" else
                 "Environmental inspection and remediation are the main reported themes; "
                 "verify follow-up evidence before interpretation.")
        cards.append({
            "cid": cid, "basin": YELLOW, "topic": topic,
            "title": f"Synthetic Short-Video Demo {index:02d}",
            "link": f"https://example.invalid/demo/douyin/{cid}",
            "sheet": f"frames/{cid}.jpg", "vlm_status": "synthetic_reviewer_demo",
            "shot": {
                "\u65f6\u957f": float(row[DURATION] or 0), "\u5206\u8fa8\u7387": row[RESOLUTION] or "720x1280",
                "\u753b\u5e45": "Portrait", "\u4e3b\u8272\u8c03": "Blue" if index % 2 else "Green",
                "\u4eae\u5ea6": 0.56 + 0.01 * (index % 5), "\u8272\u5f69\u4e30\u5bcc\u5ea6": 0.48 + 0.01 * (index % 7),
                "\u5e27\u6570": 6,
            },
            "promo": {
                "\u4e92\u52a8\u603b\u91cf": interactions, "\u70b9\u8d5e\u6570": likes,
                "\u8bc4\u8bba\u6570": comments, "\u8f6c\u53d1\u6570": shares, "\u6536\u85cf\u6570": favourites,
                "\u8f6c\u53d1_\u70b9\u8d5e\u6bd4": round(shares / likes, 4) if likes else None,
                "\u8bc4\u8bba_\u70b9\u8d5e\u6bd4": round(comments / likes, 4) if likes else None,
            },
            "senti": {
                "\u8bc4\u8bba\u6570": comments, "\u60c5\u611f\u5206\u5e03": {"\u6b63\u9762": 0, "\u4e2d\u6027": comments, "\u8d1f\u9762": 0},
                "\u8d1f\u9762\u5360\u6bd4": 0.0, "\u8bc9\u6c42\u5206\u5e03": {"Service quality": comments},
                "\u8fc7\u95f8\u95e8": False, "\u5916\u63a8\u58f0\u660e": "Synthetic demo; no population inference.",
            },
            "vlm": {
                "\u4e3b\u4f53": "Yellow River landscape", "\u573a\u666f": "Synthetic basin setting",
                "\u89c6\u89c9\u4e3b\u9898": topic, "\u753b\u9762\u6587\u5b57": "Synthetic reviewer demo",
                "\u8bae\u9898\u503e\u5411": topic, "\u7f6e\u4fe1": 0.88,
            },
            "theme": {"\u6807\u7b7e": topic, "\u6838\u5fc3\u4fe1\u606f": [claim]},
            "advice": ["Use this card only to verify interface behaviour.",
                       "Do not treat synthetic values as research findings."],
            "top": {
                "claim": claim, "recommend": round(0.80 + 0.01 * (index % 8), 3),
                "confidence": "High", "actionability": "Medium", "evidence": ["E1", "E2"],
                "evidence_cats": ["Visual", "Interaction"], "all_valid": True,
            },
            "alts": [], "n_conclusions": 1, "conflict": "", "asr": {"\u72b6\u6001": "no_backend"},
        })

    cards.sort(key=lambda card: -(card["top"]["recommend"] or 0))
    agg = {
        "hue": list(collections.Counter(card["shot"]["\u4e3b\u8272\u8c03"] for card in cards).items()),
        "orient": list(collections.Counter(card["shot"]["\u753b\u5e45"] for card in cards).items()),
        "topic": list(collections.Counter(card["topic"] for card in cards).items()),
        "top": [[card["title"], card["promo"]["\u4e92\u52a8\u603b\u91cf"]]
                for card in sorted(cards, key=lambda x: -(x["promo"]["\u4e92\u52a8\u603b\u91cf"] or 0))[:12]],
        "asr_ok": 0,
        "hueList": [card["cid"] for card in cards],
    }
    result = {
        "meta": {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "synthetic_reviewer_demo", "prompt_version": None,
            "total_analyzed": len(cards), "status": "synthetic_demo",
            "note": "Synthetic reviewer data for interface verification only.",
            "excluded": {}, "no_conclusion": [],
        },
        "topics": {
            "\u957f\u6c5f": {"n": 0, "cards": [], "agg": {}},
            "\u9ec4\u6cb3": {"n": len(cards), "sec": "hh", "cards": cards, "agg": agg},
        },
        "others": {},
    }
    DST.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[reviewer-video] {len(cards)} synthetic cards -> {DST}")
    return result


if __name__ == "__main__":
    build()
