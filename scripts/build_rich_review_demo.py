# -*- coding: utf-8 -*-
"""Generate a rich, deterministic synthetic dataset for reviewer demos.

The generator starts from the committed synthetic SQL templates and expands
them to realistic scales. It never reads the author's production database.
All identifiers, posts, comments, accounts, URLs, dates, and engagement values
are synthetic and deterministic.
"""
from __future__ import annotations

import csv
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "sql" / "demo_seed.sql"

BASIN = "\u6d41\u57df"
TOPIC = "\u8bae\u9898"
PROVINCE = "\u76ee\u6807\u7701\u4efd"
REGION = "\u53d1\u5e03\u5730\u533a"
PUBLISHED = "\u53d1\u5e03\u65f6\u95f4"
COLLECTED = "\u91c7\u96c6\u65f6\u95f4"
CATEGORY = "\u5206\u7c7b"
TITLE = "\u6807\u9898"
BODY = "\u6b63\u6587"
CONTENT = "\u5fae\u535a\u5185\u5bb9"
LINK = "\u5fae\u535a\u94fe\u63a5"
DETAIL = "\u8be6\u60c5\u94fe\u63a5"
AUTHOR_ID = "\u4f5c\u8005ID"
AUTHOR_NAME = "\u4f5c\u8005\u6635\u79f0"
AUTHOR_HOME = "\u4f5c\u8005\u4e3b\u9875"
REPOSTS = "\u8f6c\u53d1\u6570"
COMMENTS = "\u8bc4\u8bba\u6570"
LIKES = "\u70b9\u8d5e\u6570"
FAVOURITES = "\u6536\u85cf\u6570"
SHARES = "\u5206\u4eab\u6570"
REPLIES = "\u56de\u590d\u6570"
COMMENT_ID = "\u8bc4\u8bbaID"
COMMENT_TEXT = "\u8bc4\u8bba\u5185\u5bb9"
COMMENT_TIME = "\u8bc4\u8bba\u65f6\u95f4"
SOURCE = "\u6765\u6e90"
ARTICLE_ID = "\u5fae\u535aID"
USER_ID = "\u7528\u6237ID"
USER_NAME = "\u6635\u79f0"
GENDER = "\u6027\u522b"
USER_REGION = "\u7528\u6237\u5730\u533a"
USER_HOME = "\u7528\u6237\u4e3b\u9875"
CONTENT_ID = "\u5185\u5bb9ID"
VIDEO_ID = "\u89c6\u9891ID"
VIDEO_TITLE = "\u89c6\u9891\u6807\u9898"
VIDEO_DESC = "\u89c6\u9891\u63cf\u8ff0"
HIT = "\u547d\u4e2d\u5173\u952e\u8bcd"
DURATION = "\u65f6\u957f\u79d2"
RESOLUTION = "\u5206\u8fa8\u7387"

YELLOW = "\u9ec4\u6cb3"
YANGTZE = "\u957f\u6c5f"
ECO = "\u751f\u6001\u6cbb\u7406"
TOUR = "\u6587\u65c5"
HEALTH = "\u533b\u60a3\u77db\u76fe"
SOCIAL = "\u793e\u4f1a\u6cbb\u7406"
SYNTHETIC = "\u5408\u6210\u6f14\u793a"

YELLOW_PROVS = ["\u5c71\u4e1c", "\u6cb3\u5357", "\u9655\u897f", "\u5c71\u897f",
                "\u5185\u8499\u53e4", "\u7518\u8083", "\u5b81\u590f", "\u9752\u6d77"]
YELLOW_WEIGHTS = [484, 99, 96, 93, 89, 86, 78, 72]
YANGTZE_PROVS = ["\u56db\u5ddd", "\u6c5f\u82cf", "\u6d59\u6c5f", "\u5b89\u5fbd", "\u6c5f\u897f",
                 "\u6e56\u5317", "\u6e56\u5357", "\u91cd\u5e86", "\u4e91\u5357", "\u8d35\u5dde", "\u4e0a\u6d77"]
YANGTZE_WEIGHTS = [310, 120, 110, 100, 95, 110, 105, 80, 95, 90, 55]

