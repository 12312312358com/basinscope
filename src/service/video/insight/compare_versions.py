# -*- coding: utf-8 -*-
"""对比两个提示词版本的分析结果（默认 v1.1 备份 vs 当前 v1.2），量化"口播证据 E7"的增量。

用法：
    python service/video/insight/compare_versions.py
    python service/video/insight/compare_versions.py --old dashboard_gen/_video_insight_v11.json \
        --new dashboard_gen/video_insight.json
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PRJ = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
DEFAULT_OLD = os.path.join(_PRJ, 'dashboard_gen', '_video_insight_v11.json')
DEFAULT_NEW = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.json')


def load(p):
    d = json.load(io.open(p, encoding='utf-8'))
    return {str(i['content_id']): i for i in d.get('items', [])}, d.get('meta', {})


def _top(it):
    cs = it.get('conclusions') or []
    return cs[0] if cs else {}


def _cats(it):
    return set(_top(it).get('evidence_cats') or [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', default=DEFAULT_OLD)
    ap.add_argument('--new', default=DEFAULT_NEW)
    ap.add_argument('--show', type=int, default=6, help='展示多少条主题标签变化样例')
    a = ap.parse_args()

    if not os.path.exists(a.old):
        raise SystemExit('缺少旧版本文件：%s' % a.old)
    old, om = load(a.old)
    new, nm = load(a.new)
    both = [c for c in old if c in new]
    print('旧版本 %s：%d 条（prompt=%s）' % (os.path.basename(a.old), len(old), om.get('prompt_version')))
    print('新版本 %s：%d 条（prompt=%s）' % (os.path.basename(a.new), len(new), nm.get('prompt_version')))
    print('可比对（两版都有） = %d 条\n' % len(both))
    if not both:
        return

    # ---- 1) 证据类别使用分布：E7 是否被真正采用 ----
    oc = collections.Counter()
    nc = collections.Counter()
    e7_top = e7_any = 0
    for c in both:
        oc.update(_cats(old[c]))
        cc = _cats(new[c])
        nc.update(cc)
        if '口播' in cc:
            e7_top += 1
        blob = json.dumps(new[c].get('conclusions') or [], ensure_ascii=False)
        if '"E7"' in blob:
            e7_any += 1
    print('== 推荐结论的证据类别分布 ==')
    keys = ['画面', '文本', '来源', '传播', '评论', '视觉', '口播']
    print('  %-6s %-8s %-8s' % ('类别', 'v1.1', 'v1.2'))
    for k in keys:
        print('  %-6s %-8d %-8d' % (k, oc.get(k, 0), nc.get(k, 0)))
    print('  → top1 结论引用「口播」的条数：v1.2 = %d / %d' % (e7_top, len(both)))
    print('  → 任一候选结论引用 E7 的条数：v1.2 = %d / %d\n' % (e7_any, len(both)))

    # ---- 2) 推荐度 / 结论条数 ----
    def stat(d, key=None):
        vals = []
        for c in both:
            if key == 'rec':
                for x in (d[c].get('conclusions') or []):
                    if x.get('recommend') is not None:
                        vals.append(x['recommend'])
            elif key == 'n':
                vals.append(len(d[c].get('conclusions') or []))
            elif key == 'conf':
                t = _top(d[c])
                if t.get('confidence') is not None:
                    vals.append(t['confidence'])
        vals.sort()
        return vals

    for key, label in (('rec', '推荐度'), ('conf', 'top1 置信'), ('n', '结论条数')):
        o, n = stat(old, key), stat(new, key)
        if o and n:
            print('== %s ==' % label)
            print('  v1.1: n=%d 中位=%.3f 均值=%.3f' % (len(o), o[len(o) // 2], sum(o) / len(o)))
            print('  v1.2: n=%d 中位=%.3f 均值=%.3f\n' % (len(n), n[len(n) // 2], sum(n) / len(n)))

    # ---- 3) 主题标签变化 ----
    changed = []
    for c in both:
        o = ((old[c].get('analysis') or {}).get('主题') or {}).get('标签') or ''
        n = ((new[c].get('analysis') or {}).get('主题') or {}).get('标签') or ''
        if o != n and n:
            changed.append((c, o, n,
                            ((new[c].get('analysis') or {}).get('主题') or {}).get('议题倾向') or ''))
    print('== 主题标签发生变化：%d / %d 条（%.0f%%）=='
          % (len(changed), len(both), 100.0 * len(changed) / len(both)))
    for c, o, n, t in changed[:a.show]:
        print('  %s  [%s]' % (c, t))
        print('      v1.1: %s' % (o or '（空）'))
        print('      v1.2: %s' % n)

    # ---- 4) 核心信息条数变化 ----
    def core_cnt(d, c):
        return len(((d[c].get('analysis') or {}).get('主题') or {}).get('核心信息') or [])
    o_sum = sum(core_cnt(old, c) for c in both)
    n_sum = sum(core_cnt(new, c) for c in both)
    print('\n== 核心信息点总数 ==\n  v1.1 = %d → v1.2 = %d（%+.0f%%）'
          % (o_sum, n_sum, 100.0 * (n_sum - o_sum) / max(o_sum, 1)))


if __name__ == '__main__':
    main()
