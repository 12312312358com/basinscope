# -*- coding: utf-8 -*-
"""
流域专题数据构建（长江 / 黄河）
--------------------------------------------------
数据源：db_weibo_basin 的 t_basin_article / t_basin_comment
议题口径：只保留「生态治理」「文旅」两个议题（新作品的聚焦范围）
输出：basin_data.json —— 供 build_unified_page.py 的 basin_views() 使用

批次 1（词云改造）新增字段：
  byTopic[t].clusters  事件簇统计（释义/篇数/跨度/互动/省份/3 条代表原文/词云可见词）
  byTopic[t].merge     同义归并（明细词 → 概念总量，篇数口径）
  byTopic[t].coverage  簇覆盖率与簇间重叠（防止把「没被簇覆盖」误读成「没有舆情」）
  wordsCloud           词云专用词表 [[词, 篇数, 组名, 色]]，组成员 = Top60 ∪ 三议题簇词表
  口径细节见 dashboard_gen/event_clusters.py 的文件头。

批次 2（恢复被精简掉的 8 个维度）新增字段：
  trend     月度声量（全量 + 分议题）/ 年×月矩阵 / 峰值月 / 2026 集中度（采样偏差量化）
  channel   话语主体受控归类（官方/媒体/个人/终端标识/未归类）+ 可判定率 + 规则表
  interact  赞:评:转 结构与单篇均值、转赞比（分议题 + 全流域）
  nodes     作者榜（脱敏）、集中度曲线、官方 vs 个人、每个事件的首发者
  events    byTopic[t].clusters 内的 sent（情感构成）与 first（首发者）
  risk      规则化四级评分 + 逐事件计分明细（四项因子、原始值、归一值、加权分）
  cmt      评论侧扩充（24 小时 / 长度 / 情感 / 议题 / 用户集中度）
  calib     情感模型校准实测（中性占比、极端值占比、词典法交叉一致性、不一致样例）
  cross     跨平台对照现状（抖音两表结构 + 实际条数）
  口径细节见 dashboard_gen/basin_modules.py 的文件头。

原则：所有数字都来自 SQL 聚合或对真实文本的分词统计，无一处估值。
      样本量不足时如实标注（例如评论），不做外推。
"""
import os
import io
import json
import re
import datetime
from collections import Counter

import pymysql
from pymysql.cursors import DictCursor
import jieba

import event_clusters as EC          # 事件簇词表（常量表，零依赖；批次 1 新增）
import basin_modules as BM          # 模块级规则表（渠道归类 / 风险分级 / 校准词典；批次 2 新增）
import basin_geo as BGEO            # 地理常量表（干流示意走向 / 山东地市；批次 3 首页新增）

BASE = os.path.dirname(os.path.abspath(__file__))
DB = dict(host=os.getenv('DB_HOST', 'localhost'),
          port=int(os.getenv('DB_PORT', '3306')),
          user=os.getenv('DB_USER', 'root'),
          password=os.getenv('DB_PASSWORD', ''),
          database=os.getenv('DB_NAME', 'db_weibo_basin'),
          charset='utf8mb4')

# 微博聚焦议题 = 本作品三大主题（生态环境治理 / 文旅 / 医患矛盾）。
# 库内另有「社会治理」为兜底类（关键词未命中其他议题），只作占比分母、不展开。
TOPICS = ('生态治理', '文旅', '医患矛盾')
BASINS = ('长江', '黄河')

# 评论样本闸门：低于该数量时，评论相关结论一律标注「样本不足，不外推」
COMMENT_GATE = 30

# 34 个省级行政区（国标口径，港澳台按中国省级行政区处理）
PROVS = set('''北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽
福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏
陕西 甘肃 青海 宁夏 新疆 台湾 香港 澳门'''.split())

STOP = set("""
的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己
这 那 我们 他们 什么 可以 这个 那个 但是 因为 所以 如果 还是 已经 现在 就是 这样 让 被
把 给 对 从 而且 以及 或者 并 与 及 等 之 其 该 这些 那些 一些 时候 问题 事情 地方 应该
需要 可能 表示 认为 觉得 知道 出来 起来 下来 过来 一下 一起 一直 一定 一样 之后 之前
今天 昨天 明天 大家 网友 微博 转发 评论 点赞 真的 不是 没有 还有 这么 那么 怎么 为什么
什么 时候 进行 通过 关于 对于 由于 为了 并且 虽然 然而 因此 于是 目前 已经 正在 表示
出现 发生 导致 造成 影响 相关 有关 方面 情况 工作 建设 发展 中国 我国 全国 各地
全文 网页链接 展开 查看更多 客户端 视频 图片 回复 分享 链接 内容 文章 消息 报道 记者
媒体 网友 大家 一起 真是 实在 简直 居然 竟然 然后 接着 于是 也就是说 所谓
""".split())


def pct(n, d):
    return round(n * 100.0 / d, 1) if d else 0.0


def parse_year(s):
    """从发布时间里取年份（容错空值/异常格式）"""
    m = re.match('^([0-9]{4})', str(s or '').strip())
    return m.group(1) if m else None


def parse_month(s):
    m = re.match('^([0-9]{4})-([0-9]{2})', str(s or '').strip())
    return m.group(1) + '-' + m.group(2) if m else None


def geo_prov(v):
    """「发布地区」→ 省级行政区名（作者 IP 属地口径）。

    归一规则：去掉「来自 / 发布于 / IP属地」前缀；「中国香港」→「香港」。
    返回 None 表示该条不是可用的省级值（空、未知、境外、异常串），
    调用方需据此如实统计缺失率 —— 该字段实测缺失过半，不能当全量用。
    """
    s = str(v or '').strip()
    if not s:
        return None
    s = re.sub(r'^(来自|发布于|IP\s*属地)\s*[:：]?\s*', '', s).strip()
    if s.startswith('中国') and s[2:] in PROVS:
        return s[2:]
    return s if s in PROVS else None


def mc(counter, n=None):
    """Counter → 按「计数降序、词名升序」确定性排序的 list。

    为什么不用 `Counter.most_common()`（2026-10-07 修）：
    上游 SELECT 没有 ORDER BY，行序由 MySQL 随意返回 → Counter 的
    **插入顺序**随之变化；而 `most_common()` 对**同计数**的排序沿用插入序
    → 同一份数据两次构建，词频榜里同分词的先后会翻转。
    实测：长江 byTopic/生态治理 第 23~24 位「新闻/环境」都是 26，
    两次构建互换了位置；黄河 wordsCloud 第 30~31 位同样翻转。
    词云与热词榜都直接展示这个顺序 → **页面上肉眼可见地抖动**。
    加词名做次级键后总序唯一，与行序彻底解耦。
    """
    items = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return items[:n] if n is not None else items


def mc_top(counter, default=None):
    """取计数最高的一项；**并列时按 key 升序**保证可复现。

    `Counter.most_common(1)[0][0]` 在并列时沿用插入序 → 同一份数据两次构建
    可能给同一个作者/同一个月不同的「主要渠道」「主要议题」。
    这类 argmax 用在**只显示单个值**的地方，比排行榜更隐蔽：
    榜单顺序变了读者还能看出来，单值漂移往往无人察觉。
    """
    if not counter:
        return default
    return mc(counter, 1)[0][0]


def words_of(text):
    """分词并过滤：停用词、单字、以及不含汉字的碎片（'...' / 英文 / 数字）"""
    out = []
    for w in jieba.cut(str(text or '')):
        w = w.strip()
        if len(w) < 2 or w in STOP:
            continue
        if not re.search('[一-龥]', w):
            continue
        out.append(w)
    return out


def sentiment_of(text, sn):
    """snownlp 情感极性 → 正/中/负（长文截断到 300 字，避免拖慢）"""
    return sent_pair(text, sn)[0]


def sent_pair(text, sn):
    """→ (档位 or None, 原始极性分 p or None)

    批次 2 新增：校准模块需要**原始分**才能量化「偏两端」这件事
    （只看三档占比是看不出模型把 0.41 和 0.99 都算成"负面"的）。
    """
    s = str(text or '').strip()[:300]
    if not s:
        return None, None
    try:
        p = sn(s).sentiments
    except Exception:
        return None, None
    if p >= 0.60:
        return '正面', p
    if p <= 0.40:
        return '负面', p
    return '中性', p


def dict_sent(text):
    """词典法极性（极性子词典计数，批次 2 的交叉验证基准，不是替代模型）"""
    t = str(text or '')
    pos = sum(1 for w in BM.CALIB_POS if w in t)
    neg = sum(1 for w in BM.CALIB_NEG if w in t)
    if pos > neg:
        return '正面', pos, neg
    if neg > pos:
        return '负面', pos, neg
    return '中性', pos, neg


# ==================================================================
# 事件簇统计（批次 1 新增）
# ------------------------------------------------------------------
# 口径（与 docs/双流域专题-内容深化方案.md 完全一致，改口径必须同时改文档）：
#   命中判定：正文包含该簇任一词（等价于 SQL 的 `微博内容 LIKE '%词%'`）
#             —— **不匹配「命中关键词」字段**，那是采集端配额标记，不是内容证据
#   去重键  ：微博ID
#   簇间关系：允许重叠（实测「消费」同属两簇），故各簇篇数不可相加
# 为什么在 Python 侧算而不是再查 22 次库：文章行已全部载入内存，子串匹配等价且快得多。
# ==================================================================
def hits_of(rows, words):
    """命中任一词的微博（按 微博ID 去重，同 ID 只留首条）"""
    uniq = {}
    for r in rows:
        txt = str(r.get('微博内容') or '')
        if not txt:
            continue
        for w in words:
            if w in txt:
                uniq.setdefault(r['微博ID'], r)
                break
    return list(uniq.values())


def engagement(r):
    return int(r['点赞数'] or 0) + int(r['评论数'] or 0) + int(r['转发数'] or 0)


def cluster_stats(rows, basin, topic, wfreq):
    """算出某流域某议题下每个事件簇的统计量。

    wfreq：全量词频表（Counter），用于标注「本簇词里哪些能在词云上看到」——
           词表是短语级的，jieba 可能把「生态修复」切碎、把「退捕」切成单字滤掉，
           所以词云可见词往往少于词表本身，前端会如实说明差了几个。
    返回 (clusters, ids_by_name)
    """
    out, ids_by_name = [], {}
    for name, words, gloss, color in EC.clusters_of(basin, topic):
        hit = hits_of(rows, words)
        if not hit:
            continue                       # 0 篇的簇不进页面，避免空卡
        ids_by_name[name] = {r['微博ID'] for r in hit}
        times = [str(r['发布时间'])[:10] for r in hit if r['发布时间']]
        top = sorted(hit, key=engagement, reverse=True)[:3]
        prov = mc(Counter((r['目标省份'] or '未标注') for r in hit), 4)
        visible = [w for w in words if wfreq.get(w)]
        out.append({
            'name': name, 'words': words, 'gloss': gloss, 'color': color,
            'n': len(hit),
            't0': min(times) if times else '-',
            't1': max(times) if times else '-',
            'rep': sum(int(r['转发数'] or 0) for r in hit),
            'cmt': sum(int(r['评论数'] or 0) for r in hit),
            'lk': sum(int(r['点赞数'] or 0) for r in hit),
            'prov': [[k, int(v)] for k, v in prov],
            'vis': visible, 'nvis': len(visible),
            'ev': [{'txt': str(r['微博内容'] or '').replace('\n', ' ')[:150],
                    'au': r['作者昵称'] or '-',
                    'tm': str(r['发布时间'] or '')[:10],
                    'pv': r['目标省份'] or '-',
                    'eng': engagement(r),
                    'rep': int(r['转发数'] or 0), 'lk': int(r['点赞数'] or 0),
                    'url': r['微博链接'] or ''} for r in top],
        })
    out.sort(key=lambda c: -c['n'])
    return out, ids_by_name


def coverage_of(ids_by_name, topic_rows):
    """簇覆盖率：被任一簇覆盖的篇数 / 议题总篇数；附簇间重叠篇数"""
    cnt = Counter()
    for ids in ids_by_name.values():
        for x in ids:
            cnt[x] += 1
    covered = len(cnt)
    return {
        'topicRows': topic_rows,
        'covered': covered,
        'pct': pct(covered, topic_rows),
        'overlap': sum(1 for v in cnt.values() if v > 1),
    }


def merge_stats(rows, basin, topic):
    """同义归并：明细词 → 概念总量（篇数口径；与词频口径的「次」不是一回事）"""
    out = []
    for g in EC.merge_groups_of(basin, topic):
        hit = hits_of(rows, g['words'])
        out.append({'label': g['label'], 'words': g['words'], 'note': g['note'],
                    'n': len(hit)})
    return out


