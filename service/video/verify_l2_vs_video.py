# -*- coding: utf-8 -*-
"""验证 L2「关键帧」是否"差不多"等于视频本身（代表性/保真度核对）。

方法：同一条视频做**两次抽帧**——
  A) L2 法：只解 I 帧（`-skip_frame nokey`）—— L2 实际"看到"的；
  B) 基准：**均匀抽帧**（横跨整段时长等间隔取 N 帧）—— 视频内容的公平代理。
然后比三项：
  1. **时间线覆盖**：I 帧在 0..1 相对时间轴上的**最大间隔**（越大=漏得越多）；
  2. **视觉一致性**：两者的 均值亮度 / 主色调 是否接近；
  3. **帧量**：I 帧数 vs 基准帧数。
原始视频全程不落盘（两次都只写临时 JPEG，读后即删）。

产物：video_features/l2_verification.html（左右对照）+ .csv（指标表）
用法：
    .venv/Scripts/python.exe service/video/verify_l2_vs_video.py --n 6
"""
import argparse
import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import sheet as _sheet                                  # noqa: E402
from probe import probe as _probe                       # noqa: E402
from fetch import extract_keyframes, extract_uniform, _evenly    # noqa: E402
import analyzers.keyframe as _kf                        # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DEFAULT_L2 = os.path.join(REPO_ROOT, 'video_features', 'l2_features.jsonl')
DEFAULT_FRAMES = os.path.join(REPO_ROOT, 'video_features', 'frames')
DEFAULT_OUT = os.path.join(REPO_ROOT, 'video_features', 'l2_verification')

_REF_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Referer': 'https://www.douyin.com/'}


