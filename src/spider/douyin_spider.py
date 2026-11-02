# -*- coding: utf-8 -*-
"""
抖音短视频 / 评论 定向采集（长江·黄河流域 · 生态治理 + 文旅 + 医患矛盾）
=============================================================================
与 river_basin_spider.py（微博侧）并列，是新作品的**第二个数据源**。两者共用同一套口径：

  流域省份   BASIN_PROVINCES / BASIN_SHARED_PROVINCES   （来自 river_basin_spider）
  议题词库   TOPIC_KEYWORDS                            （来自 river_basin_spider）
  省份归一   mask_region                               （来自 auto_weibo_to_db_NEW）
  流域判定   basin_classify_basin                      （来自 river_basin_spider）
  脱敏工具   hash_id / mask_nickname / mask_pii_text   （来自 auto_weibo_to_db_NEW）
  数据库     engine                                    （指向 db_weibo_basin）

落库到独立新表 t_douyin_article / t_douyin_comment，不与微博两张表混写；
跨平台聚合时只能比**结构占比**，不可比绝对值（点赞/评论的计费口径不同）。

【为什么不在 Python 里直接 requests 调接口】
抖音 Web 接口带 a_bogus / X-Bogus / verifyFp 等签名，算法随前端版本漂移，
逆向维护成本极高且容易失效。本模块改为**在浏览器上下文内监听页面自身发出的 XHR**：
让页面自己的 JS 去算签名，我们只截响应体（DrissionPage 的 listen 机制）。
对签名算法变更天然免疫 —— 微博侧抓评论（buildComments）已在用同一机制。

【议题范围】
默认只跑「生态治理」「文旅」「医患矛盾」三议题（新作品聚焦主题）；
微博侧老爬虫仍保留 4 议题不动，因为 t_basin_* 里的社会治理/医患矛盾数据已入库，
重抓不会改变历史数据，收窄它的关键词池只会断绝将来补数据的可能。

用法：
  python douyin_spider.py --dry-run                            # 预览关键词矩阵，不联网不写库
  python douyin_spider.py --provinces-per-basin 1 --pages 1     # 小规模试跑（不写库请加 --dry-run）
  python douyin_spider.py                                       # 正式全量
  python douyin_spider.py --topic 生态治理                       # 只跑指定议题
  python douyin_spider.py --basin 黄河 --no-comments
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

_SPIDER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SPIDER_DIR not in sys.path:
    sys.path.insert(0, _SPIDER_DIR)

# 复用微博侧的全部口径与工具，保证两个平台"同词表、同省份表、同流域判定"
from river_basin_spider import (           # noqa: E402
    BASIN_PROVINCES,
    TOPIC_KEYWORDS,
    basin_classify_basin,
    basin_extract_province,
)
from auto_weibo_to_db_NEW import (         # noqa: E402
    clean_text,
    engine,
    hash_id,
    mask_nickname,
    mask_pii_text,
    safe_int,
    take_over_real_edge,
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


PLATFORM = '抖音'

DOUYIN_CONFIG = {
    'basins': ['黄河', '长江'],
    # 新作品聚焦主题：只跑这两个议题
    'topics': ['生态治理', '文旅', '医患矛盾'],
    'provinces_per_basin': None,      # None = 全部省份
    # 2026-09-25：每议题用满 9 个词（消极/中性/积极各 3），改前为 1（只跑第一个词）
    'keywords_per_topic': 9,
    'pages_per_keyword': 4,           # 提量：每个关键词监听 3 -> 4 屏搜索结果
    'search_type': 'video',           # general / video
    'fetch_comments': True,
    'video_limit': 30,                # 提量：按评论数取前 8 -> 30 条视频抓评论（全局上限）
    'comment_scrolls': 6,             # 提量：每条视频下滑 4 -> 6 次评论区
    'sleep_min': 4.0,
    'sleep_max': 9.0,
    'dry_run': False,
}

_dy_logger = logging.getLogger('douyin_spider')
_dy_logger.setLevel(logging.INFO)
if not _dy_logger.handlers:
    _h = logging.FileHandler(os.path.join(_SPIDER_DIR, 'douyin_spider.log'), encoding='utf-8')
    _h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    _dy_logger.addHandler(_h)


# =============================================================================
# 1. 关键词矩阵
# =============================================================================
def douyin_build_keywords(basins=None, topics=None,
                          provinces_per_basin=None, keywords_per_topic=None):
    """构造「省份 × 议题词」矩阵。与微博侧同构，只是落库表与平台不同。

    微博搜索对空格分隔的多词按 AND 处理，抖音搜索框同理，
    所以 `山东 景区宰客` 得到的是同时含这两个要素的内容。
    """
    cfg = DOUYIN_CONFIG
    basins = basins or cfg['basins']
    topics = topics or cfg['topics']
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


# =============================================================================
# 2. 建表（独立新表，不动 t_basin_*）
# =============================================================================
DDL_DY_ARTICLE = """
CREATE TABLE IF NOT EXISTS `t_douyin_article` (
  `视频ID`     VARCHAR(64)  NOT NULL,
  `视频标题`   TEXT,
  `视频描述`   TEXT,
  `话题标签`   TEXT,
  `点赞数`     BIGINT       DEFAULT 0,
  `评论数`     BIGINT       DEFAULT 0,
  `收藏数`     BIGINT       DEFAULT 0,
  `分享数`     BIGINT       DEFAULT 0,
  `时长秒`     FLOAT        COMMENT '视频时长（秒），来自 aweme.video.duration(ms)；无则 NULL',
  `分辨率`     VARCHAR(16)  COMMENT '如 1080x1920',
  `播放地址`   TEXT         COMMENT 'aweme.video.play_addr（带签名、有时效，现取现用）',
  `封面`       TEXT         COMMENT 'aweme.video.cover 首图地址',
  `发布地区`   VARCHAR(32),
  `发布时间`   TEXT,
  `作者ID`     VARCHAR(64),
  `作者昵称`   TEXT,
  `作者主页`   VARCHAR(128),
  `视频链接`   TEXT,
  `平台`       VARCHAR(8)   DEFAULT '抖音',
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `目标省份`   VARCHAR(16),
  `采集时间`   DATETIME,
  PRIMARY KEY (`视频ID`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`),
  KEY `idx_platform` (`平台`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DDL_DY_COMMENT = """
CREATE TABLE IF NOT EXISTS `t_douyin_comment` (
  `评论ID`     VARCHAR(64)  NOT NULL,
  `评论内容`   TEXT,
  `评论时间`   TEXT,
  `点赞数`     BIGINT       DEFAULT 0,
  `回复数`     BIGINT       DEFAULT 0,
  `视频ID`     VARCHAR(64),
  `用户ID`     VARCHAR(64),
  `昵称`       TEXT,
  `性别`       VARCHAR(8),
  `用户地区`   VARCHAR(32),
  `用户主页`   VARCHAR(128),
  `平台`       VARCHAR(8)   DEFAULT '抖音',
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `采集时间`   DATETIME,
  PRIMARY KEY (`评论ID`),
  KEY `idx_video` (`视频ID`),
  KEY `idx_basin` (`流域`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DY_ART_COLS = ['视频ID', '视频标题', '视频描述', '话题标签', '点赞数', '评论数', '收藏数',
               '分享数', '时长秒', '分辨率', '播放地址', '封面',
               '发布地区', '发布时间', '作者ID', '作者昵称', '作者主页', '视频链接',
               '平台', '流域', '议题', '命中关键词', '目标省份', '采集时间']

# 存量表补列（CREATE TABLE IF NOT EXISTS 对已存在的表不生效，需 ALTER 补齐）——方案 §四 E3
DY_ART_EXTRA_COLS = [
    ('时长秒', "FLOAT COMMENT '视频时长（秒）'"),
    ('分辨率', "VARCHAR(16) COMMENT '如 1080x1920'"),
    ('播放地址', "TEXT COMMENT 'aweme.video.play_addr（带签名、有时效）'"),
    ('封面', "TEXT COMMENT 'aweme.video.cover 首图地址'"),
]
DY_COM_COLS = ['评论ID', '评论内容', '评论时间', '点赞数', '回复数', '视频ID', '用户ID',
               '昵称', '性别', '用户地区', '用户主页', '平台', '流域', '议题',
               '命中关键词', '采集时间']


def douyin_ensure_tables():
    with engine.connect() as conn:
        conn.execute(text(DDL_DY_ARTICLE))
        conn.execute(text(DDL_DY_COMMENT))
        # 存量表补列：CREATE TABLE IF NOT EXISTS 对已存在的表不生效，逐列检查后 ALTER
        existing = {r[0] for r in conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_douyin_article'"))}
        for col, ddl in DY_ART_EXTRA_COLS:
            if col not in existing:
                conn.execute(text('ALTER TABLE `t_douyin_article` ADD COLUMN `%s` %s' % (col, ddl)))
                print('   t_douyin_article 补列：%s' % col)
        conn.commit()
    _dy_logger.info('抖音数据表已就绪')
    print(' 抖音数据表已就绪：t_douyin_article / t_douyin_comment')


# =============================================================================
# 3. 字段归一
# =============================================================================
def format_ts(ts):
    """抖音 create_time 是秒级/毫秒级 unix 时间戳 -> 'YYYY-MM-DD HH:MM:SS'。"""
    try:
        n = int(ts)
    except (TypeError, ValueError):
        return ''
    if n > 10 ** 11:      # 毫秒
        n //= 1000
    if n <= 0:
        return ''
    try:
        return datetime.fromtimestamp(n).strftime('%Y-%m-%d %H:%M:%S')
    except (OverflowError, OSError, ValueError):
        return ''


_GENDER_MAP = {1: '男', 2: '女'}


def norm_gender(g):
    """抖音 user.gender：0 未知 / 1 男 / 2 女。"""
    try:
        return _GENDER_MAP.get(int(g), '未知')
    except (TypeError, ValueError):
        return '未知'


def _region_of(aweme):
    """视频发布地区：poi.city -> city -> ip_label -> 未知（再经 mask_region 归一为省）。"""
    for key in ('poi',):
        node = aweme.get(key)
        if isinstance(node, dict):
            for sub in ('city', 'province', 'name'):
                if node.get(sub):
                    return basin_extract_province(node[sub])
    for key in ('city', 'ip_label', 'location'):
        v = aweme.get(key)
        if isinstance(v, str) and v.strip():
            return basin_extract_province(v)
    return '未知'


def _hashtags_of(aweme):
    tags = []
    for t in (aweme.get('text_extra') or []):
        if isinstance(t, dict) and t.get('hashtag_name'):
            tags.append(t['hashtag_name'])
    return '|'.join(tags)


def _video_meta_of(aweme):
    """从 aweme.video 取 (时长秒, 分辨率, 播放地址, 封面)（方案 §四 E3）。

    XHR 里 aweme.video 结构大致为：
        video.duration          # 毫秒
        video.width / height    # 或 video.play_addr.width / height
        video.play_addr.url_list[0]
        video.bit_rate[0].play_addr.url_list[0]   # 多档位（低码档可省流量）
        video.cover.url_list[0]
    字段名随平台改版可能变动，故做多路径兜底；取不到即 None/''（不报错、不编造）。
    """
    v = aweme.get('video') or {}
    # 时长（毫秒 → 秒）
    dur = v.get('duration')
    dur_s = round(dur / 1000.0, 3) if isinstance(dur, (int, float)) and dur else None
    # 分辨率
    w, h = v.get('width'), v.get('height')
    pa = v.get('play_addr') or {}
    if not (w and h):
        w = pa.get('width') or w
        h = pa.get('height') or h
    res = ('%dx%d' % (w, h)) if (w and h) else None
    # 播放地址：优先 play_addr，其次首个 bit_rate 档
    play = ''
    urls = pa.get('url_list') or []
    if urls:
        play = urls[0]
    if not play:
        br = v.get('bit_rate') or []
        if br and isinstance(br[0], dict):
            u2 = (br[0].get('play_addr') or {}).get('url_list') or []
            if u2:
                play = u2[0]
    # 封面
    cover = ''
    cu = (v.get('cover') or {}).get('url_list') or []
    if cu:
        cover = cu[0]
    return dur_s, res, play, cover


def _packet_body(packet):
    """把 listen 抓到的响应体统一成 dict（可能是 dict / str / bytes）。"""
    if packet is None:
        return None
    try:
        body = packet.response.body
    except Exception:
        return None
    if isinstance(body, dict):
        return body
    if isinstance(body, (bytes, bytearray)):
        body = body.decode('utf-8', 'ignore')
    if isinstance(body, str):
        body = body.strip()
        if not body.startswith('{'):
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return None


# =============================================================================
# 4. 采集：搜索结果里的视频
# =============================================================================
def douyin_crawl_videos(page, kw_items, screens_per_keyword):
    """逐关键词打开抖音搜索页，边下滑边监听 general/search 响应，累积去重。"""
    collected = {}
    total = len(kw_items)
    search_type = DOUYIN_CONFIG['search_type']

    for idx, item in enumerate(kw_items, 1):
        keyword = item['keyword']
        basin, topic, province = item['basin'], item['topic'], item['province']
        print('\n [%d/%d] 关键词：【%s】  [%s · %s]' % (idx, total, keyword, basin, topic))
        _dy_logger.info('[%d/%d] 抖音搜索 %s (%s/%s)' % (idx, total, keyword, basin, topic))

        time.sleep(random.uniform(DOUYIN_CONFIG['sleep_min'], DOUYIN_CONFIG['sleep_max']))

        url = 'https://www.douyin.com/search/%s?type=%s' % (
            urllib.parse.quote(keyword), search_type)
        try:
            page.listen.start('general/search/single')
            page.get(url)
            time.sleep(3)

            for s in range(screens_per_keyword):
                # 触发页面自身发起下一页请求（签名由页面 JS 计算）
                try:
                    page.scroll.to_bottom()
                except Exception:
                    pass
                time.sleep(random.uniform(1.5, 2.8))
                print('   第%d屏…' % (s + 1))

            n_pkt = 0
            while True:
                packet = page.listen.wait(count=1, timeout=2)
                if not packet:
                    break
                data = _packet_body(packet)
                if not data:
                    continue
                n_pkt += 1
                for card in (data.get('data') or []):
                    aweme = card.get('aweme_info') or card.get('aweme_detail')
                    if not aweme:
                        continue
                    vid = str(aweme.get('aweme_id') or '')
                    if not vid:
                        continue
                    if vid in collected:
                        old = collected[vid]['命中关键词']
                        if keyword not in old.split('|'):
                            collected[vid]['命中关键词'] = old + '|' + keyword
                        continue
                    stat = aweme.get('statistics') or {}
                    author = aweme.get('author') or {}
                    desc = (aweme.get('desc') or '').replace('\n', ' ').strip()
                    dur_s, res, play_url, cover_url = _video_meta_of(aweme)
                    collected[vid] = {
                        '视频ID': vid,
                        '视频标题': mask_pii_text(desc[:120]),
                        '视频描述': mask_pii_text(desc),
                        '话题标签': _hashtags_of(aweme),
                        '点赞数': str(stat.get('digg_count', 0)),
                        '评论数': str(stat.get('comment_count', 0)),
                        '收藏数': str(stat.get('collect_count', 0)),
                        '分享数': str(stat.get('share_count', 0)),
                        '时长秒': dur_s,
                        '分辨率': res,
                        '播放地址': play_url,
                        '封面': cover_url,
                        '发布地区': _region_of(aweme),
                        '发布时间': format_ts(aweme.get('create_time')),
                        '作者ID': hash_id(author.get('uid') or author.get('sec_uid') or ''),
                        '作者昵称': mask_nickname(author.get('nickname', '未知')),
                        '作者主页': '已脱敏',
                        '视频链接': 'https://www.douyin.com/video/%s' % vid,
                        '平台': PLATFORM,
                        '流域': basin,
                        '议题': topic,
                        '命中关键词': keyword,
                        '目标省份': province,
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    }
            page.listen.stop()
            print('   本词捕获 %d 个响应包，累计去重后 %d 条' % (n_pkt, len(collected)))
        except Exception as e:
            try:
                page.listen.stop()
            except Exception:
                pass
            _dy_logger.error('关键词【%s】采集失败：%s' % (keyword, e))
            print('   关键词【%s】采集失败：%s' % (keyword, e))

    return list(collected.values())


# =============================================================================
# 5. 采集：视频评论
# =============================================================================
def douyin_crawl_comments(page, videos, limit, scrolls):
    """按评论数取前 limit 条视频，进详情页下滑评论区并监听 comment/list。"""
    picked = sorted(videos, key=lambda x: safe_int(x['评论数']), reverse=True)[:limit]
    print('\n 已按评论数选出 %d 条视频抓取评论：' % len(picked))
    print('-' * 64)
    for i, v in enumerate(picked, 1):
        preview = (v['视频标题'] or v['视频描述'] or '')[:26].replace('\n', ' ')
        print('  %2d. [评论数:%-6s] %s  [%s·%s]' % (i, v['评论数'], preview, v['流域'], v['议题']))
    print('-' * 64)

    meta = {v['视频ID']: (v['流域'], v['议题'], v['命中关键词']) for v in picked}
    all_comments, seen = [], set()

    for v in picked:
        vid = v['视频ID']
        basin, topic, keyword = meta[vid]
        print('  抓取视频 %s 的评论…' % vid)
        try:
            page.listen.start('comment/list')
            page.get('https://www.douyin.com/video/%s' % vid)
            time.sleep(random.uniform(3.0, 5.0))
            for _ in range(scrolls):
                try:
                    page.scroll.to_bottom()
                except Exception:
                    pass
                time.sleep(random.uniform(1.8, 3.2))

            while True:
                packet = page.listen.wait(count=1, timeout=2)
                if not packet:
                    break
                data = _packet_body(packet)
                if not data:
                    continue
                for c in (data.get('comments') or []):
                    cid = str(c.get('cid') or '')
                    if not cid or cid in seen:
                        continue
                    seen.add(cid)
                    ui = c.get('user') or {}
                    all_comments.append({
                        '评论ID': cid,
                        '评论内容': mask_pii_text((c.get('text') or '').replace('\n', ' ').strip()),
                        '评论时间': format_ts(c.get('create_time')),
                        '点赞数': str(c.get('digg_count', 0)),
                        '回复数': str(c.get('reply_comment_total', 0)),
                        '视频ID': vid,
                        '用户ID': hash_id(ui.get('uid') or ui.get('sec_uid') or ''),
                        '昵称': mask_nickname(ui.get('nickname', '')),
                        '性别': norm_gender(ui.get('gender')),
                        '用户地区': basin_extract_province(ui.get('ip_label') or ''),
                        '用户主页': '已脱敏',
                        '平台': PLATFORM,
                        '流域': basin,
                        '议题': topic,
                        '命中关键词': keyword,
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })
            page.listen.stop()
            print('    该视频累计评论 %d 条' % len(all_comments))
        except Exception as e:
            try:
                page.listen.stop()
            except Exception:
                pass
            print('  评论采集异常(视频:%s)：%s' % (vid, e))
            _dy_logger.error('评论采集异常(视频:%s)：%s' % (vid, e))

    return all_comments


# =============================================================================
# 6. 入库（临时表 + UPSERT，模式与微博侧一致）
# =============================================================================
def douyin_save_to_db(articles, comments):
    art_n, com_n = 0, 0
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if articles:
        try:
            df = pd.DataFrame(articles)[DY_ART_COLS].copy()
            for c in ('点赞数', '评论数', '收藏数', '分享数'):
                df[c] = df[c].map(safe_int)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(clean_text)
            csv_path = os.path.join(_SPIDER_DIR, 'douyin_videos_%s.csv' % stamp)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            df.to_csv(os.path.join(_SPIDER_DIR, 'douyin_video_data.csv'),
                      index=False, encoding='utf-8-sig')
            print(' 视频 CSV：%s' % csv_path)

            with engine.connect() as conn:
                df.to_sql('t_douyin_article_temp', con=conn, if_exists='replace',
                          index=False, chunksize=1000)
                cols = ', '.join('`%s`' % c for c in DY_ART_COLS)
                conn.execute(text(
                    'INSERT INTO `t_douyin_article` (%s) SELECT %s FROM `t_douyin_article_temp` '
                    'ON DUPLICATE KEY UPDATE '
                    '`点赞数`=VALUES(`点赞数`), `评论数`=VALUES(`评论数`), '
                    '`收藏数`=VALUES(`收藏数`), `分享数`=VALUES(`分享数`), '
                    '`时长秒`=VALUES(`时长秒`), `分辨率`=VALUES(`分辨率`), '
                    '`播放地址`=VALUES(`播放地址`), `封面`=VALUES(`封面`), '
                    '`流域`=VALUES(`流域`), `议题`=VALUES(`议题`), '
                    '`命中关键词`=VALUES(`命中关键词`)' % (cols, cols)))
                conn.commit()
                conn.execute(text('DROP TABLE IF EXISTS `t_douyin_article_temp`'))
            art_n = len(df)
            print(' 视频入库完成：%d 条' % art_n)
        except Exception as e:
            _dy_logger.error('视频入库失败：%s' % e)
            print(' 视频入库失败：%s' % e)

    if comments:
        try:
            df = pd.DataFrame(comments)[DY_COM_COLS].copy()
            for c in ('点赞数', '回复数'):
                df[c] = df[c].map(safe_int)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(clean_text)
            csv_path = os.path.join(_SPIDER_DIR, 'douyin_comments_%s.csv' % stamp)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            df.to_csv(os.path.join(_SPIDER_DIR, 'douyin_comment_data.csv'),
                      index=False, encoding='utf-8-sig')
            print(' 评论 CSV：%s' % csv_path)

            with engine.connect() as conn:
                df.to_sql('t_douyin_comment_temp', con=conn, if_exists='replace',
                          index=False, chunksize=1000)
                cols = ', '.join('`%s`' % c for c in DY_COM_COLS)
                conn.execute(text(
                    'INSERT INTO `t_douyin_comment` (%s) SELECT %s FROM `t_douyin_comment_temp` '
                    'ON DUPLICATE KEY UPDATE '
                    '`点赞数`=VALUES(`点赞数`), `回复数`=VALUES(`回复数`)' % (cols, cols)))
                conn.commit()
                conn.execute(text('DROP TABLE IF EXISTS `t_douyin_comment_temp`'))
            com_n = len(df)
            print(' 评论入库完成：%d 条' % com_n)
        except Exception as e:
            _dy_logger.error('评论入库失败：%s' % e)
            print(' 评论入库失败：%s' % e)

    print('\n 持久化完成：视频 %d 条，评论 %d 条' % (art_n, com_n))


# =============================================================================
# 7. 关键词矩阵预览（dry-run 也能跑，无需浏览器）
# =============================================================================
def douyin_preview_keywords(kw_items):
    print('\n' + '=' * 72)
    print('抖音采集 —— 关键词矩阵（共 %d 个）' % len(kw_items))
    print('=' * 72)

    grouped = {}
    for it in kw_items:
        grouped.setdefault((it['basin'], it['topic']), []).append(it['keyword'])
    for (basin, topic), kws in grouped.items():
        print('\n【%s · %s】%d 个' % (basin, topic, len(kws)))
        for i in range(0, len(kws), 4):
            print('   ' + '   '.join('%-16s' % k for k in kws[i:i + 4]))

    out = os.path.join(_SPIDER_DIR, 'douyin_keywords_preview.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('抖音采集 —— 关键词矩阵（%s）\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        f.write('共 %d 个关键词\n\n' % len(kw_items))
        for it in kw_items:
            f.write('%-20s 流域=%-4s 议题=%-8s 省份=%s\n'
                    % (it['keyword'], it['basin'], it['topic'], it['province']))
    print('\n关键词清单已写入：%s' % out)


# =============================================================================
# 8. 主流程
# =============================================================================
def douyin_job(argv=None):
    ap = argparse.ArgumentParser(prog='douyin_spider.py',
                                 description='抖音短视频/评论 流域专项采集')
    ap.add_argument('--dry-run', action='store_true', help='只生成关键词矩阵，不联网不写库')
    ap.add_argument('--basin', action='append', choices=['黄河', '长江'], help='只抓指定流域，可重复')
    ap.add_argument('--topic', action='append', choices=list(TOPIC_KEYWORDS.keys()),
                    help='只抓指定议题，可重复')
    ap.add_argument('--pages', type=int, help='每个关键词监听几屏')
    ap.add_argument('--no-comments', action='store_true', help='跳过评论抓取')
    ap.add_argument('--provinces-per-basin', type=int, help='每个流域取前 N 个省')
    args = ap.parse_args(argv)

    basins = args.basin or DOUYIN_CONFIG['basins']
    topics = args.topic or DOUYIN_CONFIG['topics']
    screens = args.pages if args.pages else DOUYIN_CONFIG['pages_per_keyword']
    fetch_comments = DOUYIN_CONFIG['fetch_comments'] and not args.no_comments
    ppb = (args.provinces_per_basin if args.provinces_per_basin
           else DOUYIN_CONFIG['provinces_per_basin'])

    kw_items = douyin_build_keywords(basins=basins, topics=topics, provinces_per_basin=ppb)
    if not kw_items:
        print(' 关键词为空，请检查 --basin / --topic 参数。')
        return

    douyin_preview_keywords(kw_items)

    if args.dry_run or DOUYIN_CONFIG['dry_run']:
        print('\n[dry-run] 仅预览，未发起任何请求、未写数据库。')
        return

    print('\n' + '=' * 72)
    print('即将开始抓取（抖音）')
    print('  关键词 %d 个 × 每词 %d 屏' % (len(kw_items), screens))
    print('  评论：%s' % ('开启（前 %d 条视频 × 下滑 %d 次）' % (DOUYIN_CONFIG['video_limit'],
                                                              DOUYIN_CONFIG['comment_scrolls'])
                        if fetch_comments else '关闭'))
    print('  提示：需先在独立 profile 中登录抖音（www.douyin.com）。')
    print('=' * 72)

    douyin_ensure_tables()

    page = take_over_real_edge()
    if not page:
        print(' 浏览器接管失败，请确认 Edge 已安装后重试。')
        return

    page.get('https://www.douyin.com')
    time.sleep(2)

    t0 = time.time()
    videos = douyin_crawl_videos(page, kw_items, screens)
    print('\n 视频抓取完毕，共 %d 条（已去重）' % len(videos))
    _dy_logger.info('视频抓取完毕，共 %d 条' % len(videos))

    comments = []
    if fetch_comments and videos:
        comments = douyin_crawl_comments(page, videos, DOUYIN_CONFIG['video_limit'],
                                         DOUYIN_CONFIG['comment_scrolls'])
        print(' 评论抓取完毕，共 %d 条' % len(comments))
        _dy_logger.info('评论抓取完毕，共 %d 条' % len(comments))

    douyin_save_to_db(videos, comments)

    if videos:
        print('\n 分布小结（视频）：')
        stat = {}
        for a in videos:
            key = (a['流域'], a['议题'])
            stat[key] = stat.get(key, 0) + 1
        for (b, t), n in sorted(stat.items(), key=lambda x: -x[1]):
            print('   %-10s %-10s %5d' % (b, t, n))

    print('\n 全部任务完成，耗时 %.1f 分钟' % ((time.time() - t0) / 60))


if __name__ == '__main__':
    douyin_job(sys.argv[1:])