# ==================================================================
# 批次 2：恢复被精简掉的 8 个维度所需的聚合
# ------------------------------------------------------------------
# 全部为只读统计：不改库、不新增采集、不外推。样本不足处只描述现象并标注。
# ==================================================================
def _minmax(vals):
    """→ (归一化列表, 最小值, 最大值)；全相等时一律给 0，避免除以 0 造出假区分度"""
    lo, hi = (min(vals), max(vals)) if vals else (0, 0)
    if hi <= lo:
        return [0.0 for _ in vals], lo, hi
    return [(v - lo) * 1.0 / (hi - lo) for v in vals], lo, hi


def trend_stats(A, sentById):
    """传播趋势与节奏：月度声量 + 年×月矩阵 + 峰值 + 采集集中度（采样偏差量化）"""
    ym, byTopicM = Counter(), {t: Counter() for t in TOPICS}
    for r in A:
        m = parse_month(r['发布时间'])
        if not m:
            continue
        ym[m] += 1
        byTopicM[r['议题']][m] += 1
    months = sorted(ym.items())
    yrs = sorted({m[:4] for m in ym})
    mat = [[ym.get('%s-%02d' % (y, i + 1), 0) for i in range(12)] for y in yrs]
    tot = sum(ym.values()) or 1
    # 并列时按月份名升序，避免同一份数据两次构建给出不同「峰值月」
    peak = (mc_top(ym, '-'), max(ym.values())) if ym else ('-', 0)
    # 「17 个词×近 8 天」式的热力卡需要 0 值也保留格位，故矩阵按全量月份铺满
    span = [m for m in ('%s-%02d' % (y, i + 1) for y in yrs for i in range(1, 13))]
    full = [ym.get(m, 0) for m in span]
    # 采集集中度：最近 12 个月 / 全部
    last12 = sorted(ym)[-12:]
    c12 = sum(ym[m] for m in last12)
    cut = max((str(r['采集时间'])[:10] for r in A if r.get('采集时间')), default='-')
    return {
        'months': months,
        'byTopic': {t: sorted(byTopicM[t].items()) for t in TOPICS},
        'years': yrs,
        'mat': mat,                       # 行 = 年，列 = 1~12 月
        'matX': ['%d月' % (i + 1) for i in range(12)],
        'span': span, 'full': full,       # 连续月份序列（含 0 值空档）
        'peak': [peak[0], peak[1], pct(peak[1], tot)],
        'n2026': sum(v for k, v in ym.items() if k.startswith('2026')),
        'last12': [last12[0], last12[-1], c12, pct(c12, tot)],
        'y2026pct': pct(sum(v for k, v in ym.items() if k.startswith('2026')), tot),
        'cut': cut,                       # 采集截止日（最后一个月是断月，必须标注）
        'lastMonth': last12[-1],
        'lastPartial': bool(months and months[-1][0] == cut[:7]),
    }


def channel_stats(A):
    """发布渠道与话语主体：受控归类 + 可判定率 + 未归类样例（可复核）"""
    kind, raw, byTopic, how = Counter(), Counter(), {t: Counter() for t in TOPICS}, {}
    for r in A:
        c = r['分类'] or '未标注'
        k, h = BM.classify_channel(c)
        kind[k] += 1
        raw[c] += 1
        byTopic[r['议题']][k] += 1
        how.setdefault(k, Counter())[h] += 1
    agent = sum(kind[k] for k in BM.AGENT_ORDER)
    unk = kind.get(BM.UNKNOWN_CN, 0)
    dev = kind.get(BM.DEVICE_CN, 0)
    # 未归类 / 终端样例（各取篇数最高的 8 个原值，页面上可逐条核对）
    def _sample(target):
        return [[c, n] for c, n in mc(raw)
                if BM.classify_channel(c)[0] == target][:8]
    return {
        'kind': [[k, kind.get(k, 0)] for k in BM.AGENT_ORDER + (BM.DEVICE_CN, BM.UNKNOWN_CN)],
        'agentKnown': agent, 'agentPct': pct(agent, len(A)),
        'device': dev, 'unknown': unk,
        'byTopic': {t: [[k, byTopic[t].get(k, 0)] for k in BM.AGENT_ORDER] for t in TOPICS},
        'top': [[c, n, BM.classify_channel(c)[0], BM.classify_channel(c)[1]]
                for c, n in mc(raw, 12)],
        'unkSample': _sample(BM.UNKNOWN_CN),
        'devSample': _sample(BM.DEVICE_CN),
        'rules': BM.CHANNEL_RULES,
    }


def interact_stats(A):
    """互动结构与扩散效率：三指标构成、单篇均值、转赞比（分议题 + 全流域）"""
    def one(rows):
        n = len(rows) or 1
        lk = sum(int(r['点赞数'] or 0) for r in rows)
        cm = sum(int(r['评论数'] or 0) for r in rows)
        rp = sum(int(r['转发数'] or 0) for r in rows)
        t = (lk + cm + rp) or 1
        return {'n': len(rows), 'lk': lk, 'cm': cm, 'rp': rp,
                'share': [round(lk * 100.0 / t, 1), round(cm * 100.0 / t, 1),
                          round(rp * 100.0 / t, 1)],
                'perLk': round(lk * 1.0 / n, 1), 'perCm': round(cm * 1.0 / n, 1),
                'perRp': round(rp * 1.0 / n, 1), 'ratio': round(cm * 1.0 / (lk or 1), 3),
                'rrRatio': round(rp * 1.0 / (lk or 1), 4)}
    out = {'all': one(A), 'byTopic': {t: one([r for r in A if r['议题'] == t]) for t in TOPICS}}
    # 高扩散榜：转发绝对值 Top 8（附篇内其它指标，便于核验"高扩散"不是高赞带来的错觉）
    top = sorted(A, key=lambda r: int(r['转发数'] or 0), reverse=True)[:8]
    out['top'] = [{'txt': str(r['微博内容'] or '').replace('\n', ' ')[:90],
                   'au': r['作者昵称'] or '-', 'tp': r['议题'],
                   'tm': str(r['发布时间'] or '')[:10],
                   'rp': int(r['转发数'] or 0), 'lk': int(r['点赞数'] or 0),
                   'cm': int(r['评论数'] or 0), 'pv': r['目标省份'] or '-',
                   'url': r['微博链接'] or ''} for r in top]
    return out


# 事件类型 = 命中关键词去掉「省名 」前缀。命中关键词有两种形态：
#   单省型  '陕西 医患纠纷'                 → 进矩阵
#   多省合并 '陕西 医患纠纷|四川 医患纠纷|…'  → 只计数，不进矩阵（无法归到单一省份）
# 事件 ↔ 议题是严格一一对应（医患纠纷=医患矛盾 / 景区宰客=文旅 /
# 环保督察=生态治理 / 食品安全=社会治理兜底层），所以事件类型可以当议题反查索引。
EV_RIVER = {'长江': BGEO.YZ_PROV, '黄河': BGEO.YL_PROV}   # 沿江序位（上游 → 下游）
EV_ORDER = ['医患纠纷', '景区宰客', '环保督察', '食品安全']  # 三大主题 → 兜底层
EV2TOPIC = {'医患纠纷': '医患矛盾', '景区宰客': '文旅',
            '环保督察': '生态治理', '食品安全': '社会治理'}


