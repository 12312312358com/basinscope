# -*- coding: utf-8 -*-
"""微博 `分类` 字段的受控词表与多维度归类器。

【为什么需要这个模块】
t_article.`分类` 存的是微博账号标签的**自由拼接串**，例如：
    "娱乐博主"、"娱乐博主 iPhone客户端"、"数码博主 微博原创视频博主"、
    "iPhone 17 Pro Max"、"HUAWEI Mate 60 Pro"
全表 29,710 行产生 **5,116 个互不相同的取值**，其中 90.5% 的取值样本数 ≤ 5；
拆词后 4,676 个词元里有 2,655 个只出现 1 次。

直接 `GROUP BY 分类` 再 `ORDER BY COUNT DESC` 取 Top-N、把剩余合并成「其他」，
是"结果几乎全部落到其他"的直接原因：
    Top10 只覆盖 18.72%，其余 81.28%（24,149 条）全部倒进「其他」。

【本模块的做法】
不做"先排序再截断"，而是**先归类再聚合**：
1) 标签切分：把拼接串按空白/顿号/逗号/竖线拆成独立词元（一条记录可含多个标签）；
2) 三维度归类（互相正交，可同时命中）：
     - domain  账号/话题领域（娱乐综艺、科技数码 ……）
     - cert    认证/身份类型（微博原创视频博主、头条文章作者 ……）
     - device  发布来源/设备（Apple、华为、OPPO ……）
3) 匹配顺序 = 先具体后笼统：关键词按长度降序匹配、认证规则按具体度排序，
   避免 "博主"、"视频" 这类泛词把 "微博原创视频博主" 提前短路；
4) 设备在**整串**上匹配（"iPhone 17 Pro Max" 被空格切碎后，Pro/17/Max 不构成独立标签）；
5) 未命中任何维度的词元进 unmapped 池并原样暴露，供词表迭代；
6) 「未标注领域」（原串本身不含领域信息，如只有设备标签）与「其他领域」
   （是博主但领域词不在词表内）**分列统计**，不混进一个万能「其他」桶。

纯标准库实现，无副作用、无数据库依赖，可被 Flask 应用与离线生成脚本共同导入。
"""

from __future__ import annotations

import re
from collections import Counter

__all__ = [
    'split_labels', 'classify_raw', 'aggregate_labels', 'domain_distribution',
    'DOMAIN_KEYWORDS', 'CERT_RULES', 'DEVICE_RULES',
    'UNLABELED_TEXT', 'OTHER_DOMAIN_TEXT',
]

# ---------------------------------------------------------------- 常量与词表

#: 标签分隔符：空白（含全角空格）、顿号、逗号、斜杠、竖线、加号、间隔号
LABEL_SPLIT = re.compile(r'[\s\u3000、,，/|｜+·]+')

UNLABELED_TEXT = '未标注领域'
OTHER_DOMAIN_TEXT = '其他领域'

