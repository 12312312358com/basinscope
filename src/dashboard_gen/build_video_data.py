# -*- coding: utf-8 -*-
"""视频分析数据构建：读三层特征库 → 聚合 → `video_data.json`（供 video_analysis.html 出图）。

原则同 build_basin_data.py：**所有数字来自真实统计，无一处估值**；样本不足如实标注。

数据源：
  video_features/l1_features.jsonl  全量（元数据/封面/评论）
  video_features/l2_features.jsonl  抽样（关键帧，覆盖 118 条中的有效部分）
  video_features/l3_features.jsonl  可选（音频层，装了 ASR 后端才有真实转写）
"""
import collections
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, '..'))
VF = os.path.join(REPO, 'video_features')
OUT = os.path.join(_HERE, 'video_data.json')


def _load(p):
    out = []
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def _i(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _buckets(vals, edges, labels):
    c = collections.Counter()
    for v in vals:
        for i, e in enumerate(edges):
            if v < e:
                c[labels[i]] += 1
                break
        else:
            c[labels[-1]] += 1
    return [{'name': l, 'value': c.get(l, 0)} for l in labels]


def _kv(r, ana, key):
    return ((r.get('features', {}).get(ana, {}) or {}).get('kv') or {}).get(key)


def build():
    l1 = _load(os.path.join(VF, 'l1_features.jsonl'))
    l2 = _load(os.path.join(VF, 'l2_features.jsonl'))
    l3 = _load(os.path.join(VF, 'l3_features.jsonl'))

    d = {'meta': {'l1_n': len(l1), 'l2_n': len(l2), 'l2_ok': 0, 'l3_n': len(l3)},
         'l1': {}, 'l2': {}, 'l3': {}}

    # ---------------- L1（全量） ----------------
    d['l1']['platform'] = [{'name': k or '?', 'value': v}
                           for k, v in collections.Counter(r.get('platform') for r in l1).most_common()]
    d['l1']['basin'] = [{'name': k or '未标', 'value': v}
                        for k, v in collections.Counter(r.get('basin') for r in l1).most_common()]
    d['l1']['topic'] = [{'name': k or '未标', 'value': v}
                        for k, v in collections.Counter(r.get('topic') for r in l1).most_common()]

    # 互动画像
    inter = [_i(_kv(r, 'meta_profile', '互动总量')) for r in l1]
    r2l = [_i(_kv(r, 'meta_profile', '转发_点赞比')) for r in l1 if _kv(r, 'meta_profile', '转发_点赞比')]
    d['l1']['interact'] = {
        'total': int(sum(inter)),
        'buckets': _buckets([v for v in inter], [10, 100, 1000, 10000, 100000, float('inf')],
                            ['<10', '10~100', '100~1k', '1k~1w', '1w~10w', '≥10w']),
        'r2l_avg': round(sum(r2l) / len(r2l), 3) if r2l else None,
    }

    # 封面视觉（有封面的行）
    hue = collections.Counter()
    bright = []
    aspect = collections.Counter()
    has_cover = 0
    for r in l1:
        cv = (r.get('features', {}).get('cover_visual', {}) or {}).get('kv') or {}
        if cv.get('has_cover'):
            has_cover += 1
            if cv.get('主色调桶'):
                hue[cv['主色调桶']] += 1
            if cv.get('均值亮度') is not None:
                bright.append(_i(cv['均值亮度']))
            ar = _i(cv.get('长宽比'))
            aspect['竖屏' if ar and ar < 1 else '横屏'] += 1
    d['l1']['cover'] = {
        'has_cover': has_cover,
        'hue': [{'name': k, 'value': v} for k, v in hue.most_common()],
        'bright': _buckets(bright, [64, 128, 192, float('inf')], ['暗(<64)', '中(64~128)', '亮(128~192)', '高亮(≥192)']),
        'aspect': [{'name': k, 'value': v} for k, v in aspect.most_common()],
    }

    # 评论洞察
    sent = collections.Counter()
    neg = []
    dem = collections.Counter()
    n_cmt = 0
    for r in l1:
        ci = (r.get('features', {}).get('comment_insight', {}) or {}).get('kv') or {}
        sd = ci.get('情感分布') or {}
        for k, v in sd.items():
            sent[k] += v
        if ci.get('负面占比') is not None:
            neg.append(_i(ci['负面占比']))
        for k, v in (ci.get('诉求分布') or {}).items():
            dem[k] += v
        if ci.get('评论数'):
            n_cmt += 1
    d['l1']['comment'] = {
        'with_comment': n_cmt,
        'sentiment': [{'name': k, 'value': v} for k, v in sent.most_common()],
        'neg_avg': round(sum(neg) / len(neg), 3) if neg else None,
        'demand': [{'name': k, 'value': v} for k, v in dem.most_common()],
    }

    # 时长（L1 富化得到的部分）
    dur1 = [_i(_kv(r, 'meta_profile', '时长')) for r in l1 if _kv(r, 'meta_profile', '时长')]
    d['l1']['duration'] = {'n': len(dur1),
                           'buckets': _buckets(dur1, [15, 60, 300, 900, float('inf')],
                                               ['<15s', '15~60s', '1~5min', '5~15min', '≥15min'])}

    # ---------------- L2（抽样 · 关键帧） ----------------
    fr = []
    hue2 = collections.Counter()
    orient = collections.Counter()
    bright2 = []
    dur2 = []
    thumbs = []
    for r in l2:
        kv = (r.get('features', {}).get('keyframe', {}) or {}).get('kv') or {}
        if not kv.get('主色调'):
            continue
        d['meta']['l2_ok'] += 1
        fr.append(int(r.get('frames_count') or 0))
        hue2[kv.get('主色调')] += 1
        if kv.get('分辨率'):
            w, h = kv['分辨率'].split('x')
            orient['竖屏' if int(h) > int(w) else '横屏'] += 1
        if kv.get('均值亮度') is not None:
            bright2.append(_i(kv['均值亮度']))
        if kv.get('时长(秒)'):
            dur2.append(_i(kv['时长(秒)']))
        if r.get('frames_sheet'):
            thumbs.append({'id': r['content_id'], 'sheet': r['frames_sheet'],
                           'basin': r.get('basin'), 'topic': r.get('topic'),
                           'dur': kv.get('时长(秒)'), 'hue': kv.get('主色调')})
    d['l2']['frames'] = {'n': len(fr), 'avg': round(sum(fr) / len(fr), 1) if fr else 0,
                         'buckets': _buckets(fr, [5, 10, 15, float('inf')], ['<5', '5~10', '10~15', '≥15'])}
    d['l2']['hue'] = [{'name': k, 'value': v} for k, v in hue2.most_common()]
    d['l2']['orient'] = [{'name': k, 'value': v} for k, v in orient.most_common()]
    d['l2']['bright'] = _buckets(bright2, [64, 128, 192, float('inf')], ['暗', '中', '亮', '高亮'])
    d['l2']['duration'] = _buckets(dur2, [15, 60, 300, 900, float('inf')],
                                   ['<15s', '15~60s', '1~5min', '5~15min', '≥15min'])
    # 缩略图墙：按时长降序取前 24（含长/短代表）
    thumbs.sort(key=lambda t: (t.get('dur') or 0), reverse=True)
    d['l2']['thumbs'] = thumbs[:24]

    # ---------------- L3（音频层，可选） ----------------
    bk = collections.Counter(r.get('asr_backend') for r in l3)
    d['l3']['n'] = len(l3)
    d['l3']['backend'] = [{'name': k or '未装后端', 'value': v} for k, v in bk.most_common()]

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print('[video_data] 写出 %s' % OUT)
    print('  L1=%d 条 | L2=%d(有效%d) | L3=%d' % (len(l1), len(l2), d['meta']['l2_ok'], len(l3)))
    return d


if __name__ == '__main__':
    build()