AUTHOR_IP_WEIGHTS = {
    YELLOW: [("未知", 592), ("山东", 100), ("北京", 50), ("陕西", 39), ("河南", 31),
             ("广东", 28), ("江苏", 28), ("山西", 25), ("河北", 22), ("浙江", 22),
             ("内蒙古", 22), ("上海", 14), ("四川", 13), ("湖北", 11), ("甘肃", 10),
             ("宁夏", 10), ("湖南", 10), ("安徽", 10), ("福建", 8), ("广西", 7),
             ("天津", 6), ("辽宁", 6), ("云南", 5), ("青海", 5), ("江西", 4),
             ("黑龙江", 3), ("吉林", 3), ("重庆", 2), ("贵州", 2), ("西藏", 1), ("海南", 1)],
    YANGTZE: [("未知", 550), ("四川", 69), ("广东", 40), ("江苏", 40), ("浙江", 35),
              ("湖北", 33), ("湖南", 31), ("安徽", 28), ("上海", 27), ("江西", 24),
              ("重庆", 23), ("云南", 20), ("贵州", 18), ("青海", 15), ("福建", 15),
              ("北京", 22), ("河南", 12), ("陕西", 10), ("山东", 9), ("广西", 9)],
}
AUTHOR_PROVS = ["\u5317\u4eac", "\u4e0a\u6d77", "\u5e7f\u4e1c", "\u6c5f\u82cf", "\u6d59\u6c5f",
                "\u5c71\u4e1c", "\u6cb3\u5357", "\u9655\u897f", "\u5c71\u897f", "\u5185\u8499\u53e4",
                "\u7518\u8083", "\u5b81\u590f", "\u9752\u6d77", "\u56db\u5ddd", "\u6e56\u5317",
                "\u6e56\u5357", "\u5b89\u5fbd", "\u798f\u5efa", "\u6c5f\u897f", "\u8fbd\u5b81",
                "\u5409\u6797", "\u9ed1\u9f99\u6c5f", "\u5929\u6d25", "\u6cb3\u5317", "\u5e7f\u897f",
                "\u4e91\u5357", "\u8d35\u5dde", "\u6d77\u5357", "\u91cd\u5e86", "\u897f\u85cf"]

OFFICIAL = ["\u751f\u6001\u73af\u5883\u90e8\u5b98\u65b9\u5fae\u535a", "\u5c71\u4e1c\u751f\u6001\u73af\u5883\u5385\u5b98\u65b9\u5fae\u535a",
            "\u6cb3\u5357\u53d1\u5e03", "\u9655\u897f\u6587\u65c5\u53d1\u5e03", "\u5185\u8499\u53e4\u65b0\u95fb\u529e\u516c\u5ba4"]
MEDIA = ["\u6f8e\u6e43\u65b0\u95fb\u5b98\u65b9\u5fae\u535a", "\u4eba\u6c11\u65e5\u62a5", "\u592e\u89c6\u65b0\u95fb", "\u65b0\u4eac\u62a5",
         "\u4e2d\u56fd\u9752\u5e74\u62a5", "\u6cb3\u5357\u65e5\u62a5", "\u5c71\u4e1c\u665a\u62a5"]
INDIVIDUAL = ["\u65c5\u884c\u535a\u4e3b", "\u6444\u5f71\u8fbe\u4eba", "\u533b\u751f", "\u5f8b\u5e08",
              "\u81ea\u5a92\u4f53", "\u521b\u4f5c\u8005", "\u8bd5\u8bc4\u535a\u4e3b"]
DEVICE = ["iPhone\u5ba2\u6237\u7aef", "\u5fae\u535a\u7f51\u9875\u7248", "HUAWEI Mate 60", "OPPO A2 Pro 5G"]
UNKNOWN = ["\u9ec4\u6cb3\u89c2\u5bdf", "\u672c\u5730\u8d44\u8baf", "\u5173\u6ce8\u6c11\u751f", "\u8857\u5934\u968f\u62cd", "\u5468\u672b\u8bb0\u5f55"]