#: 领域关键词表。键为受控类别，值为关键词列表。
#: 每个关键词只归属一个类别，保证 primary 归类无歧义。
DOMAIN_KEYWORDS = {
    '娱乐综艺': ['娱乐', '综艺', '明星', '电视剧', '电影', '短剧', '影视', '追剧', '偶像',
                 '演出', '颜值', '舞蹈', '音乐', '微小说', '剧迷', '搞笑', '幽默', '段子',
                 '吐槽', '娱评', '追星', '综艺感', '演员', '艺人', '剧场'],
    '体育健身': ['体育', '赛事', '足球', '篮球', '运动健身', '运动', '健身', '跑步', '网球',
                 '乒乓', '马拉松', '球迷', '冰雪'],
    '游戏电竞': ['游戏', '电竞', '手游', '主机游戏', '玩家', '网游'],
    '动漫二次元': ['动漫', '二次元', '漫画', '番剧', 'cosplay', '手办'],
    '科技数码': ['数码', '科技', '科学', '科普', '手机', '电脑', '互联网', '编程', '软件',
                 '硬件', '人工智能', '通信', '5g', '极客', '数码测评', 'ai', '相机',
                 '摄影器材', '无人机', '数码产品', 'html5', '前端', '数据科学'],
    '汽车出行': ['汽车', '车评', '汽车测评', '出行', '摩托', '新能源车', '车主', '试驾'],
    '财经职场': ['财经', '股市', '投资', '金融', '经济', '房产', '楼市', '商业', '创业',
                 '职场', '好物', '消费', '理财', '保险', '区块链', '基金', '股票', '顾问'],
    '母婴教育': ['母婴育儿', '育儿', '母婴', '亲子', '孕产', '教育', '校园', '考试', '学习',
                 '留学', '考研', '升学'],
    '文化读书': ['读书', '读物', '历史', '文化', '文学', '艺术', '收藏', '书法', '国学',
                 '纪录片', '佛学', '国画', '人文', '诗词', '作家', '网络作家', '诗人',
                 '代表作', '剧本'],
    '健康医疗': ['健康', '医疗', '养生', '瘦身', '疾病', '医生', '药', '中医', '心理',
                 '减脂', '营养'],
    '时尚美妆': ['时尚', '美妆', '穿搭', '护肤', '彩妆', '潮流', '发型', '香水', '模特'],
    '生活方式': ['美食', '家居', '宠物', '萌宠', '旅游', '摄影', '设计', '手工', '园艺',
                 '生活', '星座', '婚恋', '咖啡', '茶', '菜谱', '美食测评', '情感', '心灵',
                 '女性成长', '写真', '旅行', '民宿'],
    '社会民生': ['社会', '民生', '公益', '三农', '政务', '法律', '辟谣', '时政', '新闻',
                 '国际', '军事', '深度', '同城', '公安', '本地', '资讯', '时事', '退役军人',
                 '律师', '法官'],
}

#: 认证/身份规则：(受控类别, 正则)。**顺序即优先级**，具体在前、笼统在后。
CERT_RULES = [
    ('微博原创视频博主', r'原创视频博主'),
    ('微博剪辑视频博主', r'剪辑视频博主'),
    ('微博解说/译制视频博主', r'解说视频|译制视频'),
    ('微博VLOG博主', r'vlog'),
    ('微博视频号', r'视频号'),
    ('微博新知博主', r'新知博主|年度新知|新锐新知'),
    ('头条文章作者', r'头条文章作者'),
    ('本地资讯博主', r'本地资讯|本地博主|本地新势力'),
    ('超话主持人/粉丝', r'超话|创作官'),
    ('微博电视/娱评团成员', r'电视团|娱评团'),
    ('测评师/观察员', r'测评师|观察官|观察团|评论员|分析师'),
    ('问答答主', r'答主'),
    ('媒体/官方机构', r'媒体|官方|发布号|政务号|蓝v|法人微博'),
    ('内容创作者', r'内容创作者|创作者|签约作者'),
    ('泛领域博主', r'博主'),          # 领域维度未命中时的身份兜底，必须排在最后
]

#: 设备/来源规则：(受控类别, 正则)。按品牌具体度排序，在**整串**上匹配。
DEVICE_RULES = [
    ('Apple', r'iphone|ipad|ipod|ios|apple|macbook|\bmac\b'),
    ('华为/荣耀', r'huawei|华为|honor|荣耀|mate\s?\d|pura|nova|harmonyos|鸿蒙'),
    ('小米/红米', r'xiaomi|redmi|小米|红米'),
    ('OPPO/一加', r'oppo|oneplus|一加|find\s?[xX0-9]'),
    ('vivo/iQOO', r'vivo|iqoo'),
    ('三星', r'samsung|三星|galaxy'),
    ('Android 通用', r'android|安卓'),
    ('微博网页版', r'网页版|pc版|web版'),
    ('微博轻享版', r'轻享版'),
    ('其他客户端', r'客户端|\bapp\b'),
]

#: 微博站内功能/榜单标签：既非领域也非身份，单独归一类，避免污染领域分布
FUNCTION_LABELS = re.compile(r'^(实时|热门|榜单|印像|周末|新鲜事|超话榜|话题|微博搜索|'
                             r'头像本人|相册|关注|粉丝|置顶|微博|新时代)$')

