# -*- coding: utf-8 -*-
"""
长江 / 黄河流域热点事件专项爬虫（独立文件）
=============================================================================
本文件由 auto_weibo_to_db_NEW.py 拆分而来，两者相互独立：
  - auto_weibo_to_db_NEW.py  : 保持原样，只跑热搜榜爬虫，行为一字未改
  - river_basin_spider.py    : 本文件，按「流域省份 x 议题词」定向采集

与热搜爬虫的差异：
  关键词来源   热搜榜 Top35             -> 流域省份 x 议题词 组合
  地域口径     无（只记作者 IP）         -> 内容口径（显式指定省份）+ 作者 IP
  落库表       t_article / t_comment    -> t_basin_article / t_basin_comment（独立新表）
  省份提取     mask_region（已修复）      -> 直接复用 mask_region，规则不漂移

用法：
  python river_basin_spider.py --dry-run                             # 预览关键词矩阵，不联网不写库
  python river_basin_spider.py --provinces-per-basin 1 --pages 1      # 小规模试跑（8 个词）
  python river_basin_spider.py                                       # 正式全量（80 个词）
  python river_basin_spider.py --basin 黄河 --topic 医患矛盾           # 只跑指定流域 / 议题

注意：非 --dry-run 时会执行 basin_ensure_tables()，新建两张独立表，
      不会读写 t_article / t_comment。
=============================================================================
"""
import argparse
import json
import logging
import os
import random
import re
import sys
import time
import urllib.parse
from datetime import datetime

import pandas as pd
from sqlalchemy import text

# 复用热搜爬虫的工具函数与数据库引擎。import 只会执行它的模块级定义，
# 不会触发 main_job()（该调用被 __main__ 保护）。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auto_weibo_to_db_NEW import (          # noqa: E402
    clean_text,
    engine,
    format_article_time,
    format_comment_time,
    hash_id,
    mask_nickname,
    mask_pii_text,
    mask_region,
    safe_int,
    take_over_real_edge,
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# =============================================================================
# 【新增模块】长江 / 黄河流域热点事件专项爬虫
# -----------------------------------------------------------------------------
# 本段为纯新增内容，不修改上方任何既有逻辑。原有 main_job() 行为完全不变。
#
# 与上方热搜爬虫的差异：
#   关键词来源  热搜榜 Top35            -> 流域省份 × 议题词 组合
#   地域口径    无（只记作者 IP）        -> 内容口径（显式指定省份）+ 作者 IP
#   省份提取    复用 mask_region        -> basin_extract_province（同一实现）
#               （mask_region 已于 2026-09-21 修好，"发布于 广东" 不再被截成 "发布于"）
#   落库表      t_article / t_comment   -> t_basin_article / t_basin_comment（独立）
#
# 用法：
#   python auto_weibo_to_db_NEW.py                # 原有：热搜爬虫（另一个文件）
#   python river_basin_spider.py --dry-run         # 只预览关键词矩阵，不联网不写库
#   python river_basin_spider.py                   # 正式抓取
#   python river_basin_spider.py --basin 黄河 --topic 医患矛盾
# =============================================================================

BASIN_CONFIG = {
    'basins': ['黄河', '长江'],       # 抓哪些流域
    'provinces_per_basin': None,      # 每流域取几个省，None = 全部
    # 2026-10-12：本作品默认聚焦「生态治理 + 文旅 + 医患矛盾」三个议题。
    # 社会治理继续保留为兜底议题，不进入默认采集和专题展开。
    'topics': ['生态治理', '文旅', '医患矛盾'],
    # 2026-09-25：每议题用满 9 个词（消极/中性/积极各 3），改前为 1（只跑第一个词，
    # 导致文旅语料 100% 负面）。轮转顺序保证取前 N 个时三类情感都覆盖。
    'keywords_per_topic': 9,
    'pages_per_keyword': 3,           # 提量：每关键词 2 -> 3 页
    'fetch_comments': True,
    # ⚠️ comment_limit 是「全部文章里按评论数取前 N 条」的**全局上限**，
    # 不是每关键词 N 条（见 basin_crawl_comments 的 sorted(...)[:limit]）。
    'comment_limit': 50,              # 提量：8 -> 50 条微博抓评论
    'comment_pages': 5,               # 提量：每条微博评论翻 3 -> 5 页
    'sleep_min': 3.0,
    'sleep_max': 8.0,
    'dry_run': False,
}