def evprov_stats(A, basin, rest=()):
    """建议 1 / 建议 3 的数据层：事件类型 × 省份传播强度矩阵 + 扩散比。

    A     = 三大主题聚焦样本（默认口径，行 = 3 类事件）
    rest  = 兜底层样本（社会治理等）。它以**第 4 行「食品安全 / 兜底层」**进入矩阵：
            那一行的行标签是**事件类型**而不是议题，多列一行不等于把兜底层当成占比分母，
            但必须在表里标明它是兜底层，否则读者会误以为它是第四个主题。

    为什么中心量用「去极值均值」（该格去掉最高一条后的均值）而不是均值 / 中位数：
      ① 均值被单条极值污染 —— 黄河「陕西 医患纠纷」原始均值 1775.5，去极值后 9.7（183 倍）；
         全流域转发 原始均值 76.4 / 去极值 21.7；
      ② 中位数太保守 —— 4×8 矩阵里中位数几乎全 0，弱信号被一起抹掉；
      ③ 两者之间没有第三个稳健选择，去极值均值同时保住「整体水平」和「抗单条污染」。

    为什么条数不进编码：32 个格条数全落在 19~26，是采集配额均衡的结果，
    不是真实热度；页面必须写明，否则会把配额设计读成地域差异。
    """
    provs = EV_RIVER[basin]                      # 沿江序位（上游 → 下游）
    cell = {}                                   # (事件, 省) -> [转发, 点赞, 评论]
    isRest = {}                                 # (事件, 省) -> 是否来自兜底层
    multi = 0                                   # 多省合并串条数（只计数，不进矩阵）
    multiEv = {}
    SRC = [(r, False) for r in A] + [(r, True) for r in rest]
    for r, _rest in SRC:
        kw = str(r['命中关键词'] or '')
        pv = r['目标省份'] or ''
        if '|' in kw:                           # 多省合并：无法归到单一省份
            multi += 1
            for part in kw.split('|'):
                e = part.strip().split(' ')[-1]
                multiEv[e] = multiEv.get(e, 0) + 1
            continue
        ev = kw.strip().split(' ')[-1] if kw.strip() else ''
        if not ev or (pv and not kw.startswith(pv)):
            continue                            # 关键词与目标省份对不上 → 不硬塞
        cell.setdefault((ev, pv), []).append(
            [int(r['转发数'] or 0), int(r['点赞数'] or 0), int(r['评论数'] or 0)])
        if _rest:
            isRest[(ev, pv)] = True

    def agg(v):
        fs = sorted(x[0] for x in v)
        n = len(fs)
        trim = sum(fs[:-1]) / (n - 1) if n > 2 else (sum(fs) / n if n else 0.0)
        return {'n': n, 'mean': sum(fs) / n if n else 0.0, 'trim': trim,
                'med': fs[n // 2] if n else 0, 'max': fs[-1] if n else 0}

    evs = [e for e in EV_ORDER if any(k[0] == e for k in cell)]
    evs += sorted({k[0] for k in cell} - set(evs))       # 词表外的类型也列出，不丢数据
    rows = []
    for e in evs:
        cs = []
        for p in provs:
            c = agg(cell.get((e, p), []))
            c['rest'] = bool(isRest.get((e, p)))
            cs.append(c)
        rows.append({'ev': e, 'topic': EV2TOPIC.get(e, '—'),
                     'rest': any(c['rest'] for c in cs),
                     'cells': cs,
                     'medTrim': sorted(x['trim'] for x in cs)[len(cs) // 2] if cs else 0,
                     'all': agg([z for p in provs for z in cell.get((e, p), [])])})
    # 扩散比 = 总转发 / 总点赞（结构量，不受采集配额影响）。
    # 分母口径只取聚焦样本 A（与全站其他卡片一致），兜底层那一行单列、不进合计。
    totF = sum(int(r['转发数'] or 0) for r in A)
    totZ = sum(int(r['点赞数'] or 0) for r in A)
    spread = []
    for r in rows:
        f = sum(x[0] for p in provs for x in cell.get((r['ev'], p), []))
        z = sum(x[1] for p in provs for x in cell.get((r['ev'], p), []))
        spread.append({'ev': r['ev'], 'topic': r['topic'], 'f': f, 'z': z,
                       'zf': round(f * 1.0 / z, 3) if z else 0.0,
                       'n': r['all']['n'], 'med': r['all']['med'],
                       'trim': round(r['all']['trim'], 2), 'max': r['all']['max'],
                       'fShare': round(f * 100.0 / totF, 1) if totF else 0.0})
    return {'evs': evs, 'provs': provs, 'rows': rows, 'spread': spread,
            'multi': multi, 'multiEv': multiEv,
            'all': {'f': totF, 'z': totZ, 'zf': round(totF * 1.0 / totZ, 3) if totZ else 0,
                    'n': len(A)}}


def nodes_stats(A):
    """关键传播节点：作者榜 + 集中度 + 官方 vs 个人 + 单篇影响力"""
    by = {}
    for r in A:
        a = r['作者ID'] or r['作者昵称'] or '-'
        d = by.setdefault(a, {'nick': r['作者昵称'] or '-', 'n': 0, 'lk': 0, 'cm': 0,
                              'rp': 0, 'mx': 0, 'tp': Counter(), 'ch': Counter()})
        d['n'] += 1
        d['lk'] += int(r['点赞数'] or 0)
        d['cm'] += int(r['评论数'] or 0)
        d['rp'] += int(r['转发数'] or 0)
        d['mx'] = max(d['mx'], int(r['点赞数'] or 0))   # 单条最高赞 = 爆发力口径
        d['tp'][r['议题']] += 1
        d['ch'][BM.classify_channel(r['分类'])[0]] += 1
    tot = len(A) or 1
    rank = sorted(by.values(), key=lambda d: (-d['n'], -d['lk']))
    rows = []
    for d in rank[:15]:
        kd = mc_top(d['ch'], BM.UNKNOWN_CN)
        rows.append({'nick': d['nick'], 'n': d['n'], 'lk': d['lk'], 'cm': d['cm'],
                     'rp': d['rp'], 'tp': mc_top(d['tp'], '-'),
                     'ch': kd, 'mx': d['mx'],
                     'avg': int(d['n'] and d['lk'] / d['n']),
                     'ntop': len(d['tp']),
                     'eng': d['lk'] + d['cm'] + d['rp']})
    # 集中度：Top N 作者的篇数占比（横轴 N，纵轴累计 %）
    cum, acc, xs, ys = 0, 0, [], []
    for i, d in enumerate(rank, 1):
        acc += d['n']
        if i in (1, 3, 5, 10, 20, 50, 100):
            xs.append('Top%d' % i)
            ys.append(pct(acc, tot))
    conc = {}
    for k in (1, 5, 10, 20, 50):
        conc[k] = sum(d['n'] for d in rank[:k])
    # 一次作者（只发 1 条）与头部作者的对照
    once = sum(1 for d in rank if d['n'] == 1)
    # 官方 / 个人 作者结构（可判定样本内）
    kindN, kindA = Counter(), Counter()
    for r in A:
        k = BM.classify_channel(r['分类'])[0]
        kindN[k] += 1
        kindA.setdefault(k, set()).add(r['作者ID'])
    return {
        'rank': rows, 'authors': len(by), 'once': once,
        'oncePct': pct(once, len(by)),
        'conc': [[k, conc[k], pct(conc[k], tot)] for k in (1, 5, 10, 20, 50)],
        'concX': xs, 'concY': ys,
        'kindN': [[k, kindN.get(k, 0)] for k in BM.AGENT_ORDER],
        'kindA': [[k, len(kindA.get(k, ()))] for k in BM.AGENT_ORDER],
        'topN': [[d['nick'], d['n']] for d in rank[:15]],
    }


# ------------------------------------------------------------------
# 跨平台传播节点（2026-10-08 新增）
# ------------------------------------------------------------------
# 为什么不用「活跃跨度」（活跃起止时间差）当分类维度：
#   实测 `发布时间` 字段大面积非标—— 小红书 1183 条里549 条（46.4%）是空串
#   或 '昨天 18:28' 这类相对时间，知乎 950 条里 140 条同类，微博则 100% 标准。
#   用半数缺失的样本算「活跃 3 年以上」，结论不可信。所以**主动不算**，
#   改用两个完全可算的口径：单条爆发力 + 议题广度。
#
# 三平台的节点形态实测差异很大，且不能共用一把尺子：
#   微博头部 n≥3（持续输出）；小红书头部几乎全是 n=1 但单条赞最高
#   （91,859，均赞 585）；知乎均赞最低（105）但评论/赞比最高。
#   强行合并排名会让小红书的「一条即爆」被当成微博语境的「长尾过客」。
#
# 硬约束：作者 ID 三平台不通用（实测微博×小红书重叠 0 人），因此本页只能做
#   「平台之间的结构对比」，**不能**声称是「同一个人跨平台追踪」。该口径
#   会写进页面披露条（nodes_gap_note）。
NODES_PLAT_FORMS = {
    '微博': '持续输出',
    '小红书': '单条爆款',
    '知乎': '深度讨论',
}


def nodes_cross_platform(cur, basin):
    """跨平台节点：议题×平台矩阵 + 各平台爆发力Top + 节点类型归属。

    cur 需是 DictCursor，调用方负责关闭。**纯只读**，不采集。
    basin：'长江'/'黄河' —— **必须按流域过滤**。四张平台表都有 `流域` 字段，
    且两个流域的条数确实不同（实测小红书 长江536 / 黄河647）；不过滤会让
    长江页和黄河页显示同一份数字，等于在流域专题里给出全域口径的假对比。

    任一平台表缺失/读失败 → 该平台整体标missing，页面上按「未采集」虚线格
    渲染，与「真 0 条」严格区分（不能让人把缺口当成"这平台没这话题"）。
    """
    out = {'platforms': [], 'matrix': [], 'gap_note': '', 'timeField': {}}
    mats = {}
    bursts = []
    # ⚠ 两层格式化，转义层数很容易写错（写错的表现是「四个平台全 missing」，
    #   因为异常被 except 吞掉）：
    #   第 1 层 = 本文件的 `'...%s...' % (表名, W)`，把表名填进去；
    #   W 的内容是**原样插入**、不会再被解析，所以这里必须是单 `%s`。
    #   第 2 层 = pymysql 内部的 `query % args`（只有传了 args 才发生），
    #   所以字面 `%` 必须写成 `%%`（见下方 LIKE '%%%%-%%%%'）。
    W = 'WHERE 流域=%s'

    for plat, a_tbl, _c_tbl in BM.PLATFORM_TABLES:
        rec = {'name': plat, 'form': NODES_PLAT_FORMS.get(plat, ''),
               'article': 0, 'authors': 0, 'active': 0, 'activePct': 0.0,
               'avgLike': 0, 'maxLike': 0, 'missing': False, 'topics': []}
        try:
            cur.execute('SELECT COUNT(*) c, COUNT(DISTINCT 作者ID) a FROM `%s` %s'
                        % (a_tbl, W), (basin,))
            r = cur.fetchone() or {}
            rec['article'] = int(r.get('c') or 0)
            rec['authors'] = int(r.get('a') or 0)
            if not rec['article']:
                rec['missing'] = True
                out['platforms'].append(rec)
                mats[plat] = {}
                continue
            # 议题分布（矩阵格子）
            cur.execute('SELECT 议题, COUNT(*) c FROM `%s` %s GROUP BY 议题'
                        % (a_tbl, W), (basin,))
            mats[plat] = {x['议题']: int(x['c']) for x in cur.fetchall() if x['议题']}
            rec['topics'] = sorted(mats[plat].items(), key=lambda kv: -kv[1])
            # 互动量级 + 活跃作者占比
            cur.execute('SELECT MAX(点赞数) mx, AVG(点赞数) av FROM `%s` %s'
                        % (a_tbl, W), (basin,))
            r = cur.fetchone() or {}
            rec['maxLike'] = int(r.get('mx') or 0)
            rec['avgLike'] = round(float(r.get('av') or 0))
            cur.execute('SELECT COUNT(*) c FROM (SELECT 作者ID FROM `%s` '
                        '%s AND 作者ID IS NOT NULL AND 作者ID <> "" '
                        'GROUP BY 作者ID HAVING COUNT(*) >= 2) t' % (a_tbl, W), (basin,))
            rec['active'] = int((cur.fetchone() or {}).get('c') or 0)
            rec['activePct'] = pct(rec['active'], rec['authors'])
            # 爆发力榜：按单条最高赞降序。取 n>=2，n=1 的单条账号另计。
            cur.execute('''SELECT 作者昵称, COUNT(*) n, MAX(点赞数) mx,
                                  ROUND(AVG(点赞数)) av, COUNT(DISTINCT 议题) nt
                           FROM `%s` %s AND 作者昵称 IS NOT NULL AND 作者昵称 <> ''
                           GROUP BY 作者ID, 作者昵称
                           HAVING n >= 2 ORDER BY mx DESC LIMIT 6''' % (a_tbl, W),
                        (basin,))
            for x in cur.fetchall():
                bursts.append({'plat': plat, 'nick': x['作者昵称'], 'n': int(x['n']),
                               'max': int(x['mx'] or 0), 'avg': int(x['av'] or 0),
                               'ntop': int(x['nt'] or 0)})
        except Exception as e:
            # 表不存在 / 没权限 / 字段变了 —— 登记为 missing，绝不让整页构建中断
            # ⚠ 但不能**静默**：SQL 写错时四个平台会一起变 missing，页面上表现为
            #   "全部未采集"，与"真的没数据"完全无法区分。故把原因记下来，
            #   并在下方「全员 missing」时向上抛，让构建期就能看见真错误。
            rec['missing'] = True
            rec['article'] = 0
            rec['why'] = '%s: %s' % (type(e).__name__, e)
            mats[plat] = {}
        out['platforms'].append(rec)

    if all(p.get('missing') for p in out['platforms']):
        # 四平台同时 missing 只可能是 SQL/连接写错，不是"都没采集"——必须暴露
        raise RuntimeError('跨平台节点：四个平台全部读取失败 → %s'
                           % ' | '.join(p.get('why', '') for p in out['platforms']))

    # ---- 议题 × 平台矩阵 ----
    allTopics = sorted({t for m in mats.values() for t in m})
    for t in allTopics:
        row = {'topic': t, 'cells': [], 'total': 0,
               'covered': len([p for p in mats if mats[p].get(t)])}
        for plat in [p[0] for p in BM.PLATFORM_TABLES]:
            v = mats.get(plat, {}).get(t, 0)
            row['cells'].append([plat, v])
            row['total'] += v
        row['share'] = {plat: pct(v, row['total']) for plat, v in row['cells']}
        out['matrix'].append(row)
    #行序：声量降序；同量时按名排（显式次级排序键，保证两次构建一致）
    out['matrix'].sort(key=lambda r: (-r['total'], r['topic']))

    # ---- 节点类型归属（只用可算口径，不用活跃跨度）----
    # 顺序要紧：先剔除零互动，再分类，最后计数。
    #   反过来写会把「avg=0 的账号」误判成爆发型（条件里有 avg>=1000，
    #   但若写成 else-if 兜底就会把零互动的塞进常态型）—— 而0 均赞账号
    #   在本项目里真实存在（四****境 n=8 单条最高赞 1），必须单独归类。
    for b in bursts:
        if b['avg'] <= 0:
            b['kind'] = '零互动'
        elif b['n'] <= 3 and b['avg'] >= 1000:
            b['kind'] = '爆发型'
        else:
            b['kind'] = '常态型'
    out['bursts'] = bursts
    out['kindN'] = mc(Counter(b['kind'] for b in bursts))

    # ---- 时间字段可用性（必须如实披露，跨度不可算就是不可算）----
    for plat, a_tbl, _c in BM.PLATFORM_TABLES:
        try:
            cur.execute("SELECT COUNT(*) c FROM `%s` %s AND 发布时间 IS NOT NULL "
                        "AND 发布时间 <> '' AND 发布时间 LIKE '%%%%-%%%%'" % (a_tbl, W),
                        (basin,))
            ok = int((cur.fetchone() or {}).get('c') or 0)
            cur.execute('SELECT COUNT(*) c FROM `%s` %s' % (a_tbl, W), (basin,))
            tot = int((cur.fetchone() or {}).get('c') or 0)
            out['timeField'][plat] = {'ok': ok, 'total': tot, 'pct': pct(ok, tot)}
        except Exception:
            out['timeField'][plat] = {'ok': 0, 'total': 0, 'pct': 0}

    _zero = [p['name'] for p in out['platforms'] if p['missing']]
    _bad_t = [k for k, v in out['timeField'].items() if v['total'] and v['pct'] < 90]
    out['gap_note'] = (
        '作者 ID 三平台不通用（实测微博×小红书重叠 0 人），本页是<b>平台结构对比</b>，'
        '不是「同一个人跨平台追踪」。'
        + ('%s尚无数据（表已建、条数为 0），页面上按「未采集」虚线格渲染，'
           '与「真 0 条」严格区分。' % '、'.join(_zero) if _zero else '')
        + ('节点分类只用「单条爆发力 + 议题广度」，'
           '不用「活跃跨度」——%s 的发布时间有相当比例是空值或相对时间（如「昨天 18:28」），'
           '算出来的跨度不可信。' % '、'.join(_bad_t) if _bad_t else '')
    )
    return out


def risk_stats(byTopic, idmaps, sentById, hitrows):
    """风险分级预警：四个可复核因子 → 0~100 分 → 四级

    口径（四条都在页面上写出来）：
      · 负面占比  取**绝对值**（该事件命中微博中被判负面的比例），不再归一 ——
                  "一半是负面"本身就是可读的量级，归一化会把它抹平。
      · 声量/扩散/敏感度  取**本流域内 min-max 归一**，因为它们只有相对含义。
      · 敏感度    命中文本中出现 BM.SENS_WORDS 的篇数占比。
      · 权重      团队设定（40/25/20/15），不是拟合出来的；页面附"改权重会怎样"的提示。
    """
    items = []
    for t in TOPICS:
        for cl in (byTopic.get(t) or {}).get('clusters') or []:
            ids = idmaps.get(t, {}).get(cl['name']) or set()
            pos = neu = neg = 0
            for i in ids:
                s = sentById.get(i)
                if s == '正面':
                    pos += 1
                elif s == '负面':
                    neg += 1
                elif s == '中性':
                    neu += 1
            n = cl['n'] or 1
            items.append({'name': cl['name'], 'topic': t, 'n': cl['n'],
                          'pos': pos, 'neu': neu, 'neg': neg,
                          'negPct': pct(neg, n), 'perRp': cl['rep'] * 1.0 / n,
                          'sens': None})
    if not items:
        return {'items': [], 'factors': BM.RISK_FACTORS, 'levels': BM.RISK_LEVELS}
    # 敏感度：命中文本里出现敏感词的比例（在事件层用词表粗判，篇级去重）
    sens = []
    for t in TOPICS:
        for cl in (byTopic.get(t) or {}).get('clusters') or []:
            ids = idmaps.get(t, {}).get(cl['name']) or set()
            rows = hitrows.get((t, cl['name'])) or []
            hit = sum(1 for r in rows
                      if any(w in str(r.get('微博内容') or '') for w in BM.SENS_WORDS))
            sens.append(pct(hit, len(ids)) / 100.0 if ids else 0.0)
    for it, s in zip(items, sens):
        it['sens'] = s
    # 样本闸门：命中篇数 < RISK_GATE 的事件不入级（只作线索），
    # 且 min-max 归一**只在过闸事件内做** —— 否则一个 3 篇的小簇会把大簇压扁。
    for it in items:
        it['gated'] = it['n'] >= BM.RISK_GATE
    calc = [it for it in items if it['gated']]
    for it in items:
        if it['gated']:
            continue
        it.update({'score': None, 'key': '灰', 'level': BM.GRAY_LEVEL[1],
                   'act': BM.GRAY_LEVEL[2], 'p_neg': None, 'p_n': None,
                   'p_sens': None, 'p_rp': None, 'f_neg': None, 'f_n': None,
                   'f_sens': None, 'f_rp': None})
    if not calc:
        items.sort(key=lambda x: -x['n'])
        return {'items': items, 'factors': BM.RISK_FACTORS, 'levels': BM.RISK_LEVELS,
                'gate': BM.RISK_GATE, 'scale': None}
    nx, nlo, nhi = _minmax([it['n'] for it in calc])
    rx, rlo, rhi = _minmax([it['perRp'] for it in calc])
    sx, slo, shi = _minmax([it['sens'] for it in calc])
    for it, a, b, c in zip(calc, nx, rx, sx):
        f1 = it['negPct'] / 100.0
        score = BM.RISK_FACTORS[0][1] * f1 + BM.RISK_FACTORS[1][1] * a + \
                BM.RISK_FACTORS[2][1] * c + BM.RISK_FACTORS[3][1] * b
        key, lv, act = BM.risk_level(score)
        it.update({'f_neg': round(f1, 3), 'f_n': round(a, 3), 'f_sens': round(c, 3),
                   'f_rp': round(b, 3),
                   'p_neg': round(BM.RISK_FACTORS[0][1] * f1, 1),
                   'p_n': round(BM.RISK_FACTORS[1][1] * a, 1),
                   'p_sens': round(BM.RISK_FACTORS[2][1] * c, 1),
                   'p_rp': round(BM.RISK_FACTORS[3][1] * b, 1),
                   'score': round(score, 1), 'key': key, 'level': lv, 'act': act})
    # 排序：先按是否入级，再按得分（未入级的按篇数），保证"线索"不被当成"低风险"
    items.sort(key=lambda x: (not x['gated'], -(x['score'] or 0), -x['n']))
    return {'items': items, 'factors': BM.RISK_FACTORS, 'levels': BM.RISK_LEVELS,
            'gate': BM.RISK_GATE,
            'scale': {'n': [nlo, nhi], 'rp': [round(rlo, 1), round(rhi, 1)],
                      'sens': [round(slo, 3), round(shi, 3)]}}


def comment_stats(C, sn):
    """评论侧扩充：时段 / 长度 / 情感 / 议题 / 用户集中度（样本不足时只描述结构）"""
    hours = [0] * 24
    bins = [0, 0, 0, 0, 0]                     # 1-10 / 11-25 / 26-50 / 51-100 / 100+
    sent = Counter()
    users = Counter()
    for r in C:
        tm = str(r['评论时间'] or '')
        m = re.search(r'\s(\d{2}):', tm)
        if m:
            hours[int(m.group(1))] += 1
        L = len(str(r['评论内容'] or '').strip())
        if L <= 10:
            bins[0] += 1
        elif L <= 25:
            bins[1] += 1
        elif L <= 50:
            bins[2] += 1
        elif L <= 100:
            bins[3] += 1
        else:
            bins[4] += 1
        s = sentiment_of(r['评论内容'], sn)
        if s:
            sent[s] += 1
        users[r['用户ID'] or r['昵称'] or '-'] += 1
    return {
        'hours': hours,
        'lenBins': [['1-10', bins[0]], ['11-25', bins[1]], ['26-50', bins[2]],
                    ['51-100', bins[3]], ['100+', bins[4]]],
        'sent': [[k, sent.get(k, 0)] for k in ('正面', '中性', '负面')],
        'users': mc(users, 10),
        'nUsers': len(users),
    }


def comment_gate_stats(C):
    """按平台×流域×主题计算评论样本闸门；调用方传入的是单流域评论集。"""
    counts = Counter()
    for r in C:
        plat = str(r.get('平台') or '微博').strip() or '微博'
        topic = str(r.get('议题') or '未标注').strip() or '未标注'
        if topic in TOPICS:
            counts[(plat, topic)] += 1
    by_topic = {}
    for t in TOPICS:
        n = sum(cnt for (p, tt), cnt in counts.items() if tt == t)
        by_topic[t] = {'count': n, 'gate': n >= COMMENT_GATE}
    by_platform = {}
    for (p, t), n in sorted(counts.items()):
        by_platform.setdefault(p, {})[t] = {'count': n, 'gate': n >= COMMENT_GATE}
    by_platform.setdefault('微博', {})
    for t in TOPICS:
        by_platform['微博'].setdefault(t, {'count': 0, 'gate': False})
    return {
        'scope': '平台×流域×主题',
        'gate': COMMENT_GATE,
        'byTopic': by_topic,
        'byPlatform': by_platform,
        'allTopicsEnough': all(v['gate'] for v in by_topic.values()),
    }

def calib_stats(A, sentById, scores):
    """情感模型校准实测：中性占比、极端分占比、词典法交叉一致性、不一致样例

    这里给的是**证据**，不是结论 —— 用来回答"为什么说 SnowNLP 偏两端"。
    """
    ext_hi = sum(1 for v in scores.values() if v is not None and v >= 0.90)
    ext_lo = sum(1 for v in scores.values() if v is not None and v <= 0.10)
    ext = sum(1 for v in scores.values() if v is not None and (v >= 0.90 or v <= 0.10))
    n = sum(1 for v in scores.values() if v is not None) or 1
    neu = sum(1 for s in sentById.values() if s == '中性')
    # 极性分十档直方图：回答"偏两端"到底偏到什么程度（0.9 以上有多少）
    hist = [0] * 10
    for v in scores.values():
        if v is None:
            continue
        i = min(9, int(v * 10))
        hist[i] += 1
    agree = 0
    diff = []
    dist = {'一致': 0, '不一致': 0}
    dthree = Counter()
    for r in A:
        s = sentById.get(r['微博ID'])
        if not s:
            continue
        d, pos, neg = dict_sent(r['微博内容'])
        dthree[d] += 1
        if d == s:
            agree += 1
            dist['一致'] += 1
        else:
            dist['不一致'] += 1
            if len(diff) < 12:
                diff.append({'txt': str(r['微博内容'] or '').replace('\n', ' ')[:70],
                             'model': s, 'dict': d, 'pos': pos, 'neg': neg,
                             'tp': r['议题'], 'tm': str(r['发布时间'] or '')[:10],
                             'url': r['微博链接'] or ''})
    return {
        'n': n,
        'extHi': ext_hi, 'extLo': ext_lo, 'extPct': pct(ext, n),
        'bandPct': pct(n - ext, n),        # 落在 0.1~0.9 之间（中间带）的比例
        'neuPct': pct(neu, n),             # 真正被判「中性」的比例（0.4~0.6）
        'hist': hist,
        'histX': ['%.1f-%.1f' % (i / 10.0, i / 10.0 + 0.1) for i in range(10)],
        'agree': agree, 'agreePct': pct(agree, n),
        'dictDist': [[k, dist[k]] for k in ('一致', '不一致')],
        'dictThree': [[k, dthree.get(k, 0)] for k in ('正面', '中性', '负面')],
        'diff': diff,
        'posWords': BM.CALIB_POS, 'negWords': BM.CALIB_NEG,
    }


def main():
    conn = pymysql.connect(cursorclass=DictCursor, **DB)
    cur = conn.cursor()
    ph = ','.join(['%s'] * len(TOPICS))

    arts = {}
    for b in BASINS:
        cur.execute("SELECT * FROM t_basin_article WHERE 议题 IN (%s) AND 流域=%%s" % ph,
                    list(TOPICS) + [b])
        arts[b] = cur.fetchall()

    # 兜底层（社会治理等未命中三大主题的样本）：默认不进入任何视图，
    # 只有「事件类型 × 省份」矩阵把它作为**第 4 行**显式列出并标注「兜底层」——
    # 因为那里的行是事件类型（食品安全）而不是议题，多列一行不等于把兜底层当成分母。
    artsRest = {}
    for b in BASINS:
        cur.execute("SELECT * FROM t_basin_article WHERE 议题 NOT IN (%s) AND 流域=%%s" % ph,
                    list(TOPICS) + [b])
        artsRest[b] = cur.fetchall()

    cmts = {}
    for b in BASINS:
        cur.execute("SELECT * FROM t_basin_comment WHERE 议题 IN (%s) AND 流域=%%s" % ph,
                    list(TOPICS) + [b])
        cmts[b] = cur.fetchall()

    # 全量口径（含被前端过滤掉的议题）：给「议题占比参照」做分母。
    # 说明：本作品只展开生态治理与文旅两个议题，但单独说"生态治理 245 条"没有标尺，
    #       分母层能让"占本流域全部舆情 X%"这类结论站得住。
    allTop, allN = {}, {}
    for b in BASINS:
        cur.execute('SELECT 议题, COUNT(*) c FROM t_basin_article WHERE 流域=%s GROUP BY 议题',
                    (b,))
        rows = cur.fetchall()
        allTop[b] = [[r['议题'] or '未标注', r['c']] for r in rows]
        allN[b] = sum(r['c'] for r in rows)
    conn.close()

    # snownlp 懒加载（首次 import 有点慢）
    from snownlp import SnowNLP as sn

    out = {
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'topics': list(TOPICS),
        'commentGate': COMMENT_GATE,
        'db': DB['database'],
        'basins': {},
    }

    for b in BASINS:
        A = arts[b]
        C = cmts[b]
        n = len(A)
        topics = Counter(r['议题'] for r in A)
        provs = Counter((r['目标省份'] or '未标注') for r in A)
        cats = Counter((r['分类'] or '未标注') for r in A)
        years = Counter(parse_year(r['发布时间']) for r in A)
        years.pop(None, None)
        months = Counter(parse_month(r['发布时间']) for r in A)
        months.pop(None, None)

        # 热词（正文分词）—— 存 60 个：柱状图取前 15，词云用全量
        hw = Counter()
        for r in A:
            hw.update(set(words_of(r['微博内容'])))   # 用 set：同一微博内不重复计
        # 命中关键词（已是词袋，按空格拆）
        kw = Counter()
        for r in A:
            for k in re.split('[\\s,，、;；]+', str(r['命中关键词'] or '')):
                k = k.strip()
                if k:
                    kw[k] += 1

        # 情感（正文）——算一次并缓存，供整体与分议题复用；原始分留给校准页
        sent = Counter()
        sentById, scoreById = {}, {}
        for r in A:
            s, p = sent_pair(r['微博内容'], sn)
            sentById[r['微博ID']] = s
            scoreById[r['微博ID']] = p
            if s:
                sent[s] += 1
        sentT = sum(sent.values())

        # 互动量
        repost = sum(int(r['转发数'] or 0) for r in A)
        ccount = sum(int(r['评论数'] or 0) for r in A)
        like = sum(int(r['点赞数'] or 0) for r in A)
        authors = len({r['作者ID'] for r in A if r['作者ID']})

        # 高互动文章（转发+评论+点赞 排序）—— 批次 2 由 Top10 扩到 Top15
        top = sorted(A, key=lambda r: (int(r['点赞数'] or 0) + int(r['评论数'] or 0)
                                       + int(r['转发数'] or 0)), reverse=True)[:15]
        topArts = [{
            'text': (str(r['微博内容'] or '').replace('\n', ' ')[:110]),
            'author': r['作者昵称'] or '-',
            'topic': r['议题'],
            'prov': r['目标省份'] or '-',
            'time': str(r['发布时间'] or '')[:10],
            'like': int(r['点赞数'] or 0),
            'cmt': int(r['评论数'] or 0),
            'rep': int(r['转发数'] or 0),
            'url': r['微博链接'] or '',
        } for r in top]

        # ---- 按议题拆分（生态治理 / 文旅 / 医患矛盾 各自的热词、省份、情感）----
        byTopic = {}
        idmaps, hitrows = {}, {}
        for t in TOPICS:
            sub = [r for r in A if r['议题'] == t]
            hwt = Counter()
            for r in sub:
                hwt.update(set(words_of(r['微博内容'])))
            kwt = Counter()
            for r in sub:
                for k in re.split('[\\s,，、;；]+', str(r['命中关键词'] or '')):
                    k = k.strip()
                    if k:
                        kwt[k] += 1
            provt = Counter((r['目标省份'] or '未标注') for r in sub)
            sentt = Counter()
            for r in sub:
                s = sentById.get(r['微博ID'])
                if s:
                    sentt[s] += 1
            clu, idmap = cluster_stats(sub, b, t, hw)
            idmaps[t] = idmap
            byId = {r['微博ID']: r for r in sub}
            for c in clu:
                ids = idmap.get(c['name']) or set()
                # 事件级情感（批次 2：事件监测与风险分级都要用）—— 直接复用已算好的判定
                sc = Counter(sentById.get(i) for i in ids if sentById.get(i))
                c['sent'] = [[k, sc.get(k, 0)] for k in ('正面', '中性', '负面')]
                c['negPct'] = pct(sc.get('负面', 0), c['n'])
                # 首发者：该事件最早的一条（识别"谁先把这件事带进流域舆情的"）
                rs = [byId[i] for i in ids if i in byId]
                hitrows[(t, c['name'])] = rs
                if rs:
                    f = min(rs, key=lambda r: str(r['发布时间'] or '9999'))
                    c['first'] = {'au': f['作者昵称'] or '-',
                                  'tm': str(f['发布时间'] or '')[:16],
                                  'pv': f['目标省份'] or '-',
                                  'url': f['微博链接'] or '',
                                  'txt': str(f['微博内容'] or '').replace('\n', ' ')[:90]}
                # 事件的月度分布（事件监测的热力矩阵用）；只保留有样本的月份
                cm = Counter()
                for r in rs:
                    mm = parse_month(r['发布时间'])
                    if mm:
                        cm[mm] += 1
                c['months'] = sorted(cm.items())
            byTopic[t] = {
                'n': len(sub),
                'clusters': clu,                          # 事件簇（批次 1）
                'merge': merge_stats(sub, b, t),           # 同义归并（批次 1）
                'coverage': coverage_of(idmap, len(sub)),  # 簇覆盖率（批次 1）
                'hotwords': mc(hwt, 60),
                'keywords': mc(kwt, 10),
                'provDist': mc(provt, 10),
                'sent': [[k, sentt.get(k, 0)] for k in ('正面', '中性', '负面')],
                'like': sum(int(r['点赞数'] or 0) for r in sub),
                'cmtCnt': sum(int(r['评论数'] or 0) for r in sub),
                'authors': len({r['作者ID'] for r in sub if r['作者ID']}),
            }

        # 评论侧
        cGen = Counter()
        for r in C:
            g = str(r['性别'] or '').strip().lower()
            cGen['男' if g in ('m', '男') else ('女' if g in ('f', '女') else '未知')] += 1
        cTopic = Counter(r['议题'] for r in C)
        CG = comment_gate_stats(C)
        cYears = Counter(parse_year(r['评论时间']) for r in C)
        cYears.pop(None, None)
        cExt = comment_stats(C, sn)      # 批次 2：时段 / 长度 / 情感 / 用户集中度
        topCmt = sorted(C, key=lambda r: int(r['点赞数'] or 0), reverse=True)[:10]
        topCmts = [{
            'text': str(r['评论内容'] or '').replace('\n', ' ')[:120],
            'nick': r['昵称'] or '-',
            'like': int(r['点赞数'] or 0),
            'topic': r['议题'],
            'time': str(r['评论时间'] or '')[:10],
        } for r in topCmt]

        # ---- 作者 IP 属地（发布地区）—— 地图专用口径，与「目标省份」严格分开 ----
        geo = Counter()
        for r in A:
            gp = geo_prov(r['发布地区'])
            if gp:
                geo[gp] += 1
        geoKnown = sum(geo.values())

        # ---- 事件簇词云数据（批次 1）----
        # 成员 = Top60 ∪ 三议题簇词表；频次沿用全量词频表（即现有词云口径，篇数），
        # 不用 LIKE 命中数 —— 那会把「生态」算进「生态环境」，与 Top60 不可比。
        want = [w for w, _ in mc(hw, 60)]
        for _t in TOPICS:
            for _w in EC.all_match_words(b, _t):
                if _w not in want:
                    want.append(_w)
        cloud = []
        for w in want:
            v = hw.get(w, 0)
            if v <= 0:
                continue            # jieba 没切出该词（短语被切碎/单字被滤掉）→ 词云上放不了
            _kind, _grp = EC.classify_word(b, w)
            cloud.append([w, v, _grp, EC.color_of_word(b, w)])
        cloud.sort(key=lambda x: -x[1])
        _cmap, _camb = EC.word_cluster_map(b)

        # ---- 批次 2：恢复被精简模块所需的聚合 ----
        TR = trend_stats(A, sentById)
        CHn = channel_stats(A)
        IA = interact_stats(A)
        EP = evprov_stats(A, b, artsRest.get(b) or [])
        ND = nodes_stats(A)
        RK = risk_stats(byTopic, idmaps, sentById, hitrows)
        CB = calib_stats(A, sentById, scoreById)

        out['basins'][b] = {
            'basin': b,
            'articles': n,
            'comments': len(C),
            'authors': authors,
            'repost': repost,
            'cmtCnt': ccount,
            'like': like,
            'topicDist': [[k, topics[k]] for k in TOPICS if topics.get(k)],
            'provDist': mc(provs, 12),
            'provCount': len([p for p in provs if p != '未标注']),
            'categories': mc(cats, 8),
            'hotwords': mc(hw, 60),
            'keywords': mc(kw, 12),
            'years': sorted(years.items()),
            'months': sorted(months.items()),
            'sent': [[k, sent.get(k, 0)] for k in ('正面', '中性', '负面')],
            'sentTotal': sentT,
            'topArticles': topArts,
            'commentGender': [[k, cGen.get(k, 0)] for k in ('男', '女', '未知')],
            'commentTopics': mc(cTopic),
            'commentYears': sorted(cYears.items()),
            'topComments': topCmts,
            'commentEnough': CG['allTopicsEnough'],
            'commentGateScope': CG['scope'],
            'commentGateByTopic': CG['byTopic'],
            'commentGateByPlatform': CG['byPlatform'],
            'byTopic': byTopic,
            'wordsCloud': cloud,                        # 词云专用（批次 1）
            'clusterNames': EC.cluster_names(b),        # 事件簇名（词云联动/图例）
            'clusterAmb': _camb,                        # 跨簇词（如实标注）
            'clusterGate': EC.CLUSTER_GATE,             # 样本闸门
            'geoProv': mc(geo),
            'geoKnown': geoKnown,
            'geoUnknown': n - geoKnown,
            # ---- 批次 2 新增 ----
            'trend': TR,
            'channel': CHn,
            'interact': IA,
            'evprov': EP,
            'nodes': ND,
            'risk': RK,
            'cmt': cExt,
            'calib': CB,
            'allTopics': sorted(allTop[b], key=lambda x: -x[1]),   # 含其他议题（分母层）
            'allN': allN[b],
            'filtered': allN[b] - n,                               # 被前端过滤掉的条数
        }
        print('[%s] 文章 %d · 评论 %d · 作者 %d · 热词 %d'
              % (b, n, len(C), authors, len(hw)))

    # ==============================================================
    # 批次 2 · 跨流域词对照 + 跨平台现状
    # --------------------------------------------------------------
    # 说明：这里用的对照词取自各自议题 Top60，**未进对方 Top60 的词按 0 计**，
    # 页面上必须写明这一点 —— 否则会把"没进榜"读成"不存在"。
    # ==============================================================
    for b in BASINS:
        ob = [x for x in BASINS if x != b][0]
        mine, other = out['basins'][b], out['basins'][ob]
        cmpd = {}
        for t in TOPICS:
            m40 = dict(list((mine['byTopic'].get(t) or {}).get('hotwords') or [])[:40])
            o40 = dict(list((other['byTopic'].get(t) or {}).get('hotwords') or [])[:40])
            diff = []
            for w, v in m40.items():
                if v < 8:
                    continue                       # 低频词不做跨流域比较（样本太薄）
                # 只比"能挂上事件或概念"的词；公文套话/泛义实词跨流域差异没有解释力
                if EC.classify_word(b, w, t)[0] not in ('event', 'concept'):
                    continue
                ov = o40.get(w, 0)
                diff.append([w, v, ov, round(v * 1.0 / (ov or 1), 2)])
            cmpd[t] = {
                'diff': sorted(diff, key=lambda x: -(x[1] - x[2]))[:12],
                'rev': sorted(diff, key=lambda x: (x[1] - x[2]))[:8],
                'only': sorted([x for x in diff if x[2] == 0], key=lambda x: -x[1])[:12],
                'co': [w for w in m40 if w in o40],
                'mineTop': list(m40.items())[:15],
                'otherTop': list(o40.items())[:15],
                'nMine': len(m40), 'nOther': len(o40),
                'other': ob,
            }
        out['basins'][b]['cmpWords'] = cmpd

    # 跨平台：按登记表逐平台读「内容表 + 评论表」的字段与条数 —— 只读，不采集
    conn = pymysql.connect(cursorclass=DictCursor, **DB)
    cur = conn.cursor()
    dy = {}
    platRows = []
    for plat, a_tbl, c_tbl in BM.PLATFORM_TABLES:
        for t in (a_tbl, c_tbl):
            try:
                cur.execute('SELECT COUNT(*) c FROM `%s`' % t)
                n0 = cur.fetchone()['c']
                cur.execute('SHOW COLUMNS FROM `%s`' % t)
                dy[t] = {'rows': n0, 'cols': [r['Field'] for r in cur.fetchall()],
                         'platform': plat}
            except Exception:
                # 表不存在 / 读失败：登记为 0 行，不让整页构建中断
                dy[t] = {'rows': 0, 'cols': [], 'platform': plat, 'missing': True}
        # 该平台实际采到了哪些议题、最新一次采集在什么时候 —— 只读，取不到就留空
        topics, latest = [], ''
        try:
            cur.execute('SELECT 议题, COUNT(*) c FROM `%s` GROUP BY 议题 ORDER BY c DESC' % a_tbl)
            topics = [[r['议题'], r['c']] for r in cur.fetchall()]
            cur.execute('SELECT MAX(采集时间) m FROM `%s`' % a_tbl)
            latest = str(cur.fetchone()['m'] or '')
        except Exception:
            pass
        platRows.append({
            'name': plat,
            'article': dy[a_tbl]['rows'],
            'comment': dy[c_tbl]['rows'],
            'live': dy[a_tbl]['rows'] > 0,      # 内容表有条数才算「已接入」
            'aTable': a_tbl, 'cTable': c_tbl,
            'topics': topics, 'latest': latest,
        })
    cur.execute('SELECT COUNT(*) c FROM t_basin_article WHERE 流域 IN (%s,%s)' % ('%s', '%s'),
                list(BASINS))
    dy['weiboRows'] = cur.fetchone()['c']
    conn.close()
    # 缺口说明必须**由实际条数推导**，不能写死 —— 写死的文案会在采集进展后变成假话
    _pend = [x['name'] for x in platRows if not x['live']]
    _live = [x['name'] for x in platRows if x['live']]
    if _pend:
        _blk = ('%s 尚无数据（表已建、条数为 0），需在独立浏览器 profile 登录后实跑；'
                '%s 已有数据。未实跑的平台一律留空、不填任何数字。'
                % ('、'.join(_pend), '、'.join(_live) or '无'))
    else:
        _blk = ('%s 均已有数据，可进入「结构占比」计算阶段（跨平台仍不对齐绝对值）。'
                % '、'.join(_live))
    out['cross'] = {'tables': dy, 'platforms': platRows, 'metrics': BM.CROSS_METRICS,
                    'blocker': _blk}

    # ---- 跨平台传播节点（新增，独立连接；失败不拖垮整页）----
    # 放在 cross 之后：复用同一套 PLATFORM_TABLES 口径，但**不共用上面的 conn**
    # —— 上面那个已 close()，且它的 DictCursor 状态还被 xplat 段依赖。
    #
    # ⚠ 按流域分别算：四张平台表都有 `流域` 字段，两个流域的条数确实不同
    #   （小红书 长江536/黄河647、知乎 466/484）。挂在顶层会让长江页与黄河页
    #   显示同一份数字 —— 流域专题里这是硬错误，不是"偷懒省一次查询"。
    for _b in BASINS:
        try:
            _c2 = pymysql.connect(cursorclass=DictCursor, **DB)
            out['basins'][_b]['nodesCross'] = nodes_cross_platform(_c2.cursor(), _b)
            _c2.close()
        except Exception as e:
            out['basins'][_b]['nodesCross'] = {
                'platforms': [], 'matrix': [], 'bursts': [],
                'kindN': [], 'timeField': {},
                'gap_note': '跨平台节点数据读取失败（%s），本页仅显示单平台口径。' % e}
            print('[WARN] 跨平台节点数据读取失败（%s）：%s' % (_b, e))

    # ==============================================================
    # 多平台（跨源）口径 —— 【严格增量】不改动上方微博口径的任何键
    # --------------------------------------------------------------
    # 背景：小红书 / 知乎 数据已落库（t_xhs_* / t_zhihu_*），但此前只进「跨平台结构对照」
    #       一张状态表，流域专题的图表仍是微博单源。这里把新平台按
    #       「流域 × 议题 × 平台」聚合，供流域视图的跨源卡片消费。
    #
    # 议题口径：四源**交集** = 生态治理 / 医患矛盾（微博/小红书/知乎三者都有）；
    #          文旅 / 社会治理为微博独有，单列为 onlyWeibo，不与跨源口径混算。
    # 平台口径：抖音两表已建但 0 条 —— 登记为 absent，一律不填数字。
    # 互动量：字段按平台存在性自适应（微博有「转发数」无「收藏数」；
    #        小红书/知乎相反），缺失字段记 None，页面须标 N/A，不得当 0 混算。
    # ==============================================================
    XPLAT_TOPICS = ('生态治理', '医患矛盾')
    XPLAT_ONLY_WEIBO = ('文旅',)
    XPLAT_SRC = [
        ('微博',   't_basin_article',  't_basin_comment'),
        ('小红书', 't_xhs_article',    't_xhs_comment'),
        ('知乎',   't_zhihu_article',  't_zhihu_comment'),
    ]
    x_ph = ','.join(['%s'] * len(XPLAT_TOPICS))
    x_plat, x_mat, x_merge, x_live, x_absent = {}, {}, {}, [], []
    # 跨平台内容聚合（严格增量）：平台级热词 / 高赞 / 情感样本
    x_phw, x_ptop, x_ptxt = {}, {}, {}
    # 跨平台评论正文（供观点聚类，严格增量）：x_cc[basin][topic] = [{plat,like,txt}]
    x_cc = {}
    conn = pymysql.connect(cursorclass=DictCursor, **DB)
    cur = conn.cursor()
    for plat, a_tbl, c_tbl in XPLAT_SRC:
        rec = {'name': plat, 'article': 0, 'comment': 0, 'like': None, 'cmtCnt': None,
               'repost': None, 'fav': None, 'share': None, 'topics': [], 'latest': ''}
        try:
            cur.execute('SELECT COUNT(*) c FROM `%s`' % a_tbl)
            rec['article'] = cur.fetchone()['c']
            cur.execute('SELECT COUNT(*) c FROM `%s`' % c_tbl)
            rec['comment'] = cur.fetchone()['c']
            cur.execute('SHOW COLUMNS FROM `%s`' % a_tbl)
            acols = {r['Field'] for r in cur.fetchall()}
            # 互动量：只汇总该表真实存在的字段，不存在的保持 None（页面标 N/A）
            pair = [('点赞数', 'like'), ('评论数', 'cmtCnt'), ('转发数', 'repost'),
                    ('收藏数', 'fav'), ('分享数', 'share')]
            sel = ['SUM(`%s`) `%s`' % (f, k) for f, k in pair if f in acols]
            if sel:
                cur.execute('SELECT %s FROM `%s`' % (','.join(sel), a_tbl))
                row = cur.fetchone() or {}
                for f, k in pair:
                    if f in acols:
                        rec[k] = int(row.get(k) or 0)
            cur.execute('SELECT 议题, COUNT(*) c FROM `%s` GROUP BY 议题 ORDER BY c DESC' % a_tbl)
            rec['topics'] = [[r['议题'], r['c']] for r in cur.fetchall()]
            cur.execute('SELECT MAX(采集时间) m FROM `%s`' % a_tbl)
            rec['latest'] = str(cur.fetchone()['m'] or '')
            # 流域 × 议题 明细（仅交集议题）
            for b in BASINS:
                x_mat.setdefault(b, {t: {} for t in XPLAT_TOPICS})
                x_merge.setdefault(b, {})
                cur.execute('SELECT 议题, COUNT(*) c FROM `%s` WHERE 流域=%%s AND 议题 IN (%s) '
                            'GROUP BY 议题' % (a_tbl, x_ph), [b] + list(XPLAT_TOPICS))
                amap = {r['议题']: r['c'] for r in cur.fetchall()}
                cur.execute('SELECT 议题, COUNT(*) c FROM `%s` WHERE 流域=%%s AND 议题 IN (%s) '
                            'GROUP BY 议题' % (c_tbl, x_ph), [b] + list(XPLAT_TOPICS))
                cmap = {r['议题']: r['c'] for r in cur.fetchall()}
                for t in XPLAT_TOPICS:
                    x_mat[b][t][plat] = amap.get(t, 0)
                    x_merge[b].setdefault(t, {'article': {}, 'comment': {}})
                    x_merge[b][t]['article'][plat] = amap.get(t, 0)
                    x_merge[b][t]['comment'][plat] = cmap.get(t, 0)
            # 跨平台热词 / 情感 / 高赞内容：从真实正文聚合（严格增量，不新增采集）
            # 各平台内容字段名不同（微博=微博内容 / 小红书·知乎=正文），且 weibo 无收藏/分享列，
            # 故按 acols 动态拼 SELECT，失败仅跳过本平台、不污染其他平台游标。
            if rec['article'] > 0:
                try:
                    content_col = '微博内容' if '微博内容' in acols else '正文'
                    _wanted = ['流域', '议题', '发布地区', '点赞数', '评论数',
                               '转发数', '收藏数', '分享数', '标题', content_col]
                    _sel = ['`%s`' % c for c in _wanted if c in acols]
                    if content_col not in acols:
                        raise RuntimeError('缺内容字段：%s' % a_tbl)
                    cur.execute('SELECT %s FROM `%s`' % (','.join(_sel), a_tbl))
                    for r in cur.fetchall():
                        b_ = r.get('流域'); t_ = r.get('议题')
                        if t_ not in XPLAT_TOPICS:
                            continue
                        slot = x_merge[b_][t_]        # 已在上方 setdefault 建好
                        slot.setdefault('hotwords', Counter()).update(words_of(r.get(content_col)))
                        eng = (int(r.get('点赞数') or 0) + int(r.get('评论数') or 0)
                               + int(r.get('转发数') or 0) + int(r.get('收藏数') or 0)
                               + int(r.get('分享数') or 0))
                        ta = {'plat': plat, 'like': int(r.get('点赞数') or 0),
                              'cmt': int(r.get('评论数') or 0), 'rep': int(r.get('转发数') or 0),
                              'share': int(r.get('收藏数') or 0) + int(r.get('分享数') or 0),
                              'text': ((str(r.get('标题') or '') or str(r.get(content_col) or ''))[:90]).replace('\n', ' '),
                              'topic': t_, 'prov': str(r.get('发布地区') or '—')[:8],
                              'time': str(r.get('发布时间') or '')[:10], 'eng': eng}
                        slot.setdefault('topArticles', []).append(ta)
                        if len(slot.setdefault('texts', [])) < 250:
                            slot['texts'].append(r.get(content_col))
                        x_phw.setdefault(plat, Counter()).update(words_of(r.get(content_col)))
                        x_ptop.setdefault(plat, []).append(ta)
                        if len(x_ptxt.setdefault(plat, [])) < 300:
                            x_ptxt[plat].append(r.get(content_col))
                except Exception as _e:
                    # 单平台聚合失败不中断整页构建
                    rec.setdefault('xerr', str(_e)[:120])
            # 跨平台评论正文：供 TF-IDF + KMeans 观点聚类（三源合并口径）
            if rec['comment'] > 0:
                try:
                    cur.execute('SHOW COLUMNS FROM `%s`' % c_tbl)
                    ccols = {r['Field'] for r in cur.fetchall()}
                    if '评论内容' in ccols:
                        _cw = [c for c in ('流域', '议题', '评论内容', '点赞数', '命中关键词')
                               if c in ccols]
                        cur.execute('SELECT %s FROM `%s`'
                                    % (','.join('`%s`' % c for c in _cw), c_tbl))
                        for r in cur.fetchall():
                            b_ = r.get('流域')
                            t_ = r.get('议题')
                            if t_ not in XPLAT_TOPICS:
                                continue
                            _txt = str(r.get('评论内容') or '').strip()
                            if len(_txt) < 2:
                                continue
                            x_cc.setdefault(b_, {}).setdefault(t_, []).append(
                                {'plat': plat, 'like': int(r.get('点赞数') or 0),
                                 'txt': _txt, 'kw': str(r.get('命中关键词') or '')})
                except Exception as _e:
                    rec.setdefault('cerr', str(_e)[:120])
            x_plat[plat] = rec
            if rec['article'] > 0:
                x_live.append(plat)
            else:
                x_absent.append(plat)
        except Exception:
            # 表缺失 / 读失败：登记为 absent，不让整页构建中断
            rec['missing'] = True
            x_plat[plat] = rec
            x_absent.append(plat)
    conn.close()
    for b in BASINS:
        for t in XPLAT_TOPICS:
            m = x_merge.setdefault(b, {}).setdefault(t, {'article': {}, 'comment': {}})
            m['articleSum'] = sum(m['article'].values())
            m['commentSum'] = sum(m['comment'].values())
            m['gate'] = m['commentSum'] >= COMMENT_GATE
            m['gateByPlatform'] = {p: (n >= COMMENT_GATE) for p, n in m['comment'].items()}
    # ---- 跨平台评论观点聚类（严格增量）----
    # 口径：三源合并评论（微博单源仅 36/19 条、不足门槛；合并后 长江 596 / 黄河 936 条）。
    # 特征：每条评论的「命中关键词」词袋（库内已标注的领域词，长江 23 维 / 黄河 38 维）
    #       —— 实测比原始正文分词的簇间区分度高一个量级（silhouette 0.50/0.42 vs 0.03），
    #       故取关键词空间，再跑 TF-IDF + KMeans。簇由算法自动划分，不做人工语义命名。
    # 标签：clus[i]['label'] = 独占词（本簇文档占比≥15% 且≥其他簇 2 倍），2026-10-06 起启用。
    #       旧的「簇中心 top6 高频词」保留在terms，仅供对照/词云用，不再作标签 ——
    #       它会把跨簇高频词（'非法采砂|四川'/'绿色发展' 等）混进每个簇的标签，
    #       实测造成两簇标签 Jaccard 71%、簇不可区分。
    # 可复现：进聚类前按 (plat, topic, txt, -like) 稳定排序。上游 SELECT 无 ORDER BY，
    #       行序不定会让 KMeans 的 k-means++ 初始化结果漂移（实测黄河 sil 在
    #       0.390~0.422 间跳、sizes 由 [456,142,134,134,70] 变 [528,142,134,75,57]）。
    x_cluster = {}
    try:
        import numpy as _np
        from sklearn.feature_extraction.text import TfidfVectorizer as _TV
        from sklearn.cluster import KMeans as _KM
        from sklearn.metrics import silhouette_score as _sil
    except Exception:
        _np = _TV = _KM = _sil = None
    _KWSPLIT = re.compile(r'[\s,，、;；]+')
    for b in BASINS:
        bag = []
        for t, rows in (x_cc.get(b) or {}).items():
            for r in rows:
                raw_kw = [w.strip() for w in _KWSPLIT.split(r.get('kw') or '')
                          if len(w.strip()) >= 2]
                # ---- 概念归一（2026-10-06 P1b）----
                # 「命中关键词」字段里同一概念有两种写法：`排污` 与 `排污|四川`、
                # `医闹` 与 `医闹|山东`。直接当两个特征会把一个概念劈成两半 ——
                # 实测黄河 13 个基名被这样劈开（医闹 → 70 / 53 / 13，
                # 医患纠纷 → 55 / 74 / 3），既虚增特征维度，
                # 又让同义词的占比在簇间被摊薄、独占词判不出来。
                # 这里按 `|` 前的基名去重（同一评论内只算一次），
                # 省份信息不丢：省份本身是独立命中词（'四川' / '山东' 等），
                # 已单独占一个特征位。
                kws = sorted({w.split('|')[0] for w in raw_kw})
                if not kws:
                    continue          # 无关键词的评论进不了关键词空间，跳过
                bag.append({'plat': r['plat'], 'topic': t, 'like': r['like'],
                            'txt': r['txt'], 'seg': ' '.join(kws)})
        if _TV is None or len(bag) < 60:
            x_cluster[b] = {'n': len(bag), 'k': 0, 'ok': False, 'clusters': [],
                            'err': 'sklearn 不可用' if _TV is None else '样本不足'}
            continue
        # ---- 可复现性：聚类前按稳定键排序（2026-10-06 P0）----
        # 上游 SELECT 没有 ORDER BY，行序由 MySQL 随意返回；而 KMeans 的
        # k-means++ 初始化依赖样本行序 → 同一份数据、同一组参数，
        # 不同次构建会得到不同的簇分布与标签（实测黄河 sil 在
        # 0.390~0.422 间漂移、sizes 由[456,142,134,134,70] 变成
        # [528,142,134,75,57]）。任何页面上的聚类数字都是不可复现的。
        # 修法：进聚类前按内容稳定排序，与数据库返回顺序解耦。
        bag.sort(key=lambda x: (x['plat'], x['topic'], x['txt'], -x['like']))
        K = 5 if len(bag) >= 250 else (4 if len(bag) >= 120 else 3)
        try:
            vec = _TV(analyzer='word', token_pattern=r'(?u)\S+', min_df=2,
                      max_df=0.6, max_features=3000)
            X = vec.fit_transform([x['seg'] for x in bag])
            km = _KM(n_clusters=K, n_init=10, random_state=42)
            lab = km.fit_predict(X)
            terms = _np.array(vec.get_feature_names_out())
            try:
                sil = round(float(_sil(X, lab)), 3)
            except Exception:
                sil = None
            clus = []
            # ---- 簇标签改用「独占词」（2026-10-06 P1）----
            # 原做法 terms = 簇中心 TF-IDF 权重 top6 高频词。实测长江/黄河
            # 均出现两簇 top6 有 5 个词一字不差（Jaccard 71%），
            # 根因是「非法采砂|四川」「绿色发展」「陕西」这类跨簇高频词
            # 挤进了每个簇的 top6，把标签糊成一样。
            # 改用「独占词」：该词在本簇的文档占比 ≥15%，且 ≥ 其他簇占比的
            # 2 倍。实测每个簇都能取到 1~5 个互不相同的独占词，簇因此可区分。
            # terms 仍保留（供词云/其他视图与 tooltip），但不再作标签。
            # ⚠ 用 sorted tuple 而非 set 存词袋：set 的迭代顺序受
            #   PYTHONHASHSEED 影响 → Counter.most_common() 的并列名次会
            #   在不同进程间翻转 → 同一份数据两次构建出来的区分词顺序不同。
            #   2026-10-06 实测：簇边界与条数完全一致，仅词序抖动。
            _kwsets = [tuple(sorted(_KWSPLIT.split(x['seg']))) for x in bag]
            _gidx = [[i for i, L in enumerate(lab) if L == ci] for ci in range(K)]
            _gidx = [g for g in _gidx if g]
            _cnt = []
            for g in _gidx:
                c = Counter()
                for i in g:
                    c.update(_kwsets[i])
                _cnt.append(c)
            _n_all = len(bag)
            clus = []
            for gi, idx in enumerate(_gidx):
                cent = _np.asarray(km.cluster_centers_[gi]).ravel()
                top = terms[cent.argsort()[::-1][:6]].tolist()
                n_in = len(idx)
                excl = []
                # 显式定序：先按本簇占比降序，再按词名升序 —— 不依赖
                # Counter 的插入序（并列名次在不同进程/不同输入顺序下会翻转）。
                for w, c_in in sorted(_cnt[gi].items(), key=lambda kv: (-kv[1], kv[0])):
                    p_in = c_in / float(n_in)
                    if p_in < 0.15:
                        break
                    c_out = sum(_cnt[gj].get(w, 0)
                                for gj in range(len(_gidx)) if gj != gi)
                    p_out = c_out / max(1, _n_all - n_in)
                    if p_in >= 2.0 * p_out:
                        excl.append({'w': w, 'in': round(p_in * 100, 1),
                                     'out': round(p_out * 100, 1)})
                    if len(excl) >= 5:
                        break
                sub = [bag[i] for i in idx]
                clus.append({
                    # label = 独占词（优先）；为空时退回中心词，绝不留空
                    'terms': top, 'label': [e['w'] for e in excl] or top[:3],
                    'excl': excl, 'n': len(idx),
                    'topics': [[k, v] for k, v in
                               mc(Counter(x['topic'] for x in sub))],
                    'plats': [[k, v] for k, v in
                              mc(Counter(x['plat'] for x in sub))],
                    'samples': [{'plat': x['plat'], 'topic': x['topic'],
                                 'like': x['like'], 'txt': x['txt'][:120]}
                                # 并列点赞数用内容兜底排序，避免并列时顺序抖动
                                for x in sorted(sub, key=lambda y: (-y['like'], y['txt']))[:3]]})
            clus.sort(key=lambda c: -c['n'])
            x_cluster[b] = {'n': len(bag), 'k': K, 'sil': sil, 'ok': True,
                            'labelMode': '独占词（本簇占比≥15% 且≥其他簇 2 倍）',
                            'clusters': clus}
        except Exception as _e:
            x_cluster[b] = {'n': len(bag), 'k': 0, 'ok': False, 'clusters': [],
                            'err': str(_e)[:120]}
    # 把累计的 Counter / 文本样本 转成可序列化结构，并跑跨平台情感（严格增量）
    try:
        from snownlp import SnowNLP as _XSN
    except Exception:
        _XSN = None
    for b in BASINS:
        for t in XPLAT_TOPICS:
            m = x_merge.get(b, {}).get(t)
            if not m:
                continue
            m['hotwords'] = [[w, n] for w, n in mc(m.pop('hotwords', Counter()), 15)]
            arts = sorted(m.pop('topArticles', []), key=lambda x: -x['eng'])[:8]
            m['topArticles'] = [{k: v for k, v in a.items() if k != 'eng'} for a in arts]
            txts = m.pop('texts', [])
            if _XSN is not None and txts:
                pos = neu = neg = 0
                for s in txts:
                    try:
                        lab, _ = sent_pair(s, _XSN)
                    except Exception:
                        lab = None
                    if lab == '正面': pos += 1
                    elif lab == '中性': neu += 1
                    elif lab == '负面': neg += 1
                m['sent'] = [['正面', pos], ['中性', neu], ['负面', neg]]
                m['sentSample'] = len(txts)
            else:
                m['sent'] = [['正面', 0], ['中性', 0], ['负面', 0]]
                m['sentSample'] = 0
    for plat in x_live:
        rec = x_plat.get(plat, {})
        rec['hotwords'] = [[w, n] for w, n in mc(x_phw.get(plat, Counter()), 15)]
        rec['topArticles'] = [{k: v for k, v in a.items() if k != 'eng'}
                              for a in sorted(x_ptop.get(plat, []), key=lambda x: -x.get('eng', 0))[:8]]
        txts = x_ptxt.get(plat, [])
        if _XSN is not None and txts:
            pos = neu = neg = 0
            for s in txts:
                try:
                    lab, _ = sent_pair(s, _XSN)
                except Exception:
                    lab = None
                if lab == '正面': pos += 1
                elif lab == '中性': neu += 1
                elif lab == '负面': neg += 1
            rec['sent'] = [['正面', pos], ['中性', neu], ['负面', neg]]
            rec['sentSample'] = len(txts)
        else:
            rec['sent'] = [['正面', 0], ['中性', 0], ['负面', 0]]
            rec['sentSample'] = 0
    out['xplat'] = {
        'topicsCommon': list(XPLAT_TOPICS),
        'topicsOnlyWeibo': list(XPLAT_ONLY_WEIBO),
        'platforms': x_plat,
        'live': x_live,
        'absent': x_absent,
        'matrix': x_mat,          # matrix[basin][topic][platform] = 文章数
        'merged': x_merge,        # merged[basin][topic] = {article:{},comment:{},..Sum,gate}
        'gate': COMMENT_GATE,
        'cluster': x_cluster,     # 跨平台评论观点聚类（三源合并）
    }

    # ==============================================================
    # 批次 3：首页（第三段）—— 跨两流域的"一屏总括"
    # --------------------------------------------------------------
    # 首页与两个流域专题的分工：
    #   首页只回答「这个作品手里有什么、东西落在哪、当期最要紧的是什么、往哪去」，
    #   不重复任何流域内部的结构细节（那些归各自的 17 个模块）。
    # 所有数字都由已抓取的 t_basin_* 现算，不新增采集、不估值。
    # ==============================================================
    conn = pymysql.connect(cursorclass=DictCursor, **DB)
    cur = conn.cursor()

    # ---- ① 落地区域（山东省）：两套口径必须分开说 ----
    # 目标省份 = 采集时配额指定的"内容涉及省"；发布地区 = 作者的 IP 属地。
    # 两者是完全不同的东西（一个是内容讲的省，一个是人所在的省），绝不能合并成一个"山东声量"。
    def tally(sql, args=()):
        cur.execute(sql, args)
        return {str(r['k']): r['c'] for r in cur.fetchall() if r['k']}

    tgt = tally('SELECT 目标省份 k, COUNT(*) c FROM t_basin_article GROUP BY 1')
    ipr = tally('SELECT 发布地区 k, COUNT(*) c FROM t_basin_article '
                'WHERE 发布地区 IS NOT NULL AND 发布地区 <> %s GROUP BY 1', ('未知',))
    tgt_all = sum(tgt.values())
    ipr_all = sum(ipr.values())
    tgt_rank = sorted(tgt.items(), key=lambda z: (-z[1], z[0]))
    ipr_rank = sorted(ipr.items(), key=lambda z: (-z[1], z[0]))

    def rank_of(pairs, k):
        for i, z in enumerate(pairs):
            if z[0] == k:
                return i + 1, z[1]
        return None, 0

    sd_t, sd_tn = rank_of(tgt_rank, '山东')
    sd_i, sd_in = rank_of(ipr_rank, '山东')

    # 山东（采集目标口径）的议题与情感构成。
    # ⚠️ t_basin_article 里山东 97 条含全部 4 个议题，而本专题展开生态治理 + 文旅 + 医患矛盾，
    #    所以必须同时给「全量 97」与「聚焦 47」两套，否则页面上会被误读成专题口径。
    cur.execute('SELECT * FROM t_basin_article WHERE 目标省份=%s', ('山东',))
    sdRows = cur.fetchall()
    sdFocus = [r for r in sdRows if (r['议题'] or '') in TOPICS]

    def sent_of(rows):
        c = Counter()
        for r in rows:
            s, _p = sent_pair(r.get('微博内容'), sn)
            if s:
                c[s] += 1
        return c

    def pack(rows):
        sc = sent_of(rows)
        return {
            'rows': len(rows),
            'topic': [[k, v] for k, v in mc(Counter(r['议题'] or '未标注' for r in rows))],
            'sent': [[k, sc.get(k, 0)] for k in ('正面', '中性', '负面')],
            'sentTotal': sum(sc.values()),
        }

    sdAll = pack(sdRows)
    sdOnly = pack(sdFocus)
    sdProv = dict(Counter(r.get('流域') or '未标注' for r in sdRows))
    sdTop = sorted(sdFocus or sdRows, key=lambda r: -(r.get('点赞数') or 0))[:5]

    # ---- ② 当期要闻：两流域各自的头号事件簇与最高风险事件 ----
    hot_cluster, hot_risk = [], None
    for b in BASINS:
        for t in TOPICS:
            bt = out['basins'][b]['byTopic'].get(t) or {}
            for c in (bt.get('clusters') or []):
                hot_cluster.append({'basin': b, 'topic': t, 'name': c.get('name'),
                                    'n': c.get('n'), 'span': c.get('span'),
                                    'first': c.get('first'), 'sent': c.get('sent')})
        rk = out['basins'][b]['risk']['items']
        for it in rk:
            if not it.get('gated'):
                continue          # 未过 30 篇闸门的不入级，不能当"最高风险事件"报出去
            row = dict(it)
            row['basin'] = b
            if hot_risk is None or (row.get('score') or 0) > (hot_risk.get('score') or 0):
                hot_risk = row
    hot_cluster.sort(key=lambda z: -(z['n'] or 0))

    # ---- ③ 两流域核心指标对照 ----
    def one(b):
        d = out['basins'][b]
        rk = d['risk']['items']
        lv = Counter(x['key'] for x in rk)
        return d, rk, lv

    dY, rkY, lvY = one('长江')
    dH, rkH, lvH = one('黄河')
    cmp_rows = [
        {'m': '库内微博（全量口径）', 'y': dY['allN'], 'h': dH['allN'], 'kind': 'n',
         'note': '流域表全部议题，未过滤'},
        {'m': '聚焦样本（生态治理 + 文旅 + 医患矛盾）', 'y': dY['articles'], 'h': dH['articles'], 'kind': 'n',
         'note': '本作品实际展开的样本'},
        {'m': '其余议题（被过滤）', 'y': dY['filtered'], 'h': dH['filtered'], 'kind': 'n',
         'note': '社会治理 / 医患矛盾 —— 保留在库、不入本专题'},
        {'m': '评论（去重后入库）', 'y': dY['comments'], 'h': dH['comments'], 'kind': 'n',
         'note': '两流域均低于 %d 条闸门' % COMMENT_GATE},
        {'m': '参与作者数', 'y': dY['authors'], 'h': dH['authors'], 'kind': 'n',
         'note': '按作者ID 去重'},
        {'m': '覆盖省级行政区', 'y': dY['provCount'], 'h': dH['provCount'], 'kind': 'n',
         'note': '采集目标省份口径'},
        {'m': 'IP 属地可归属率', 'y': round(dY['geoKnown'] / dY['articles'] * 100, 1),
         'h': round(dH['geoKnown'] / dH['articles'] * 100, 1), 'kind': 'p',
         'note': '发布地区为空/未知的不计入'},
        {'m': '声量峰值月', 'y': dY['trend']['peak'][0], 'h': dH['trend']['peak'][0], 'kind': 's',
         'note': '%d 条 / %d 条' % (dY['trend']['peak'][1], dH['trend']['peak'][1])},
        {'m': '2026 年样本占比', 'y': dY['trend']['y2026pct'], 'h': dH['trend']['y2026pct'],
         'kind': 'p', 'note': '采样偏差，不可当传播趋势读'},
        {'m': '话语主体可判定率', 'y': dY['channel']['agentPct'], 'h': dH['channel']['agentPct'],
         'kind': 'p', 'note': '官方/媒体/个人三分类之外的不计入'},
        {'m': '互动结构（赞:评:转）', 'y': dY['interact']['all']['share'],
         'h': dH['interact']['all']['share'], 'kind': 's', 'note': '全流域合计占比'},
        {'m': '情感构成（正/中/负）',
         'y': '/'.join('%.1f%%' % (x[1] / dY['sentTotal'] * 100) for x in dY['sent'])
              if dY['sentTotal'] else '-',
         'h': '/'.join('%.1f%%' % (x[1] / dH['sentTotal'] * 100) for x in dH['sent'])
              if dH['sentTotal'] else '-', 'kind': 's',
         'note': '模型三档，未校准，只作结构参考'},
        {'m': '事件簇数', 'y': sum(len((dY['byTopic'].get(t) or {}).get('clusters') or [])
                                for t in TOPICS),
         'h': sum(len((dH['byTopic'].get(t) or {}).get('clusters') or [])
                  for t in TOPICS), 'kind': 'n', 'note': '可重叠，篇数不可相加'},
        {'m': '风险分级（红/橙/黄/蓝/灰）',
         'y': '/'.join(str(lvY.get(k, 0)) for k in ('红', '橙', '黄', '蓝', '灰')),
         'h': '/'.join(str(lvH.get(k, 0)) for k in ('红', '橙', '黄', '蓝', '灰')), 'kind': 's',
         'note': '灰=未过 %d 篇闸门，不入级' % BM.RISK_GATE},
        {'m': '最高风险事件', 'y': (rkY[0]['name'] + '（%.1f 分）' % rkY[0]['score']) if rkY else '-',
         'h': (rkH[0]['name'] + '（%.1f 分）' % rkH[0]['score']) if rkH else '-', 'kind': 's',
         'note': '规则化四级评分'},
        {'m': '作者集中度（Top10 占比）', 'y': dY['nodes']['conc'][2][2],
         'h': dH['nodes']['conc'][2][2], 'kind': 'p', 'note': '越高越集中于少数账号'},
        {'m': '情感模型中性段占比', 'y': dY['calib']['neuPct'], 'h': dH['calib']['neuPct'],
         'kind': 'p', 'note': '中性越低说明模型越"敢表态"'},
    ]
    conn.close()

    out['home'] = {
        'kpi': {
            'articles': dY['articles'] + dH['articles'],
            'allN': dY['allN'] + dH['allN'],
            'filtered': dY['filtered'] + dH['filtered'],
            'comments': dY['comments'] + dH['comments'],
            'authors': dY['authors'] + dH['authors'],
            'provinces': len(tgt),
            'clusters': len(hot_cluster),
            'riskItems': len(rkY) + len(rkH),
            'yz': {'articles': dY['articles'], 'allN': dY['allN'], 'comments': dY['comments']},
            'hh': {'articles': dH['articles'], 'allN': dH['allN'], 'comments': dH['comments']},
            'months': sorted(set([m for b in BASINS for m, _n in out['basins'][b]['trend']['months']])),
        },
        'cmp': cmp_rows,
        'landing': {
            'prov': '山东', 'basin': '黄河',
            # 两套口径分开给，页面也必须分开展示
            'target': {'n': sd_tn, 'rank': sd_t, 'of': len(tgt_rank), 'total': tgt_all},
            'ip': {'n': sd_in, 'rank': sd_i, 'of': len(ipr_rank), 'total': ipr_all},
            'topTarget': [list(z) for z in tgt_rank[:8]],
            'topIp': [list(z) for z in ipr_rank[:8]],
            # 两套口径各给一次：all = 该省全部 4 议题；focus = 本专题真正展开的 2 议题
            'all': sdAll,
            'focus': sdOnly,
            'basinSplit': [[k, v] for k, v in sorted(sdProv.items(), key=lambda z: -z[1])],
            'top': [{'text': (r.get('微博内容') or '')[:110],
                     'like': int(r.get('点赞数') or 0), 'cmt': int(r.get('评论数') or 0),
                     'rep': int(r.get('转发数') or 0),
                     'time': str(r.get('发布时间') or '')[:10],
                     'topic': r.get('议题') or '未标注'} for r in sdTop],
            'cities': BGEO.SD_CITIES,
            'riverCities': BGEO.SD_RIVER_CITIES,
            'anchors': BGEO.SD_ANCHORS,
            'note': BGEO.SD_DATA_NOTE,
        },
        'hot': {
            'cluster': hot_cluster[:6],
            'clusterAll': len(hot_cluster),
            'risk': hot_risk,
        },
        # 首页中国地图的填充值：采集目标省份口径的全表（20 个流域省）。
        # 只给这 20 个 —— 非流域省两江都不通行，页面上按"非流域"固定色处理，不给数字。
        'prov': {k: v for k, v in tgt_rank},
    }

    # 首页自带一致性断言：任何一条对不上就中止，不生成"看起来对"的页面
    H = out['home']
    assert H['kpi']['articles'] == sum(out['basins'][b]['articles'] for b in BASINS)
    assert H['kpi']['allN'] == sum(out['basins'][b]['allN'] for b in BASINS)
    assert H['kpi']['filtered'] == H['kpi']['allN'] - H['kpi']['articles']
    assert H['landing']['target']['n'] == len(sdRows), \
        '山东采集目标条数与逐行明细不一致：%s vs %s' % (H['landing']['target']['n'], len(sdRows))
    assert set(H['landing']['cities']) == set(BGEO.SD_CITIES) and len(BGEO.SD_CITIES) == 16
    assert set(BGEO.SD_RIVER_CITIES) <= set(BGEO.SD_CITIES), '沿黄 9 市必须都在 16 地市内'
    assert len(BGEO.SD_RIVER_CITIES) == 9, '黄河在山东流经 9 市'
    assert hot_risk is not None, '两流域都没有可入级事件，首页"当期要闻"无从填'

    DST = os.path.join(BASE, 'basin_data.json')
    io.open(DST, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False))
    print('\n输出:', os.path.basename(DST), '%.1f KB' % (os.path.getsize(DST) / 1024.0))
    for b in BASINS:
        d = out['basins'][b]
        print('  %s: 议题 %s | 省份 %d 个 | 情感 %s'
              % (b, d['topicDist'], d['provCount'],
                 dict(zip(('正', '中', '负'), [x[1] for x in d['sent']]))))
        _cl = [(t, d['byTopic'][t]['clusters'], d['byTopic'][t]['coverage'])
               for t in TOPICS if d['byTopic'].get(t)]
        for _t, _c, _cg in _cl:
            print('     %s：%d 簇 · 覆盖 %d/%d（%.1f%%）· 簇间重叠 %d 篇 · 词云 %d 词'
                  % (_t, len(_c), _cg['covered'], _cg['topicRows'], _cg['pct'],
                     _cg['overlap'], len(d['wordsCloud'])))
        print('     IP 属地：可归属 %d / %d 条（缺失 %.1f%%），Top %s'
              % (d['geoKnown'], d['articles'], pct(d['geoUnknown'], d['articles']),
                 d['geoProv'][:3]))
    print('  评论闸门(%d)：%s'
          % (COMMENT_GATE, {b: out['basins'][b]['commentEnough'] for b in BASINS}))
    print('\n== 批次 2 恢复模块数据 ==')
    for b in BASINS:
        d = out['basins'][b]
        ch, it, nd, rk, cb, tr = (d['channel'], d['interact'], d['nodes'], d['risk'],
                                  d['calib'], d['trend'])
        print('  [%s] 趋势峰值 %s(%d 条, %s%%) · 2026 占比 %s%% · 连续月 %d 点'
              % (b, tr['peak'][0], tr['peak'][1], tr['peak'][2], tr['y2026pct'],
                 len(tr['months'])))
        print('     渠道：可判定主体 %d/%d（%s%%） 终端 %d 未归类 %d'
              % (ch['agentKnown'], d['articles'], ch['agentPct'], ch['device'],
                 ch['unknown']))
        print('     互动：赞:评:转 = %s · 单篇 转 %.1f 赞 %.1f · 转赞比 %.4f'
              % (it['all']['share'], it['all']['perRp'], it['all']['perLk'],
                 it['all']['rrRatio']))
        print('     节点：作者 %d 位 · 一次作者 %s%% · Top10 占 %s%%'
              % (nd['authors'], nd['oncePct'], nd['conc'][2][2]))
        lv = Counter(x['key'] for x in rk['items'])
        print('     风险：%d 个事件 · 分级 %s · 最高 %s(%s)'
              % (len(rk['items']), dict(lv),
                 rk['items'][0]['name'] if rk['items'] else '-',
                 rk['items'][0]['score'] if rk['items'] else 0))
        print('     校准：中性段 %s%% · 极端分(>=.9 或 <=.1) %s%% · 词典法一致率 %s%%'
              % (cb['neuPct'], cb['extPct'], cb['agreePct']))
    print('  跨平台：%s'
          % ' / '.join('%s 内容%d·评论%d' % (p['name'], p['article'], p['comment'])
                       for p in out['cross']['platforms']))
    for b in BASINS:
        d = out['basins'][b]
        print('  [%s] 全量 %d 条（含被过滤 %d 条）：%s'
              % (b, d['allN'], d['filtered'], d['allTopics']))

    print('\n== 批次 3 首页（第三段）==')
    H = out['home']
    tgtL, ipL = H['landing']['target'], H['landing']['ip']
    print('  样本：全量 %d / 聚焦 %d / 过滤 %d / 评论 %d / 作者 %d / 覆盖省 %d'
          % (H['kpi']['allN'], H['kpi']['articles'], H['kpi']['filtered'],
             H['kpi']['comments'], H['kpi']['authors'], H['kpi']['provinces']))
    print('  月度跨度：%s ~ %s（%d 个月）'
          % (H['kpi']['months'][0], H['kpi']['months'][-1], len(H['kpi']['months'])))
    print('  对照表：%d 行指标 × 2 流域' % len(H['cmp']))
    print('  山东·采集目标口径：%d 条（第 %d / %d 位，全国合计 %d）'
          % (tgtL['n'], tgtL['rank'], tgtL['of'], tgtL['total']))
    print('  山东·发布属地口径：%d 条（第 %d / %d 位，可归属合计 %d）'
          % (ipL['n'], ipL['rank'], ipL['of'], ipL['total']))
    print('  山东·全量口径 %d 条 议题 %s ｜ 情感 %s'
          % (H['landing']['all']['rows'], H['landing']['all']['topic'],
             H['landing']['all']['sent']))
    print('  山东·聚焦口径 %d 条 议题 %s ｜ 情感 %s ｜ 流域 %s'
          % (H['landing']['focus']['rows'], H['landing']['focus']['topic'],
             H['landing']['focus']['sent'], H['landing']['basinSplit']))
    print('  当期要闻：%d 个事件簇（两流域×三议题）；最高风险 %s（%s · %.1f 分）'
          % (H['hot']['clusterAll'], H['hot']['risk']['name'],
             H['hot']['risk']['basin'], H['hot']['risk']['score']))
    print('  事件簇 Top3：%s'
          % ' / '.join('%s(%s %d 条)' % (c['name'], c['basin'], c['n'])
                       for c in H['hot']['cluster'][:3]))
    print('  山东无地市数据（现有采集仅到省级）→ 省图只画边界 + 标 9 个沿黄市')


if __name__ == '__main__':
    main()

