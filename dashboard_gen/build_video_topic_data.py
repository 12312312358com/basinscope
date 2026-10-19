# -*- coding: utf-8 -*-
"""把「短视频智能分析」结果切片成前端可直接消费的数据。

数据来源：
  1) dashboard_gen/video_insight.json     —— 模型产出（画面读数 / 六维分析 / 推荐结论）
  2) video_features/l2_features.jsonl     —— 原始证据（关键帧统计 / 互动 / 评论）

输出：dashboard_gen/video_topic_data.json
  { "meta": {...}, "topics": { "长江": {n, cards[], agg}, "黄河": {...} }, "others": {...} }

口径（与方案一致）：
  - 只把 basin 恰为「长江」「黄河」的条目挂到两个专题；
  - '黄河长江'（双流域命中）与 '未知' 归入 others，不混算（否则 长江+黄河 ≠ 总数）。
"""
from __future__ import annotations

import collections
import io
import json
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(BASE)
INSIGHT = os.path.join(BASE, 'video_insight.json')
L2 = os.path.join(PRJ, 'video_features', 'l2_features.jsonl')
L3 = os.path.join(PRJ, 'video_features', 'l3_features.jsonl')
DST = os.path.join(BASE, 'video_topic_data.json')

BASINS = ('长江', '黄河')
PFX = {'长江': 'yz', '黄河': 'hh'}
MAIN_TOPICS = ('生态治理', '文旅', '医患矛盾')


