# -*- coding: utf-8 -*-
"""L1-3 评论情感与诉求：SnowNLP 情感分布 + 诉求关键词词典。

落实红线③：样本不足（N<30）时明确标注"不外推"。
诉求词典为轻量规则，覆盖投诉维权 / 质疑 / 咨询求助 / 夸赞认可 / 失望不满五类。
"""
from base import BaseAnalyzer, register
from collections import Counter

try:
    from snownlp import SnowNLP
except Exception:
    SnowNLP = None

GATE = 30
DEMAND_LEX = {
    '投诉维权': ['投诉', '维权', '举报', '曝光', '侵权', '欺骗', '欺骗消费者', '坑', '假'],
    '质疑': ['质疑', '为什么', '怎么回', '忽悠', '骗', '真的吗'],
    '咨询求助': ['怎么', '如何', '求助', '咨询', '哪里', '求', '请问', '什么情况'],
    '夸赞认可': ['点赞', '支持', '好评', '好看', '赞', '棒', '不错', '厉害', '美丽', '喜欢'],
    '失望不满': ['失望', '差评', '垃圾', '无语', '气愤', '愤怒', '坑人', '恶心', '后悔', '太差'],
}


def _sent(text):
    if SnowNLP is None:
        return 0.5
    try:
        return SnowNLP(text).sentiments
    except Exception:
        return 0.5


@register
class CommentInsightAnalyzer(BaseAnalyzer):
    name = 'comment_insight'
    version = '0.2'
    needs = ('comments',)

    def analyze(self, ctx):
        texts = [t for t in (ctx.get('comments') or []) if isinstance(t, str) and t.strip()]
        n = len(texts)
        if n == 0:
            return {'评论数': 0, '状态': '无评论', '情感分布': None, '诉求分布': None, '样本过闸门': False}
        pos = neg = neu = 0
        for t in texts:
            s = _sent(t)
            if s >= 0.6:
                pos += 1
            elif s <= 0.4:
                neg += 1
            else:
                neu += 1
        demands = Counter()
        for t in texts:
            for cat, kws in DEMAND_LEX.items():
                if any(k in t for k in kws):
                    demands[cat] += 1
        return {
            '评论数': n,
            '情感分布': {'正面': pos, '中性': neu, '负面': neg},
            '负面占比': round(neg / n, 3),
            '诉求分布': dict(demands),
            '样本过闸门': n >= GATE,
            '外推声明': ('基于%d条样本，仅作现象提示' % n) if n < GATE else '样本达闸门-可作结构参考',
        }