# 领域关键词按长度降序预排序，实现"长词优先、具体优先"的匹配顺序
_DOMAIN_SORTED = sorted(
    ((kw.lower(), cat) for cat, kws in DOMAIN_KEYWORDS.items() for kw in kws),
    key=lambda kv: -len(kv[0]),
)
_CERT_COMPILED = [(cat, re.compile(pat, re.IGNORECASE)) for cat, pat in CERT_RULES]
_DEVICE_COMPILED = [(cat, re.compile(pat, re.IGNORECASE)) for cat, pat in DEVICE_RULES]

#: 需从词元上剥掉的后缀，剥离后再做领域匹配（"娱乐博主" -> "娱乐"）
_SUFFIX_RE = re.compile(r'(博主|认证|达人|大v|作者|创作者|观察官|测评师|资讯|栏目|栏目组|'
                        r'团成员|成员|官方|账号|号)$')

#: 设备型号碎片（"iPhone 17 Pro Max" 被空格切开后的 17 / Pro / Max / Mate / Find / Note …）
#: 仅当整串已命中某设备品牌时，这类纯 ASCII/数字词元才被判为型号碎片，不计入未映射池。
_MODEL_FRAG = re.compile(r'^[A-Za-z0-9+\-. ]{1,14}$')

#: 设备版本后缀（"华为 Mate 60 至尊版" 这类中文碎片，同样不计入未映射池）
_MODEL_FRAG_CN = re.compile(r'^(至尊版|典藏版|标准版|全网通|限量版|旗舰版|青春版|版)$')

#: 设备版本串（"超级Pro版" 这类中英混排碎片，整串已命中设备时同样不计入未映射）
_MODEL_FRAG_MIX = re.compile(r'^(超级|旗舰|增强|专业|高配)?[A-Za-z0-9]*(pro|max|plus|ultra|note|mate|find)?版$',
                             re.IGNORECASE)


def split_labels(raw):
    """把 `分类` 拼接串拆成词元列表（去空、去重、保序）。"""
    if not raw:
        return []
    out, seen = [], set()
    for tok in LABEL_SPLIT.split(str(raw).strip()):
        tok = tok.strip()
        if tok and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _match_domain(token):
    """在单个词元上匹配领域。返回 (受控类别, 命中的关键词) 或 None。

    先剥后缀再匹配，避免 "娱乐博主" 因含 "博主" 而被身份规则抢走；
    关键词按长度降序，保证 "运动健身" 优先于泛词 "运动"。
    """
    core = _SUFFIX_RE.sub('', token).lower()
    if not core:
        return None
    for kw, cat in _DOMAIN_SORTED:
        if kw in core:
            return cat, kw
    return None


def _match_by_rules(text, rules):
    for cat, rx in rules:
        if rx.search(text):
            return cat
    return None


def classify_raw(raw):
    """把一条 `分类` 原串归类（三维度正交，可同时命中）。

    返回 dict：
        raw       原始串
        domains   命中的领域列表（去重，按"命中关键词长度"降序，可能多个）
        primary   主领域（最具体的一个；无则 None）
        certs     命中的认证/身份列表
        devices   命中的设备/来源列表
        functions 站内功能标签
        unmapped  三个维度都没命中的词元（原样保留，供词表迭代）
    """
    s = '' if raw is None else str(raw)
    tokens = split_labels(s)
    domains, domain_scores = [], {}
    certs, devices, functions, unmapped = [], [], [], []
    trace = []          # 归类依据：(维度, 受控类别, 触发词元/关键词)

    # 设备优先在整串上匹配："iPhone 17 Pro Max" 被空格切碎后，碎片不构成独立标签
    whole_device = _match_by_rules(s, _DEVICE_COMPILED)
    if whole_device:
        devices.append(whole_device)
        trace.append(('device', whole_device, s))

    for tok in tokens:
        hit = False

        m = _match_domain(tok)
        if m:
            cat, kw = m
            hit = True
            trace.append(('domain', cat, '%s<-关键词"%s"' % (tok, kw)))
            if cat not in domain_scores:
                domains.append(cat)
                domain_scores[cat] = len(kw)
            else:
                domain_scores[cat] = max(domain_scores[cat], len(kw))

        c = _match_by_rules(tok, _CERT_COMPILED)
        if c:
            hit = True
            trace.append(('cert', c, tok))
            if c not in certs:
                certs.append(c)

        d = _match_by_rules(tok, _DEVICE_COMPILED)
        if d:
            hit = True
            if d not in devices:
                devices.append(d)
                trace.append(('device', d, tok))

        if FUNCTION_LABELS.match(tok):
            hit = True
            functions.append(tok)
            trace.append(('function', tok, tok))

        if not hit:
            # 整串已识别出设备品牌 + 词元是型号碎片 -> 归设备，不算未映射
            if whole_device and (_MODEL_FRAG.match(tok) or _MODEL_FRAG_CN.match(tok)
                                 or _MODEL_FRAG_MIX.match(tok)):
                trace.append(('device', whole_device, '%s(型号碎片)' % tok))
                continue
            unmapped.append(tok)
            trace.append(('unmapped', '-', tok))

    # 主领域：命中关键词越长越具体，取最具体的一个
    domains.sort(key=lambda c: -domain_scores.get(c, 0))
    primary = domains[0] if domains else None

    return {
        'raw': s,
        'domains': domains,
        'primary': primary,
        'certs': certs,
        'devices': devices,
        'functions': functions,
        'unmapped': unmapped,
        'trace': trace,
    }