_BASIN_DIR = os.path.dirname(os.path.abspath(__file__))

# 省份简称，与 ECharts china 地图区域名一致。
# 注意：这里每省只登记一条流域，专供「关键词矩阵」使用（避免同一个省的关键词
# 在两条流域里各生成一遍）。共同源头省的归属见下面的 BASIN_SHARED_PROVINCES。
BASIN_PROVINCES = {
    '黄河': ['山东', '河南', '山西', '陕西', '内蒙古', '宁夏', '甘肃', '青海'],
    '长江': ['四川', '重庆', '湖北', '湖南', '江西', '安徽', '江苏',
             '浙江', '上海', '云南', '贵州', '西藏'],
}

# 共同源头省：地理上同属长江、黄河两条流域。
# 仅用于 basin_classify_basin 打「黄河长江」标签，不影响关键词矩阵。
BASIN_SHARED_PROVINCES = {
    '青海': ['黄河', '长江'],   # 黄河发源于青海，长江源头（沱沱河）亦在青海唐古拉山
    '四川': ['长江', '黄河'],   # 长江上游主干，黄河在川西北若尔盖过境
}

# =============================================================================
# 议题词库
# -----------------------------------------------------------------------------
# 2026-10-12 改版：聚焦议题（生态治理 / 文旅 / 医患矛盾）改为「按情感三分类」组织，每议题
# 6~10 个词，三类齐备；并由此**推导**出扁平词表 TOPIC_KEYWORDS，保持
# `TOPIC_KEYWORDS[topic][:n]` 的旧调用方式不变。
#
# 为什么必须三分类齐备：
#   旧词表用 `[:1]` 只取第一个词，导致「文旅」实际只用「景区宰客」召回 ——
#   语料 100% 是负面投诉，正向文旅内容一条都进不来。改成三分类 + 轮转展开后，
#   取前 N 个词时能自动覆盖 消极/中性/积极，不再单边偏斜。
#
# 轮转顺序：消极 → 中性 → 积极 → 消极 → … 因此
#   keywords_per_topic=3 → 每议题恰好各取 1 个消极 / 1 个中性 / 1 个积极。
# =============================================================================

# 聚焦议题：本作品默认聚焦「生态治理 + 文旅 + 医患矛盾」三个主题
FOCUS_TOPIC_WORDS = {
    '生态治理': {
        '消极': ['排污', '水污染', '非法采砂'],
        '中性': ['环保督察', '河长制', '环境监测'],
        '积极': ['生态修复', '绿色发展', '生态补偿'],
    },
    '文旅': {
        '消极': ['景区宰客', '旅游乱象', '导游强迫购物'],
        '中性': ['文旅', '旅游景区', '文旅局'],
        '积极': ['文旅融合', '乡村旅游', '非遗'],
    },
    '医患矛盾': {
        '消极': ['医闹', '伤医', '医疗事故'],
        '中性': ['医患纠纷', '医疗纠纷', '看病难'],
        '积极': ['医患互信', '医疗改革', '医德医风'],
    },
}

# 非聚焦议题：社会治理保留为兜底词表，仅用于历史口径或 `--topic` 临时复跑。
LEGACY_TOPIC_WORDS = {
    '社会治理': ['食品安全', '物业纠纷', '校园安全', '教育乱收费', '城管执法', '交通治理'],
}


def _flatten_by_roundrobin(topic_words):
    """按 消极→中性→积极 轮转展开成扁平列表，保证前 N 个词三类均衡。"""
    order = [k for k in ('消极', '中性', '积极') if k in topic_words]
    if not order:
        return []
    buckets = {k: list(topic_words[k]) for k in order}
    out, i = [], 0
    while any(buckets[k] for k in order):
        k = order[i % len(order)]
        if buckets[k]:
            out.append(buckets[k].pop(0))
        i += 1
    return out


TOPIC_KEYWORDS = {}
for _t, _w in FOCUS_TOPIC_WORDS.items():
    TOPIC_KEYWORDS[_t] = _flatten_by_roundrobin(_w)