def _load_l2(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _urls(ids):
    from sqlalchemy import create_engine, text
    eng = create_engine('mysql+pymysql://%s:%s@%s:3306/%s?charset=utf8mb4' % (os.getenv('MS_DB_USER', 'root'), os.getenv('MS_DB_PASSWORD', ''), os.getenv('MS_DB_HOST', 'localhost'), os.getenv('MS_DB_NAME', 'mindspider')))
    with eng.connect() as c:
        rows = c.execute(text("SELECT `aweme_id`,`video_download_url` FROM `douyin_aweme` "
                              "WHERE `video_download_url`<>''"))
        m = {r[0]: r[1] for r in rows}
    return {i: m.get(i) for i in ids}


def _pick(records, n):
    """按时长分层挑 n 条（覆盖 短/中/长），仅取状态 ok 的。"""
    ok = [r for r in records if r.get('video_url_status') == 'ok' and r.get('frames_count')]
    durs = []
    for r in ok:
        d = (r['features']['keyframe'].get('kv') or {}).get('时长(秒)') or 0
        durs.append((d, r))
    durs.sort(key=lambda x: x[0])
    if not durs:
        return []
    idx = []
    for k in range(n):
        idx.append(round(k * (len(durs) - 1) / max(n - 1, 1)))
    seen, out = set(), []
    for i in idx:
        if i not in seen:
            seen.add(i)
            out.append(durs[i][1])
    return out


def _rel_gaps(pts):
    pts = sorted(pts)
    if len(pts) < 2:
        return None, None
    mn, mx = pts[0], pts[-1]
    if mx <= mn:
        return None, None
    rel = [(p - mn) / (mx - mn) for p in pts]
    gaps = [rel[i + 1] - rel[i] for i in range(len(rel) - 1)]
    return max(gaps), sum(gaps) / len(gaps)


def run(n=6, ref=12, l2_path=DEFAULT_L2, frames_dir=DEFAULT_FRAMES, out=DEFAULT_OUT):
    recs = _load_l2(l2_path)
    picks = _pick(recs, n)
    if not picks:
        print('[验证] 没有可用的 L2 ok 样本'); return 0
    ids = [r['content_id'] for r in picks]
    um = _urls(ids)

    rows, cards = [], []
    for r in picks:
        cid = r['content_id']
        url = um.get(cid)
        if not url:
            print('  [跳过] %s 无地址' % cid); continue
        kv = r['features']['keyframe'].get('kv') or {}
        dur = kv.get('时长(秒)') or 0
        print('  对照 %s (时长%.1fs)…' % (cid, dur))
        try:
            probe = _probe(url, headers=_REF_UA, timeout=30)
        except Exception:
            probe = None
        # 抽【全部】I 帧（大上限）→ 比较"取前N(旧)"与"均匀取N(新)"两种截断策略的覆盖率
        all_if = extract_keyframes(url, headers=_REF_UA, max_frames=500, timeout=150)
        first_n = all_if[:20]                        # 旧行为：取最早的 20
        fb_used = False
        if len(all_if) < 5:
            # 与 l2_runner 一致：I 帧过少 → 按时长自适应 fps 均匀兜底（方案 §6b.7）
            fb = (15.0 / dur) if dur else 0.1
            fb_frames = extract_uniform(url, headers=_REF_UA, fps=fb, max_frames=40, timeout=180)
            if fb_frames:
                l2_frames = _evenly(fb_frames, 20)
                fb_used = True
            else:
                l2_frames = all_if
        else:
            l2_frames = _evenly(all_if, 20)          # 新行为：全片均匀取 20
        fps = (ref / dur) if dur else (1.0 / 10)
        ref_frames = extract_uniform(url, headers=_REF_UA, fps=fps, max_frames=ref, timeout=180)
        if not all_if and not ref_frames:
            print('   两次抽帧都为空，跳过'); continue

        l2_kv = _kf.KeyframeAnalyzer().analyze({'frames': l2_frames, 'probe': probe or {}})
        ref_kv = _kf.KeyframeAnalyzer().analyze({'frames': ref_frames, 'probe': probe or {}})
        pts_all = sorted(p for p, _ in all_if)
        span = (pts_all[-1] - pts_all[0]) if len(pts_all) >= 2 else 0

        def _cov(seq):
            pp = sorted(p for p, _ in seq)
            return ((pp[-1] - pp[0]) / span) if (span and len(pp) >= 2) else 1.0
        cov_old = _cov(first_n)
        if fb_used:
            # 均匀兜底帧的 pts 是序号，与真实 I 帧 pts 不同基 → 不能直接比；
            # 均匀抽帧按构造就覆盖全片，覆盖率记 1.0，间隔取 1/N。
            cov_new = 1.0
            max_gap = round(1.0 / max(len(l2_frames), 1), 3)
        else:
            cov_new = _cov(l2_frames)
            kept = sorted(p for p, _ in l2_frames)
            gaps = [(kept[i + 1] - kept[i]) / span for i in range(len(kept) - 1)] if span else []
            max_gap = max(gaps) if gaps else None

        # 缩略图
        os.makedirs(frames_dir, exist_ok=True)
        l2_img = os.path.join(frames_dir, '%s_l2.jpg' % cid)
        ref_img = os.path.join(frames_dir, '%s_ref.jpg' % cid)
        _sheet.make_sheet(l2_frames, l2_img,
                          title='L2 I帧 保留%d/%d张 覆盖%.0f%%  %s' % (len(l2_frames), len(all_if), cov_new * 100, cid))
        _sheet.make_sheet(ref_frames, ref_img,
                          title='基准 均匀%d帧（横跨全片） %s' % (len(ref_frames), cid))

        bl2 = l2_kv.get('均值亮度'); bref = ref_kv.get('均值亮度')
        hue_same = (l2_kv.get('主色调') == ref_kv.get('主色调'))
        fair = (cov_new >= 0.85) and (max_gap is not None and max_gap <= 0.25) and \
               (bl2 is not None and bref is not None and abs(bl2 - bref) <= 25)
        rows.append({
            'content_id': cid, '时长(s)': dur,
            '真实I帧数': len(all_if), 'L2保留数': len(l2_frames), '基准帧数': len(ref_frames),
            '覆盖率(旧:取前N)': round(cov_old, 3), '覆盖率(新:均匀)': round(cov_new, 3),
            'I帧最大间隔(占全片)': round(max_gap, 3) if max_gap is not None else '',
            'L2亮度': bl2, '基准亮度': bref,
            '亮度差': round(abs(bl2 - bref), 1) if (bl2 is not None and bref is not None) else '',
            'L2主色调': l2_kv.get('主色调'), '基准主色调': ref_kv.get('主色调'),
            '主色调一致': '是' if hue_same else '否',
            '代表性': '好' if fair else '存疑',
        })
        cards.append({'cid': cid, 'dur': dur, 'l2': l2_img, 'ref': ref_img,
                      'metrics': rows[-1]})

    if not rows:
        print('[验证] 无结果'); return 0
    _write_csv(out + '.csv', rows)
    _write_html(out + '.html', cards)
    print('\n[验证] %d 条对照完成：\n  %s\n  %s' % (len(rows), out + '.csv', out + '.html'))
    for r in rows:
        print('  %s 时长%.0fs 真实I帧%-4d 保留%-3d 覆盖[旧%s→新%s] 最大间隔%-7s 亮度差%-6s 主色%s → %s'
              % (r['content_id'], r['时长(s)'] or 0, r['真实I帧数'], r['L2保留数'],
                 r['覆盖率(旧:取前N)'], r['覆盖率(新:均匀)'], r['I帧最大间隔(占全片)'],
                 r['亮度差'], r['主色调一致'], r['代表性']))
    return len(rows)


def _write_csv(path, rows):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_html(path, cards):
    import base64

    def emb(p):
        if p and os.path.exists(p):
            with open(p, 'rb') as f:
                return 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
        return ''
    out = ['<!doctype html><html><head><meta charset="utf-8"><title>L2 vs 视频</title>',
           '<style>body{font:13px/1.6 system-ui,"Microsoft YaHei";margin:18px;color:#222}',
           '.card{border:1px solid #ddd;border-radius:8px;padding:12px;margin:14px 0}',
           '.two{display:flex;gap:12px;flex-wrap:wrap}.two>div{flex:1;min-width:360px}',
           'img{max-width:100%;border:1px solid #eee}',
           'table{border-collapse:collapse;margin-top:8px}td,th{border:1px solid #ccc;padding:3px 8px}',
           '.good{color:#0a7}.bad{color:#c00;font-weight:700}</style></head><body>',
           '<h2>L2 关键帧 vs 视频本身 —— 代表性核对</h2>',
           '<p>上=L2 只解 I 帧（L2 实际看到）；下=均匀抽帧（视频内容代理）。两者越像，L2 越"差不多等于视频"。</p>']
    for c in cards:
        m = c['metrics']
        cls = 'good' if m['代表性'] == '好' else 'bad'
        out.append('<div class="card"><b>%s</b> ｜ 时长 %.1fs ｜ 判定 <span class="%s">%s</span>'
                   % (c['cid'], c['dur'] or 0, cls, m['代表性']))
        out.append('<div class="two"><div><b>L2 I 帧</b><img src="%s"></div>'
                   '<div><b>基准（均匀）</b><img src="%s"></div></div>' % (emb(c['l2']), emb(c['ref'])))
        out.append('<table><tr>' + ''.join('<th>%s</th>' % k for k in m) + '</tr><tr>'
                   + ''.join('<td>%s</td>' % ('' if v is None else v) for v in m.values()) + '</tr></table>')
        out.append('</div>')
    out.append('</body></html>')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


def main():
    ap = argparse.ArgumentParser(description='验证 L2 关键帧 vs 视频（代表性核对）')
    ap.add_argument('--n', type=int, default=6, help='对照几条（按时长分层抽样）')
    ap.add_argument('--ref', type=int, default=12, help='基准均匀抽帧数')
    ap.add_argument('--l2', default=DEFAULT_L2)
    ap.add_argument('--out', default=DEFAULT_OUT)
    a = ap.parse_args()
    run(a.n, a.ref, a.l2, DEFAULT_FRAMES, a.out)


if __name__ == '__main__':
    main()