def aggregate_labels(grouped_rows, top_n=None, unlabeled_text=UNLABELED_TEXT,
                     other_text=OTHER_DOMAIN_TEXT):
    """对 `(分类原串, 计数)` 序列做受控归类与聚合。

    参数
    ----
    grouped_rows : iterable[(str, int)]
        形如 `SELECT 分类, COUNT(*) FROM t_article GROUP BY 分类` 的结果。
    top_n : int | None
        仅截断返回的展示列表；**不参与归类、不产生「其他」堆积**——
        这是与旧实现（先排序再截断）的关键区别。

    返回 dict：
        rows_total   参与归类的总行数
        domain       {'dist': 含"未标注领域"的完整分布,
                      'dist_labeled': 仅已标注样本的分布(占比基数为 labeled_rows),
                      'labeled_rows', 'labeled_rate', 'multi_label_rows'}
        domain_multi 多标签领域计数（一行计入多个领域，忠实反映多标签）
        cert/device/function  各维度的分布
        unmapped     未命中词元池（含 rate）
        audit        覆盖率与兜底率的结构化体检结果
    """
    total = 0
    dom_counter = Counter()
    dom_multi = Counter()
    cert_counter = Counter()
    dev_counter = Counter()
    fn_counter = Counter()
    unmapped = Counter()
    unlabeled_rows = 0
    other_domain_rows = 0
    multi_label_rows = 0

    for raw, cnt in grouped_rows:
        try:
            cnt = int(cnt)
        except (TypeError, ValueError):
            continue
        if cnt <= 0:
            continue
        total += cnt
        res = classify_raw(raw)

        if len(res['domains']) > 1:
            multi_label_rows += cnt
        for c in res['domains']:
            dom_multi[c] += cnt

        if res['primary']:
            dom_counter[res['primary']] += cnt
        elif res['certs'] and '泛领域博主' in res['certs']:
            # 是博主身份，但领域词不在词表内 -> 单列，不混进"未标注"
            dom_counter[other_text] += cnt
            other_domain_rows += cnt
        else:
            # 只有设备/认证/功能标签，原串本身不含领域信息
            dom_counter[unlabeled_text] += cnt
            unlabeled_rows += cnt

        for c in res['certs']:
            cert_counter[c] += cnt
        for d in res['devices']:
            dev_counter[d] += cnt
        for f in res['functions']:
            fn_counter[f] += cnt
        for u in res['unmapped']:
            unmapped[u] += cnt

    labeled = total - unlabeled_rows
    dist = dom_counter.most_common()
    dist_labeled = [(k, v) for k, v in dist if k != unlabeled_text]
    if top_n:
        dist = dist[:top_n]
        dist_labeled = dist_labeled[:top_n]

    return {
        'rows_total': total,
        'domain': {
            'dist': [[k, v] for k, v in dist],
            'dist_labeled': [[k, v] for k, v in dist_labeled],
            'labeled_rows': labeled,
            'labeled_rate': round(labeled / total * 100, 2) if total else 0.0,
            'multi_label_rows': multi_label_rows,
        },
        'domain_multi': [[k, v] for k, v in dom_multi.most_common()],
        'cert': {'dist': [[k, v] for k, v in cert_counter.most_common()]},
        'device': {'dist': [[k, v] for k, v in dev_counter.most_common()]},
        'function': {'dist': [[k, v] for k, v in fn_counter.most_common()]},
        'unmapped': {
            'dist': [[k, v] for k, v in unmapped.most_common(50)],
            'rows': sum(unmapped.values()),
            'rate': round(sum(unmapped.values()) / total * 100, 2) if total else 0.0,
        },
        'audit': _audit(total, dom_counter, unmapped, unlabeled_rows, other_domain_rows),
    }


