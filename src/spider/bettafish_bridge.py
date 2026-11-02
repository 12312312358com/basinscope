# -*- coding: utf-8 -*-
"""
BettaFish(MediaCrawler) 采集结果 → 本项目统一表（数据回收桥）
=============================================================================
用途
    把 7 个平台采集到的内容/评论，按 `source_keyword` 反解出
    **流域 / 议题 / 目标省份 / 情感**，落到作品库 db_weibo_basin 的两张统一表，
    供仪表盘与生成链按「流域 × 议题」口径消费。

    ⚠️ 本文件属作品自身代码，**不含任何 BettaFish 源码**（路线①：独立调用）。

映射规则（唯一口径，与 basin_keyword_source.py 同源）
    A 类关键词「省份 议题词」→ 流域/议题/省份/情感 全部由 basin_keywords_map.json 直接给出；
      其中流域用 `basin_all`（地理口径），四川/青海记为「黄河长江」。
    B 类关键词「纯议题词」→ 无省份，改用**作者 IP 属地**判定流域：
      mask_region() 取省 → basin_classify_basin() 判流域（与微博/抖音侧同一实现）。

用法
    python spider/bettafish_bridge.py --selftest            # 用合成数据自检映射，不连库
    python spider/bettafish_bridge.py --dry-run             # 连源库只统计，不写目标库
    python spider/bettafish_bridge.py --create-table        # 建目标表
    python spider/bettafish_bridge.py                       # 正式导入（内容）
    python spider/bettafish_bridge.py --with-comments       # 连评论一起导入
    python spider/bettafish_bridge.py --platforms xhs wb    # 只处理指定平台

源库连接（优先 --src-url，其次环境变量，最后取默认）
    MINDSPIDER_DB_HOST / _PORT / _USER / _PASSWORD / _NAME
=============================================================================
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_weibo_to_db_NEW import engine as TARGET_ENGINE      # noqa: E402  作品库 db_weibo_basin
from river_basin_spider import basin_classify_basin, mask_region   # noqa: E402  同一口径

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
KW_MAP_FILE = os.path.join(_HERE, 'basin_keywords_map.json')

TARGET_TABLE = 't_bettafish_article'
TARGET_CMT_TABLE = 't_bettafish_comment'

# ---------------------------------------------------------------------------
# 各平台源表与「候选列名」。
# 用候选列表而不是硬编码列名：不同 commit / 版本的字段名有出入，
# 运行时按实际表结构挑第一个存在的列，缺列自动跳过（不报错）。
# ---------------------------------------------------------------------------
SRC = {
    'xhs': {
        'table': 'xhs_note',
        'id': ['note_id'], 'title': ['title'], 'content': ['desc'],
        'author_id': ['user_id'], 'author_nick': ['nickname'],
        'like': ['liked_count'], 'cmt': ['comment_count'],
        'time': ['time', 'last_update_time'], 'url': ['note_url', 'note_id'],
        'ip': ['ip_location'], 'kw': ['source_keyword'],
        'share': ['share_count'], 'collect': ['collected_count'],
        'cover': ['image_list', 'video_url'],
    },
    'dy': {
        'table': 'douyin_aweme',
        'id': ['aweme_id'], 'title': ['title'], 'content': ['desc'],
        'author_id': ['user_id'], 'author_nick': ['nickname'],
        'like': ['liked_count'], 'cmt': ['comment_count'],
        'time': ['create_time'], 'url': ['aweme_url', 'aweme_id'],
        'ip': ['ip_location'], 'kw': ['source_keyword'],
        'share': ['share_count'], 'collect': ['collected_count'],
        'cover': ['cover_url'],
    },
    'ks': {
        'table': 'kuaishou_video',
        'id': ['video_id'], 'title': ['title'], 'content': ['desc'],
        'author_id': ['user_id'], 'author_nick': ['nickname'],
        'like': ['liked_count'],         'cmt': [],
        'time': ['create_time'], 'url': ['video_url', 'video_id'],
        'ip': [], 'kw': ['source_keyword'],
        'share': [], 'collect': [],
        'cover': ['video_cover_url'],
    },
    'bili': {
        'table': 'bilibili_video',
        'id': ['video_id'], 'title': ['title'], 'content': ['desc'],
        'author_id': ['user_id'], 'author_nick': ['nickname'],
        'like': ['liked_count'],         'cmt': ['video_comment'],
        'time': ['create_time'], 'url': ['video_url', 'video_id'],
        'ip': [], 'kw': ['source_keyword'],
        'share': ['video_share_count'], 'collect': ['video_favorite_count'],
        'cover': ['video_cover_url'],
    },
    'wb': {
        'table': 'weibo_note',
        'id': ['note_id'], 'title': [], 'content': ['content'],
        'author_id': ['user_id'], 'author_nick': ['nickname'],
        'like': ['liked_count'], 'cmt': ['comments_count'],
        'time': ['create_date_time', 'create_time'], 'url': ['note_url', 'note_id'],
        'ip': ['ip_location'], 'kw': ['source_keyword'],
        'share': ['shared_count'], 'collect': [], 'cover': [],
    },
    'tieba': {
        'table': 'tieba_note',
        'id': ['note_id'], 'title': ['title'], 'content': ['desc'],
        'author_id': ['user_link'], 'author_nick': ['user_nickname'],
        'like': [], 'cmt': ['total_replay_num'],
        'time': ['publish_time'], 'url': ['note_url', 'note_id'],
        'ip': ['ip_location'], 'kw': ['source_keyword'],
        'share': [], 'collect': [], 'cover': [],
    },
    'zhihu': {
        'table': 'zhihu_content',
        'id': ['content_id'], 'title': ['title'], 'content': ['content_text'],
        'author_id': ['user_id', 'user_url_token'], 'author_nick': ['user_nickname'],
        'like': ['voteup_count'], 'cmt': ['comment_count'],
        'time': ['created_time'], 'url': ['content_url', 'content_id'],
        'ip': [], 'kw': ['source_keyword'],
        'share': [], 'collect': [], 'cover': [],
    },
}

# 评论表：父内容ID 用于继承流域/议题（评论表本身没有 source_keyword）
CMT = {
    'xhs':     {'table': 'xhs_note_comment',       'id': ['comment_id'],   'parent': ['note_id'],
                'content': ['content'], 'nick': ['nickname'], 'like': ['comment_like_count'],
                'time': ['create_time'], 'ip': ['ip_location']},
    'dy':      {'table': 'douyin_aweme_comment',   'id': ['comment_id'],   'parent': ['aweme_id'],
                'content': ['content'], 'nick': ['nickname'], 'like': ['comment_like_count', 'like_count'],
                'time': ['create_time'], 'ip': ['ip_location']},
    'ks':      {'table': 'kuaishou_video_comment', 'id': ['comment_id'],   'parent': ['video_id'],
                'content': ['content'], 'nick': ['nickname'], 'like': [],
                'time': ['create_time'], 'ip': []},
    'bili':    {'table': 'bilibili_video_comment', 'id': ['comment_id'],   'parent': ['video_id'],
                'content': ['content'], 'nick': ['nickname'], 'like': ['like_count'],
                'time': ['create_time'], 'ip': ['ip_location']},
    'wb':      {'table': 'weibo_note_comment',     'id': ['comment_id'],   'parent': ['note_id'],
                'content': ['content'], 'nick': ['nickname'], 'like': ['comment_like_count'],
                'time': ['create_time'], 'ip': ['ip_location']},
    'tieba':   {'table': 'tieba_comment',          'id': ['comment_id'],   'parent': ['note_id'],
                'content': ['content'], 'nick': ['user_nickname'], 'like': [],
                'time': ['create_time', 'publish_time'], 'ip': ['ip_location']},
    'zhihu':   {'table': 'zhihu_comment',          'id': ['comment_id'],   'parent': ['content_id'],
                'content': ['content'], 'nick': ['user_nickname'], 'like': ['like_count'],
                'time': ['created_time', 'create_time'], 'ip': ['ip_location']},
}

DDL_TARGET = """
CREATE TABLE IF NOT EXISTS `%s` (
  `平台`       VARCHAR(16)  NOT NULL,
  `内容ID`     VARCHAR(191) NOT NULL,
  `标题`       TEXT,
  `内容`       TEXT,
  `作者ID`     TEXT,
  `作者昵称`   TEXT,
  `点赞数`     BIGINT DEFAULT 0,
  `评论数`     BIGINT DEFAULT 0,
  `转发数`     BIGINT DEFAULT 0 COMMENT '抖音/小红书=B站的分享数；微博=转发数；无此字段的平台恒为0',
  `收藏数`     BIGINT DEFAULT 0 COMMENT '小红书/抖音=collected_count；B站=favorite_count；其余平台无',
  `封面`       TEXT COMMENT '封面图/首图地址；无此字段的平台为空',
  `发布时间`   VARCHAR(64),
  `内容链接`   TEXT,
  `IP属地`     VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `目标省份`   VARCHAR(16),
  `情感`       VARCHAR(8),
  `流域来源`   VARCHAR(8) COMMENT 'keyword=词表 / ip=作者属地 / 空=未判出',
  `采集时间`   DATETIME,
  PRIMARY KEY (`平台`, `内容ID`),
  KEY `idx_bf_basin` (`流域`), KEY `idx_bf_topic` (`议题`), KEY `idx_bf_kw` (`命中关键词`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BettaFish 多平台采集内容（统一口径）';
""" % TARGET_TABLE

DDL_TARGET_CMT = """
CREATE TABLE IF NOT EXISTS `%s` (
  `平台`     VARCHAR(16)  NOT NULL,
  `评论ID`   VARCHAR(191) NOT NULL,
  `内容ID`   VARCHAR(191) COMMENT '父内容ID',
  `评论内容` TEXT,
  `作者昵称` TEXT,
  `点赞数`   BIGINT DEFAULT 0,
  `评论时间` VARCHAR(64),
  `IP属地`   VARCHAR(32),
  `流域`     VARCHAR(16),
  `议题`     VARCHAR(32),
  `目标省份` VARCHAR(16),
  `情感`     VARCHAR(8),
  `采集时间` DATETIME,
  PRIMARY KEY (`平台`, `评论ID`),
  KEY `idx_bfc_content` (`内容ID`), KEY `idx_bfc_basin` (`流域`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BettaFish 多平台评论（继承父内容口径）';
""" % TARGET_CMT_TABLE

ART_COLS = ['平台', '内容ID', '标题', '内容', '作者ID', '作者昵称', '点赞数', '评论数',
            '转发数', '收藏数', '封面',
            '发布时间', '内容链接', 'IP属地', '命中关键词', '流域', '议题', '目标省份',
            '情感', '流域来源', '采集时间']
CMT_COLS = ['平台', '评论ID', '内容ID', '评论内容', '作者昵称', '点赞数', '评论时间',
            'IP属地', '流域', '议题', '目标省份', '情感', '采集时间']

# 后来新增的列（存量表靠 ensure_article_columns() 补；建表时 DDL 里已包含）\
ART_EXTRA_COLS = [
    ('转发数', "BIGINT DEFAULT 0 COMMENT '抖音/小红书/B站=分享数；微博=转发数；无此字段的平台恒为 0'"),
    ('收藏数', "BIGINT DEFAULT 0 COMMENT '小红书/抖音=collected_count；B站=favorite_count；其余平台无'"),
    ('封面', "TEXT COMMENT '封面图/首图地址；小红书取 image_list 第一张；无此字段的平台为空'"),
]


# ---------------------------------------------------------------------------
# 词表映射
# ---------------------------------------------------------------------------
def load_kw_map(path=None):
    p = path or KW_MAP_FILE
    if not os.path.isfile(p):
        sys.exit('找不到词表映射 %s\n请先运行: python spider/basin_keyword_source.py --write' % p)
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f).get('map', {})


def resolve(keyword, ip_location, kwmap):
    """关键词 + 作者属地 -> (议题, 流域, 目标省份, 情感, 来源)。

    A 类：词表直接给出（流域取地理口径 basin_all，四川/青海=黄河长江）
    B 类：词表只给议题/情感，流域靠作者 IP 属地判定
    """
    kw = (keyword or '').strip()
    m = kwmap.get(kw)

    if m and m.get('kind') == 'A':
        return (m.get('topic'), m.get('basin_all') or m.get('basin'),
                m.get('province'), m.get('sentiment'), 'keyword')

    # B 类（或词表外的关键词）
    prov = mask_region(ip_location) if ip_location else '未知'
    basin = basin_classify_basin(prov)
    if basin in ('未知', '非流域'):
        return (m.get('topic') if m else None, basin, '', (m.get('sentiment') if m else None), 'ip')
    return (m.get('topic') if m else None, basin, prov,
            (m.get('sentiment') if m else None), 'ip')


def _pick(cols_available, candidates):
    for c in candidates:
        if c in cols_available:
            return c
    return None


def _i(v):
    """宽松取整：'1.2万' / None / '3' 都能吃下，失败给 0。"""
    if v is None:
        return 0
    s = str(v).strip().replace(',', '')
    if not s:
        return 0
    mult = 1
    if s.endswith('万'):
        mult, s = 10000, s[:-1]
    elif s.endswith('亿'):
        mult, s = 100000000, s[:-1]
    try:
        return int(float(s) * mult)
    except (ValueError, TypeError):
        return 0


def _cover(v):
    """取封面地址：有的平台给单条 URL，有的给列表（小红书 image_list 是 JSON 数组串）。

    列表只取第一张当封面；解析不出来就原样返回（不猜、不丢）。
    """
    s = ('' if v is None else str(v)).strip()
    if not s:
        return ''
    if s.startswith('['):
        try:
            arr = json.loads(s)
        except (ValueError, TypeError):
            arr = None
        if isinstance(arr, list) and arr:
            s = str(arr[0]).strip()
        else:
            # JSON 解析不了就退化为按逗号切第一段
            s = s.strip('[]').split(',')[0].strip().strip('"\'')
    return s[:1000]


def _dt(v):
    """把时间统一成 'YYYY-MM-DD HH:MM:SS'，与既有表 t_basin_article 的口径一致。

    能吃下四种来源形态：
      - 裸 Unix 时间戳（秒 / 毫秒）—— 抖音、B站、贴吧的 create_time 就是这种
      - ISO 串带时区 —— 微博的 create_date_time 形如 '2026-04-16 13:56:24+08:00'
      - 'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DD'
      - 其它无法识别的，原样返回（不猜、不丢）
    """
    if v is None:
        return ''
    s = str(v).strip()
    if not s:
        return ''
    if s.isdigit():
        n = int(s)
        if n > 10 ** 12:          # 毫秒时间戳
            n //= 1000
        try:
            return datetime.fromtimestamp(n).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError, OverflowError, TypeError):
            return s
    s2 = s.replace('T', ' ')
    s2 = re.sub(r'\.\d+', '', s2)                       # 去掉毫秒
    s2 = re.sub(r'(Z|[+-]\d{2}:?\d{2})$', '', s2)       # 去掉时区后缀
    m = re.match(r'^(\d{4}-\d{2}-\d{2})(?:[ ](\d{2}:\d{2}(?::\d{2})?))?', s2.strip())
    if m:
        d, t = m.group(1), m.group(2) or '00:00:00'
        if len(t) == 5:
            t += ':00'
        return d + ' ' + t
    return s


# ---------------------------------------------------------------------------
# 源库
# ---------------------------------------------------------------------------
def src_engine(src_url=None):
    if src_url:
        return create_engine(src_url, future=True)
    host = os.getenv('MINDSPIDER_DB_HOST', 'localhost')
    port = os.getenv('MINDSPIDER_DB_PORT', '3306')
    user = os.getenv('MINDSPIDER_DB_USER', 'root')
    pwd = os.getenv('MINDSPIDER_DB_PASSWORD', '')
    name = os.getenv('MINDSPIDER_DB_NAME', 'mindspider')
    return create_engine('mysql+pymysql://%s:%s@%s:%s/%s?charset=utf8mb4'
                         % (user, pwd, host, port, name), future=True)


def table_cols(eng, table):
    from sqlalchemy import inspect
    try:
        return {c['name'] for c in inspect(eng).get_columns(table)}
    except Exception:
        return set()


def read_platform(eng, plat, limit=None):
    """读某平台内容表并映射成目标行；表不存在/字段缺失时安全跳过。"""
    cfg = SRC[plat]
    cols = table_cols(eng, cfg['table'])
    if not cols:
        print('   [跳过] %s：源表 %s 不存在（该平台还没采集过？）' % (plat, cfg['table']))
        return [], {}

    kwcol = _pick(cols, cfg['kw'])
    if not kwcol:
        print('   [跳过] %s：源表缺 source_keyword 字段，无法反解流域/议题' % plat)
        return [], {}

    picked = {}
    for key in ('id', 'title', 'content', 'author_id', 'author_nick',
                'like', 'cmt', 'time', 'url', 'ip', 'share', 'collect', 'cover'):
        picked[key] = _pick(cols, cfg[key]) if cfg[key] else None

    want = [c for c in picked.values() if c] + [kwcol]
    sql = 'SELECT %s FROM `%s`' % (', '.join('`%s`' % c for c in sorted(set(want))), cfg['table'])
    if limit:
        sql += ' LIMIT %d' % int(limit)

    df = pd.read_sql(text(sql), con=eng)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows, id2ctx, skipped = [], {}, 0

    for rec in df.to_dict('records'):
        cid = rec.get(picked['id'])
        if cid is None or str(cid).strip() == '':
            skipped += 1
            continue
        cid = str(cid)
        topic, basin, prov, sent, src = resolve(rec.get(kwcol), rec.get(picked['ip']), KW_MAP)
        ctx = (topic, basin, prov, sent)
        id2ctx[cid] = ctx
        title = rec.get(picked['title']) if picked['title'] else None
        content = rec.get(picked['content']) if picked['content'] else None
        # 微博等平台源表没有 title 字段 → 回落到正文前 50 字，
        # 与既有表 t_basin_article 的「微博内容」口径一致（避免整列空着）。
        if not (title and str(title).strip()):
            title = (str(content)[:50] if content else '')
        rows.append({
            '平台': plat, '内容ID': cid,
            '标题': title,
            '内容': content,
            '作者ID': str(rec.get(picked['author_id']) or '') if picked['author_id'] else '',
            '作者昵称': rec.get(picked['author_nick']) if picked['author_nick'] else None,
            '点赞数': _i(rec.get(picked['like'])) if picked['like'] else 0,
            '评论数': _i(rec.get(picked['cmt'])) if picked['cmt'] else 0,
            '转发数': _i(rec.get(picked['share'])) if picked['share'] else 0,
            '收藏数': _i(rec.get(picked['collect'])) if picked['collect'] else 0,
            '封面': _cover(rec.get(picked['cover'])) if picked['cover'] else '',
            '发布时间': _dt(rec.get(picked['time'])) if picked['time'] else '',
            '内容链接': str(rec.get(picked['url']) or '') if picked['url'] else '',
            'IP属地': str(rec.get(picked['ip']) or '') if picked['ip'] else '',
            '命中关键词': str(rec.get(kwcol) or ''),
            '流域': basin, '议题': topic, '目标省份': prov or '',
            '情感': sent or '', '流域来源': src, '采集时间': now,
        })
    print('   [%s] %s -> %d 行（跳过无ID %d）' % (plat, cfg['table'], len(rows), skipped))
    return rows, id2ctx


def read_comments(eng, plat, id2ctx, limit=None):
    """读评论表，流域/议题从父内容继承（评论表没有 source_keyword）。"""
    cfg = CMT[plat]
    cols = table_cols(eng, cfg['table'])
    if not cols:
        print('   [跳过] %s 评论：表 %s 不存在' % (plat, cfg['table']))
        return []
    picked = {}
    for key in ('id', 'parent', 'content', 'nick', 'like', 'time', 'ip'):
        picked[key] = _pick(cols, cfg[key]) if cfg[key] else None
    if not (picked['id'] and picked['parent']):
        print('   [跳过] %s 评论：缺评论ID或父ID字段' % plat)
        return []

    want = [c for c in picked.values() if c]
    sql = 'SELECT %s FROM `%s`' % (', '.join('`%s`' % c for c in sorted(set(want))), cfg['table'])
    if limit:
        sql += ' LIMIT %d' % int(limit)
    df = pd.read_sql(text(sql), con=eng)

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows, orphan = [], 0
    for rec in df.to_dict('records'):
        cid = rec.get(picked['id'])
        pid = rec.get(picked['parent'])
        if cid is None or pid is None:
            continue
        ctx = id2ctx.get(str(pid))
        if not ctx:
            orphan += 1
            continue
        topic, basin, prov, sent = ctx
        rows.append({
            '平台': plat, '评论ID': str(cid), '内容ID': str(pid),
            '评论内容': rec.get(picked['content']) if picked['content'] else None,
            '作者昵称': rec.get(picked['nick']) if picked['nick'] else None,
            '点赞数': _i(rec.get(picked['like'])) if picked['like'] else 0,
            '评论时间': _dt(rec.get(picked['time'])) if picked['time'] else '',
            'IP属地': str(rec.get(picked['ip']) or '') if picked['ip'] else '',
            '流域': basin, '议题': topic, '目标省份': prov or '',
            '情感': sent or '', '采集时间': now,
        })
    print('   [%s] %s -> %d 条评论（无对应父内容跳过 %d）' % (plat, cfg['table'], len(rows), orphan))
    return rows


# ---------------------------------------------------------------------------
# 写目标库
# ---------------------------------------------------------------------------
def upsert(eng, table, cols, rows, chunk=500):
    if not rows:
        return 0
    upd = ', '.join('`%s`=VALUES(`%s`)' % (c, c) for c in cols if c not in ('平台', '内容ID', '评论ID'))
    sql = 'INSERT INTO `%s` (%s) VALUES (%s) ON DUPLICATE KEY UPDATE %s' % (
        table, ', '.join('`%s`' % c for c in cols), ', '.join(':%s' % c for c in cols), upd)
    total = 0
    with eng.begin() as conn:
        for i in range(0, len(rows), chunk):
            conn.execute(text(sql), rows[i:i + chunk])
            total += len(rows[i:i + chunk])
    return total


def summarize(rows, key='流域', extra='议题'):
    from collections import Counter
    c1, c2 = Counter(r.get(key) or '(空)' for r in rows), Counter(
        '%s|%s' % (r.get(key) or '(空)', r.get(extra) or '(空)') for r in rows)
    print('   按%s：' % key + '   '.join('%s=%d' % kv for kv in sorted(c1.items(), key=lambda x: -x[1])))
    print('   按%s×%s：' % (key, extra) + '   '.join('%s=%d' % kv for kv in sorted(c2.items(), key=lambda x: -x[1])))


# ---------------------------------------------------------------------------
# 自检（不连库）
# ---------------------------------------------------------------------------
def selftest():
    kwmap = load_kw_map()
    cases = [
        ('山东 排污', '山东'),
        ('四川 文旅融合', '四川 成都'),
        ('青海 水污染', ''),
        ('非遗', '广东'),          # B 类 -> 靠 IP
        ('非遗', ''),              # B 类且无 IP -> 未知
        ('导游强迫购物', '非流域地区'),
    ]
    print('=' * 74)
    print('映射自检（A 类看词表，B 类看作者 IP）')
    print('=' * 74)
    for kw, ip in cases:
        topic, basin, prov, sent, src = resolve(kw, ip, kwmap)
        print('  关键词 %-16s IP属地 %-10s -> 议题=%-5s 流域=%-9s 省份=%-5s 情感=%-4s [%s]'
              % (kw, ip or '(空)', topic or '-', basin or '-', prov or '-', sent or '-', src))


# ---------------------------------------------------------------------------
def ensure_article_columns(eng):
    """给已存在的目标表补新列。

    `CREATE TABLE IF NOT EXISTS` 对**已存在**的表什么都不做，所以后来新增的字段
    （转发数 / 收藏数 / 封面）必须显式 ALTER，否则老库跑完仍然是旧结构。
    幂等：只加缺失的列。
    """
    have = table_cols(eng, TARGET_TABLE)
    if not have:
        return
    todo = [(n, d) for n, d in ART_EXTRA_COLS if n not in have]
    if not todo:
        return
    with eng.begin() as c:
        for n, d in todo:
            c.execute(text('ALTER TABLE `%s` ADD COLUMN `%s` %s'
                           % (TARGET_TABLE, n, d)))
    print('已给 %s 补列：%s' % (TARGET_TABLE, '、'.join(n for n, _ in todo)))


def main(argv=None):
    ap = argparse.ArgumentParser(description='BettaFish 采集结果 → 作品库统一表')
    ap.add_argument('--platforms', nargs='+', default=list(SRC.keys()),
                    choices=list(SRC.keys()), help='要回收的平台，默认全部')
    ap.add_argument('--with-comments', action='store_true', help='连评论一起导入')
    ap.add_argument('--limit', type=int, help='每平台最多处理多少行（调试用）')
    ap.add_argument('--create-table', action='store_true', help='只建目标表')
    ap.add_argument('--dry-run', action='store_true', help='只统计，不写目标库')
    ap.add_argument('--selftest', action='store_true', help='用合成数据自检映射，不连库')
    ap.add_argument('--src-url', help='源库 SQLAlchemy URL，覆盖环境变量')
    args = ap.parse_args(argv)

    if args.selftest:
        selftest()
        return

    global KW_MAP
    KW_MAP = load_kw_map()
    print('词表映射：%d 个关键词（%s）' % (len(KW_MAP), KW_MAP_FILE))

    if args.create_table:
        with TARGET_ENGINE.begin() as c:
            c.execute(text(DDL_TARGET))
            c.execute(text(DDL_TARGET_CMT))
        ensure_article_columns(TARGET_ENGINE)
        print('已建表：%s / %s' % (TARGET_TABLE, TARGET_CMT_TABLE))
        return

    eng = src_engine(args.src_url)
    all_arts, all_cmts, ctx_per_plat = [], [], {}
    for plat in args.platforms:
        rows, id2ctx = read_platform(eng, plat, args.limit)
        all_arts.extend(rows)
        ctx_per_plat[plat] = id2ctx
        if args.with_comments and id2ctx:
            all_cmts.extend(read_comments(eng, plat, id2ctx, args.limit))

    print('\n合计：内容 %d 行，评论 %d 行' % (len(all_arts), len(all_cmts)))
    if all_arts:
        summarize(all_arts)
    if all_cmts:
        summarize(all_cmts)

    if args.dry_run:
        print('\n[dry-run] 未写目标库。')
        return

    with TARGET_ENGINE.begin() as c:
        c.execute(text(DDL_TARGET))
        c.execute(text(DDL_TARGET_CMT))
    ensure_article_columns(TARGET_ENGINE)
    n1 = upsert(TARGET_ENGINE, TARGET_TABLE, ART_COLS, all_arts)
    print('\n写入 %s：%d 行' % (TARGET_TABLE, n1))
    if args.with_comments:
        n2 = upsert(TARGET_ENGINE, TARGET_CMT_TABLE, CMT_COLS, all_cmts)
        print('写入 %s：%d 行' % (TARGET_CMT_TABLE, n2))


KW_MAP = {}

if __name__ == '__main__':
    main(sys.argv[1:])