TOPIC_WORDS = {
    ECO: ["\u73af\u4fdd\u7763\u5bdf", "\u7763\u5bdf\u6574\u6539", "\u6c34\u6c61\u67d3", "\u751f\u6001\u4fee\u590d", "\u6e7f\u5730\u4fdd\u62a4"],
    TOUR: ["\u666f\u533a\u5bb0\u5ba2", "\u6e38\u5ba2\u4f53\u9a8c", "\u6587\u65c5\u878d\u5408", "\u5bfc\u6e38\u670d\u52a1", "\u9152\u5e97\u6c11\u5bbf"],
    HEALTH: ["\u533b\u7597\u7ea0\u7eb7", "\u533b\u60a3\u6c9f\u901a", "\u533b\u7597\u4e8b\u6545", "\u533b\u9662\u7ba1\u7406", "\u6cd5\u5f8b\u7ef4\u6743"],
    SOCIAL: ["\u98df\u54c1\u5b89\u5168", "\u57ce\u5e02\u6cbb\u7406", "\u516c\u5171\u670d\u52a1", "\u5e94\u6025\u7ba1\u7406"],
}

TARGETS = {
    "t_article": 2430,
    "t_comment": 140,
    "t_basin_article": 2430,
    "t_basin_comment": 140,
    "t_xhs_article": 3358,
    "t_xhs_comment": 669,
    "t_zhihu_article": 950,
    "t_zhihu_comment": 740,
    "t_douyin_article": 18,
    "t_douyin_comment": 18,
}


def parse_seed():
    pattern = re.compile(r"INSERT INTO `([^`]+)` \((.*?)\) VALUES \((.*)\);\s*$")
    rows = defaultdict(list)
    for line in SEED.read_text(encoding="utf-8-sig").splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        table, cols, vals = m.groups()
        columns = [x.strip().strip("`") for x in cols.split(",")]
        values = next(csv.reader([vals], delimiter=",", quotechar="'", escapechar="\\", skipinitialspace=True))
        if len(columns) == len(values):
            rows[table].append(dict(zip(columns, values)))
    return rows


def weighted(provinces, weights, total):
    pool = []
    for p, w in zip(provinces, weights):
        pool.extend([p] * w)
    if not pool:
        return ["\u672a\u77e5"] * total
    return [pool[(i * 37 + 11) % len(pool)] for i in range(total)]


def month_pool():
    dates = []
    for year in range(2011, 2027):
        for month in range(1, 13):
            if year == 2011 and month < 9:
                continue
            if year == 2026 and month > 10:
                continue
            dates.append((year, month))
    return dates


def _topic_sequence():
    plans = {
        YELLOW: [(ECO, 371), (TOUR, 359), (HEALTH, 169), (SOCIAL, 198)],
        YANGTZE: [(ECO, 406), (TOUR, 417), (HEALTH, 233), (SOCIAL, 277)],
    }
    out = []
    for basin, items in plans.items():
        for topic, count in items:
            out.extend([(basin, topic)] * count)
    random.Random(20261112).shuffle(out)
    return out


def _comment_topic_sequence():
    plans = {
        YELLOW: [(ECO, 19), (HEALTH, 40)],
        YANGTZE: [(ECO, 40), (HEALTH, 41)],
    }
    out = []
    for basin, items in plans.items():
        for topic, count in items:
            out.extend([(basin, topic)] * count)
    random.Random(20261113).shuffle(out)
    return out


def _time_for(i, dates, rng):
    year, month = rng.choice(dates)
    day = 1 + rng.randrange(27)
    hour = 7 + rng.randrange(15)
    minute = rng.randrange(60)
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"


def _author_profiles():
    profiles = []
    for i in range(1800):
        aid = f"demo-author-{i:04d}"
        profiles.append((aid, f"DemoAuthor{i:04d}", f"https://example.invalid/demo/user/{aid}"))
    return profiles


def _commenter_profiles():
    profiles = []
    for i in range(500):
        uid = f"demo-user-{i:04d}"
        profiles.append((uid, f"DemoUser{i:04d}", f"https://example.invalid/demo/user/{uid}"))
    return profiles


def _category_for(i):
    kinds = [OFFICIAL, MEDIA, INDIVIDUAL, DEVICE, UNKNOWN]
    weights = [14, 20, 46, 8, 12]
    rng = random.Random(3000 + i)
    group = rng.choices(kinds, weights=weights, k=1)[0]
    return group[rng.randrange(len(group))]


