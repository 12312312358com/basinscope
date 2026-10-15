# -*- coding: utf-8 -*-
"""
小红书 / 知乎 定向采集（长江·黄河流域 · 「医患矛盾」焦点话题）
=============================================================================
与 river_basin_spider.py（微博侧）、douyin_spider.py（抖音侧）并列，是**第三、第四个数据源**。
三者共用同一套口径，落在同一套库里，只在「表」与「平台」字段上分开：

  流域省份   BASIN_PROVINCES                （来自 river_basin_spider）
  议题词库   FOCUS_TOPIC_WORDS_EXT          （本文件定义，见下方「为什么词表写在这里」）
  省份归一   mask_region                    （来自 auto_weibo_to_db_NEW）
  流域判定   basin_classify_basin           （来自 river_basin_spider）
  脱敏工具   hash_id / mask_nickname / mask_pii_text （来自 auto_weibo_to_db_NEW）
  数据库     engine                          （指向 db_weibo_basin）
  浏览器接管 take_over_real_edge             （Edge 独立 profile）

落库到 4 张独立新表，**不与 t_basin_* / t_douyin_* 混写**：
    t_xhs_article   / t_xhs_comment      （平台='小红书'）
    t_zhihu_article / t_zhihu_comment    （平台='知乎'）
字段布局与 t_douyin_* 对齐（同为「内容表 + 评论表」两件套 + 平台判别列），
所以跨平台模块可以按同一套「只比结构占比」的口径直接读它们。

--------------------------------------------------------------------------
【为什么不在 Python 里直接 requests 调接口】
小红书 / 知乎的 Web 接口都带前端签名：
  小红书  x-s / x-t / x-s-common（+ a1 指纹）
  知乎    x-zse-96（+ d_c0）
这两套算法随前端版本漂移，逆向维护成本极高。本模块沿用 douyin_spider 的成熟做法：
**在浏览器上下文里监听页面自身发出的 XHR** —— 让页面自己的 JS 去算签名，
我们只截响应体（DrissionPage 的 page.listen）。对签名算法变更天然免疫。

--------------------------------------------------------------------------
【为什么词表写在这里，而不是去改 river_basin_spider】
river_basin_spider.TOPIC_KEYWORDS['医患矛盾'] 是**旧的扁平 6 词表**，属历史口径。
它有两个已知问题：
  ① 扁平表下 `[:n]` 截断会只取到前面的负面词（「文旅」当年就踩过这个坑）；
  ② 本模块是新平台、新批次，改它会影响微博侧历史复跑的可比性。
因此本模块自带一份「按 消极/中性/积极 三分类」组织的 医患矛盾 词表，
并用 river_basin_spider 的 _flatten_by_roundrobin 展开 —— 前 N 个词三类均衡，
从源头上避免「召回全是负面投诉」的采样偏差。**微博侧词表一字未改。**

--------------------------------------------------------------------------
【采集范围（两类主题）】
  主题一 医患矛盾  —— 本模块自带三分类词表（见 FOCUS_TOPIC_WORDS_EXT）
  主题二 生态治理  —— 即用户所说的「生态环境主题」，沿用项目既有议题名与词表
                     （与 river_basin_spider / 抖音侧完全同源，保证跨平台可比）
  流域    黄河（山东/河南/山西/陕西/内蒙古/宁夏/甘肃/青海）
          长江（四川/重庆/湖北/湖南/江西/安徽/江苏/浙江/上海/云南/贵州/西藏）
  关键词  省份 × 议题词（每议题 9 词，消极/中性/积极各 3），见 dry-run 输出
  落库    t_xhs_* / t_zhihu_*（21+16 列，脱敏）
  留底    spider/_raw/*.jsonl（**未加工原始体**，开式 schema，供后续分析）

--------------------------------------------------------------------------
【原始数据留存】
除了归一入库，还把每条**未加工的原始响应对象**追加进 `spider/_raw/` 下的 JSONL，
供后续做词频/主题建模/事件抽取/情感校准。理由：归一表只留了现在想到的字段，
响应体里还有很多当下没用、以后可能有用的东西（image_list、话题、所属问题…）。
⚠️ 原始体含未脱敏作者字段 → 该目录已 gitignore，**不得提交仓库、不得对外发布**；
   对外展示一律只用 t_xhs_* / t_zhihu_* 的脱敏聚合结果。用 `--raw-off` 可关闭。

--------------------------------------------------------------------------
【✅ 小红书字段已按 2026-09-28 实跑校准】
对照 `_packet_search_小红书_*.json` 核实：
  data.items[] ✓ / item{id, model_type, xsec_token, note_card} ✓
  note_card.display_title ✓（20 条里 16 条有，纯图笔记无）
  interact_info.{liked,collected,comment_count,shared_count} ✓
  user.{user_id, nickname, nick_name} ✓
  **无 desc 字段** → 搜索结果的「正文」为空（需进详情页才能拿到，属已知限制）
  **发布时间只在 corner_tag_info[{'type':'publish_time','text':'09-01'|'1天前'}]**
  **详情 URL 必须带 xsec_token（20/20 都有），否则开不了详情页/评论区**

--------------------------------------------------------------------------
【⚠️ 已校准（2026-09-29 实跑验证）】
  · 小红书 `comment/page`        评论列表字段名
  · 小红书 `web/v1/feed`         笔记详情（用来补搜索响应缺失的「正文」desc）
  · 知乎   `search_v3`           搜索字段名
  · 知乎   评论接口 = `api/v4/answers/{id}/root_comments?order=normal&...`
           ⚠️ 知乎回答页**不会**因滚动/点击自动触发评论 XHR，必须主动 fetch 该接口
           （见 _zhihu_fetch_comments）。评论作者嵌套在 `author.member`，
           字段 content / created_time / vote_count / child_comment_count / ip_info(多为空)。
  · 知乎   正文走 SSR（window.__INITIAL_STATE__），不监听详情 XHR（listen_detail 故意为空）。
带评论跑一次 `--dump-packet`，会落 `_packet_comment_知乎_*` / `_packet_search_*` 等
（知乎评论响应经 _zhihu_fetch_comments 内 _dump 落盘，不依赖 listen_detail）。

--------------------------------------------------------------------------
【正文补抓（小红书搜索响应没有 desc）】
详情页本来就要打开（抓评论），所以**顺带**监听 detail 端点把正文取回来，不额外加请求。
⚠️ 覆盖范围只到「按评论数选中的前 `content_limit` 条」；其余行正文仍为空。
想全量补正文，就调大 `content_limit`（代价是时长）。

--------------------------------------------------------------------------
【⚠️ 首跑必须校准（与 douyin_spider 同一约定）】
各平台 adapter 用的是**候选字段路径 + 容错解析**；未 dump 校准过的端点
不允许把结果当结论用。已提供：
  python xhs_zhihu_spider.py --self-test        # 离线跑归一函数单测，不联网
  python xhs_zhihu_spider.py --dry-run          # 预览关键词矩阵，不联网
  python xhs_zhihu_spider.py --ensure-tables-only  # 只建表
用法：
  python xhs_zhihu_spider.py --platform 小红书 --pages 1 --provinces-per-basin 1
  python xhs_zhihu_spider.py                                   # 正式全量（两主题×两平台）
  python xhs_zhihu_spider.py --topic 医患矛盾                   # 只跑一个主题
  python xhs_zhihu_spider.py --raw-off --no-comments            # 不留原始体 / 不抓评论
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
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text

_SPIDER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SPIDER_DIR not in sys.path:
    sys.path.insert(0, _SPIDER_DIR)

# 复用微博侧的全部口径与工具，保证多平台「同省份表、同流域判定、同脱敏规则」
from river_basin_spider import (           # noqa: E402
    BASIN_PROVINCES,
    TOPIC_KEYWORDS,
    _flatten_by_roundrobin,
    basin_classify_basin,
    basin_extract_province,
)
from auto_weibo_to_db_NEW import (         # noqa: E402
    clean_text,
    engine,
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
# 0. 焦点话题词表（本模块自带，不改 river_basin_spider）
# =============================================================================
# 结构与 FOCUS_TOPIC_WORDS 一致：消极 / 中性 / 积极 三分类，各 3 词 = 9 词。
# 三分类齐备是硬要求：扁平表 + [:3] 截断会只召回「医闹/伤医」这类负面词，
# 得到的「医患矛盾舆情」其实是「医疗负面舆情」，样本结构从一开始就是歪的。
FOCUS_TOPIC_WORDS_EXT = {
    '医患矛盾': {
        '消极': ['医闹', '伤医', '医疗事故'],
        '中性': ['医患纠纷', '医疗纠纷', '看病难'],
        '积极': ['医患互信', '医疗改革', '医德医风'],
    },
}

# 本模块可用的完整词表 = 焦点头条(本文件) + 原项目既有词表(生态治理/文旅/社会治理)
LOCAL_TOPIC_KEYWORDS = {}
for _t, _w in FOCUS_TOPIC_WORDS_EXT.items():
    LOCAL_TOPIC_KEYWORDS[_t] = _flatten_by_roundrobin(_w)
for _t, _w in TOPIC_KEYWORDS.items():
    LOCAL_TOPIC_KEYWORDS.setdefault(_t, list(_w))


# =============================================================================
# 1. 配置
# =============================================================================
# 本次任务的焦点话题（可用 --topic 覆盖）：
#   ① 医患矛盾    —— 本模块自带三分类词表（FOCUS_TOPIC_WORDS_EXT）
#      ⚠️ 已于 2026-09-29 在小红书(634 文/376 评) + 知乎(539 文/460 评) 采集完成，
#         故默认不再抓取，仅保留 --topic 医患矛盾 的历史覆写能力。
#   ② 生态治理    —— 即用户所说的「生态环境主题」，**沿用项目既有议题名与词表**
#      （与 river_basin_spider.FOCUS_TOPIC_WORDS['生态治理'] / 抖音侧完全同源）
#      ★ 当前默认（也是本轮唯一采集目标）只收生态治理，停止抓取医患矛盾。
#
# 为什么标签必须是「生态治理」而不是「生态环境」：
#   CROSS_METRICS 的「议题结构」要跨平台比对 篇数占比 —— 各平台议题标签必须同名，
#   否则跨平台页会把「生态环境」与「生态治理」当成两个议题，占比对不上。
#   若要改显示名，只改这一处标签 + 前端口径字典，不要只在采集端改。
FOCUS_TOPIC_MEDICAL = '医患矛盾'
FOCUS_TOPIC_ECO = '生态治理'

XZ_CONFIG = {
    'basins': ['黄河', '长江'],
    'topics': [FOCUS_TOPIC_ECO, FOCUS_TOPIC_MEDICAL, '文旅'],   # 默认三主题
    'platforms': ['小红书', '知乎'],   # 两个平台都覆盖
    'provinces_per_basin': None,       # None = 全部省份
    'keywords_per_topic': 9,           # 三分类各 3 词，全部用上
    'screens_per_keyword': 3,          # 每个关键词监听 3 屏搜索结果
    'fetch_comments': True,
    'fetch_body': True,                # 进详情页时顺带补抓「正文」（小h书搜索结果无正文）
    'content_limit': 30,               # 按评论数取前 30 条内容抓评论（本次运行内上限）
    'comment_scrolls': 5,              # 每条内容下滑 5 次评论区
    'zhihu_comments_per_article': 150, # 知乎每篇回答最多抓多少条评论（按 offset 翻页）
    'sleep_min': 4.0,
    'sleep_max': 9.0,
    'keep_raw': True,                  # 保留原始响应体到 spider/_raw/（JSONL，供后续分析）
    'dump_packet': False,              # True 则额外把响应体单独落盘，供首跑字段校准
    'dump_max': 3,                     # 每个阶段最多落盘几个响应包（详情页+评论各需 1 个）
    'dry_run': False,
}

_xz_logger = logging.getLogger('xhs_zhihu_spider')
_xz_logger.setLevel(logging.INFO)
if not _xz_logger.handlers:
    _h = logging.FileHandler(os.path.join(_SPIDER_DIR, 'xhs_zhihu_spider.log'), encoding='utf-8')
    _h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    _xz_logger.addHandler(_h)


# =============================================================================
# 2. 平台 adapter（差异全在这里，主流程对平台无感）
# -----------------------------------------------------------------------------
# 每个平台提供：
#   login_url        首次实跑前需登录的站点
#   search_url(kw)   搜索页 URL（触发页面自身发 XHR）
#   listen_search    搜索 XHR 的 URL 特征（page.listen.start 的子串）
#   pick_items(body) 从搜索响应体里取出「条目列表」
#   norm_article(it, ctx)  条目 -> 内容表一行（dict）
#   listen_comment   评论 XHR 的 URL 特征
#   pick_comments(body)    从评论响应体里取出「评论列表」
#   norm_comment(c, ctx)   评论 -> 评论表一行（dict）
#   detail_url(art)  内容详情页 URL（进详情页才能触发评论 XHR）
# -----------------------------------------------------------------------------
def _deep_get(obj, path, default=None):
    """按 'a.b.0.c' 取嵌套值；任一层缺失返回 default。用于容错解析。"""
    cur = obj
    for seg in str(path).split('.'):
        if cur is None:
            return default
        if isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError):
                return default
            continue
        if isinstance(cur, dict):
            if seg not in cur:
                return default
            cur = cur[seg]
        else:
            return default
    return default if cur is None else cur


def _first_of(obj, paths, default=''):
    """按候选路径列表逐个尝试，返回第一个「非空」的值。"""
    for p in paths:
        v = _deep_get(obj, p)
        if v not in (None, '', [], {}):
            return v
    return default


def _fmt_ts_any(ts):
    """把 unix 秒 / 毫秒 时间戳转成 'YYYY-MM-DD HH:MM:SS'；失败原样返回字符串。"""
    if ts in (None, '', 0):
        return ''
    try:
        n = int(ts)
    except (TypeError, ValueError):
        return str(ts)[:64]
    if n > 10 ** 11:          # 毫秒
        n //= 1000
    if n <= 0:
        return ''
    try:
        return datetime.fromtimestamp(n).strftime('%Y-%m-%d %H:%M:%S')
    except (OverflowError, OSError, ValueError):
        return ''


_GENDER_MAP = {'m': '男', 'f': '女', 'male': '男', 'female': '女', '1': '男', '2': '女'}
_GENDER_NUM = {1: '男', 2: '女'}


def _norm_gender(g):
    """各平台性别取值五花八门（'m'/'f'、1/2、'男'/'女'），统一成 男/女/未知。"""
    if g is None or g == '':
        return '未知'
    if isinstance(g, int):
        return _GENDER_NUM.get(g, '未知')
    s = str(g).strip()
    if s in ('男', '女'):
        return s
    return _GENDER_MAP.get(s.lower(), '未知')


def _topic_of(kw_item):
    return kw_item['topic'], kw_item['keyword'], kw_item['basin'], kw_item['province']


def _normalize_relative_time(s):
    """把小红书的模糊时间归一成 'YYYY-MM-DD'；解析不了就原样返回（宁可留原文，不编）。

    2026-09-28 首跑实测：小红书搜索结果**没有**标准时间字段，
    发布时间只出现在 `corner_tag_info[{'type':'publish_time','text':...}]`，取值形如：
      '09-01'（月-日，**无年份**） / '1天前' / '3小时前' / '昨天' / '刚刚'
    """
    s = (s or '').strip()
    if not s:
        return ''
    now = datetime.now()
    m = re.fullmatch(r'(\d+)\s*(分钟|小时|天)前', s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {'分钟': timedelta(minutes=n),
                 '小时': timedelta(hours=n),
                 '天': timedelta(days=n)}[unit]
        return (now - delta).strftime('%Y-%m-%d')
    if s == '昨天':
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    if s in ('今天', '刚刚'):
        return now.strftime('%Y-%m-%d')
    m = re.fullmatch(r'(\d{1,2})-(\d{1,2})', s)
    if m:
        mo, dd = int(m.group(1)), int(m.group(2))
        try:
            cand = datetime(now.year, mo, dd)
        except ValueError:
            return s
        if cand > now + timedelta(days=1):    # 落在未来 → 必是去年的
            cand = datetime(now.year - 1, mo, dd)
        return cand.strftime('%Y-%m-%d')
    return s


def _xhs_publish_time(card):
    """小红书发布时间藏在 corner_tag_info 里，取 type=='publish_time' 的那条。"""
    for t in (card.get('corner_tag_info') or []):
        if isinstance(t, dict) and t.get('type') == 'publish_time':
            return _normalize_relative_time(str(t.get('text', '')))
    return ''


def _xhs_note_url(item, note_id):
    """笔记详情 URL。**必须带 xsec_token** —— 首跑实测 20/20 条都有该字段，
    不带 token 直接开 /explore/<id> 会被拒（这是首跑前最大的一个坑）。
    token 有时效，故 内容ID 才是稳定主键，链接只作快照。"""
    tok = _first_of(item, ['xsec_token'], '')
    url = 'https://www.xiaohongshu.com/explore/%s' % note_id
    if tok:
        url += '?xsec_token=%s&xsec_source=pc_search' % tok
    return url


# ----------------------------- 小红书 -----------------------------
def _xhs_pick_items(body):
    return (_deep_get(body, 'data.items') or _deep_get(body, 'data.data')
            or _deep_get(body, 'data') or [])


def _xhs_norm_article(it, ctx):
    card = it.get('note_card') or it.get('note') or it
    nid = str(_first_of(it, ['id', 'note_id']) or _first_of(card, ['note_id', 'id']))
    if not nid:
        return None
    topic, keyword, basin, province = ctx
    inter = card.get('interact_info') or {}
    user = card.get('user') or {}
    title = _first_of(card, ['display_title', 'title'], '')
    # ⚠️ 首跑实测：搜索结果里**没有 `desc` 字段**（note_card 只有
    # cover/image_list/interact_info/user/type/corner_tag_info + 多数带 display_title）。
    # 所以「正文」只能靠后续进详情页补（见 default 组说明）；此处留空而不是编造。
    desc = _first_of(card, ['desc', 'description'], '')
    return {
        '内容ID': nid,
        '标题': mask_pii_text(str(title)[:120]),
        '正文': mask_pii_text(str(desc).replace('\n', ' ').strip()),
        '话题标签': ' '.join(_xhs_tags(card)),
        '点赞数': str(_first_of(inter, ['liked_count', 'liked'], '0')),
        '评论数': str(_first_of(inter, ['comment_count', 'comments_count'], '0')),
        '收藏数': str(_first_of(inter, ['collected_count', 'collected'], '0')),
        '分享数': str(_first_of(inter, ['shared_count', 'share_count'], '0')),
        '详情链接': _xhs_note_url(it, nid),
        '封面': _first_of(card, ['cover.url_default', 'cover.url'], ''),
        '发布地区': mask_region(_first_of(it, ['note_card.ip_location', 'ip_location'], '未知')),
        '发布时间': _xhs_publish_time(card),
        '作者ID': hash_id(_first_of(user, ['user_id', 'id'], '')),
        '作者昵称': mask_nickname(_first_of(user, ['nickname', 'nick_name'], '未知')),
        '作者主页': '已脱敏',
        '平台': '小红书',
        '流域': basin,
        '议题': topic,
        '命中关键词': keyword,
        '目标省份': province,
        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def _xhs_tags(card):
    raw = card.get('tag_list') or card.get('tags') or []
    out = []
    for t in raw:
        if isinstance(t, dict):
            nm = t.get('name') or t.get('tag_name')
            if nm:
                out.append('#' + str(nm))
        elif isinstance(t, str):
            out.append('#' + t)
    return out


def _xhs_pick_comments(body):
    return (_deep_get(body, 'data.comments') or _deep_get(body, 'comments')
            or _deep_get(body, 'data.data') or [])


def _xhs_norm_comment(c, ctx):
    cid = str(_first_of(c, ['id', 'comment_id'], ''))
    if not cid:
        return None
    topic, keyword, basin, ui = ctx
    user = c.get('user_info') or c.get('user') or {}
    return {
        '评论ID': cid,
        '评论内容': mask_pii_text(str(_first_of(c, ['content', 'text'], '')).replace('\n', ' ').strip()),
        '评论时间': _fmt_ts_any(_first_of(c, ['create_time', 'time'])),
        '点赞数': str(_first_of(c, ['like_count', 'liked_count'], '0')),
        '回复数': str(_first_of(c, ['sub_comment_count', 'reply_count'], '0')),
        '内容ID': ui['id'],
        '用户ID': hash_id(_first_of(user, ['user_id', 'id'], '')),
        '昵称': mask_nickname(_first_of(user, ['nickname', 'nick_name'], '未知')),
        '性别': _norm_gender(_first_of(user, ['gender'], '')),
        '用户地区': mask_region(_first_of(c, ['ip_location'], '未知')),
        '用户主页': '已脱敏',
        '平台': '小红书',
        '流域': basin,
        '议题': topic,
        '命中关键词': keyword,
        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


# ----------------------------- 知乎 -----------------------------
_ZHIHU_TYPE_URL = {'answer': 'answer', 'article': 'p', 'zvideo': 'zvideo', 'pin': 'pin'}


def _zhihu_pick_items(body):
    return _deep_get(body, 'data') or []


def _zhihu_norm_article(it, ctx):
    obj = it.get('object') or it.get('object_detail') or it
    if isinstance(obj, list):        # search_v3 偶见 object 为单元素数组
        obj = obj[0] if obj else {}
    otype = _first_of(obj, ['type'], 'answer')
    oid = str(_first_of(obj, ['id', 'answer_id', 'article_id'], ''))
    if not oid:
        return None
    topic, keyword, basin, province = ctx
    author = obj.get('author') or {}
    qid = _first_of(obj, ['question.id'], '')
    seg = _ZHIHU_TYPE_URL.get(otype, 'answer')
    if seg == 'answer' and qid:
        link = 'https://www.zhihu.com/question/%s/answer/%s' % (qid, oid)
    else:
        link = 'https://www.zhihu.com/%s/%s' % (seg, oid)
    title = _first_of(obj, ['title', 'question.title'], '')
    body_txt = _first_of(obj, ['excerpt', 'content', 'description'], '')
    return {
        '内容ID': '%s_%s' % (otype, oid),
        '标题': mask_pii_text(str(title)[:120]),
        '正文': mask_pii_text(str(body_txt).replace('\n', ' ').strip()),
        '话题标签': ' '.join(_zhihu_topics(obj)),
        '点赞数': str(_first_of(obj, ['voteup_count', 'like_count'], '0')),
        '评论数': str(_first_of(obj, ['comment_count', 'comments_count'], '0')),
        '收藏数': str(_first_of(obj, ['favorites_count', 'collect_count'], '0')),
        '分享数': str(_first_of(obj, ['share_count'], '0')),
        '详情链接': link,
        '封面': _first_of(obj, ['thumbnail', 'image_url'], ''),
        '发布地区': mask_region(_first_of(obj, ['ip_info', 'ip_location'], '未知')),
        '发布时间': _fmt_ts_any(_first_of(obj, ['created_time', 'created', 'updated_time'])),
        '作者ID': hash_id(_first_of(author, ['id', 'url_token'], '')),
        '作者昵称': mask_nickname(_first_of(author, ['name'], '未知')),
        '作者主页': '已脱敏',
        '平台': '知乎',
        '流域': basin,
        '议题': topic,
        '命中关键词': keyword,
        '目标省份': province,
        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def _zhihu_topics(obj):
    raw = obj.get('topics') or obj.get('question.topics') or []
    out = []
    for t in raw:
        if isinstance(t, dict) and t.get('name'):
            out.append(str(t['name']))
        elif isinstance(t, str):
            out.append(t)
    return out


def _zhihu_pick_comments(body):
    return _deep_get(body, 'data') or []


def _zhihu_norm_comment(c, ctx):
    cid = str(_first_of(c, ['id', 'comment_id'], ''))
    if not cid:
        return None
    topic, keyword, basin, ui = ctx
    author = c.get('author') or {}
    member = author.get('member') or {}     # 知乎评论作者嵌套在 author.member（非 user_info）
    # 知乎性别：1=男 0=女 -1=未知；走本地映射，避免与全局 _norm_gender 的 0=未知 冲突
    _ZH_GENDER = {-1: '未知', 0: '女', 1: '男', 2: '女'}
    g = _first_of(member, ['gender'], '')
    gender = _ZH_GENDER.get(g, '未知') if isinstance(g, int) else _norm_gender(g)
    content = _first_of(c, ['content', 'excerpt'], '')
    content = re.sub(r'<[^>]+>', ' ', str(content)).replace('\n', ' ').strip()
    return {
        '评论ID': cid,
        '评论内容': mask_pii_text(content),
        '评论时间': _fmt_ts_any(_first_of(c, ['created_time', 'created'])),
        '点赞数': str(_first_of(c, ['vote_count', 'like_count'], '0')),
        '回复数': str(_first_of(c, ['child_comment_count', 'reply_count'], '0')),
        '内容ID': ui['id'],
        '用户ID': hash_id(_first_of(member, ['id', 'url_token'], '')),
        '昵称': mask_nickname(_first_of(member, ['name'], '未知')),
        '性别': gender,
        '用户地区': mask_region(_first_of(c, ['ip_info', 'ip_location', 'address_text'], '未知')),
        '用户主页': '已脱敏',
        '平台': '知乎',
        '流域': basin,
        '议题': topic,
        '命中关键词': keyword,
        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def _zhihu_fetch_comments(page, aid, max_n=150, dump_packet=False):
    """知乎评论走 API 主动拉取（页面滚动/点击不会自动触发评论 XHR）。

    用已登录页面的同源 fetch 调用 answers/{aid}/root_comments，
    结果存到 window.__zc__ 再读回（不依赖 page.listen 匹配）。
    按 offset 翻页直到：本页 data 不足一页 / paging.is_end / 达到 max_n。
    """
    out, seen = [], set()
    offset, limit = 0, 20
    while len(out) < max_n:
        url = ('https://www.zhihu.com/api/v4/answers/%s/root_comments'
               '?order=normal&limit=%d&offset=%d&status=open' % (aid, limit, offset))
        js = ("fetch(%s,{credentials:'include',"
              "headers:{'x-requested-with':'XMLHttpRequest','accept':'application/json'}})"
              ".then(r=>r.text()).then(t=>window.__zc__=t)"
              ".catch(e=>window.__zc__='ERR:'+e);" % json.dumps(url))
        try:
            page.run_js('window.__zc__=""')   # 清空上一页残留，避免翻页时读到旧值
            page.run_js(js)
        except Exception:
            pass
        raw = None
        for _ in range(25):
            time.sleep(0.4)
            try:
                raw = page.run_js('return window.__zc__ || ""')
            except Exception:
                raw = ''
            if raw not in (None, ''):
                break
        if not raw or str(raw).startswith('ERR'):
            break
        try:
            body = json.loads(raw)
        except Exception:
            break
        if dump_packet and offset == 0:
            _dump('comment_知乎', body, 1)
        data = (body.get('data') or []) if isinstance(body, dict) else []
        if not data:
            break
        for c in data:
            cid = str(_first_of(c, ['id'], ''))
            if not cid or cid in seen:
                continue
            seen.add(cid)
            out.append(c)
        if len(data) < limit:
            break
        paging = body.get('paging') or {}
        if paging.get('is_end'):
            break
        offset += limit
        time.sleep(random.uniform(0.8, 1.6))
    return out[:max_n]


PLATFORM_ADAPTERS = {
    '小红书': dict(
        name='小红书',
        login_url='https://www.xiaohongshu.com',
        tables=('t_xhs_article', 't_xhs_comment'),
        listen_search='search/notes',
        listen_comment='comment/page',
        # ⚠️ 未校准：笔记详情接口（含 `note_card.desc`，即搜索响应缺失的「正文」）。
        # 首跑时靠它把正文补回来 + 落一份 dump 供校准；匹配不上就是空转，不报错。
        listen_detail=('web/v1/feed',),
        search_url=lambda kw: ('https://www.xiaohongshu.com/search_result?keyword=%s'
                               '&source=web_explore_feed&type=51' % urllib.parse.quote(kw)),
        pick_items=_xhs_pick_items,
        norm_article=_xhs_norm_article,
        pick_comments=_xhs_pick_comments,
        norm_comment=_xhs_norm_comment,
        detail_url=lambda art: art.get('详情链接') or (
            'https://www.xiaohongshu.com/explore/%s' % art['内容ID']),
    ),
    '知乎': dict(
        name='知乎',
        login_url='https://www.zhihu.com',
        tables=('t_zhihu_article', 't_zhihu_comment'),
        listen_search='search_v3',
        # 知乎评论走「主动 fetch answers/{id}/root_comments」（见 _zhihu_fetch_comments），
        # 不依赖页面滚动触发，故此处仅作端点记录、运行期不使用 page.listen 抓评论。
        listen_comment='root_comments',
        # 知乎正文走 SSR 页面 __INITIAL_STATE__（_detail_body_from_page），不监听 detail XHR。
        # 若保留 ('api/v4/answers','api/v4/articles') 会子串误匹配
        # api/v4/answers/{id}/root_comments（真实评论接口）与 .../voters（点赞组件），
        # 前者被当详情包 continue 掉 → 评论永远抽不到，后者产生噪音 dump。
        listen_detail=(),
        search_url=lambda kw: ('https://www.zhihu.com/search?type=content&q=%s'
                               % urllib.parse.quote(kw)),
        pick_items=_zhihu_pick_items,
        norm_article=_zhihu_norm_article,
        pick_comments=_zhihu_pick_comments,
        norm_comment=_zhihu_norm_comment,
        detail_url=lambda art: art.get('详情链接') or '',
    ),
}


def _as_patterns(v):
    """把 adapter 里的监听目标统一成 tuple（支持 str / list / tuple / set）。"""
    if not v:
        return ()
    if isinstance(v, str):
        return (v,)
    return tuple(v)


def _packet_url(packet):
    """取包的真实请求 URL（用于区分「评论包」与「详情包」）。取不到返回 ''。"""
    try:
        return str(packet.url or '')
    except Exception:
        return ''


def _find_desc(obj, depth=0):
    """在任意结构里递归找第一个非空的 `desc` 字符串。找不到返回 ''。"""
    if depth > 8 or obj is None:
        return ''
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'desc' and isinstance(v, str) and v.strip():
                return v.strip()
        for v in obj.values():
            r = _find_desc(v, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj[:2]:
            r = _find_desc(v, depth + 1)
            if r:
                return r
    return ''


def _detail_body_from_page(page):
    """从**页面自身**取正文（不依赖 XHR）。

    首跑实测（2026-09-28）：打开 /explore/<id> 后**没有**捕获到承载正文的接口
    （`web/v1/feed` 一条都没匹配上），因为笔记详情页是**服务端渲染**的 ——
    正文不在 XHR 响应里，而在页面里。改走两条路：
    ① `window.__INITIAL_STATE__` 内嵌的笔记对象（小红书/知乎的通用做法）
    ② 渲染后的 DOM 文案（`#detail-desc` / `.desc`）
    取不到返回 ''（不猜、不抛）。

    ✅ 2026-09-29 实跑验证：小红书**30/30 全命中**，正文为真实笔记内容
    （最长 2894 字、均值 407 字；视频类笔记的 desc 常常只有 `#话题` 标签，属真实数据）。
    """
    # ① 内嵌初始状态
    try:
        raw = page.run_js('return (window.__INITIAL_STATE__ ? '
                          'JSON.stringify(window.__INITIAL_STATE__) : "")')
        if raw:
            st = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(st, dict):
                for root in ('note', 'detail', 'answer', 'article'):
                    if root in st:
                        r = _find_desc(st[root])
                        if r:
                            return r
                r = _find_desc(st)
                if r:
                    return r
    except Exception:
        pass
    # ② 渲染后的正文 DOM
    for sel in ('#detail-desc', '.desc', '.content', 'css:#detail-desc'):
        try:
            el = page.ele(sel)
            if el is not None and getattr(el, 'text', ''):
                return str(el.text).replace('\n', ' ').strip()
        except Exception:
            continue
    return ''


def _extract_body_text(platform, body):
    """从详情响应里抽「正文」；抽不到返回 ''（不猜、不抛）。

    详见文件头「待校准」清单 —— 这两条路径是**按公共知识预写**的，
    必须用 `--dump-packet` 落一份真实响应核对后才算数。
    （2026-09-28 实测：小红书详情页走的是服务端渲染，这条路径通常用不上，
     正文实际由 `_detail_body_from_page()` 从页面取。）
    """
    paths = {
        '小红书': ('data.items.0.note_card.desc', 'data.note.note_card.desc',
                   'data.0.note_card.desc'),
        '知乎': ('content', 'excerpt', 'target.content', 'data.0.content'),
    }.get(platform, ())
    for p in paths:
        v = _deep_get(body, p)
        if v:
            return str(v).replace('\n', ' ').strip()
    return ''


# =============================================================================
# 2.5 原始数据留存（供后续分析：词频 / 主题建模 / 事件抽取 / 情感校准）
# -----------------------------------------------------------------------------
# 为什么要在「归一入库」之外再存一份原始体：
#   归一后的表只保留我们**现在**想到要的字段（21 / 16 列）。而小红书/知乎的
#   响应体里还有很多当下用不到、但以后可能有用的东西（image_list、xsec_token、
#   话题、问答所属问题、更多互动指标…）。一旦只存归一结果，这些就永久丢了。
#   所以额外把**未加工的原始对象**逐条追加进 JSONL，做「开式 schema」留底。
#
# ⚠️ 合规红线：原始体含**未脱敏**的作者昵称/ID 等。因此
#   - 该目录 `spider/_raw/` 已写进 .gitignore，**不得提交仓库**；
#   - 仅作本地分析原料，**不得对外发布或并入任何交付材料**；
#   - 对外展示仍只走 t_xhs_* / t_zhihu_* 的**脱敏聚合结果**。
# =============================================================================
_RAW_DIR = os.path.join(_SPIDER_DIR, '_raw')
_raw_handles = {}

_PLATFORM_SLUG = {'小红书': 'xhs', '知乎': 'zhihu', '抖音': 'douyin', '微博': 'weibo'}


def raw_path(platform, kind, topic):
    """原始数据落点：spider/_raw/<平台>_<article|comment>_<议题>.jsonl"""
    os.makedirs(_RAW_DIR, exist_ok=True)
    return os.path.join(_RAW_DIR, '%s_%s_%s.jsonl'
                        % (_PLATFORM_SLUG.get(platform, platform), kind, topic))


def raw_write(platform, kind, meta, raw):
    """把一条未加工的原始对象追加进 JSONL（开式 schema，字段照原样保留）。"""
    if not XZ_CONFIG['keep_raw']:
        return
    try:
        key = (platform, kind, meta.get('议题', ''))
        fh = _raw_handles.get(key)
        if fh is None:
            fh = open(raw_path(platform, kind, meta.get('议题', '')), 'a', encoding='utf-8')
            _raw_handles[key] = fh
        rec = {'采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               '平台': platform, '类型': kind}
        rec.update(meta)
        rec['raw'] = raw
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception as e:
        _xz_logger.warning('原始数据留存失败(%s/%s)：%s' % (platform, kind, e))


def raw_close():
    """收尾关闭所有句柄（主流程末尾必调，异常路径也要调）。"""
    for fh in _raw_handles.values():
        try:
            fh.close()
        except Exception:
            pass
    _raw_handles.clear()


# =============================================================================
# 2.6 字段契约（供 `_probe_packet.py` 拿真实 dump 反向核对）
# -----------------------------------------------------------------------------
# 这里声明「各归一函数**实际读取**的候选路径」。校准不再是"肉眼看 JSON"，
# 而是跑 `python _probe_packet.py <dump>` 让它逐字段报告：命中 / 部分命中 / 全部落空。
#
# ⚠️ 改归一逻辑时**必须同步改这里**，否则校准会给出过期结论。
# 结构： (平台, 类型) -> {'list': 取条目列表的路径, 'item': {字段: [相对候选路径]}}
#       类型 = article（搜索）/ comment（评论）/ detail（详情，用于补正文）
# =============================================================================
FIELD_PROBES = {
    ('小红书', 'article'): {
        'list': ['data.items'],
        'item': {
            '内容ID': ['id', 'note_id'],
            '标题': ['note_card.display_title', 'note_card.title'],
            '正文': ['note_card.desc', 'note_card.description'],          # 实测落空
            '话题标签': ['note_card.tag_list', 'note_card.tags'],          # 实测落空
            '点赞数': ['note_card.interact_info.liked_count'],
            '评论数': ['note_card.interact_info.comment_count'],
            '收藏数': ['note_card.interact_info.collected_count'],
            '分享数': ['note_card.interact_info.shared_count'],
            '封面': ['note_card.cover.url_default', 'note_card.cover.url'],
            '发布时间': ['note_card.corner_tag_info'],                     # 特殊解析
            '作者ID': ['note_card.user.user_id'],
            '作者昵称': ['note_card.user.nickname', 'note_card.user.nick_name'],
            '发布地区': ['note_card.ip_location', 'ip_location'],
            # ⚠️ 2026-09-28 探针实测：搜索响应里**没有** ip_location（0/20），
            # 所以小红书「内容」的 发布地区 会**恒为「未知」**。
            # → 前置端做省份/地域榜时必须剔除「未知」，不能当类目参与排序
            #   （与 7eee611 修的「未知被当地区参与省级排行」是同一类红线）。
            #   评论侧可能有 ip_location（待 comment dump 校准）。
            'xsec_token': ['xsec_token'],                                  # 详情页必需
        },
        # 2026-09-28 探针实测（搜索 dump，20 条）：11/14 字段命中，以下三项确认不存在。
        # 正文靠 `_detail_body_from_page()` 从**服务端渲染的详情页**取（没有承载正文的 XHR）。
        'absent': {
            '正文': '搜索响应无 desc（实测 0/20）→ 只能从详情页补抓',
            '话题标签': '搜索响应无 tag_list/tags（实测 0/20）',
            '发布地区': '搜索响应无 ip_location（实测 0/20）→ 恒为「未知」',
        },
    },
    ('小红书', 'comment'): {
        'list': ['data.comments', 'comments', 'data.data'],
        'item': {
            '评论ID': ['id', 'comment_id'],
            '评论内容': ['content', 'text'],
            '评论时间': ['create_time', 'time'],
            '点赞数': ['like_count', 'liked_count'],
            '回复数': ['sub_comment_count', 'reply_count'],
            '用户ID': ['user_info.user_id', 'user.user_id'],
            '昵称': ['user_info.nickname', 'user_info.nick_name',
                     'user.nickname', 'user.nick_name'],
            '用户地区': ['ip_location'],
        },
        # 2026-09-28 探针实测（对 _packet_comment_小红书_*.json，10 条）：
        # 8/9 字段 100% 命中；**性别**在评论响应里**根本没有**（0/10）。
        # → 小红书评论的 性别 恒为「未知」，不要在前端做性别分布。
        'absent': {
            '性别': '评论响应无性别字段（2026-09-28 实测 0/10）→ 恒为「未知」',
        },
    },
    ('小红书', 'detail'): {
        'list': ['data.items', 'data.note', 'data'],
        'item': {
            '正文': ['note_card.desc', 'desc'],
            '内容ID': ['id', 'note_card.note_id'],
        },
    },
    ('知乎', 'article'): {
        'list': ['data'],
        'item': {
            '内容ID': ['object.id', 'object.answer_id', 'object.article_id'],
            '类型': ['object.type'],
            '标题': ['object.title', 'object.question.title'],
            '正文': ['object.excerpt', 'object.content', 'object.description'],
            '话题标签': ['object.topics', 'object.question.topics'],
            '点赞数': ['object.voteup_count', 'object.like_count'],
            '评论数': ['object.comment_count', 'object.comments_count'],
            '收藏数': ['object.favorites_count', 'object.collect_count'],
            '分享数': ['object.share_count'],
            '封面': ['object.thumbnail', 'object.image_url'],
            '发布时间': ['object.created_time', 'object.created', 'object.updated_time'],
            '作者ID': ['object.author.id', 'object.author.url_token'],
            '作者昵称': ['object.author.name'],
            '发布地区': ['object.ip_info', 'object.ip_location'],
            '问题ID': ['object.question.id'],
        },
    },
    ('知乎', 'comment'): {
        'list': ['data'],
        'item': {
            '评论ID': ['id', 'comment_id'],
            '评论内容': ['content', 'excerpt'],
            '评论时间': ['created_time', 'created'],
            '点赞数': ['like_count', 'vote_count'],
            '回复数': ['reply_count', 'child_comment_count'],
            '用户ID': ['author.id', 'author.url_token'],
            '昵称': ['author.name'],
            '性别': ['author.gender'],
            '用户地区': ['ip_info', 'ip_location'],
        },
    },
    ('知乎', 'detail'): {
        'list': [],
        'item': {
            '正文': ['content', 'excerpt', 'target.content'],
        },
    },
}


# =============================================================================
# 3. 建表（4 张独立新表，布局与 t_douyin_* 对齐；不动 t_basin_* / t_douyin_*）
# =============================================================================
def _ddl_article(tbl):
    return """
