# -*- coding: utf-8 -*-
"""
长江 / 黄河流域 —— 「生态治理 + 文旅 + 医患矛盾」A+B 关键词源（独立新增文件）
=============================================================================
用途
    给多平台采集器（复用 BettaFish/MindSpider 或本项目自有爬虫）提供统一的
    关键词清单。**只产词表，不联网、不写库、不改动任何既有爬虫。**

为什么是 A+B
    多平台搜索接口对「多词组合」的语义并不统一（微博按 AND，小红书/抖音/知乎
    未必），所以单一策略都会有短板：

      A 类（精准）「省份 议题词」  例：湖北 环保督察
          → 命中即归属该省与流域，精度高；但复合词召回有限。
      B 类（召回）「议题词」      例：环保督察
          → 各平台通吃、量大；但**不含地域**，需事后按作者 IP 属地 /
            内容提及省份判定流域（复用 mask_region / basin_classify_basin）。

    两者合并 = 精度兜底 + 召回补充；入库后统一用 `source_keyword` 字段反解。

口径唯一性
    省份表 / 议题词库 全部 import 自 `river_basin_spider`，**不在此处另写一份**，
    避免与微博、抖音两侧漂移。

用法
    python spider/basin_keyword_source.py                      # 预览（默认 dry-run）
    python spider/basin_keyword_source.py --write              # 落盘词表与映射
    python spider/basin_keyword_source.py --keywords-per-topic 4 --write
    python spider/basin_keyword_source.py --no-b               # 只要 A 类
=============================================================================
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from river_basin_spider import (          # noqa: E402
    BASIN_PROVINCES,
    FOCUS_TOPIC_WORDS,
    TOPIC_KEYWORDS,
    _PROV_TO_BASIN,
)


def _sentiment_of(topic, word):
    """词 -> 情感分类（消极/中性/积极）；非聚焦议题返回 '-'。"""
    for s, words in (FOCUS_TOPIC_WORDS.get(topic) or {}).items():
        if word in words:
            return s
    return '-'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))

# 本作品聚焦的三个主题（与前端取数口径一致：生态治理 + 文旅 + 医患矛盾）
FOCUS_TOPICS = ('生态治理', '文旅', '医患矛盾')

# 默认用满整个议题词表（每议题 9 词，三情感类各 3）。
# 若显式传 --keywords-per-topic N，则按轮转顺序取前 N 个 —— 轮转保证
# N>=3 时消极/中性/积极三类都会被覆盖到。
DEFAULT_WORDS_PER_TOPIC = None


def _basin_of_province(prov):
    """省份 -> 流域标签（青海/四川两地共源时返回 '黄河长江'）。"""
    hits = _PROV_TO_BASIN.get(prov, [])
    if len(hits) >= 2:
        return '黄河长江'
    return hits[0] if hits else '非流域'


def _pick_words(topic, n):
    """取议题词：n 为 None/0 时用满整个词表，否则按轮转顺序取前 n 个。"""
    words = TOPIC_KEYWORDS.get(topic, [])
    return list(words) if not n else list(words)[:int(n)]


def build_matrix(topics=None, words_per_topic=None, with_a=True, with_b=True):
    """
    生成 A+B 关键词矩阵。

    返回 list[dict]，每项：
      keyword   : 实际送进搜索框的字符串
      kind      : 'A'(省份组合) | 'B'(纯议题词)
      topic     : 议题
      province  : A 类为目标省份；B 类为 None
      basin     : A 类为该省在 BASIN_PROVINCES 里**登记的那条流域**（用于配额分配）；
                  B 类为 None（事后判定）
      basin_all : A 类为该省的**地理真实归属**（四川/青海为 '黄河长江'，共源）；
                  B 类为 None。下游若要按地理口径聚合，请用 basin_all，别用 basin。
      topic_word: 该条用的议题词
    """
    topics = list(topics or FOCUS_TOPICS)
    n = words_per_topic or DEFAULT_WORDS_PER_TOPIC

    items, seen = [], set()

    # ---- A 类：流域省份 × 议题词 ----
    if with_a:
        for basin, provs in BASIN_PROVINCES.items():
            for prov in provs:
                for topic in topics:
                    for w in _pick_words(topic, n):
                        kw = '%s %s' % (prov, w)
                        if kw in seen:
                            continue
                        seen.add(kw)
                        items.append({
                            'keyword': kw, 'kind': 'A', 'topic': topic,
                            'province': prov, 'basin': basin,
                            'basin_all': _basin_of_province(prov), 'topic_word': w,
                            'sentiment': _sentiment_of(topic, w),
                        })

    # ---- B 类：纯议题词（跨流域通用，靠事后判流域）----
    if with_b:
        for topic in topics:
            for w in _pick_words(topic, n):
                if w in seen:
                    continue
                seen.add(w)
                items.append({
                    'keyword': w, 'kind': 'B', 'topic': topic,
                    'province': None, 'basin': None, 'basin_all': None, 'topic_word': w,
                    'sentiment': _sentiment_of(topic, w),
                })

    return items


def balanced_subset(items, limit, b_share=0.2):
    """从完整矩阵里抽一个**均衡子集**，而不是随机截断。

    为什么要均衡而不是随机
        MediaCrawler 的 key_manager 在关键词超限时是 `random.shuffle` 后截断 —— 那样
        20 个省 / 2 个议题 / 3 类情感会被打乱成任意分布，跑出来的样本没法做地区或
        议题的横向对比，而且每次跑结果还不一样（不可复现）。这里改成确定性抽样。

    抽取顺序（三层，先保覆盖、再保深度）
        第 1 层：每个省各取第 1 个 A 词  → 保证 **20 个省全部出现**
        第 2 层：每个省各取第 2 个 A 词  → 此时一个省已跨两个议题
        第 3 层：继续按"省轮次"加深，直到 A 类配额用完
        B 类：按 `b_share` 预留份额，按 (议题 × 情感) 轮转取，保证三类情感都在

    省内的词序怎么定（决定情感均衡）
        给每个省一个序号 pi（0..19），该省第 k 个词取
            议题 = topics[(pi + k) % 2]
            词   = words[(pi + k) % 9]
        词表本身是「消极→中性→积极」轮转扁平化的，所以词序号 % 3 就是情感类。
        pi 逐个递增 → 不同省用到的词序号错开 → 20 个省自然把 9 个词、3 类情感铺满。
    """
    if not limit or limit >= len(items):
        return items

    topics = list(FOCUS_TOPICS)
    a_items = [i for i in items if i['kind'] == 'A']
    b_items = [i for i in items if i['kind'] == 'B']

    # 省份出现顺序：按流域分组，再按登记顺序（与 BASIN_PROVINCES 一致）
    provs = []
    for _basin, plist in BASIN_PROVINCES.items():
        for p in plist:
            if p not in provs:
                provs.append(p)

    # 把 A 类按 (省, 词序) 排成方阵：matrix[prov] = [按 pi 轮转排序后的词]
    by_prov = {p: [] for p in provs}
    for it in a_items:
        by_prov.setdefault(it['province'], []).append(it)

    def _rank_key(prov, it):
        """该省的词按 (pi+k) 轮转后的次序；用议题+词在词表里的位置反推 k。"""
        pi = provs.index(prov)
        topic_i = topics.index(it['topic']) if it['topic'] in topics else 0
        words = TOPIC_KEYWORDS.get(it['topic'], [])
        wi = words.index(it['topic_word']) if it['topic_word'] in words else 0
        # k 满足 (pi+k)%2 == topic_i 且 (pi+k)%9 == wi → 取最小非负解
        for k in range(18):
            if (pi + k) % 2 == topic_i and (pi + k) % 9 == wi:
                return k
        return 99

    for p in provs:
        by_prov[p].sort(key=lambda it, _p=p: _rank_key(_p, it))

    # B 类：按 (词序 k, 议题) 轮转 → k%3 即情感，先取满三情感
    b_items.sort(key=lambda it: (
        TOPIC_KEYWORDS.get(it['topic'], []).index(it['topic_word'])
        if it['topic_word'] in TOPIC_KEYWORDS.get(it['topic'], []) else 99,
        topics.index(it['topic']) if it['topic'] in topics else 0))

    n_b = min(len(b_items), int(round(limit * max(0.0, min(1.0, b_share)))))
    n_a = limit - n_b

    picked = []
    # 第 1..N 层：第 k 层 = 每个省的第 k 个词
    k = 0
    while len(picked) < n_a:
        added = False
        for p in provs:
            if len(picked) >= n_a:
                break
            if k < len(by_prov.get(p, [])):
                picked.append(by_prov[p][k])
                added = True
        if not added:            # 所有省的第 k 层都空了
            break
        k += 1

    if len(picked) < n_a:        # A 类不够就补 B
        need = n_a - len(picked)
        picked += b_items[:need]
        n_b = max(0, n_b - need)

    picked += b_items[:n_b]

    # 输出顺序：保持原始 items 顺序，便于与完整词表对照
    chosen = {i['keyword'] for i in picked}
    return [i for i in items if i['keyword'] in chosen]


def summarize(items):
    """按 议题 / 流域 / 类型 汇总，并打印样例。"""
    print('=' * 74)
    print('A+B 关键词矩阵（共 %d 个）' % len(items))
    print('=' * 74)

    by_topic = Counter(i['topic'] for i in items)
    by_kind = Counter(i['kind'] for i in items)
    by_basin = Counter(i['basin'] or '(待判定)' for i in items)

    print('\n按类型：' + '   '.join('%s=%d' % (k, v) for k, v in sorted(by_kind.items())))
    print('按议题：' + '   '.join('%s=%d' % (k, v) for k, v in by_topic.items()))
    by_sent = Counter(i['sentiment'] for i in items)
    print('按情感：' + '   '.join('%s=%d' % (k, v) for k, v in sorted(by_sent.items())))
    print('\n按流域（登记口径，用于配额）：' + '   '.join('%s=%d' % (k, v) for k, v in by_basin.items()))

    shared = [i for i in items if i.get('basin_all') == '黄河长江']
    if shared:
        print('[WARN] 共源省（地理同属两流域，注册表里只登记一条）：%s —— %d 个关键词'
              % ('、'.join(sorted({i['province'] for i in shared})), len(shared)))

    print('\n各议题启用的议题词（按情感三分类）：')
    for t in FOCUS_TOPICS:
        used = [w for w in TOPIC_KEYWORDS.get(t, []) if any(
            i['topic'] == t and i['topic_word'] == w for i in items)]
        by_s = {}
        for w in used:
            by_s.setdefault(_sentiment_of(t, w), []).append(w)
        print('   %-6s ' % t + '   '.join(
            '%s: %s' % (s, '、'.join(by_s.get(s, [])) or '—')
            for s in ('消极', '中性', '积极')))
        miss = [s for s in ('消极', '中性', '积极') if not by_s.get(s)]
        if miss:
            print('   %-6s [WARN] 缺情感类：%s —— 提高 --keywords-per-topic，或补词表'
                  % ('', '、'.join(miss)))
        rest = [w for w in TOPIC_KEYWORDS.get(t, []) if w not in used]
        if rest:
            print('   %-6s 词表还有 %d 个未启用：%s' % ('', len(rest), '、'.join(rest)))

    a_items = [i for i in items if i['kind'] == 'A']
    b_items = [i for i in items if i['kind'] == 'B']
    print('\nA 类样例（省份组合）：')
    for i in a_items[:6]:
        print('   %-22s -> %s·%s' % (i['keyword'], i['basin'], i['topic']))
    print('    …共 %d 个' % len(a_items))
    print('\nB 类（纯议题词，需事后判流域）：')
    for i in b_items:
        print('   %-22s -> %s' % (i['keyword'], i['topic']))
    print('    …共 %d 个' % len(b_items))


def write_outputs(items, tag=''):
    """落盘两份：给采集器的 KEYWORDS 串 + 事后反解用的映射。"""
    kws = [i['keyword'] for i in items]
    txt = os.path.join(_HERE, 'basin_keywords%s.txt' % tag)
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(','.join(kws))          # MediaCrawler 的 KEYWORDS 就是逗号分隔

    mp = os.path.join(_HERE, 'basin_keywords_map%s.json' % tag)
    with open(mp, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(timespec='seconds'),
            'topics': list(FOCUS_TOPICS),
            'count': len(items),
            'map': {i['keyword']: {k: i[k] for k in ('kind', 'topic', 'province', 'basin',
                                                     'basin_all', 'sentiment')}
                    for i in items},
        }, f, ensure_ascii=False, indent=2)

    print('\n已写入：')
    print('   关键词串   %s' % txt)
    print('   反解映射   %s' % mp)
    return txt, mp


def main(argv=None):
    ap = argparse.ArgumentParser(description='长江/黄河流域「生态治理+文旅」A+B 关键词源')
    ap.add_argument('--topics', nargs='+', default=list(FOCUS_TOPICS),
                    choices=list(TOPIC_KEYWORDS.keys()), help='议题，默认 生态治理 文旅')
    ap.add_argument('--keywords-per-topic', type=int, default=DEFAULT_WORDS_PER_TOPIC,
                    help='每个议题取前 N 个词（按 消极→中性→积极 轮转，N>=3 覆盖三类情感）；'
                         '默认用满整个议题词表')
    ap.add_argument('--no-a', action='store_true', help='不要 A 类（省份组合）')
    ap.add_argument('--no-b', action='store_true', help='不要 B 类（纯议题词）')
    ap.add_argument('--limit-keywords', type=int, default=None,
                    help='只取 N 个关键词（**均衡抽样**，非随机截断）—— 用于控制单次采集耗时。'
                         '抽样规则：先保证每个省至少 1 个词、再逐层加深、B 类按 --b-share 留份额。')
    ap.add_argument('--b-share', type=float, default=0.2,
                    help='--limit-keywords 时 B 类（纯议题词）占总数的比例，默认 0.2')
    ap.add_argument('--tag', default='',
                    help='输出文件后缀，如 --tag -1h → basin_keywords-1h.txt')
    ap.add_argument('--write', action='store_true', help='落盘词表与映射（默认只预览）')
    args = ap.parse_args(argv)

    items = build_matrix(topics=args.topics,
                         words_per_topic=args.keywords_per_topic,
                         with_a=not args.no_a, with_b=not args.no_b)
    if not items:
        print('关键词为空，请检查 --topics / --keywords-per-topic。')
        return

    full_n = len(items)
    if args.limit_keywords:
        items = balanced_subset(items, args.limit_keywords, args.b_share)
        print('已做均衡抽样：%d 个 → %d 个（b_share=%.2f）\n'
              % (full_n, len(items), args.b_share))

    summarize(items)

    # 抽样后补充一段"覆盖度自检"——这是判断能不能用来做横向对比的关键
    a_items = [i for i in items if i['kind'] == 'A']
    provs = sorted({i['province'] for i in a_items})
    print('\n覆盖度自检：')
    print('   Ａ类覆盖省份 %d 个：%s' % (len(provs), '、'.join(provs) or '—'))
    print('   议题分布     %s' % '   '.join(
        '%s=%d' % (t, sum(1 for i in items if i['topic'] == t)) for t in FOCUS_TOPICS))
    print('   情感分布     %s' % '   '.join(
        '%s=%d' % (s, sum(1 for i in items if i['sentiment'] == s))
        for s in ('消极', '中性', '积极')))
    print('   含 B 类       %d 个' % sum(1 for i in items if i['kind'] == 'B'))

    if args.write:
        write_outputs(items, tag=args.tag)
    else:
        print('\n[dry-run] 仅预览，未写任何文件。加 --write 落盘。')


if __name__ == '__main__':
    main(sys.argv[1:])