def _synthetic_content(basin, topic, word, i):
    if topic == ECO:
        return (f"{SYNTHETIC}{i:04d}\uff1a{basin}\u6d41\u57df\u751f\u6001\u6cbb\u7406\u6301\u7eed\u63a8\u8fdb\uff0c"
                f"{word}\u76f8\u5173\u8ba8\u8bba\u5f97\u5230\u5173\u6ce8\uff0c\u516c\u4f17\u5173\u6ce8\u6574\u6539\u3001\u8d23\u4efb\u548c\u540e\u7eed\u5904\u7406\u3002")
    if topic == TOUR:
        return (f"{SYNTHETIC}{i:04d}\uff1a{basin}\u6d41\u57df\u6587\u65c5\u53d1\u5c55\u53d7\u5230\u5173\u6ce8\uff0c"
                f"{word}\u6210\u4e3a\u8ba8\u8bba\u91cd\u70b9\uff0c\u6e38\u5ba2\u4f53\u9a8c\u548c\u670d\u52a1\u8d28\u91cf\u5f97\u5230\u8ba8\u8bba\u3002")
    if topic == HEALTH:
        return (f"{SYNTHETIC}{i:04d}\uff1a\u533b\u60a3\u77db\u76fe\u76f8\u5173\u8ba8\u8bba\u51fa\u73b0\uff0c"
                f"{word}\u6210\u4e3a\u5173\u6ce8\u7126\u70b9\uff0c\u516c\u4f17\u8ba8\u8bba\u8d23\u4efb\u8ba4\u5b9a\u548c\u5904\u7406\u8fdb\u5c55\u3002")
    return (f"{SYNTHETIC}{i:04d}\uff1a{basin}\u6d41\u57df\u793e\u4f1a\u6cbb\u7406\u76f8\u5173\u8ba8\u8bba\u51fa\u73b0\uff0c"
            f"{word}\u6210\u4e3a\u5173\u6ce8\u70b9\uff0c\u516c\u4f17\u5173\u6ce8\u516c\u5171\u670d\u52a1\u548c\u540e\u7eed\u5904\u7406\u3002")


