# -*- coding: utf-8 -*-
"""从 video_insight.md 反向恢复 video_insight.json（崩溃救援用）。

背景：一次收尾写盘处的 NameError 把 JSON 截成 0 字节，而逐条渲染的 MD 完整保留。
MD 是 render_md() 的输出，格式确定，故可逆解析；被占位符污染的条目（<...>）剔除，
交给 build_insight.py 的断点续跑重做。

用法：
    python service/video/insight/recover_from_md.py                 # 写 .recovered.json 并体检
    python service/video/insight/recover_from_md.py --apply         # 校验通过后覆盖正式 JSON
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VDIR = os.path.dirname(_HERE)
_PRJ = os.path.dirname(os.path.dirname(_VDIR))
sys.path.insert(0, _VDIR)

MD = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.md')
OUT = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.recovered.json')
PROMPT_VERSION = 'v1.1'

_PH = re.compile(r'<[^<>\n]{1,60}>')


def _dash(v):
    v = (v or '').strip()
    return None if v in ('', '—', '-', '（无）', 'None', 'null') else v


def _f(sec, name, flags=0):
    m = re.search(r'\*\*%s\*\*：(.*)$' % re.escape(name), sec, re.M | flags)
    return m.group(1).strip() if m else None


def _ev(s):
    return re.findall(r'\[(E\d)\]', s or '')


def parse(md_text):
    blocks = re.split(r'\n## 第 \d+ 条 · ', md_text)[1:]
    items, polluted = [], []
    for b in blocks:
        head, _, rest = b.partition('\n')
        title = head.strip()

        cid_m = re.search(r'\*\*内容ID\*\*：`(\d+)`', rest)
        if not cid_m:
            continue
        cid = cid_m.group(1)
        basin = re.search(r'\*\*流域\*\*：([^｜\n]*)', rest)
        topic = re.search(r'\*\*议题\*\*：([^｜\n]*)', rest)
        plat = re.search(r'\*\*平台\*\*：([^\n]*)', rest)
        link = re.search(r'\*\*来源链接\*\*：(.*)', rest)
        chain = re.search(r'\*\*模型链路\*\*：视觉=(\S+)（(\S+)）｜文本=(.*)', rest)

        def seg(marker, nxt):
            i = rest.find(marker)
            if i < 0:
                return ''
            j = rest.find(nxt, i) if nxt else len(rest)
            return rest[i:(j if j > 0 else len(rest))]

        s1 = seg('### ① 画面内容', '### ②')
        s2 = seg('### ② 主题与核心信息', '### ③')
        s3 = seg('### ③ 传播画像', '### ④')
        s4 = seg('### ④ 情感与诉求', '### ⑤')
        s5 = seg('### ⑤ 客观视觉指标', '### ⑥')
        s6 = seg('### ⑥ ★ 推荐结论', '### ⑦')
        s7 = seg('### ⑦ 建议', '### ⑧')

        vt = _f(s1, '议题倾向') or ''
        vm = re.match(r'^(.*?)（置信 (.*?)）?$', vt)
        vlm = None
        if '未取得画面读数' not in s1:
            vlm = {
                '主体': _dash(_f(s1, '主体')),
                '场景': _dash(_f(s1, '场景')),
                '画面文字': _dash(_f(s1, '画面文字')),
                '视觉主题': _dash(_f(s1, '视觉主题')),
                '议题倾向': _dash(vm.group(1)) if vm else _dash(vt),
                '置信': (_dash(vm.group(2)) if (vm and vm.group(2)) else None),
            }

        analysis = {
            '主题': {
                '标签': _dash(_f(s2, '主题标签')),
                '议题倾向': _dash(_f(s2, '议题倾向')),
                '核心信息': re.findall(r'^- 核心信息：(.*)$', s2, re.M),
                '置信': _dash(_f(s2, '置信')),
            },
            '传播': {'类型': _dash(_f(s3, '扩散类型')), '解读': _dash(_f(s3, '解读'))},
            '情感诉求': {
                '情感': _dash(_f(s4, '情感')),
                '负面占比': _dash(_f(s4, '负面占比')),
                '主要诉求': [x for x in (_f(s4, '主要诉求') or '').split('、') if x and x != '—'],
                '解读': _dash(_f(s4, '解读')),
            },
            '客观视觉': {
                '画幅': _dash(_f(s5, '画幅')),
                '主色调': _dash(_f(s5, '主色调')),
                '亮度': _dash(_f(s5, '亮度')),
                '解读': _dash(_f(s5, '解读')),
            },
            '建议': re.findall(r'^- (.*)$', s7, re.M),
        }

        concl, top = [], {}
        mt = re.search(r'\*\*推荐度 ([\d.]+)\*\*（置信 ([\d.]+) · 可操作性 ([\d.]+) · 证据类别 (.*?)）', s6)
        if mt:
            claim = re.search(r'^> (.*)$', s6, re.M)
            ev = re.search(r'\*\*证据链\*\*：(.*)', s6)
            cats = [c.strip() for c in mt.group(4).split('、') if c.strip() and c.strip() != '无']
            top = {'claim': (claim.group(1).strip() if claim else ''),
                   'evidence': _ev(ev.group(1) if ev else ''),
                   'evidence_cats': cats,
                   'confidence': float(mt.group(2)), 'actionability': float(mt.group(3)),
                   'recommend': float(mt.group(1)),
                   'evidence_all_valid': '降权' not in s6}
            concl.append(top)
        for m in re.finditer(r'^- （推荐度 ([\d.]+) · 置信 ([\d.]+)）(.*?) ｜证据：(.*)$', s6, re.M):
            concl.append({'claim': m.group(3).strip(), 'evidence': _ev(m.group(4)),
                          'confidence': float(m.group(2)), 'recommend': float(m.group(1))})

        conflict = None
        mc = re.search(r'一致性提示\*\*：(.*?)（建议人工复核）', s5)
        if mc:
            conflict = mc.group(1).strip()

        blob = json.dumps({'vlm': vlm, 'analysis': analysis, 'top': top}, ensure_ascii=False)
        is_ph = bool(_PH.search(blob))

        it = {
            'content_id': cid, 'basin': (basin.group(1).strip() if basin else None),
            'topic': (topic.group(1).strip() if topic else None),
            'platform': (plat.group(1).strip() if plat else 'dy'),
            'title': title, 'link': (link.group(1).strip() if link else ''),
            'prompt_version': PROMPT_VERSION,
            'vlm': vlm,
            'vlm_status': (chain.group(1) if chain else ('ok' if vlm else 'failed')),
            'vlm_elapsed': (chain.group(2) if chain else None),
            'backend': (chain.group(3).strip() if chain else ''),
            'analysis': analysis, 'conclusions': concl,
            'conflict': conflict, 'recovered': True,
        }
        if is_ph:
            it['placeholder'] = True
            polluted.append(cid)
        items.append(it)
    return items, polluted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='校验通过后覆盖正式 JSON')
    a = ap.parse_args()

    md = io.open(MD, encoding='utf-8').read()
    items, polluted = parse(md)
    ok = [i for i in items if not i.get('placeholder') and i.get('conclusions')]
    print('[恢复] 解析 %d 条；可用 %d 条；占位符污染 %d 条（将重跑）'
          % (len(items), len(ok), len(polluted)))
    if polluted:
        print('       污染 cid:', ', '.join(polluted))

    meta = {'generated': __import__('time').strftime('%Y-%m-%dT%H:%M:%S'),
            'prompt_version': PROMPT_VERSION, 'n': len(ok),
            'note': ('由 video_insight.md 反向恢复（崩溃救援）；画面读数来自关键帧拼图；'
                     '无参考文献输出。'),
            'recovered_from_md': True}
    data = {'meta': meta, 'items': ok}
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=2))
    print('[恢复] 写出候选：%s' % OUT)

    if a.apply:
        dst = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.json')
        io.open(dst, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=2))
        print('[恢复] 已覆盖正式产物：%s（%d 条）' % (dst, len(ok)))


if __name__ == '__main__':
    main()