for _t, _w in LEGACY_TOPIC_WORDS.items():
    TOPIC_KEYWORDS[_t] = list(_w)

_PROV_TO_BASIN = {}
for _b, _provs in BASIN_PROVINCES.items():
    for _p in _provs:
        _PROV_TO_BASIN.setdefault(_p, []).append(_b)

# 并入共同源头省。合并后青海、四川各有 2 条流域记录，
# basin_classify_basin 里的 `len(hits) >= 2 -> '黄河长江'` 分支由此可达。
for _p, _b_list in BASIN_SHARED_PROVINCES.items():
    _bucket = _PROV_TO_BASIN.setdefault(_p, [])
    for _b in _b_list:
        if _b not in _bucket:
            _bucket.append(_b)

# 独立 logger，不干扰上方的 auto_spider.log
basin_logger = logging.getLogger('basin_spider')
basin_logger.setLevel(logging.INFO)
if not basin_logger.handlers:
    _basin_handler = logging.FileHandler(os.path.join(_BASIN_DIR, 'basin_spider.log'), encoding='utf-8')
    _basin_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    basin_logger.addHandler(_basin_handler)


def basin_extract_province(region_name):
    """
    省份提取（流域爬虫专用）。

    mask_region 已于 2026-09-21 一并修好，两者逻辑现在完全一致 ——
    这里直接复用，避免同一套规则在两处漂移。
    """
    return mask_region(region_name)


def basin_classify_basin(province):
    """省份 -> 流域标签。青海/四川同属两条流域时返回 '黄河长江'。"""
    if not province or province == '未知':
        return '未知'
    hits = _PROV_TO_BASIN.get(province, [])
    if len(hits) >= 2:
        return '黄河长江'
    if hits:
        return hits[0]
    return '非流域'


def basin_build_keywords(basins=None, topics=None,
                         provinces_per_basin=None, keywords_per_topic=None):
    """
    构造「省份 × 议题词」关键词矩阵。
    微博搜索接口对空格分隔的多词按 AND 处理，所以 `山东 医患纠纷`
    得到的是同时含这两个词的内容，即「山东的医患矛盾类内容」。
    """
    cfg = BASIN_CONFIG
    basins = basins or cfg['basins']
    topics = topics or cfg['topics'] or list(TOPIC_KEYWORDS.keys())
    if provinces_per_basin is None:
        provinces_per_basin = cfg['provinces_per_basin']
    keywords_per_topic = keywords_per_topic or cfg['keywords_per_topic']

    items, seen = [], set()
    for basin in basins:
        provs = BASIN_PROVINCES.get(basin, [])
        if provinces_per_basin:
            provs = provs[:int(provinces_per_basin)]
        for prov in provs:
            for topic in topics:
                words = TOPIC_KEYWORDS.get(topic, [])[:int(keywords_per_topic)]
                for w in words:
                    kw = '%s %s' % (prov, w)
                    if kw in seen:
                        continue
                    seen.add(kw)
                    items.append({
                        'keyword': kw, 'basin': basin,
                        'province': prov, 'topic': topic, 'topic_word': w,
                    })
    return items


DDL_BASIN_ARTICLE = """
CREATE TABLE IF NOT EXISTS `t_basin_article` (
  `微博ID`     BIGINT       NOT NULL,
  `微博内容`   TEXT,
  `转发数`     BIGINT       DEFAULT 0,
  `评论数`     BIGINT       DEFAULT 0,
  `点赞数`     BIGINT       DEFAULT 0,
  `发布地区`   TEXT,
  `发布时间`   TEXT,
  `分类`       TEXT,
  `微博链接`   TEXT,
  `作者ID`     TEXT,
  `作者昵称`   TEXT,
  `作者主页`   TEXT,
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `目标省份`   VARCHAR(16),
  `采集时间`   DATETIME,
  PRIMARY KEY (`微博ID`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`),
  KEY `idx_pubtime` (`发布时间`(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DDL_BASIN_COMMENT = """