def build(conn):
    templates = parse_seed()
    rng = random.Random(20261112)
    dates = month_pool()
    authors = _author_profiles()
    commenters = _commenter_profiles()

    # Local-like basin/topic composition.
    article_sequence = _topic_sequence()
    yellow_targets = weighted(YELLOW_PROVS, YELLOW_WEIGHTS, 1097)
    yangtze_targets = weighted(YANGTZE_PROVS, YANGTZE_WEIGHTS, 1333)
    author_pools = {
        basin: weighted([x[0] for x in items], [x[1] for x in items], 1097 if basin == YELLOW else 1333)
        for basin, items in AUTHOR_IP_WEIGHTS.items()
    }
    province_cursor = {YELLOW: 0, YANGTZE: 0}
    basin_articles = []
    for i, (basin, topic) in enumerate(article_sequence):
        ids = templates["t_basin_article"]
        pool = [r for r in ids if r.get(BASIN) == basin and r.get(TOPIC) == topic]
        if not pool:
            pool = [r for r in ids if r.get(BASIN) == basin] or ids
        row = dict(pool[i % len(pool)])
        wid = 990000000000000000 + i
        target_list = yellow_targets if basin == YELLOW else yangtze_targets
        target_prov = target_list[province_cursor[basin]]
        province_cursor[basin] += 1
        author_prov = author_pools[basin][province_cursor[basin] - 1]
        word = TOPIC_WORDS[topic][i % len(TOPIC_WORDS[topic])]
        aid, aname, ahref = authors[(i * 17 + i // 5) % len(authors)]
        row.update({
            ARTICLE_ID: wid, CONTENT: _synthetic_content(basin, topic, word, i),
            BASIN: basin, TOPIC: topic, PROVINCE: target_prov, REGION: author_prov,
            PUBLISHED: _time_for(i, dates, rng), COLLECTED: "2026-10-15 12:00:00",
            CATEGORY: _category_for(i), AUTHOR_ID: aid, AUTHOR_NAME: aname, AUTHOR_HOME: ahref,
            LINK: f"https://example.invalid/demo/weibo/{wid}",
            HIT: f"{target_prov} {word}",
            REPOSTS: 1 + (i * 29 + 17) % 380 + (500 if i % 97 == 0 else 0),
            COMMENTS: 1 + (i * 37 + 11) % 260 + (900 if i % 113 == 0 else 0),
            LIKES: 20 + (i * 97 + 131) % 4200 + (12000 if i % 89 == 0 else 0),
        })
        basin_articles.append(row)

    basin_comments = []
    for i, (basin, topic) in enumerate(_comment_topic_sequence()):
        pool = [r for r in templates["t_basin_comment"] if r.get(BASIN) == basin and r.get(TOPIC) == topic]
        if not pool:
            pool = [r for r in templates["t_basin_comment"] if r.get(BASIN) == basin] or templates["t_basin_comment"]
        row = dict(pool[i % len(pool)])
        uid, uname, uhref = commenters[(i * 31 + 3) % len(commenters)]
        parent = next((r for r in basin_articles if r[BASIN] == basin and r[TOPIC] == topic), basin_articles[i % len(basin_articles)])
        row.update({
            COMMENT_ID: 980000000000000000 + i, ARTICLE_ID: parent[ARTICLE_ID], BASIN: basin, TOPIC: topic,
            COMMENT_TEXT: f"{SYNTHETIC}\u8bc4\u8bba{i:04d}\uff1a\u8fd9\u4e2a\u8bdd\u9898\u4e0e\u516c\u4f17\u5173\u6ce8\u7684\u95ee\u9898\u76f8\u5173\uff0c\u5e0c\u671b\u7ee7\u7eed\u516c\u5f00\u540e\u7eed\u5904\u7406\u8fdb\u5c55\u3002",
            COMMENT_TIME: _time_for(i + 17, dates, rng), SOURCE: AUTHOR_PROVS[(i * 19 + 5) % len(AUTHOR_PROVS)],
            USER_ID: uid, USER_NAME: uname, USER_HOME: uhref, GENDER: ["\u672a\u77e5", "\u5973", "\u7537"][i % 3],
            LIKES: (i * 13 + 7) % 90,
        })
        basin_comments.append(row)

    def generate_generic(table, sequence, article_ids=None):
        pool = templates[table]
        out = []
        for i, key in enumerate(sequence):
            row = dict(pool[i % len(pool)])
            basin = key[0] if isinstance(key, tuple) else None
            topic = key[1] if isinstance(key, tuple) and len(key) > 1 else None
            if basin and BASIN in row:
                same = [r for r in pool if r.get(BASIN) == basin and (topic is None or r.get(TOPIC) == topic)]
                if same:
                    row = dict(same[i % len(same)])
                row[BASIN] = basin
            if topic and TOPIC in row:
                row[TOPIC] = topic
            # unique primary key
            if table in ("t_article", "t_comment"):
                pk = ARTICLE_ID if table == "t_article" else COMMENT_ID
                row[pk] = 970000000000000000 + i
            else:
                if table == "t_douyin_article":
                    pk = VIDEO_ID
                elif table.endswith("article"):
                    pk = CONTENT_ID
                else:
                    pk = COMMENT_ID
                row[pk] = f"demo-{table}-{i:06d}"
            if article_ids and table.endswith("comment"):
                link_key = CONTENT_ID if "t_xhs" in table or "t_zhihu" in table else (VIDEO_ID if "douyin" in table else ARTICLE_ID)
                row[link_key] = article_ids[i % len(article_ids)]
            # synthetic text and unique links
            if CONTENT in row:
                row[CONTENT] = _synthetic_content(basin or YELLOW, topic or ECO, TOPIC_WORDS.get(topic or ECO, TOPIC_WORDS[ECO])[i % 5], i)
            if BODY in row:
                row[BODY] = f"{SYNTHETIC}{i:04d}\uff1a" + str(row.get(BODY, ""))
            if TITLE in row:
                row[TITLE] = f"{SYNTHETIC} {i:04d} " + str(row.get(TITLE, ""))
            if VIDEO_TITLE in row:
                row[VIDEO_TITLE] = f"{SYNTHETIC} {i:04d} " + str(row.get(VIDEO_TITLE, ""))
            if VIDEO_DESC in row:
                row[VIDEO_DESC] = f"{SYNTHETIC}{i:04d}\uff1a" + str(row.get(VIDEO_DESC, ""))
            if COMMENT_TEXT in row:
                row[COMMENT_TEXT] = f"{SYNTHETIC}\u8bc4\u8bba{i:04d}\uff1a\u8fd9\u662f\u4e00\u6761\u7528\u4e8e\u754c\u9762\u6f14\u793a\u7684\u5408\u6210\u8bc4\u8bba\u3002"
            if DETAIL in row:
                row[DETAIL] = f"https://example.invalid/demo/{table}/{i:06d}"
            if LINK in row:
                row[LINK] = f"https://example.invalid/demo/{table}/{i:06d}"
            if AUTHOR_ID in row:
                aid, aname, ahref = authors[(i * 17 + i // 7) % len(authors)]
                row[AUTHOR_ID], row[AUTHOR_NAME], row[AUTHOR_HOME] = aid, aname, ahref
            if USER_ID in row:
                uid, uname, uhref = commenters[(i * 31 + 3) % len(commenters)]
                row[USER_ID], row[USER_NAME], row[USER_HOME] = uid, uname, uhref
            if PUBLISHED in row:
                row[PUBLISHED] = _time_for(i, dates, rng)
            if COMMENT_TIME in row:
                row[COMMENT_TIME] = _time_for(i + 31, dates, rng)
            if COLLECTED in row:
                row[COLLECTED] = "2026-10-15 12:00:00"
            for numeric in (REPOSTS, COMMENTS, LIKES, FAVOURITES, SHARES, REPLIES):
                if numeric in row:
                    row[numeric] = (i * 23 + 7) % (1800 if numeric == LIKES else 320)
            out.append(row)
        return out

    # Build cross-platform articles first so comments can reference their IDs.
    xhs_articles = generate_generic("t_xhs_article", [(YELLOW if i % 3 else YANGTZE, ECO if i % 2 else HEALTH) for i in range(TARGETS["t_xhs_article"])])
    zhihu_articles = generate_generic("t_zhihu_article", [(YELLOW if i % 3 else YANGTZE, ECO if i % 2 else HEALTH) for i in range(TARGETS["t_zhihu_article"])])
    douyin_articles = generate_generic("t_douyin_article", [(YELLOW if i % 2 else YANGTZE, ECO if i % 2 else TOUR) for i in range(TARGETS["t_douyin_article"])])
    xhs_comments = generate_generic("t_xhs_comment", [(r[BASIN], r[TOPIC]) for r in xhs_articles[:TARGETS["t_xhs_comment"]]], [r[CONTENT_ID] for r in xhs_articles])
    zhihu_comments = generate_generic("t_zhihu_comment", [(r[BASIN], r[TOPIC]) for r in zhihu_articles[:TARGETS["t_zhihu_comment"]]], [r[CONTENT_ID] for r in zhihu_articles])
    douyin_comments = generate_generic("t_douyin_comment", [(r[BASIN], r[TOPIC]) for r in douyin_articles[:TARGETS["t_douyin_comment"]]], [r[VIDEO_ID] for r in douyin_articles])

    generic_articles = generate_generic("t_article", [None] * TARGETS["t_article"])
    generic_comments = generate_generic("t_comment", [None] * TARGETS["t_comment"],
                                        [r[ARTICLE_ID] for r in generic_articles])
    generated = {
        "t_basin_article": basin_articles,
        "t_basin_comment": basin_comments,
        "t_article": generic_articles,
        "t_comment": generic_comments,
        "t_xhs_article": xhs_articles, "t_xhs_comment": xhs_comments,
        "t_zhihu_article": zhihu_articles, "t_zhihu_comment": zhihu_comments,
        "t_douyin_article": douyin_articles, "t_douyin_comment": douyin_comments,
    }

    with conn.cursor() as cur:
        for table, rows in generated.items():
            cur.execute(f"TRUNCATE TABLE `{table}`")
            columns = list(rows[0].keys())
            sql = f"INSERT INTO `{table}` (" + ",".join(f"`{c}`" for c in columns) + ") VALUES (" + ",".join(["%s"] * len(columns)) + ")"
            cur.executemany(sql, [[r.get(c) for c in columns] for r in rows])
        # The dashboard also reads these safe copies.
        for src, dst in (("t_article", "t_article_safe"), ("t_comment", "t_comment_safe")):
            cur.execute(f"DROP TABLE IF EXISTS `{dst}`")
            cur.execute(f"CREATE TABLE `{dst}` AS SELECT * FROM `{src}`")
    conn.commit()
    return {k: len(v) for k, v in generated.items()}


def main():
    import os
    import pymysql
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env.reviewer")
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "db_weibo_basin_review"), charset="utf8mb4",
        autocommit=False,
    )
    try:
        summary = build(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Rich reviewer demo generated:")
    for table, count in summary.items():
        print(f"  {table}={count}")


if __name__ == "__main__":
    main()
