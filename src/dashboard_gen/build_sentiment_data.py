# -*- coding: utf-8 -*-
"""抽取 /page/sentimentAnalysis 用到的 fenci/*.csv，转成预览页可注入的 JSON。
只读项目文件，不写入项目目录。"""
import io, os, csv, json, sys, datetime
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
FENCI = os.path.join(os.path.dirname(HERE), 'fenci')
OUT = os.path.join(HERE, 'sentiment_preview_data.json')


def read_csv(name):
    path = os.path.join(FENCI, name)
    with io.open(path, encoding='utf-8-sig', errors='replace') as f:
        rows = [r for r in csv.reader(f) if r and any(str(c).strip() for c in r)]
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
    return rows[0], rows[1:], mt


#: 情感标签规范化映射：把可能出现的别名/大小写统一到 正面/中性/负面。
#: 【修复】原实现直接用 `c.get('正面')` 等三个精确字符串取值，
#:   CSV 里任何别名（"正向"/"中立"/"Positive"）都会被**静默丢弃**：
#:   它进了 total 分母却不进 v 分子，造成"v 之和 != total"的隐形对账缺口。
SENT_ALIASES = {
    '正面': '正面', '正向': '正面', '积极': '正面', 'positive': '正面', 'pos': '正面',
    '中性': '中性', '中立': '中性', 'neutral': '中性', 'neu': '中性', '一般': '中性',
    '负面': '负面', '负向': '负面', '消极': '负面', 'negative': '负面', 'neg': '负面',
}


def norm_sentiment(raw):
    """把任意情感标签归一化为 正面/中性/负面；无法识别返回 None。"""
    s = str(raw or '').strip()
    if not s:
        return None
    return SENT_ALIASES.get(s) or SENT_ALIASES.get(s.lower())


def dist(rows, headers, col):
    """固定顺序 正面 / 中性 / 负面，输出纯数组，前端按下标取值（不做中文键匹配）。

    标签先经 norm_sentiment 归一化；无法识别的标签不再静默丢弃，
    而是单独计入 'unknown' 并在 total 中如实反映，保证可对账。
    """
    i = headers.index(col)
    c = Counter()
    for r in rows:
        if len(r) <= i:
            continue
        c[norm_sentiment(r[i]) or '未知'] += 1
    return {'v': [c.get('正面', 0), c.get('中性', 0), c.get('负面', 0)],
            'total': sum(c.values()),
            'unknown': c.get('未知', 0)}


# 1) 热词情感
h1, r1, m1 = read_csv('hot_sent_final.csv')
hot = dist(r1, h1, 'sentiment')
hot_words = {}
if 'word' in h1:
    wi, si = h1.index('word'), h1.index('sentiment')
    for r in r1:
        if len(r) > max(wi, si):
            w = str(r[wi]).strip()
            lab = norm_sentiment(r[si])
            # 只收录标签能识别的词条：原先未识别标签会经 SIDX.get(..., 1)
            # 被默认成「中性」，属于静默错标；现直接剔除并计入 unknown
            if w and lab:
                hot_words[w] = lab

# 2) 评论情感
h2, r2, m2 = read_csv('comment_sent_final.csv')
comment = dist(r2, h2, 'sentiment')

# 3) 文章情感 + 机制标签
h3, r3, m3 = read_csv('article_sent_final.csv')
article = dist(r3, h3, 'sentiment')
tags = []
if 'tag' in h3:
    ti = h3.index('tag')
    tags = [[k, v] for k, v in Counter(str(r[ti]).strip() for r in r3 if len(r) > ti).most_common()
            if k]

# 4) 热词 TOP15（原页取 comment_fre.csv 前 15 行后反转）
h4, r4, m4 = read_csv('comment_fre.csv')
top15 = [[str(r[0]).strip(), int(float(r[1]))] for r in r4[:15] if len(r) > 1 and str(r[1]).strip()]

# 5) 交叉核对：旧情感词表 vs 新热词榜（读上一环节生成的实时统计）
new = json.load(io.open('hotword_preview_data.json', encoding='utf-8'))
SIDX = {'正面': 0, '中性': 1, '负面': 2}
overlap = {}
for key, label in [('article', '微博文章'), ('comment', '微博评论')]:
    top = new[key]['cleaned']['top']
    hit = [{'w': t['w'], 'freq': t['freq'], 'docf': t['docf'],
            'si': SIDX[hot_words[t['w']]]}
           for t in top if t['w'] in hot_words]
    overlap[key] = {'label': label, 'topn': len(top), 'hit': len(hit),
                    'rate': round(len(hit) / max(len(top), 1) * 100), 'rows': hit}

data = {
    'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    'labels': ['正面', '中性', '负面'],
    'src_note': 'fenci/*.csv 离线快照',
    'mtime': {'hot': m1, 'comment': m2, 'article': m3, 'fre': m4},
    'hot': hot, 'comment': comment, 'article': article,
    'article_tag': tags,
    'top15': top15,
    'overlap': overlap,
    # 标签归一化后仍无法识别的条数（正常应为 0；非 0 说明上游产出了新标签，
    # 需在 SENT_ALIASES 里补映射，否则这部分样本会从分布里消失）
    'sent_unknown': {'hot': hot.get('unknown', 0), 'comment': comment.get('unknown', 0),
                     'article': article.get('unknown', 0)},
    'new_total': {'article': new['article']['cleaned']['docs'],
                  'comment': new['comment']['cleaned']['docs']},
}

io.open(OUT, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=1))
print('已写出', OUT)
print('  热词情感', hot, '| 快照', m1)
print('  评论情感', comment, '| 快照', m2)
print('  文章情感', article, '| 快照', m3)
print('  机制标签', tags)
print('  TOP15', top15[:5])
print('  覆盖率 —— 文章 Top%d 命中 %d 个；评论 Top%d 命中 %d 个'
      % (overlap['article']['topn'], overlap['article']['hit'],
         overlap['comment']['topn'], overlap['comment']['hit']))
