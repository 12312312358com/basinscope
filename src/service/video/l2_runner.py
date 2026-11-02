# -*- coding: utf-8 -*-
"""L2 关键帧层 · 编排器 / CLI

职责（方案 §6b）：
    ① 读 L1 特征库 → 用 L1 元数据+评论情感挑 L2 样本（5%~10%，含覆盖保底）
    ② 对每条样本：取播放地址 → 探针（时长/分辨率，最佳努力）→ 流式抽关键帧（原始流不落盘）
    ③ 跑 keyframe 分析器 → 写 L2 特征库（JSONL 开放 schema）

红线（写死）：
    ① 原始视频流只过管道，绝不落盘（fetch.extract_keyframes 实现）
    ② 关键帧只做整帧色彩/亮度统计，不提人脸/声纹（keyframe.py 实现）
    ③ L2 仅覆盖抽样子集，结论标注样本量，不外推

数据源：
    L2 视频地址需从 mindspider.douyin_aweme 按 aweme_id 取 video_download_url
    （BettaFish 回收桥刻意未收该字段，见 docs/视频分析方案.md §一）。
    抖音地址带签名、有时效；过期/403 时该条自动标 skip，不中断整批。

用法：
    # 离线自检（公开样例视频，不连库、不联网鉴权，秒级验证全链路）
    python service/video/l2_runner.py --selftest

    # 真实跑（读 L1 库挑样本 → 连 mindspider 取地址 → 抽帧；地址过期自动 skip）
    python service/video/l2_runner.py --join-source

    # 只挑样本、不下载（先看挑了哪些、占比多少）
    python service/video/l2_runner.py --dry-sample --frac 0.08
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from registry import get as _reg_get  # noqa: E402
import analyzers  # noqa: E402,F401  触发 L1 三个分析器注册（不影响 L2 运行）
import analyzers.keyframe  # noqa: E402,F401  注册 'keyframe'
from store import FeatureStore, now_iso  # noqa: E402
from probe import probe as _probe  # noqa: E402
from fetch import extract_keyframes as _fetch  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DEFAULT_L1 = os.path.join(REPO_ROOT, 'video_features', 'l1_features.jsonl')
DEFAULT_OUT = os.path.join(REPO_ROOT, 'video_features', 'l2_features.jsonl')

# 公开样例视频（HEAD 已验证 200 / video/mp4 / 991017B），用于 --selftest 不依赖任何鉴权
SAMPLE_URL = ('https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/'
             'Big_Buck_Bunny_360_10s_1MB.mp4')


# ----------------------------------------------------------------------------
# 样本选择器（方案 §6b.4）：L1 → L2
# ----------------------------------------------------------------------------
def _idof(rec):
    return rec.get('content_id')


def _priority(rec):
    """返回 (score, reasons[])。score 越高越值得进 L2。"""
    feats = rec.get('features', {}) or {}
    meta = (feats.get('meta_profile', {}) or {}).get('kv') or {}
    cmt = (feats.get('comment_insight', {}) or {}).get('kv') or {}
    score = 0.0
    why = []
    total = meta.get('互动总量') or 0
    repin = meta.get('转发_点赞比')
    neg = cmt.get('负面占比')

    if total:
        score += min(total / 2000.0, 1.0) * 1.0
        if total >= 500:
            why.append('高互动')
    if neg is not None:
        controversy = 1 - abs(neg - 0.5) * 2  # 正面/负面各半 → 1.0
        if controversy > 0.4:
            score += controversy * 0.8
            why.append('情感对立')
    if repin and repin > 1:
        score += min(repin / 3.0, 1.0) * 0.6
        why.append('高转发')
    return score, why


def sample(records, frac=0.08, floor=2):
    """按优先级挑 ~frac 比例样本，并保证每个 (流域×议题) 格至少 floor 条（覆盖保底）。"""
    scored = []
    for r in records:
        s, why = _priority(r)
        scored.append((s, why, r))
    scored.sort(key=lambda x: -x[0])
    n_total = len(records)
    n_target = max(int(round(n_total * frac)), 1)
    chosen = scored[:n_target]
    chosen_ids = {_idof(r) for _, _, r in chosen}
    cells = {}
    for _, _, r in chosen:
        cells[(_cell(r))] = cells.get(_cell(r), 0) + 1
    # 覆盖保底：不足 floor 的格，从剩余里补最高优先级
    for s, why, r in scored[n_target:]:
        c = _cell(r)
        if cells.get(c, 0) < floor and _idof(r) not in chosen_ids:
            chosen.append((s, why, r))
            chosen_ids.add(_idof(r))
            cells[c] = cells.get(c, 0) + 1
    return chosen


def _cell(r):
    return (r.get('basin'), r.get('topic'))


# ----------------------------------------------------------------------------
# 视频地址获取（--join-source）
# ----------------------------------------------------------------------------
def _ms_engine():
    """mindspider 引擎；连接参数可被环境变量覆盖。"""
    from sqlalchemy import create_engine
    host = os.getenv('MS_DB_HOST', 'localhost')
    user = os.getenv('MS_DB_USER', 'root')
    pwd = os.getenv('MS_DB_PASSWORD', '')
    name = os.getenv('MS_DB_NAME', 'mindspider')
    url = f'mysql+pymysql://{user}:{pwd}@{host}:3306/{name}?charset=utf8mb4'
    return create_engine(url)


def _fetch_video_url(content_id, engine):
    import pandas as pd
    sql = ("SELECT `video_download_url` FROM `douyin_aweme` "
           "WHERE `aweme_id`=%s LIMIT 1") % content_id
    df = pd.read_sql(sql, engine)
    if df.empty:
        return None
    v = df.iloc[0, 0]
    return v if v else None


# ----------------------------------------------------------------------------
# 单条处理
# ----------------------------------------------------------------------------
def _build_ctx(frames, probe, record, comments, cover_url):
    return {
        'frames': frames,
        'probe': probe or {},
        'record': record or {},
        'comments': comments or [],
        'cover_url': cover_url,
    }


def _run_one_keyframe(frames, probe, record):
    A = _reg_get('keyframe')
    if A is None:
        raise RuntimeError('keyframe 分析器未注册')
    ctx = _build_ctx(frames, probe, record, [], None)
    try:
        kv = A().analyze(ctx)
        return {'version': A.version, 'kv': kv, 'status': kv.get('status', 'ok')}
    except Exception as e:
        return {'version': A.version, 'kv': None, 'status': 'error', 'error': str(e)[:160]}


def _process(content_id, platform, basin, topic, url, referer, no_probe,
             l1_meta, l1_comment, sheet_dir=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
               'Referer': referer}
    probe = None
    if not no_probe and url:
        try:
            probe = _probe(url, headers=headers, timeout=30)
        except Exception:
            probe = None
    frames = []
    url_status = 'missing'
    if url:
        try:
            # I 帧过少（GOP 大/短片）→ 按方案 §6b.7 退化为均匀抽帧。
            # 用【按时长自适应】的 fps（目标 ~15 帧），而不是固定 fps=1/2——后者对长片会白生成几百帧。
            _dur = (probe or {}).get('duration')
            _fb = (15.0 / float(_dur)) if _dur else 0.1
            frames = _fetch(url, headers=headers, timeout=60,
                            min_frames=5, fallback_fps=_fb)
            url_status = 'ok' if frames else 'no_frames'
        except Exception as e:
            url_status = 'fetch_error:' + str(e)[:80]
    feat = _run_one_keyframe(frames, probe, {'内容ID': content_id})
    sheet_rel = None
    if sheet_dir and frames:
        try:
            import sheet as _sheet
            os.makedirs(sheet_dir, exist_ok=True)
            name = '%s.jpg' % content_id
            title = '%s | %s/%s | 时长%s帧%s' % (content_id, basin or '-', topic or '-',
                                                (feat.get('kv') or {}).get('时长(秒)'), len(frames))
            _sheet.make_sheet(frames, os.path.join(sheet_dir, name), title=title)
            sheet_rel = os.path.join(os.path.basename(sheet_dir), name).replace('\\', '/')
        except Exception:
            sheet_rel = None
    return {
        'content_id': content_id,
        'platform': platform,
        'basin': basin,
        'topic': topic,
        'video_url_status': url_status,
        'probe': probe,
        'frames_count': len(frames),
        'frames_sheet': sheet_rel,
        'features': {'keyframe': feat},
        'l1_meta': l1_meta,
        'l1_comment': l1_comment,
        'generated_at': now_iso(),
    }


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def _load_l1(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def run_selftest(out=None):
    out = out or os.path.join(REPO_ROOT, 'video_features', 'l2_selftest.jsonl')
    store = FeatureStore(out)
    store.reset()
    synth = [
        {'内容ID': 'sample_bbb_1', '平台': '公开样例', '流域': '长江', '议题': '文旅',
         'url': SAMPLE_URL, 'l1_meta': {'互动总量': 1200}, 'l1_comment': {'负面占比': 0.3}},
        {'内容ID': 'sample_bbb_2', '平台': '公开样例', '流域': '黄河', '议题': '生态治理',
         'url': SAMPLE_URL, 'l1_meta': {'互动总量': 80, '转发_点赞比': 2.4},
         'l1_comment': {'负面占比': 0.1}},
    ]
    for s in synth:
        rec = _process(s['内容ID'], s['平台'], s['流域'], s['议题'], s['url'],
                       'https://test-videos.co.uk/', False, s['l1_meta'], s['l1_comment'])
        store.write(rec)
    print(f'[SELFTEST] 合成 {len(synth)} 条，特征库：{out}')
    for rec in store.load():
        kf = rec['features']['keyframe']
        print('  ', rec['content_id'], '| frames=%d' % rec['frames_count'],
              '| url=%s' % rec['video_url_status'], '| status=%s' % kf.get('status'),
              '| kv=', (kf.get('kv') or {}).get('主色调'), (kf.get('kv') or {}).get('均值亮度'))
    return len(synth)


def run_db(join_source=False, frac=0.08, floor=2, limit=None, no_probe=False,
           referer='https://www.douyin.com/', out=DEFAULT_OUT, l1_path=DEFAULT_L1,
           keep_frames=None, resume=False):
    records = _load_l1(l1_path)
    if not records:
        print('[L2] 未找到 L1 特征库：', l1_path)
        return 0
    chosen = sample(records, frac=frac, floor=floor)
    print(f'[L2] L1 共 {len(records)} 条 → 候选样本 {len(chosen)} 条（frac={frac}, floor={floor}）')

    engine = None
    if join_source:
        try:
            engine = _ms_engine()
            print('[L2] 已连接 mindspider，按 aweme_id 取 video_download_url')
        except Exception as e:
            print('[L2] 连接 mindspider 失败，所有样本将标 source_unreachable：', str(e)[:100])
            engine = None

    store = FeatureStore(out)
    done = set()
    if resume:
        for r in store.load():
            done.add(r.get('content_id'))
        print(f'[L2] --resume：已有 {len(done)} 条，跳过，只补未完成的')
    else:
        store.reset()
    n = 0
    for _, why, rec in chosen:
        cid = _idof(rec)
        if cid in done:
            continue
        if limit and n >= int(limit):
            print(f'[L2] 本次已达上限 {limit} 条（未跑完的先留着，可再次 --resume 续跑）')
            break
        feats = rec.get('features', {}) or {}
        l1_meta = (feats.get('meta_profile', {}) or {}).get('kv')
        l1_comment = (feats.get('comment_insight', {}) or {}).get('kv')
        url = None
        if engine is not None:
            try:
                url = _fetch_video_url(cid, engine)
            except Exception:
                url = None
        sheet_dir = None
        if keep_frames:
            sheet_dir = keep_frames if os.path.isabs(keep_frames) else os.path.join(REPO_ROOT, keep_frames)
        rec_out = _process(cid, rec.get('platform'), rec.get('basin'), rec.get('topic'),
                           url, referer, no_probe, l1_meta, l1_comment, sheet_dir)
        rec_out['sampled_reasons'] = why
        store.write(rec_out)
        n += 1
        if n % 10 == 0:
            print(f'  ... 已处理 {n}/{len(chosen)}')
    print(f'[L2] 完成，特征库写入：{out}')
    return n


def main():
    p = argparse.ArgumentParser(description='L2 关键帧层编排器')
    p.add_argument('--selftest', action='store_true', help='离线自检（公开样例视频）')
    p.add_argument('--join-source', action='store_true', help='连 mindspider 取 video_download_url')
    p.add_argument('--dry-sample', action='store_true', help='只打印挑中的样本，不下载')
    p.add_argument('--frac', type=float, default=0.08, help='抽样比例（默认 0.08=8%%）')
    p.add_argument('--floor', type=int, default=2, help='每个(流域×议题)保底条数')
    p.add_argument('--limit', type=int, default=None, help='最多处理 N 条样本')
    p.add_argument('--no-probe', action='store_true', help='跳过时长/分辨率探测（更快）')
    p.add_argument('--referer', default='https://www.douyin.com/', help='抖音拉流 Referer')
    p.add_argument('--keep-frames', default=None, metavar='DIR',
                   help='把每条抽到的关键帧拼成一张 contact sheet 存到 DIR（供人工看图；原始视频仍不落盘）')
    p.add_argument('--resume', action='store_true',
                   help='断点续跑：不重置特征库，跳过已完成的 content_id，只补未跑的（配 --limit 分批）')
    p.add_argument('--l1', default=DEFAULT_L1, help='L1 特征库路径')
    p.add_argument('--out', default=None, help='L2 特征库输出路径（默认：真实跑=l2_features.jsonl，自检=l2_selftest.jsonl）')
    a = p.parse_args()

    print('[L2] keyframe 分析器版本：', _reg_get('keyframe').version if _reg_get('keyframe') else '未注册')

    if a.selftest:
        run_selftest(a.out)  # None → l2_selftest.jsonl，绝不覆盖真实特征库
        return

    if a.dry_sample:
        records = _load_l1(a.l1)
        chosen = sample(records, frac=a.frac, floor=a.floor)
        print(f'[DRY] L1 共 {len(records)} 条 → 样本 {len(chosen)} 条')
        for s, why, r in chosen:
            print('  ', _idof(r), r.get('basin'), r.get('议题'), 'score=%.2f' % s, why)
        return

    run_db(a.join_source, a.frac, a.floor, a.limit, a.no_probe, a.referer,
           a.out or DEFAULT_OUT, a.l1, keep_frames=a.keep_frames, resume=a.resume)


if __name__ == '__main__':
    main()