CREATE TABLE IF NOT EXISTS `t_basin_comment` (
  `评论ID`     BIGINT       NOT NULL,
  `评论内容`   TEXT,
  `评论时间`   TEXT,
  `来源`       TEXT,
  `点赞数`     BIGINT       DEFAULT 0,
  `微博ID`     BIGINT,
  `用户ID`     TEXT,
  `昵称`       TEXT,
  `性别`       TEXT,
  `用户主页`   TEXT,
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `采集时间`   DATETIME,
  PRIMARY KEY (`评论ID`),
  KEY `idx_basin` (`流域`),
  KEY `idx_weibo` (`微博ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

BASIN_ART_COLS = ['微博ID', '微博内容', '转发数', '评论数', '点赞数', '发布地区', '发布时间',
                  '分类', '微博链接', '作者ID', '作者昵称', '作者主页',
                  '流域', '议题', '命中关键词', '目标省份', '采集时间']
BASIN_COM_COLS = ['评论ID', '评论内容', '评论时间', '来源', '点赞数', '微博ID', '用户ID',
                  '昵称', '性别', '用户主页', '流域', '议题', '命中关键词', '采集时间']


def basin_ensure_tables():
    with engine.connect() as conn:
        conn.execute(text(DDL_BASIN_ARTICLE))
        conn.execute(text(DDL_BASIN_COMMENT))
        conn.commit()
    basin_logger.info('流域数据表已就绪')
    print(' 流域数据表已就绪：t_basin_article / t_basin_comment')


def basin_crawl_articles(page, kw_items, pages_per_keyword):
    """对每个关键词调用 m.weibo.cn 的 searchall 接口翻页（接口形态与 main_job 一致）。"""
    collected = {}   # 微博ID -> record，天然去重
    total = len(kw_items)

    for idx, item in enumerate(kw_items, 1):
        keyword = item['keyword']
        basin, topic, province = item['basin'], item['topic'], item['province']
        print('\n [%d/%d] 关键词：【%s】  [%s · %s]' % (idx, total, keyword, basin, topic))
        basin_logger.info('[%d/%d] 抓取关键词 %s (%s/%s)' % (idx, total, keyword, basin, topic))

        time.sleep(random.uniform(BASIN_CONFIG['sleep_min'], BASIN_CONFIG['sleep_max']))

        for p in range(1, pages_per_keyword + 1):
            containerid = '100103type=1&q=%s' % keyword
            api_url = ('https://m.weibo.cn/api/container/getIndex'
                       '?containerid=%s&page_type=searchall&page=%d'
                       % (urllib.parse.quote(containerid), p))
            try:
                page.get(api_url)
                time.sleep(2)

                body = page.run_js('return document.body.innerText')
                if '滑动' in body or '验证' in body or '为了你的账号安全' in body:
                    print('  检测到滑动验证码，请在浏览器完成验证后按回车继续...')
                    input()
                    page.get(api_url)
                    time.sleep(3)

                data = json.loads(page.run_js('return document.body.innerText'))
                if data.get('ok') != 1:
                    print('   第%d页无数据(ok=%s)，跳过' % (p, data.get('ok')))
                    break

                page_count = 0
                for card in data.get('data', {}).get('cards', []):
                    mblogs = ([card.get('mblog')] if card.get('card_type') == 9 else
                              [sub.get('mblog') for sub in card.get('card_group', [])
                               if sub.get('card_type') == 9])
                    for mblog in mblogs:
                        if not mblog:
                            continue
                        wid = str(mblog.get('id', ''))
                        if not wid:
                            continue

                        # 同一微博被多个关键词命中时累积关键词，而不是覆盖
                        if wid in collected:
                            old = collected[wid]['命中关键词']
                            if keyword not in old.split('|'):
                                collected[wid]['命中关键词'] = old + '|' + keyword
                            continue

                        user = mblog.get('user', {}) or {}
                        collected[wid] = {
                            '微博ID': wid,
                            '微博内容': mask_pii_text(
                                re.sub(r'<[^>]+>', '', mblog.get('text', '')).strip().replace('\n', ' ')),
                            '转发数': str(mblog.get('reposts_count', 0)),
                            '评论数': str(mblog.get('comments_count', 0)),
                            '点赞数': str(mblog.get('attitudes_count', 0)),
                            '发布地区': basin_extract_province(mblog.get('region_name', '未知')),
                            '发布时间': format_article_time(mblog.get('created_at', '')),
                            '分类': mblog.get('source', '未知'),
                            '微博链接': 'https://weibo.com/status/%s' % wid,
                            '作者ID': hash_id(user.get('id', '')),
                            '作者昵称': mask_nickname(user.get('screen_name', '未知')),
                            '作者主页': '已脱敏',
                            '流域': basin,
                            '议题': topic,
                            '命中关键词': keyword,
                            '目标省份': province,
                            '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        }
                        page_count += 1
                print('   第%d页获取 %d 条（累计去重后 %d）' % (p, page_count, len(collected)))
            except Exception as e:
                basin_logger.error('关键词【%s】第%d页解析失败：%s' % (keyword, p, e))
                print('   第%d页解析失败：%s' % (p, e))

    return list(collected.values())


def basin_crawl_comments(page, articles, limit, comment_pages):
    """按评论数取前 limit 条微博抓评论（buildComments 监听 + fetch，与 main_job 一致）。"""
    arts = sorted(articles, key=lambda x: safe_int(x['评论数']), reverse=True)[:limit]
    print('\n 已按评论数选出 %d 条微博抓取评论：' % len(arts))
    print('-' * 64)
    for i, a in enumerate(arts, 1):
        preview = a['微博内容'][:28].replace('\n', ' ')
        print('  %2d. [评论数:%-6s] %s  [%s·%s]' % (i, a['评论数'], preview, a['流域'], a['议题']))
    print('-' * 64)

    meta = {a['微博ID']: (a['流域'], a['议题'], a['命中关键词']) for a in arts}
    all_comments, seen = [], set()

    for a in arts:
        weibo_id = a['微博ID']
        basin, topic, keyword = meta[weibo_id]
        detail_url = 'https://weibo.com/detail/%s' % weibo_id
        max_id = 0

        for p in range(1, comment_pages + 1):
            print('  抓取微博 %s 第 %d 页评论...' % (weibo_id, p))
            try:
                if p == 1:
                    page.listen.start('buildComments')
                    page.get(detail_url)
                    packet = page.listen.wait(timeout=15)
                    page.listen.stop()
                    data = packet.response.body if packet else None
                    if isinstance(data, str):
                        data = json.loads(data)
                else:
                    api_url = ('https://weibo.com/ajax/statuses/buildComments'
                               '?id=%s&count=20&max_id=%s' % (weibo_id, max_id))
                    js = """
                    return fetch('%s', {
                        method: 'GET',
                        credentials: 'include',
                        headers: {
                            'Accept': 'application/json, text/plain, */*',
                            'X-Requested-With': 'XMLHttpRequest',
                            'Referer': 'https://weibo.com/detail/%s',
                            'User-Agent': navigator.userAgent
                        }
                    }).then(r => r.text()).catch(e => '');
                    """ % (api_url, weibo_id)
                    raw = page.run_js(js)
                    if not raw or not raw.strip().startswith('{'):
                        print('    第%d页被拦截，停止该微博翻页' % p)
                        basin_logger.warning('评论第%d页被拦截：%s' % (p, weibo_id))
                        break
                    data = json.loads(raw)

                if not data or not data.get('data'):
                    break
                max_id = data.get('max_id') or data.get('max_id_str') or 0

                for c in data['data']:
                    cid = str(c.get('id', ''))
                    if not cid or cid in seen:
                        continue
                    seen.add(cid)
                    ui = c.get('user', {}) or {}
                    all_comments.append({
                        '评论ID': cid,
                        '评论内容': mask_pii_text(c.get('text_raw', '').replace('\n', ' ').strip()),
                        '评论时间': format_comment_time(c.get('created_at', '')),
                        '来源': c.get('source', ''),
                        '点赞数': str(c.get('like_counts', 0)),
                        '微博ID': weibo_id,
                        '用户ID': hash_id(ui.get('id', '')),
                        '昵称': mask_nickname(ui.get('screen_name', '')),
                        '性别': ui.get('gender', ''),
                        '用户主页': '已脱敏',
                        '流域': basin,
                        '议题': topic,
                        '命中关键词': keyword,
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })

                if max_id == 0:
                    break
                time.sleep(random.uniform(1.5, 3.0))
            except Exception as e:
                print('  评论爬取异常(微博:%s 第%d页)：%s' % (weibo_id, p, e))
                basin_logger.error('评论爬取异常(微博:%s 第%d页)：%s' % (weibo_id, p, e))
                break

    return all_comments


def basin_save_to_db(articles, comments):
    """入库：临时表 + INSERT ... ON DUPLICATE KEY UPDATE（沿用上方 save_to_db 的模式）。"""
    art_n, com_n = 0, 0
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if articles:
        try:
            df = pd.DataFrame(articles)[BASIN_ART_COLS].copy()
            df['微博ID'] = df['微博ID'].astype(str)
            for c in ('转发数', '评论数', '点赞数'):
                df[c] = df[c].map(safe_int)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(clean_text)

            csv_path = os.path.join(_BASIN_DIR, 'basin_articles_%s.csv' % stamp)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            df.to_csv(os.path.join(_BASIN_DIR, 'basin_article_data.csv'),
                      index=False, encoding='utf-8-sig')
            print(' 文章 CSV：%s' % csv_path)

            with engine.connect() as conn:
                df.to_sql('t_basin_article_temp', con=conn, if_exists='replace',
                          index=False, chunksize=1000)
                cols = ', '.join('`%s`' % c for c in BASIN_ART_COLS)
                conn.execute(text(
                    'INSERT INTO `t_basin_article` (%s) SELECT %s FROM `t_basin_article_temp` '
                    'ON DUPLICATE KEY UPDATE '
                    '`转发数`=VALUES(`转发数`), `评论数`=VALUES(`评论数`), '
                    '`点赞数`=VALUES(`点赞数`), `流域`=VALUES(`流域`), '
                    '`议题`=VALUES(`议题`), `命中关键词`=VALUES(`命中关键词`)' % (cols, cols)))
                conn.commit()
                conn.execute(text('DROP TABLE IF EXISTS `t_basin_article_temp`'))
            art_n = len(df)
            print(' 文章入库完成：%d 条' % art_n)
        except Exception as e:
            basin_logger.error('文章入库失败：%s' % e)
            print(' 文章入库失败：%s' % e)

    if comments:
        try:
            df = pd.DataFrame(comments)[BASIN_COM_COLS].copy()
            for c in ('评论ID', '微博ID'):
                df[c] = df[c].astype(str)
            df['点赞数'] = df['点赞数'].map(safe_int)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(clean_text)

            csv_path = os.path.join(_BASIN_DIR, 'basin_comments_%s.csv' % stamp)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            df.to_csv(os.path.join(_BASIN_DIR, 'basin_comment_data.csv'),
                      index=False, encoding='utf-8-sig')
            print(' 评论 CSV：%s' % csv_path)

            with engine.connect() as conn:
                df.to_sql('t_basin_comment_temp', con=conn, if_exists='replace',
                          index=False, chunksize=1000)
                cols = ', '.join('`%s`' % c for c in BASIN_COM_COLS)
                conn.execute(text(
                    'INSERT INTO `t_basin_comment` (%s) SELECT %s FROM `t_basin_comment_temp` '
                    'ON DUPLICATE KEY UPDATE `点赞数`=VALUES(`点赞数`)' % (cols, cols)))
                conn.commit()
                conn.execute(text('DROP TABLE IF EXISTS `t_basin_comment_temp`'))
            com_n = len(df)
            print(' 评论入库完成：%d 条' % com_n)
        except Exception as e:
            basin_logger.error('评论入库失败：%s' % e)
            print(' 评论入库失败：%s' % e)

    print('\n 持久化完成：文章 %d 条，评论 %d 条' % (art_n, com_n))


def basin_preview_keywords(kw_items):
    """打印 + 落盘关键词矩阵，便于人工审阅。"""
    print('\n' + '=' * 72)
    print('将要抓取的关键词矩阵（共 %d 个）' % len(kw_items))
    print('=' * 72)

    grouped = {}
    for it in kw_items:
        grouped.setdefault((it['basin'], it['topic']), []).append(it['keyword'])
    for (basin, topic), kws in grouped.items():
        print('\n【%s · %s】%d 个' % (basin, topic, len(kws)))
        for i in range(0, len(kws), 4):
            print('   ' + '   '.join('%-16s' % k for k in kws[i:i + 4]))

    out = os.path.join(_BASIN_DIR, 'basin_keywords_preview.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('流域热点事件爬虫 —— 关键词矩阵（%s）\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        f.write('共 %d 个关键词\n\n' % len(kw_items))
        for it in kw_items:
            f.write('%-20s 流域=%-4s 议题=%-8s 省份=%s\n'
                    % (it['keyword'], it['basin'], it['topic'], it['province']))
    print('\n关键词清单已写入：%s' % out)


def basin_job(argv=None):
    """流域热点事件爬虫主流程。argv 为 None 时取 sys.argv[1:]。"""
    ap = argparse.ArgumentParser(prog='auto_weibo_to_db_NEW.py basin',
                                 description='长江/黄河流域热点事件专项爬虫')
    ap.add_argument('--dry-run', action='store_true', help='只生成关键词矩阵，不联网不写库')
    ap.add_argument('--basin', action='append', choices=['黄河', '长江'], help='只抓指定流域，可重复')
    ap.add_argument('--topic', action='append', choices=list(TOPIC_KEYWORDS.keys()),
                    help='只抓指定议题，可重复')
    ap.add_argument('--pages', type=int, help='每个关键词抓几页文章')
    ap.add_argument('--no-comments', action='store_true', help='跳过评论抓取')
    ap.add_argument('--provinces-per-basin', type=int, help='每个流域取前 N 个省')
    args = ap.parse_args(argv)

    basins = args.basin or BASIN_CONFIG['basins']
    topics = args.topic or BASIN_CONFIG['topics']
    pages = args.pages if args.pages else BASIN_CONFIG['pages_per_keyword']
    fetch_comments = BASIN_CONFIG['fetch_comments'] and not args.no_comments
    ppb = args.provinces_per_basin if args.provinces_per_basin else BASIN_CONFIG['provinces_per_basin']

    kw_items = basin_build_keywords(basins=basins, topics=topics, provinces_per_basin=ppb)
    if not kw_items:
        print(' 关键词为空，请检查 --basin / --topic 参数。')
        return

    basin_preview_keywords(kw_items)

    if args.dry_run or BASIN_CONFIG['dry_run']:
        print('\n[dry-run] 仅预览，未发起任何请求、未写数据库。')
        return

    print('\n' + '=' * 72)
    print('即将开始抓取')
    print('  关键词 %d 个 × 每词 %d 页 = 约 %d 次搜索请求' % (len(kw_items), pages, len(kw_items) * pages))
    print('  评论：%s' % ('开启（前 %d 条微博 × %d 页）' % (BASIN_CONFIG['comment_limit'],
                                                          BASIN_CONFIG['comment_pages'])
                        if fetch_comments else '关闭'))
    print('=' * 72)

    basin_ensure_tables()

    page = take_over_real_edge()
    if not page:
        print(' 浏览器接管失败，请确认 Edge 已登录微博后重试。')
        return

    page.get('https://m.weibo.cn')
    time.sleep(2)

    t0 = time.time()
    articles = basin_crawl_articles(page, kw_items, pages)
    print('\n 文章抓取完毕，共 %d 条（已去重）' % len(articles))
    basin_logger.info('文章抓取完毕，共 %d 条' % len(articles))

    comments = []
    if fetch_comments and articles:
        comments = basin_crawl_comments(page, articles, BASIN_CONFIG['comment_limit'],
                                        BASIN_CONFIG['comment_pages'])
        print(' 评论抓取完毕，共 %d 条' % len(comments))
        basin_logger.info('评论抓取完毕，共 %d 条' % len(comments))

    basin_save_to_db(articles, comments)

    if articles:
        print('\n 分布小结（文章）：')
        stat = {}
        for a in articles:
            key = (a['流域'], a['议题'])
            stat[key] = stat.get(key, 0) + 1
        for (b, t), n in sorted(stat.items(), key=lambda x: -x[1]):
            print('   %-10s %-10s %5d' % (b, t, n))

    print('\n 全部任务完成，耗时 %.1f 分钟' % ((time.time() - t0) / 60))

if __name__ == "__main__":
    basin_job(sys.argv[1:])