def _l2_index():
    out = {}
    if not os.path.exists(L2):
        return out
    for line in io.open(L2, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        out[r.get('content_id')] = r
    return out


def _l3_index():
    """L3 音频层转写（可选）：文件不存在或未转写时返回空，页面显示『待转写』。"""
    out = {}
    if not os.path.exists(L3):
        return out
    for line in io.open(L3, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        kv = ((r.get('features') or {}).get('asr') or {}).get('kv') or {}
        if not kv:
            continue
        out[r.get('content_id')] = {
            '状态': kv.get('状态'),
            '转写文本': kv.get('转写文本') or '',
            '字数': kv.get('字数'),
            '语速': kv.get('语速(字/分)'),
            '音频时长': kv.get('音频时长(秒)'),
            '后端': kv.get('后端'),
            '模型': kv.get('模型'),
            '是否含人声': kv.get('是否含人声'),
        }
    return out


def _num(v):
    try:
        return int(v)
    except Exception:
        return 0


def _empty_result():
    """Write a valid empty product when optional video insights are unavailable."""
    topics = {b: {'n': 0, 'cards': [], 'agg': {}} for b in BASINS}
    out = {
        'meta': {
            'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': '',
            'prompt_version': None,
            'total_analyzed': 0,
            'status': 'not_configured',
            'note': ('Optional short-video insight data are not included in this '
                     'release. The remaining dashboard views are unaffected.'),
            'excluded': {},
            'no_conclusion': [],
        },
        'topics': topics,
        'others': {},
    }
    io.open(DST, 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print('[topic_data] video insights not configured; empty product written')
    print('[topic_data] 输出：%s  %.1f KB' % (DST, os.path.getsize(DST) / 1024))
    return out


def build():
    if not os.path.exists(INSIGHT):
        return _empty_result()
    ins = json.load(io.open(INSIGHT, encoding='utf-8'))
    l2 = _l2_index()
    l3 = _l3_index()
    print('[topic_data] L3 转写可join = %d 条' % len(l3))

    topics = {b: {'n': 0, 'cards': []} for b in BASINS}
    others = collections.Counter()
    skipped = []

    for it in ins.get('items', []):
        cid = it.get('content_id')
        raw = l2.get(cid) or {}
        kv = ((raw.get('features') or {}).get('keyframe') or {}).get('kv') or {}
        lm = raw.get('l1_meta') or {}
        lc = raw.get('l1_comment') or {}
        ana = it.get('analysis') or {}
        th = ana.get('主题') or {}
        vlm = it.get('vlm') or {}
        cs = it.get('conclusions') or []
        top = cs[0] if cs else {}

        # 无画面按证据的条目（拼图缺失/VLM 失败）仍可入列，但标注状态
        card = {
            'cid': cid,
            'basin': it.get('basin'),
            'topic': it.get('topic') or '未分类',
            'title': (it.get('title') or '（无标题）')[:60],
            'link': it.get('link') or '',
            'sheet': ('frames/%s.jpg' % cid),
            'vlm_status': it.get('vlm_status'),
            'shot': {
                '时长': kv.get('时长(秒)'),
                '分辨率': kv.get('分辨率'),
                '画幅': ('竖屏' if (kv.get('分辨率') or '').count('x') == 1 and
                        _num((kv.get('分辨率') or '0x0').split('x')[1]) >=
                        _num((kv.get('分辨率') or '0x0').split('x')[0]) else '横屏'),
                '主色调': kv.get('主色调'),
                '亮度': kv.get('均值亮度'),
                '色彩丰富度': kv.get('均值色彩丰富度'),
                '帧数': kv.get('frames_count'),
            },
            'promo': {
                '互动总量': lm.get('互动总量'),
                '点赞数': lm.get('点赞数'), '评论数': lm.get('评论数'),
                '转发数': lm.get('转发数'), '收藏数': lm.get('收藏数'),
                '转发_点赞比': lm.get('转发_点赞比'),
                '评论_点赞比': lm.get('评论_点赞比'),
            },
            'senti': {
                '评论数': lc.get('评论数'),
                '情感分布': lc.get('情感分布') or {},
                '负面占比': lc.get('负面占比'),
                '诉求分布': lc.get('诉求分布') or {},
                '过闸门': bool(lc.get('样本过闸门')),
                '外推声明': lc.get('外推声明') or '',
            },
            'vlm': {
                '主体': vlm.get('主体'), '场景': vlm.get('场景'),
                '视觉主题': vlm.get('视觉主题'),
                '画面文字': (lambda t: '；'.join(map(str, t)) if isinstance(t, (list, tuple)) else (t or ''))(vlm.get('画面文字')),
                '议题倾向': vlm.get('议题倾向'), '置信': vlm.get('置信'),
            },
            'theme': {'标签': th.get('标签'), '核心信息': th.get('核心信息') or []},
            'advice': ana.get('建议') or [],
            'top': {
                'claim': top.get('claim') or '',
                'recommend': top.get('recommend'),
                'confidence': top.get('confidence'),
                'actionability': top.get('actionability'),
                'evidence': top.get('evidence') or [],
                'evidence_cats': top.get('evidence_cats') or [],
                'all_valid': top.get('evidence_all_valid'),
            },
            'alts': [{'claim': c.get('claim'), 'recommend': c.get('recommend')}
                     for c in cs[1:]],
            'n_conclusions': len(cs),
            'conflict': it.get('conflict') or '',
            'asr': l3.get(cid) or None,
        }

        # 转写覆盖度：L3 每条只取前 N 秒音轨，长视频的口播只覆盖开头 → 必须显式标注，
        # 否则读者会误以为转写代表整条视频。
        _a = card.get('asr')
        if _a:
            try:
                _dur = float(card['shot'].get('时长') or 0)
                _aud = float(_a.get('音频时长') or 0)
                _a['视频时长'] = _dur
                _a['转写覆盖'] = round(min(_aud, _dur) / _dur, 2) if _dur > 0 else None
                _a['截断'] = bool(_dur and (_aud + 1.0) < _dur)
            except Exception:
                _a['截断'] = False

        b = it.get('basin')
        if b in topics and card['n_conclusions'] > 0:
            topics[b]['cards'].append(card)
        else:
            others[b or '空'] += 1
            if card['n_conclusions'] == 0:
                skipped.append(cid)

    for b in BASINS:
        cards = topics[b]['cards']
        cards.sort(key=lambda c: -(c['top'].get('recommend') or 0))
        topics[b]['n'] = len(cards)
        topics[b]['sec'] = PFX[b]
        topics[b]['agg'] = {
            'hue': collections.Counter(
                c['shot']['主色调'] for c in cards if c['shot'].get('主色调')).most_common(),
            'orient': collections.Counter(
                c['shot']['画幅'] for c in cards).most_common(),
            'topic': collections.Counter(c['topic'] for c in cards).most_common(),
            'top': [[c['title'], c['promo'].get('互动总量') or 0]
                    for c in sorted(cards, key=lambda x: -(x['promo'].get('互动总量') or 0))[:12]],
            'asr_ok': sum(1 for c in cards
                          if (c.get('asr') or {}).get('状态') == 'ok'
                          and (c.get('asr') or {}).get('字数')),
            'hueList': [c['cid'] for c in cards],
        }

    meta = {
        'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'source': os.path.basename(INSIGHT),
        'prompt_version': (ins.get('meta') or {}).get('prompt_version'),
        'total_analyzed': len(ins.get('items', [])),
        'note': ('样本为 L2 关键帧层抽样（仅抖音）；画面读数来自关键帧拼图而非原始视频；'
                 '结论由大模型生成并按推荐度排序，仅供辅助参考；评论未过闸门时仅作现象提示。'),
        'excluded': dict(others),
        'no_conclusion': skipped,
    }
    out = {'meta': meta, 'topics': topics}
    io.open(DST, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
    print('[topic_data] 长江 %d / 黄河 %d（另：未挂专题 %s；无结论 %d 条）'
          % (topics['长江']['n'], topics['黄河']['n'], dict(others), len(skipped)))
    print('[topic_data] 输出：%s  %.1f KB' % (DST, os.path.getsize(DST) / 1024))
    return out


if __name__ == '__main__':
    build()
