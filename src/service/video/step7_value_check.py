# -*- coding: utf-8 -*-
"""Step 7「值不值验证」材料生成（方案 §零）。

思路：拿已抽帧的 L2 样本，把三类信息拼成一张人工对比表：
    A 列 = 只看文本（标题+描述+评论）能得出的结论  → 本脚本**自动草拟**
    B 列 = 看了关键帧画面之后**多出来**的结论       → **留空，人工填**
然后人工统计「B 相对 A 的增量」：<10% 则不做视频分析；>30% 则继续投 L2/L3；中间地带只对高价值样本做。

产物：video_features/step7_value_check.csv（utf-8-sig，Excel 可直接打开填写）
       video_features/step7_value_check.html（只读浏览版，便于快速过目）
用法：
    .venv/Scripts/python.exe service/video/step7_value_check.py            # 用已抽帧的 L2 样本
    .venv/Scripts/python.exe service/video/step7_value_check.py --l2 xxx.jsonl
"""
import argparse
import csv
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

REPO_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DEFAULT_L2 = os.path.join(REPO_ROOT, 'video_features', 'l2_features.jsonl')
DEFAULT_L1 = os.path.join(REPO_ROOT, 'video_features', 'l1_features.jsonl')
DEFAULT_OUT = os.path.join(REPO_ROOT, 'video_features', 'step7_value_check')

COLS = ['#', 'content_id', '流域', '议题', '平台',
        '标题', '内容摘要',
        '互动总量', '转发_点赞比', '评论数', '负面占比', '评论诉求',
        '画面_时长(s)', '画面_分辨率', '画面_主色调', '画面_亮度', '画面_色彩丰富度', '画面_帧数',
        '画面_缩略图',
        'A_文本侧结论(自动草拟)', 'B_画面多出的结论(人工填)', '增量判定(明显/一般/无)']


def _load_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def _clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def _a_conclusion(title, content, ci):
    """自动草拟「只看文本」的结论（很粗，只作对比基线）。"""
    parts = []
    if title:
        parts.append('标题指向:' + title[:36])
    if ci.get('评论数'):
        parts.append('评论 %d 条(负面 %.0f%%)' % (ci['评论数'], (ci.get('负面占比') or 0) * 100))
    d = ci.get('诉求分布') or {}
    if d:
        parts.append('诉求:' + '/'.join(list(d.keys())[:3]))
    if not parts:
        parts.append('(文本信息不足)')
    return '；'.join(parts)


def build(l2_path, l1_path, out_base):
    l2 = _load_jsonl(l2_path)
    if not l2:
        print('[Step7] 未找到 L2 特征（%s）。请先跑 l2_runner.py --join-source' % l2_path)
        return 0
    l1map = {r.get('content_id'): r for r in _load_jsonl(l1_path)}

    # 取文本（标题/内容）—— t_bettafish_article 才有原文
    txt = {}
    try:
        from db import get_engine
        import pandas as pd
        ids = [r.get('content_id') for r in l2 if r.get('content_id')]
        eng = get_engine()
        q = ('SELECT `内容ID`,`标题`,`内容` FROM `t_bettafish_article` WHERE `内容ID` IN (%s)'
             % ','.join("'%s'" % str(i).replace("'", "") for i in ids))
        df = pd.read_sql(q, eng)
        txt = {str(r['内容ID']): r for _, r in df.iterrows()}
    except Exception as e:
        print('[Step7] 取原文失败（不影响画面列）：', str(e)[:100])

    rows = []
    for i, r in enumerate(l2, 1):
        cid = r.get('content_id')
        kv = ((r.get('features', {}) or {}).get('keyframe', {}) or {}).get('kv') or {}
        t = txt.get(str(cid))
        title = _clean(t['标题']) if t is not None else ''
        content = _clean(t['内容']) if t is not None else ''
        l1 = l1map.get(cid, {}) or {}
        f = l1.get('features', {}) or {}
        mp = (f.get('meta_profile', {}) or {}).get('kv') or {}
        ci = (f.get('comment_insight', {}) or {}).get('kv') or {}
        rows.append({
            '#': i, 'content_id': cid,
            '流域': r.get('basin'), '议题': r.get('topic'), '平台': r.get('platform'),
            '标题': title[:50], '内容摘要': content[:80],
            '互动总量': mp.get('互动总量'), '转发_点赞比': mp.get('转发_点赞比'),
            '评论数': ci.get('评论数'), '负面占比': ci.get('负面占比'),
            '评论诉求': '/'.join((ci.get('诉求分布') or {}).keys()) or '',
            '画面_时长(s)': kv.get('时长(秒)'), '画面_分辨率': kv.get('分辨率'),
            '画面_主色调': kv.get('主色调'), '画面_亮度': kv.get('均值亮度'),
            '画面_色彩丰富度': kv.get('均值色彩丰富度'), '画面_帧数': kv.get('frames_count'),
            '画面_缩略图': r.get('frames_sheet') or '',
            'A_文本侧结论(自动草拟)': _a_conclusion(title, content, ci),
            'B_画面多出的结论(人工填)': '', '增量判定(明显/一般/无)': '',
        })

    csv_path = out_base + '.csv'
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    html_path = out_base + '.html'
    with open(html_path, 'w', encoding='utf-8') as fh:
        fh.write(_html(rows, os.path.dirname(os.path.abspath(out_base))))
    print('[Step7] 生成 %d 条对比样本：\n  %s\n  %s' % (len(rows), csv_path, html_path))
    print('[Step7] 请人工填 B 列（看了画面多出的结论）→ 统计增量比例：<10% 不做 / >30% 继续投 L2/L3')
    return len(rows)


def _html(rows, base_dir):
    import base64
    th = ''.join('<th>%s</th>' % c for c in COLS)
    trs = []
    for r in rows:
        tds = []
        for c in COLS:
            v = r.get(c)
            if c == '画面_缩略图':
                p = os.path.join(base_dir, v) if v else ''
                if v and os.path.exists(p):
                    with open(p, 'rb') as imf:
                        b64 = base64.b64encode(imf.read()).decode()
                    tds.append('<td><img src="data:image/jpeg;base64,%s" style="max-width:460px"></td>' % b64)
                else:
                    tds.append('<td>(无缩略图)</td>')
            else:
                tds.append('<td>%s</td>' % ('' if v is None else v))
        trs.append('<tr>%s</tr>' % ''.join(tds))
    return ('<!doctype html><html><head><meta charset="utf-8"><title>L2 值不值验证</title>'
            '<style>body{font:13px/1.5 system-ui,"Microsoft YaHei";margin:16px;color:#222}'
            'table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:4px 6px;vertical-align:top}'
            'th{background:#f2f2f2;position:sticky;top:0}tr:nth-child(even){background:#fafafa}'
            'img{display:block}</style></head><body>'
            '<h3>L2「值不值验证」对比表（A=只看文本 / B=看画面后多出的结论，需人工填）</h3>'
            '<p>缩略图 = 该条抽到的关键帧拼图；对照它填空 B 列。</p>'
            '<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></body></html>'
            % (th, ''.join(trs)))


def main():
    ap = argparse.ArgumentParser(description='Step7 值不值验证材料生成')
    ap.add_argument('--l2', default=DEFAULT_L2)
    ap.add_argument('--l1', default=DEFAULT_L1)
    ap.add_argument('--out', default=DEFAULT_OUT, help='输出前缀（.csv/.html）')
    a = ap.parse_args()
    build(a.l2, a.l1, a.out)


if __name__ == '__main__':
    main()