def domain_distribution(grouped_rows, max_slices=None, include_unlabeled=False):
    """把 `(分类, 计数)` 直接聚合成前端饼图/树图要的 `[{'name','value'}]`。

    与旧实现（page.py 里"排序 -> 取前 10 -> 其余归其他"）的区别：
      - 占比基数为**已标注领域样本**，未标注行默认不作为扇形，
        避免它变成一个大「其他」把其余类别压成细线；
      - 未标注样本量通过 `unlabeled_rows / labeled_rate` 显式返回，
        调用方应把它展示成"覆盖率"指标，而不是隐藏的兜底桶；
      - `max_slices` 只截断**展示条数**，不参与归类，也不产生归并桶。

    返回 dict：{'items', 'categories', 'rows_total', 'labeled_rows', 'labeled_rate',
                'unlabeled_rows', 'unlabeled_rate', 'other_domain_rate',
                'catch_all_rate', 'vocab_ok'}
    """
    agg = aggregate_labels(grouped_rows)
    audit = agg['audit']
    base = agg['domain']['dist'] if include_unlabeled else agg['domain']['dist_labeled']
    items = [{'name': k, 'value': v} for k, v in base]
    if max_slices:
        items = items[:max_slices]
    return {
        'items': items,
        'categories': len(base),
        'rows_total': agg['rows_total'],
        'labeled_rows': agg['domain']['labeled_rows'],
        'labeled_rate': agg['domain']['labeled_rate'],
        'unlabeled_rows': audit.get('unlabeled_rows', 0),
        'unlabeled_rate': audit.get('unlabeled_rate', 0.0),
        'other_domain_rate': audit.get('other_domain_rate', 0.0),
        'catch_all_rate': audit.get('catch_all_rate', 0.0),
        'vocab_ok': audit.get('vocab_ok', False),
    }


def _audit(total, dom_counter, unmapped, unlabeled_rows, other_domain_rows):
    """结构化体检：把"其他类边界"拆成两个可分别监控的指标，而不是静默接受。

    - other_domain_rate  长尾归并率：是博主但领域词不在词表内 -> **词表问题**，
      这是旧实现 81.28% 塌陷的等价指标，必须低。
    - unmapped_rate      未映射词元词频占比 -> **词表问题**，同样必须低。
    - unlabeled_rate     原串本身不含领域信息（只有设备/认证/功能标签）
      -> **数据缺口**，靠加词表解决不了，必须靠正文内容分类或补采账号标签。
    """
    if not total:
        return {}
    other_rate = other_domain_rows / total
    unmapped_rate = sum(unmapped.values()) / total
    return {
        'rows_total': total,
        'domain_categories': len(dom_counter),
        'other_domain_rows': other_domain_rows,
        'other_domain_rate': round(other_rate * 100, 2),
        'unlabeled_rows': unlabeled_rows,
        'unlabeled_rate': round(unlabeled_rows / total * 100, 2),
        'catch_all_rows': other_domain_rows + unlabeled_rows,
        'catch_all_rate': round((other_domain_rows + unlabeled_rows) / total * 100, 2),
        'unmapped_tokens': len(unmapped),
        'unmapped_rate': round(unmapped_rate * 100, 2),
        # 词表健康度：只对"可通过补词表改善"的两项设阈值
        'vocab_ok': other_rate <= 0.05 and unmapped_rate <= 0.10,
    }