CREATE TABLE IF NOT EXISTS `%s` (
  `内容ID`     VARCHAR(96)  NOT NULL,
  `标题`       TEXT,
  `正文`       TEXT,
  `话题标签`   TEXT,
  `点赞数`     BIGINT       DEFAULT 0,
  `评论数`     BIGINT       DEFAULT 0,
  `收藏数`     BIGINT       DEFAULT 0,
  `分享数`     BIGINT       DEFAULT 0,
  `详情链接`   TEXT,
  `封面`       TEXT,
  `发布地区`   VARCHAR(32),
  `发布时间`   TEXT,
  `作者ID`     VARCHAR(64),
  `作者昵称`   TEXT,
  `作者主页`   VARCHAR(128),
  `平台`       VARCHAR(8),
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `目标省份`   VARCHAR(16),
  `采集时间`   DATETIME,
  PRIMARY KEY (`内容ID`),
  KEY `idx_platform` (`平台`),
  KEY `idx_basin` (`流域`),
  KEY `idx_topic` (`议题`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""" % tbl


def _ddl_comment(tbl):
    return """
CREATE TABLE IF NOT EXISTS `%s` (
  `评论ID`     VARCHAR(96)  NOT NULL,
  `评论内容`   TEXT,
  `评论时间`   TEXT,
  `点赞数`     BIGINT       DEFAULT 0,
  `回复数`     BIGINT       DEFAULT 0,
  `内容ID`     VARCHAR(96),
  `用户ID`     VARCHAR(64),
  `昵称`       TEXT,
  `性别`       VARCHAR(8),
  `用户地区`   VARCHAR(32),
  `用户主页`   VARCHAR(128),
  `平台`       VARCHAR(8),
  `流域`       VARCHAR(16),
  `议题`       VARCHAR(32),
  `命中关键词` VARCHAR(255),
  `采集时间`   DATETIME,
  PRIMARY KEY (`评论ID`),
  KEY `idx_content` (`内容ID`),
  KEY `idx_basin` (`流域`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""" % tbl


ARTICLE_COLS = ['内容ID', '标题', '正文', '话题标签', '点赞数', '评论数', '收藏数', '分享数',
                '详情链接', '封面', '发布地区', '发布时间', '作者ID', '作者昵称', '作者主页',
                '平台', '流域', '议题', '命中关键词', '目标省份', '采集时间']
COMMENT_COLS = ['评论ID', '评论内容', '评论时间', '点赞数', '回复数', '内容ID', '用户ID',
                '昵称', '性别', '用户地区', '用户主页', '平台', '流域', '议题',
                '命中关键词', '采集时间']


def ensure_tables(platforms=None):
    """为指定平台建表（幂等）。默认两个平台都建。"""
    platforms = platforms or list(PLATFORM_ADAPTERS.keys())
    made = []
    with engine.connect() as conn:
        for p in platforms:
            a_tbl, c_tbl = PLATFORM_ADAPTERS[p]['tables']
            conn.execute(text(_ddl_article(a_tbl)))
            conn.execute(text(_ddl_comment(c_tbl)))
            made += [a_tbl, c_tbl]
        conn.commit()
    _xz_logger.info('数据表已就绪：%s' % ' / '.join(made))
    print(' 数据表已就绪：%s' % ' / '.join(made))
    return made


# =============================================================================
# 4. 关键词矩阵
# =============================================================================
def build_keywords(basins=None, topics=None,
                   provinces_per_basin=None, keywords_per_topic=None):
    """构造「省份 × 议题词」矩阵，与微博/抖音同构。"""
    cfg = XZ_CONFIG
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
                words = LOCAL_TOPIC_KEYWORDS.get(topic, [])[:int(keywords_per_topic)]
                for w in words:
                    kw = '%s %s' % (prov, w)
                    if kw in seen:
                        continue
                    seen.add(kw)
                    items.append({'keyword': kw, 'basin': basin,
                                  'province': prov, 'topic': topic, 'topic_word': w})
    return items


def preview_keywords(kw_items):
    print('\n' + '=' * 72)
    print('小红书 / 知乎 采集 —— 关键词矩阵（共 %d 个）' % len(kw_items))
    print('=' * 72)
    grouped = {}
    for it in kw_items:
        grouped.setdefault((it['basin'], it['topic']), []).append(it['keyword'])
    for (basin, topic), kws in grouped.items():
        print('\n【%s · %s】%d 个' % (basin, topic, len(kws)))
        for i in range(0, len(kws), 4):
            print('   ' + '   '.join('%-16s' % k for k in kws[i:i + 4]))
    out = os.path.join(_SPIDER_DIR, 'xhs_zhihu_keywords_preview.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('小红书/知乎采集 —— 关键词矩阵（%s）\n共 %d 个关键词\n\n'
                % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(kw_items)))
        for it in kw_items:
            f.write('%-20s 流域=%-4s 议题=%-8s 省份=%s\n'
                    % (it['keyword'], it['basin'], it['topic'], it['province']))
    print('\n关键词清单已写入：%s' % out)


# =============================================================================
# 5. 采集：搜索结果
# =============================================================================
def _packet_body(packet):
    """从 DrissionPage 的 packet 里取响应体并解析成 dict；非 JSON 返回 None。"""
    if not packet:
        return None
    try:
        body = packet.response.body
    except Exception:
        return None
    if isinstance(body, (dict, list)):
        return body
    if not isinstance(body, str):
        return None
    body = body.strip()
    if not body.startswith(('{', '[')):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def crawl_articles(page, platform, kw_items, screens_per_keyword, dump_packet=False):
    """逐关键词打开搜索页，边下滑边监听搜索 XHR，累积去重。"""
    ad = PLATFORM_ADAPTERS[platform]
    collected, total = {}, len(kw_items)
    dumped = 0

    for idx, item in enumerate(kw_items, 1):
        keyword = item['keyword']
        basin, topic, province = item['basin'], item['topic'], item['province']
        print('\n [%d/%d] %s 关键词：【%s】  [%s · %s]'
              % (idx, total, platform, keyword, basin, topic))
        _xz_logger.info('[%d/%d] %s 搜索 %s (%s/%s)'
                        % (idx, total, platform, keyword, basin, topic))
        time.sleep(random.uniform(XZ_CONFIG['sleep_min'], XZ_CONFIG['sleep_max']))

        try:
            page.listen.start(ad['listen_search'])
            page.get(ad['search_url'](keyword))
            time.sleep(3)
            for s in range(screens_per_keyword):
                try:
                    page.scroll.to_bottom()
                except Exception:
                    pass
                time.sleep(random.uniform(1.5, 3.0))
                print('   第%d屏…' % (s + 1))

            n_pkt = 0
            while True:
                packet = page.listen.wait(count=1, timeout=2)
                if not packet:
                    break
                body = _packet_body(packet)
                if body is None:
                    continue
                n_pkt += 1
                if dump_packet and dumped < XZ_CONFIG['dump_max']:
                    dumped += 1
                    _dump('search_%s' % platform, body, dumped)
                for it in ad['pick_items'](body):
                    row = ad['norm_article'](it, (topic, keyword, basin, province))
                    if not row:
                        continue
                    cid = row['内容ID']
                    if cid in collected:
                        old = collected[cid]['命中关键词']
                        if keyword not in old.split('|'):
                            collected[cid]['命中关键词'] = old + '|' + keyword
                        continue
                    collected[cid] = row
                    raw_write(platform, 'article',
                              {'流域': basin, '议题': topic, '命中关键词': keyword,
                               '目标省份': province, '内容ID': cid}, it)
            page.listen.stop()
            print('   本词捕获 %d 个响应包，累计去重后 %d 条' % (n_pkt, len(collected)))
        except Exception as e:
            try:
                page.listen.stop()
            except Exception:
                pass
            _xz_logger.error('%s 关键词【%s】采集失败：%s' % (platform, keyword, e))
            print('   关键词【%s】采集失败：%s' % (keyword, e))

    return list(collected.values())


# =============================================================================
# 6. 采集：评论
# =============================================================================
def crawl_comments(page, platform, articles, limit, scrolls, dump_packet=False):
    """按评论数取前 limit 条内容，进详情页下滑评论区。

    监听**两个端点**（DrissionPage 的 targets 支持多值）：
      listen_comment —— 评论列表，产出 t_*_comment 行
      listen_detail  —— 笔记/回答详情，用来**补抓正文**（小红书搜索结果没有 desc）
    详情页本来就要打开，所以补正文是**顺带**的，不额外增加请求次数。
    ⚠️ 正文只覆盖「按评论数选中的前 limit 条」—— 没进详情页的那些仍是空。
    """
    ad = PLATFORM_ADAPTERS[platform]
    picked = sorted(articles, key=lambda x: safe_int(x['评论数']), reverse=True)[:limit]
    print('\n [%s] 已按评论数选出 %d 条内容抓取评论：' % (platform, len(picked)))
    print('-' * 64)
    for i, a in enumerate(picked, 1):
        preview = (a['标题'] or a['正文'] or '')[:26].replace('\n', ' ')
        print('  %2d. [评论数:%-6s] %s  [%s·%s]'
              % (i, a['评论数'], preview, a['流域'], a['议题']))
    print('-' * 64)

    detail_pats = _as_patterns(ad.get('listen_detail')) if XZ_CONFIG['fetch_body'] else ()
    targets = _as_patterns(ad['listen_comment']) + detail_pats

    all_comments, seen = [], set()
    body_updates = {}
    dumped = dumped_detail = 0

    for a in picked:
        ui = {'id': a['内容ID']}
        ctx = (a['议题'], a['命中关键词'], a['流域'], ui)
        url = ad['detail_url'](a)
        if not url:
            continue

        # ---- 知乎：评论走 API 主动拉取（页面滚动/点击不会自动触发评论 XHR）----
        if platform == '知乎':
            m = re.search(r'/answer/(\d+)', url) or re.search(r'/p/(\d+)', url)
            aid = m.group(1) if m else None
            if aid:
                try:
                    page.get(url)
                    time.sleep(2)
                    if XZ_CONFIG['fetch_body']:
                        txt = _detail_body_from_page(page)
                        if txt:
                            body_updates[a['内容ID']] = mask_pii_text(txt)
                    raws = _zhihu_fetch_comments(
                        page, aid,
                        XZ_CONFIG.get('zhihu_comments_per_article', 150),
                        dump_packet=dump_packet)
                    print('   [%s] 知乎 API 拉取评论 %d 条 [%s]'
                          % (platform, len(raws), a['内容ID']))
                    for c in raws:
                        row = ad['norm_comment'](c, ctx)
                        if not row or row['评论ID'] in seen:
                            continue
                        seen.add(row['评论ID'])
                        all_comments.append(row)
                        raw_write(platform, 'comment',
                                  {'流域': a['流域'], '议题': a['议题'],
                                   '命中关键词': a['命中关键词'],
                                   '目标省份': a['目标省份'],
                                   '内容ID': a['内容ID'],
                                   '评论ID': row['评论ID']}, c)
                except Exception as e:
                    _xz_logger.error('知乎评论采集异常(内容:%s)：%s' % (a['内容ID'], e))
                    print('   知乎评论采集异常(%s)：%s' % (a['内容ID'], e))
            continue

        try:
            page.listen.start(targets)
            page.get(url)
            time.sleep(2.5)
            for s in range(scrolls):
                try:
                    page.scroll.to_bottom()
                except Exception:
                    pass
                time.sleep(random.uniform(1.2, 2.4))
            print('   抓取 %s [%s] 评论区…' % (platform, a['内容ID']))

            # 详情页是服务端渲染的 —— 正文从页面自身取，不等 XHR
            if XZ_CONFIG['fetch_body']:
                txt = _detail_body_from_page(page)
                if txt:
                    body_updates[a['内容ID']] = mask_pii_text(txt)

            while True:
                packet = page.listen.wait(count=1, timeout=2)
                if not packet:
                    break
                body = _packet_body(packet)
                if body is None:
                    continue

                purl = _packet_url(packet)
                # ---- 详情包：抽正文（顺带 dump 供校准）----
                if detail_pats and any(pat in purl for pat in detail_pats):
                    if dump_packet and dumped_detail < XZ_CONFIG['dump_max']:
                        dumped_detail += 1
                        _dump('detail_%s' % platform, body, dumped_detail)
                    txt2 = _extract_body_text(platform, body)
                    if txt2:
                        body_updates.setdefault(a['内容ID'], mask_pii_text(txt2))
                    continue

                # ---- 评论包 ----
                if dump_packet and dumped < XZ_CONFIG['dump_max']:
                    dumped += 1
                    _dump('comment_%s' % platform, body, dumped)
                for c in ad['pick_comments'](body):
                    row = ad['norm_comment'](c, ctx)
                    if not row or row['评论ID'] in seen:
                        continue
                    seen.add(row['评论ID'])
                    all_comments.append(row)
                    raw_write(platform, 'comment',
                              {'流域': a['流域'], '议题': a['议题'],
                               '命中关键词': a['命中关键词'],
                               '目标省份': a['目标省份'],
                               '内容ID': a['内容ID'], '评论ID': row['评论ID']}, c)
            page.listen.stop()
            time.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            try:
                page.listen.stop()
            except Exception:
                pass
            _xz_logger.error('%s 评论采集异常(内容:%s)：%s' % (platform, a['内容ID'], e))
            print('   评论采集异常(%s)：%s' % (a['内容ID'], e))

    # 把详情页补抓到正文合并回文章行（同一列表对象，save_to_db 之前生效）
    for a in articles:
        txt = body_updates.get(a['内容ID'])
        if txt and not a.get('正文'):
            a['正文'] = txt
            raw_write(platform, 'article_body',
                      {'流域': a['流域'], '议题': a['议题'], '命中关键词': a['命中关键词'],
                       '目标省份': a['目标省份'], '内容ID': a['内容ID']}, {'正文': txt})

    if detail_pats:
        cov = len(body_updates)
        print('   [%s] 详情页补抓正文：%d 条命中（覆盖进过详情页的那 %d 条）'
              % (platform, cov, len(picked)))
        if cov == 0:
            print('   [WARN] 详情接口一条都没匹配上 —— 监听特征 listen_detail 可能失效，'
                  '请用 --dump-packet 核对（见文件头「待校准」）')
    elif platform == '知乎':
        print('   [知乎] 正文走 SSR（文章抓取阶段已取），评论阶段不监听详情 XHR，跳过补抓')

    return all_comments


def _dump(tag, body, idx=1):
    """把响应体落盘，供首跑字段名校准（不写库、不入 CSV）。"""
    path = os.path.join(_SPIDER_DIR, '_packet_%s_%d_%s.json'
                        % (tag, idx, datetime.now().strftime('%Y%m%d_%H%M%S')))
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        print('   [dump] 原始响应体已落盘，用于字段校准：%s' % os.path.basename(path))
    except Exception as e:
        print('   [dump] 落盘失败：%s' % e)


# =============================================================================
# 7. 入库（临时表 + INSERT ... ON DUPLICATE KEY UPDATE，与 douyin 同模式）
# =============================================================================
def save_to_db(platform, articles, comments):
    ad = PLATFORM_ADAPTERS[platform]
    a_tbl, c_tbl = ad['tables']
    art_n, com_n = 0, 0
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if articles:
        try:
            df = pd.DataFrame(articles)[ARTICLE_COLS].copy()
            for c in ('点赞数', '评论数', '收藏数', '分享数'):
                df[c] = df[c].map(safe_int)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(clean_text)
            slug = 'xhs' if platform == '小红书' else 'zhihu'
            df.to_csv(os.path.join(_SPIDER_DIR, '%s_articles_%s.csv' % (slug, stamp)),
                      index=False, encoding='utf-8-sig')
            print(' 内容 CSV：%s_articles_%s.csv' % (slug, stamp))

            tmp = '%s_temp' % a_tbl
            with engine.connect() as conn:
                df.to_sql(tmp, con=conn, if_exists='replace', index=False, chunksize=1000)
                cols = ', '.join('`%s`' % c for c in ARTICLE_COLS)
                conn.execute(text(
                    'INSERT INTO `%s` (%s) SELECT %s FROM `%s` '
                    'ON DUPLICATE KEY UPDATE '
                    '`标题`=VALUES(`标题`), `正文`=VALUES(`正文`), `点赞数`=VALUES(`点赞数`), '
                    '`评论数`=VALUES(`评论数`), `收藏数`=VALUES(`收藏数`), `分享数`=VALUES(`分享数`), '
                    '`流域`=VALUES(`流域`), `议题`=VALUES(`议题`), `命中关键词`=VALUES(`命中关键词`)'
                    % (a_tbl, cols, cols, tmp)))
                conn.commit()
                conn.execute(text('DROP TABLE IF EXISTS `%s`' % tmp))
            art_n = len(df)
            print(' 内容入库完成（%s）：%d 条' % (a_tbl, art_n))
        except Exception as e:
            _xz_logger.error('%s 内容入库失败：%s' % (platform, e))
            print(' 内容入库失败：%s' % e)

    if comments:
        try:
            df = pd.DataFrame(comments)[COMMENT_COLS].copy()
            for c in ('点赞数', '回复数'):
                df[c] = df[c].map(safe_int)
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].map(clean_text)
            slug = 'xhs' if platform == '小红书' else 'zhihu'
            df.to_csv(os.path.join(_SPIDER_DIR, '%s_comments_%s.csv' % (slug, stamp)),
                      index=False, encoding='utf-8-sig')
            print(' 评论 CSV：%s_comments_%s.csv' % (slug, stamp))

            tmp = '%s_temp' % c_tbl
            with engine.connect() as conn:
                df.to_sql(tmp, con=conn, if_exists='replace', index=False, chunksize=1000)
                cols = ', '.join('`%s`' % c for c in COMMENT_COLS)
                conn.execute(text(
                    'INSERT INTO `%s` (%s) SELECT %s FROM `%s` '
                    'ON DUPLICATE KEY UPDATE '
                    '`点赞数`=VALUES(`点赞数`), `回复数`=VALUES(`回复数`)'
                    % (c_tbl, cols, cols, tmp)))
                conn.commit()
                conn.execute(text('DROP TABLE IF EXISTS `%s`' % tmp))
            com_n = len(df)
            print(' 评论入库完成（%s）：%d 条' % (c_tbl, com_n))
        except Exception as e:
            _xz_logger.error('%s 评论入库失败：%s' % (platform, e))
            print(' 评论入库失败：%s' % e)

    print('\n [%s] 持久化完成：内容 %d 条，评论 %d 条' % (platform, art_n, com_n))
    return art_n, com_n


# =============================================================================
# 8. 离线自检（不联网、不写库；证明「响应 -> 表行」的映射正确）
# =============================================================================
def self_test():
    ok = fail = 0

    def chk(name, cond, extra=''):
        nonlocal ok, fail
        if cond:
            ok += 1
            print('  [OK]   %s' % name)
        else:
            fail += 1
            print('  [FAIL] %s %s' % (name, extra))

    ctx = ('医患矛盾', '湖北 医闹', '长江', '湖北')
    print('\n=== 1) 小红书：搜索响应 -> 内容行（fixture 按 2026-09-28 首跑 dump 的真实字段集构造）===')
    # 真实形状（见 _packet_search_小红书_*.json）：
    #   item = {id, model_type, xsec_token, note_card}
    #   note_card = {type, user, interact_info, cover, image_list, corner_tag_info[, display_title]}
    #   注意：**没有 desc**；发布时间只在 corner_tag_info
    xhs_body = {'success': True, 'code': 0, 'msg': '成功',
                'data': {'has_more': True, 'items': [
                    {'id': 'n1', 'model_type': 'note', 'xsec_token': 'ABC123',
                     'note_card': {
                         'type': 'video', 'display_title': '武汉某医院纠纷',
                         'user': {'user_id': 'u9', 'nickname': '路人甲', 'nick_name': '路人甲'},
                         'interact_info': {'liked': False, 'liked_count': '123',
                                           'collected': False, 'collected_count': '45',
                                           'comment_count': '6', 'shared_count': '2'},
                         'cover': {'url_default': 'http://x/y.jpg'},
                         'image_list': [{'url': 'http://x/i.jpg'}],
                         'corner_tag_info': [{'type': 'publish_time', 'text': '09-01'}]}},
                    # 第 2 条：无 display_title（实测 4/20 是这样，纯图笔记）
                    {'id': 'n2', 'model_type': 'note', 'xsec_token': 'DEF456',
                     'note_card': {
                         'type': 'normal',
                         'user': {'user_id': 'u8', 'nickname': '乙', 'nick_name': '乙'},
                         'interact_info': {'liked_count': '0', 'collected_count': '0',
                                           'comment_count': '0', 'shared_count': '0'},
                         'cover': {'url_default': 'http://x/z.jpg'},
                         'image_list': [{'url': 'http://x/j.jpg'}],
                         'corner_tag_info': [{'type': 'publish_time', 'text': '3天前'}]}}]}}
    items = _xhs_pick_items(xhs_body)
    chk('items 解析出 2 条', len(items) == 2, 'got %d' % len(items))
    row = _xhs_norm_article(items[0], ctx)
    chk('内容ID=n1', row and row['内容ID'] == 'n1')
    chk('标题=武汉某医院纠纷', row and row['标题'] == '武汉某医院纠纷')
    chk('点赞数=123', row and row['点赞数'] == '123')
    chk('评论数=6', row and row['评论数'] == '6')
    chk('收藏数=45', row and row['收藏数'] == '45')
    chk('分享数=2', row and row['分享数'] == '2')
    chk('昵称脱敏非空', row and row['作者昵称'] != '')
    chk('平台=小红书', row and row['平台'] == '小红书')
    chk('议题/流域/目标省份 齐全',
        row and (row['议题'], row['流域'], row['目标省份']) == ('医患矛盾', '长江', '湖北'))
    chk('表列齐全且与 DDL 同序', row and list(row.keys()) == ARTICLE_COLS)
    chk('详情链接带 xsec_token（首跑实测必需）',
        row and 'xsec_token=ABC123' in row['详情链接'], row and row['详情链接'])
    chk('发布时间从 corner_tag_info 取到（非空）', row and row['发布时间'] != '',
        'got %r' % (row and row['发布时间']))
    chk('发布时间归一为 YYYY-09-01', row and row['发布时间'].endswith('-09-01'),
        'got %r' % (row and row['发布时间']))
    chk('无 desc 时正文为空（已知限制，不编造）', row and row['正文'] == '')
    row2 = _xhs_norm_article(items[1], ctx)
    chk('无 display_title 时标题为空不报错', row2 is not None and row2['标题'] == '')
    chk('相对时间「3天前」已归一成日期',
        row2 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', row2['发布时间'] or ''),
        'got %r' % (row2 and row2['发布时间']))

    print('\n=== 2) 小红书：评论响应 -> 评论行 ===')
    xhs_cbody = {'success': True, 'data': {'comments': [{'id': 'c1', 'content': '太离谱了',
                 'user_info': {'user_id': 'u3', 'nickname': '网友乙'},
                 'like_count': '7', 'create_time': 1690000000000,
                 'ip_location': '上海', 'sub_comment_count': '1'}]}}
    cs = _xhs_pick_comments(xhs_cbody)
    chk('comments 解析出 1 条', len(cs) == 1)
    crow = _xhs_norm_comment(cs[0], ('医患矛盾', 'k', '长江', {'id': 'n1'}))
    chk('评论ID=c1', crow and crow['评论ID'] == 'c1')
    chk('内容ID 挂到 n1', crow and crow['内容ID'] == 'n1')
    chk('毫秒时间戳已转日期', crow and crow['评论时间'].startswith('2023-07-2'))
    chk('用户地区=上海', crow and crow['用户地区'] == '上海')
    chk('评论表列齐全', crow and list(crow.keys()) == COMMENT_COLS)

    print('\n=== 3) 知乎：搜索响应 -> 内容行 ===')
    zh_body = {'data': [{'type': 'search_result', 'object': {
        'type': 'answer', 'id': '888', 'title': '如何看待某地医闹事件',
        'excerpt': '事情经过是这样的……', 'created_time': 1690000000,
        'voteup_count': 42, 'comment_count': 3,
        'author': {'name': '知乎用户', 'url_token': 'zh1', 'id': 'a1'},
        'question': {'id': '666', 'title': '医闹'}, 'topics': [{'name': '医疗'}]}}]}
    zitems = _zhihu_pick_items(zh_body)
    chk('data 解析出 1 条', len(zitems) == 1)
    zrow = _zhihu_norm_article(zitems[0], ('医患矛盾', '湖北 医闹', '长江', '湖北'))
    chk('内容ID=answer_888', zrow and zrow['内容ID'] == 'answer_888')
    chk('点赞数=42', zrow and zrow['点赞数'] == '42')
    chk('平台=知乎', zrow and zrow['平台'] == '知乎')
    chk('链接含 question/answer', zrow and '/question/666/answer/888' in zrow['详情链接'])
    chk('内容表列齐全', zrow and list(zrow.keys()) == ARTICLE_COLS)

    print('\n=== 4) 知乎：评论响应 -> 评论行 ===')
    zh_cbody = {'data': [{'id': 'z9', 'content': '支持医生', 'created_time': 1690000000,
                          'like_count': 5, 'reply_count': 0,
                          'author': {'name': '丙', 'url_token': 'zh9', 'id': 'a9'}}]}
    zcs = _zhihu_pick_comments(zh_cbody)
    chk('评论 data 解析出 1 条', len(zcs) == 1)
    zcrow = _zhihu_norm_comment(zcs[0], ('医患矛盾', 'k', '黄河', {'id': 'answer_888'}))
    chk('评论ID=z9', zcrow and zcrow['评论ID'] == 'z9')
    chk('内容ID 挂到 answer_888', zcrow and zcrow['内容ID'] == 'answer_888')
    chk('评论表列齐全', zcrow and list(zcrow.keys()) == COMMENT_COLS)

    print('\n=== 5) 容错：空响应 / 缺字段 不抛异常 ===')
    chk('小红书空 items', _xhs_pick_items({}) == [])
    chk('知乎空 data', _zhihu_pick_items({'data': None}) == [])
    chk('缺 note_id -> None', _xhs_norm_article({'id': ''}, ctx) is None)
    chk('缺 oid -> None', _zhihu_norm_article({'object': {}}, ctx) is None)
    chk('性别 m -> 男', _norm_gender('m') == '男')
    chk('性别 2 -> 女', _norm_gender(2) == '女')
    chk('性别空 -> 未知', _norm_gender(None) == '未知')

    print('\n=== 6) 词表：三分类齐备、9 词、前 3 词跨三类 ===')
    words = LOCAL_TOPIC_KEYWORDS['医患矛盾']
    chk('医患矛盾 9 词', len(words) == 9, 'got %d' % len(words))
    chk('含消极词', '医闹' in words)
    chk('含中性词', '医患纠纷' in words)
    chk('含积极词', '医患互信' in words)

    print('\n=== 7) 关键词矩阵（默认三主题）===')
    kws = build_keywords(provinces_per_basin=2, keywords_per_topic=9)
    chk('矩阵非空', len(kws) > 0)
    chk('默认三主题', sorted(set(k['topic'] for k in kws)) == sorted([FOCUS_TOPIC_ECO, FOCUS_TOPIC_MEDICAL, '文旅']),
        'got %s' % sorted(set(k['topic'] for k in kws)))
    chk('关键词 = 省份+空格+词', all(k['keyword'] == '%s %s' % (k['province'], k['topic_word'])
                                  for k in kws))
    chk('生态治理 9 词 × 2 流域 × 2 省 = 36',
        len([k for k in kws if k['topic'] == FOCUS_TOPIC_ECO]) == 36,
        'eco=%d total=%d'
        % (len([k for k in kws if k['topic'] == FOCUS_TOPIC_ECO]), len(kws)))
    # --topic 覆写仍可生成医患矛盾关键词（保护历史能力）
    med_kws = build_keywords(topics=[FOCUS_TOPIC_MEDICAL], provinces_per_basin=2, keywords_per_topic=9)
    chk('--topic 医患矛盾 覆写仍可生成', len(med_kws) == 36, 'got %d' % len(med_kws))
    eco = [k['topic_word'] for k in kws if k['topic'] == FOCUS_TOPIC_ECO]
    chk('生态治理词表含消极/中性/积极',
        ('排污' in eco) and ('环保督察' in eco) and ('生态修复' in eco), 'got %s' % set(eco))
    med = [k['topic_word'] for k in med_kws if k['topic'] == FOCUS_TOPIC_MEDICAL]
    chk('医患词表含消极/中性/积极',
        ('医闹' in med) and ('医患纠纷' in med) and ('医患互信' in med), 'got %s' % set(med))

    print('\n=== 8) 原始数据留存（JSONL 开式 schema）===')
    XZ_CONFIG['keep_raw'] = True
    raw_write('小红书', 'article',
              {'流域': '长江', '议题': 'ZZTEST', '命中关键词': 'k',
               '目标省份': '湖北', '内容ID': 'n1'},
              {'id': 'n1', 'note_card': {'desc': '原始正文', 'image_list': [1, 2]}})
    raw_close()
    rp = raw_path('小红书', 'article', 'ZZTEST')
    chk('原始体文件已生成', os.path.exists(rp), rp)
    if os.path.exists(rp):
        lines = [ln for ln in open(rp, encoding='utf-8') if ln.strip()]
        chk('落盘 1 行', len(lines) == 1, 'got %d' % len(lines))
        rec = json.loads(lines[0])
        chk('保留原始对象（含归一表没有的 image_list）',
            rec.get('raw', {}).get('note_card', {}).get('image_list') == [1, 2])
        chk('带元数据（议题/内容ID/采集时间）',
            rec.get('议题') == 'ZZTEST' and rec.get('内容ID') == 'n1'
            and bool(rec.get('采集时间')))
        os.remove(rp)
        chk('清理后文件已删除', not os.path.exists(rp))
    XZ_CONFIG['keep_raw'] = False
    raw_write('小红书', 'article', {'议题': 'ZZTEST'}, {'id': 'n2'})
    raw_close()
    chk('--raw-off（keep_raw=False）时不落盘',
        not os.path.exists(raw_path('小红书', 'article', 'ZZTEST')))
    XZ_CONFIG['keep_raw'] = True

    print('\n=== 9) 多端点监听：详情包/评论包的区分与正文抽取 ===')
    chk('_as_patterns(str) -> 单元素 tuple', _as_patterns('comment/page') == ('comment/page',))
    chk('_as_patterns(list) -> tuple', _as_patterns(['a', 'b']) == ('a', 'b'))
    chk('_as_patterns(None) -> 空 tuple', _as_patterns(None) == ())
    chk('小红书 listen_detail 已配置', bool(_as_patterns(
        PLATFORM_ADAPTERS['小红书'].get('listen_detail'))))
    # 知乎正文走 SSR（_detail_body_from_page），listen_detail 故意为空：
    # 否则 'api/v4/answers' 子串会误吃 root_comments（真实评论）与 voters（点赞组件）
    chk('知乎 listen_detail 故意为空（正文走 SSR，避免误吃评论）',
        _as_patterns(PLATFORM_ADAPTERS['知乎'].get('listen_detail')) == ())

    class _Pkt:                       # 极简假包，只为验证 _packet_url 的容错
        def __init__(self, url):
            self.url = url

    class _BadPkt:
        @property
        def url(self):
            raise RuntimeError('no url')

    chk('_packet_url 取到 URL',
        _packet_url(_Pkt('https://edith.xiaohongshu.com/api/sns/web/v1/feed')) != '')
    chk('_packet_url 对异常包返回空串', _packet_url(_BadPkt()) == '')
    chk('_packet_url 对 None 返回空串', _packet_url(None) == '')

    dpat = _as_patterns(PLATFORM_ADAPTERS['小红书']['listen_detail'])
    chk('详情 URL 能被 listen_detail 命中',
        any(p in 'https://edith.xiaohongshu.com/api/sns/web/v1/feed' for p in dpat))
    chk('评论 URL 不会被误判成详情包',
        not any(p in 'https://edith.xiaohongshu.com/api/sns/web/v1/comment/page'
                for p in dpat))

    xhs_detail = {'data': {'items': [{'note_card': {'desc': '正文第一行\n第二行'}}]}}
    chk('小红书 详情包抽出正文', _extract_body_text('小红书', xhs_detail) == '正文第一行 第二行',
        'got %r' % _extract_body_text('小红书', xhs_detail))
    zh_detail = {'content': '<p>回答全文</p>'}
    chk('知乎 详情包抽出正文', _extract_body_text('知乎', zh_detail) == '<p>回答全文</p>',
        'got %r' % _extract_body_text('知乎', zh_detail))
    chk('抽不到正文返回空串（不抛、不猜）', _extract_body_text('小红书', {'data': {}}) == '')
    chk('未知平台返回空串', _extract_body_text('微博', xhs_detail) == '')

    print('\n=== 10) 正文回填规则（只填空、不覆盖已有）===')
    arts = [{'内容ID': 'a1', '正文': '', '流域': '长江', '议题': '医患矛盾',
             '命中关键词': 'k', '目标省份': '湖北'},
            {'内容ID': 'a2', '正文': '原有正文', '流域': '长江', '议题': '医患矛盾',
             '命中关键词': 'k', '目标省份': '湖北'}]
    updates = {'a1': '补抓正文', 'a2': '不该覆盖的正文'}
    XZ_CONFIG['keep_raw'] = False     # 本段只验合并逻辑，不落盘
    for a in arts:
        t = updates.get(a['内容ID'])
        if t and not a.get('正文'):
            a['正文'] = t
    XZ_CONFIG['keep_raw'] = True
    chk('空白正文被补上', arts[0]['正文'] == '补抓正文', 'got %r' % arts[0]['正文'])
    chk('已有正文不被覆盖', arts[1]['正文'] == '原有正文', 'got %r' % arts[1]['正文'])

    print('\n=== 11) FIELD_PROBES 字段契约一致性 ===')
    chk('覆盖 2 平台 × 3 类型',
        all((p, k) in FIELD_PROBES for p in ('小红书', '知乎')
            for k in ('article', 'comment', 'detail')))
    chk('声明的平台都在 adapter 里',
        all(p in PLATFORM_ADAPTERS for p, _ in FIELD_PROBES))
    chk('每个条目都有 list + item 声明',
        all(('list' in v and 'item' in v) for v in FIELD_PROBES.values()))
    chk('每个字段都有至少一条候选路径',
        all(bool(cands) for v in FIELD_PROBES.values() for cands in v['item'].values()))
    # 契约必须与归一函数读的字段同名 —— 防「改了归一函数忘了改契约」
    art_fields = set(FIELD_PROBES[('小红书', 'article')]['item'])
    chk('小红书内容契约含关键字段',
        {'内容ID', '标题', '点赞数', 'xsec_token', '发布时间'} <= art_fields,
        'got %s' % sorted(art_fields))
    cmt_fields = set(FIELD_PROBES[('小红书', 'comment')]['item'])
    chk('小红书评论契约含关键字段',
        {'评论ID', '评论内容', '评论时间', '点赞数', '回复数'} <= cmt_fields,
        'got %s' % sorted(cmt_fields))

    print('\n=== 12) 详情页正文补抓（服务端渲染路径）===')
    chk('_find_desc 递归找到 desc',
        _find_desc({'note': {'noteCard': {'a': 1, 'desc': '正文X'}}}) == '正文X',
        'got %r' % _find_desc({'note': {'noteCard': {'a': 1, 'desc': '正文X'}}}))
    chk('_find_desc 列表内也能找到',
        _find_desc({'note': [{'desc': '列表正文'}]}) == '列表正文')
    chk('_find_desc 无 desc 返回空', _find_desc({'note': {'title': 'T'}}) == '')
    chk('_find_desc 忽略空白 desc', _find_desc({'note': {'desc': '   '}}) == '')
    chk('_find_desc 深度上限不崩', _find_desc({'a': {'b': {'c': {}}}}) == '')
    chk('_detail_body_from_page 对坏 page 返回空（不抛）',
        _detail_body_from_page(object()) == '')

    print('\n=== 13) 已确认缺失字段的契约（探针不再报失败）===')
    for key in (('小红书', 'article'), ('小红书', 'comment')):
        pr = FIELD_PROBES[key]
        chk('%s/%s 声明了 absent' % key, bool(pr.get('absent')))
    chk('小红书评论 absent 含 性别',
        '性别' in FIELD_PROBES[('小红书', 'comment')]['absent'])
    chk('小红书搜索 absent 含 正文/发布地区',
        {'正文', '发布地区'} <= set(FIELD_PROBES[('小红书', 'article')]['absent']))

    print('\n' + '=' * 62)
    print('自检结果：通过 %d 项，失败 %d 项' % (ok, fail))
    print('=' * 62)
    return fail == 0


# =============================================================================
# 8.5 「只抓评论」模式：直接从库里取已有文章（跳过联网采集）
# =============================================================================
def _load_articles_from_db(platform, topics=None, basins=None):
    a_tbl, _ = PLATFORM_ADAPTERS[platform]['tables']
    cols = ', '.join('`%s`' % c for c in ARTICLE_COLS)
    sql = 'SELECT %s FROM `%s`' % (cols, a_tbl)
    wheres = []
    if topics:
        wheres.append("`议题` IN (%s)" % ','.join("'%s'" % t.replace("'", "''") for t in topics))
    if basins:
        wheres.append("`流域` IN (%s)" % ','.join("'%s'" % b.replace("'", "''") for b in basins))
    if wheres:
        sql += ' WHERE ' + ' AND '.join(wheres)
    with engine.connect() as c:
        rows = c.execute(text(sql)).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# 9. 主流程
# =============================================================================
def xz_job(argv=None):
    ap = argparse.ArgumentParser(prog='xhs_zhihu_spider.py',
                                 description='小红书/知乎 「医患矛盾」流域专项采集')
    ap.add_argument('--dry-run', action='store_true', help='只生成关键词矩阵，不联网不写库')
    ap.add_argument('--self-test', action='store_true', help='离线跑归一函数单测，不联网不写库')
    ap.add_argument('--ensure-tables-only', action='store_true', help='只建表后退出')
    ap.add_argument('--platform', action='append', choices=list(PLATFORM_ADAPTERS.keys()),
                    help='只抓指定平台，可重复（默认两个都抓）')
    ap.add_argument('--basin', action='append', choices=['黄河', '长江'], help='只抓指定流域')
    ap.add_argument('--topic', action='append', choices=list(LOCAL_TOPIC_KEYWORDS.keys()),
                    help='只抓指定议题（默认 医患矛盾）')
    ap.add_argument('--pages', type=int, help='每个关键词监听几屏')
    ap.add_argument('--no-comments', action='store_true', help='跳过评论抓取')
    ap.add_argument('--provinces-per-basin', type=int, help='每个流域取前 N 个省')
    ap.add_argument('--dump-packet', action='store_true', help='首跑落盘原始响应体用于字段校准')
    ap.add_argument('--raw-off', action='store_true',
                    help='不保留原始数据（默认保留到 spider/_raw/，供后续分析）')
    ap.add_argument('--comments-only', action='store_true',
                    help='跳过联网采集，直接对库里已有文章抓评论（省去文章采集耗时）')
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    platforms = args.platform or XZ_CONFIG['platforms']
    basins = args.basin or XZ_CONFIG['basins']
    topics = args.topic or XZ_CONFIG['topics']
    screens = args.pages if args.pages else XZ_CONFIG['screens_per_keyword']
    fetch_comments = XZ_CONFIG['fetch_comments'] and not args.no_comments
    ppb = (args.provinces_per_basin if args.provinces_per_basin
           else XZ_CONFIG['provinces_per_basin'])

    kw_items = build_keywords(basins=basins, topics=topics, provinces_per_basin=ppb)
    if not kw_items:
        print(' 关键词为空，请检查 --basin / --topic 参数。')
        return 1
    preview_keywords(kw_items)

    if args.ensure_tables_only:
        ensure_tables(platforms)
        return 0

    if args.dry_run or XZ_CONFIG['dry_run']:
        print('\n[dry-run] 仅预览，未发起任何请求、未写数据库。')
        return 0

    dump = args.dump_packet or XZ_CONFIG['dump_packet']
    keep_raw = XZ_CONFIG['keep_raw'] and not args.raw_off
    XZ_CONFIG['keep_raw'] = keep_raw
    comments_only = args.comments_only
    print('\n' + '=' * 72)
    print('即将开始抓取（%s）' % ' / '.join(platforms))
    print('  关键词 %d 个 × 每词 %d 屏 × %d 个平台'
          % (len(kw_items), screens, len(platforms)))
    print('  评论：%s' % ('开启（前 %d 条内容 × 下滑 %d 次）'
                        % (XZ_CONFIG['content_limit'], XZ_CONFIG['comment_scrolls'])
                        if fetch_comments else '关闭'))
    print('  议题：%s' % ' / '.join(topics))
    print('  原始数据：%s' % ('保留到 spider/_raw/（JSONL）' if keep_raw else '不保留'))
    print('  提示：需先在独立 profile（DrissionEdgeProfile）登录小红书 / 知乎。')
    print('=' * 72)

    ensure_tables(platforms)
    page = take_over_real_edge()
    if not page:
        print(' 浏览器接管失败，请确认 Edge 已安装后重试。')
        return 1

    t0 = time.time()
    for platform in platforms:
        ad = PLATFORM_ADAPTERS[platform]
        print('\n' + '#' * 72)
        print('# 平台：%s' % platform)
        print('#' * 72)
        page.get(ad['login_url'])
        time.sleep(2)

        if comments_only:
            arts = _load_articles_from_db(platform, topics=topics, basins=basins)
            print('\n [%s] 仅抓评论模式：已从库载入 %d 条已有文章'
                  % (platform, len(arts)))
        else:
            arts = crawl_articles(page, platform, kw_items, screens, dump_packet=dump)
            print('\n [%s] 内容抓取完毕，共 %d 条（已去重）' % (platform, len(arts)))
        _xz_logger.info('%s 内容抓取完毕，共 %d 条' % (platform, len(arts)))

        comments = []
        if fetch_comments and arts:
            comments = crawl_comments(page, platform, arts,
                                      XZ_CONFIG['content_limit'],
                                      XZ_CONFIG['comment_scrolls'], dump_packet=dump)
            print(' [%s] 评论抓取完毕，共 %d 条' % (platform, len(comments)))

        save_to_db(platform, arts, comments)

        if arts:
            print('\n 分布小结（%s · 内容）：' % platform)
            stat = {}
            for a in arts:
                stat[(a['流域'], a['议题'])] = stat.get((a['流域'], a['议题']), 0) + 1
            for (b, t), n in sorted(stat.items(), key=lambda x: -x[1]):
                print('   %-10s %-10s %5d' % (b, t, n))

    raw_close()
    if keep_raw:
        print('\n 原始数据已留存：%s' % _RAW_DIR)
        print('   （JSONL 开式 schema，含未脱敏作者字段 —— 仅供本地分析，勿提交仓库/勿对外发布）')

    print('\n 全部任务完成，耗时 %.1f 分钟' % ((time.time() - t0) / 60))
    return 0


if __name__ == '__main__':
    sys.exit(xz_job(sys.argv[1:]))
