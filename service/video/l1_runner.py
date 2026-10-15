# -*- coding: utf-8 -*-
"""L1 文本+封面层 · 编排器 / CLI

数据源：t_bettafish_article（BettaFish 回收桥表，含封面 708/708、文本、互动数）。
说明：t_douyin_article 当前 0 行且缺封面/时长字段，故 L1 以 BettaFish 桥接表为现实数据源
（详见 docs/视频分析L1实现说明.md 的"数据源决策"）。若日后 t_douyin_article 补采完成，
只需把 TABLE 换掉，analyzer 与 store 不动。

红线（写死）：
    ① 不下载/不保存原始视频；封面只取图、不取视频流（cover_visual 已实现）
    ② 不提取人脸/声纹特征（本层无此分析器）
    ③ 抽样结论标注样本量，不外推（comment_insight 已实现；--limit 为显式抽样）

用法：
    # 离线自检（合成数据，不连库、不联网）
    python service/video/l1_runner.py --selftest

    # 真实跑（全量，连 db_weibo_basin；含封面抓取）
    python service/video/l1_runner.py

    # 统计 skip（跳过封面网络抓取，纯本地，最稳）
    python service/video/l1_runner.py --no-cover

    # 全量 + 富化时长/分辨率（连 mindspider 取播放地址，HTTP Range 只读头部，零 ffmpeg）
    python service/video/l1_runner.py --enrich-duration
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from registry import all_analyzers, names  # noqa: E402
import analyzers  # noqa: E402,F401  触发三个分析器注册
from store import FeatureStore, now_iso  # noqa: E402
from db import get_engine  # noqa: E402
import mp4_meta  # noqa: E402

TABLE = 't_bettafish_article'
CMT_TABLE = 't_bettafish_comment'
REPO_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DEFAULT_OUT = os.path.join(REPO_ROOT, 'video_features', 'l1_features.jsonl')


def _build_ctx(record, comments, no_cover, extra=None):
    extra = extra or {}
    return {
        'record': record,
        'comments': comments,
        'cover_url': None if no_cover else (record.get('封面') or None),
        'duration': extra.get('duration'),
        'resolution': extra.get('resolution'),
    }


def _run_one(record, comments, no_cover, extra=None):
    ctx = _build_ctx(record, comments, no_cover, extra)
    feats = {}
    for A in all_analyzers():
        try:
            kv = A().analyze(ctx)
            feats[A.name] = {'version': A.version, 'kv': kv, 'status': 'ok'}
        except Exception as e:
            feats[A.name] = {'version': A.version, 'kv': None, 'status': 'error', 'error': str(e)[:160]}
    return feats


def _row_to_record(row):
    # pandas 行 → dict（列名即 t_bettafish_article 列）
    if hasattr(row, 'to_dict'):
        return row.to_dict()
    return dict(row)


def _video_url_map():
    """从 mindspider.douyin_aweme 取 {aweme_id: video_download_url}（BettaFish 桥表未收该字段）。

    连接参数可被环境变量覆盖（MS_DB_*）；连不上返回空 dict（该轮时长不富化，不中断）。
    """
    from sqlalchemy import create_engine, text
    host = os.getenv('MS_DB_HOST', 'localhost')
    user = os.getenv('MS_DB_USER', 'root')
    pwd = os.getenv('MS_DB_PASSWORD', '')
    name = os.getenv('MS_DB_NAME', 'mindspider')
    try:
        eng = create_engine(f'mysql+pymysql://{user}:{pwd}@{host}:3306/{name}?charset=utf8mb4')
        with eng.connect() as c:
            rows = c.execute(text("SELECT `aweme_id`,`video_download_url` FROM `douyin_aweme` "
                                  "WHERE `video_download_url` IS NOT NULL AND `video_download_url`<>''"))
            return {r[0]: r[1] for r in rows}
    except Exception as e:
        print('[L1] mindspider 不可达，跳过时长富化：', str(e)[:100])
        return {}


def enrich_durations(records, workers=8, timeout=6):
    """对每条记录用 mp4_meta 读头部取 时长/分辨率，返回 {content_id: {duration, resolution}}。

    零 ffmpeg；HTTP Range 只取头部（约 256KB），原始视频体不落盘（红线①）。
    地址失效（403）或非 mp4 → 该条不富化，由 meta_profile 标注"缺失"。
    并发 workers 路（默认 8）：只读头部近乎零字节，非批量下载，风控风险低。
    """
    urlmap = _video_url_map()
    if not urlmap:
        return {}
    targets = [(rec.get('内容ID'), urlmap.get(rec.get('内容ID'))) for rec in records]
    targets = [(cid, u) for cid, u in targets if u]
    out = {}
    if not targets:
        return out

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(item):
        cid, url = item
        info = mp4_meta.probe_url(url, timeout=timeout)
        if info and info.get('duration'):
            return cid, {
                'duration': info['duration'],
                'resolution': ('%dx%d' % (info['width'], info['height'])) if info.get('width') else None,
            }
        return cid, None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_one, t) for t in targets]
        done = 0
        for f in as_completed(futs):
            cid, val = f.result()
            if val:
                out[cid] = val
            done += 1
            if done % 100 == 0:
                print(f'  ... 时长富化 {done}/{len(targets)}，已取到 {len(out)} 条')
    print(f'[L1] 时长富化完成：{len(out)}/{len(records)} 条取到（其余为地址失效或无地址）')
    return out


def run_db(platform=None, limit=None, no_cover=False, out=DEFAULT_OUT, enrich=False):
    engine = get_engine()
    import pandas as pd
    sql = f'SELECT * FROM `{TABLE}`'
    if platform:
        sql += f" WHERE `平台`='{platform}'"
    df = pd.read_sql(sql, engine)
    if limit:
        df = df.head(int(limit))
    print(f'[L1] 读取 {len(df)} 条内容（数据源 {TABLE}）')

    # 评论：一次性取出按 内容ID 分组
    cmt_sql = f'SELECT `内容ID`,`评论内容` FROM `{CMT_TABLE}`'
    cmts = pd.read_sql(cmt_sql, engine)
    grouped = {}
    for _, r in cmts.iterrows():
        cid = r['内容ID']
        grouped.setdefault(cid, []).append(r['评论内容'])
    print(f'[L1] 读取评论 {len(cmts)} 条，覆盖 {len(grouped)} 个内容')

    records = [_row_to_record(row) for _, row in df.iterrows()]
    enriched = enrich_durations(records) if enrich else {}

    store = FeatureStore(out)
    store.reset()
    n = 0
    for rec in records:
        cid = rec.get('内容ID')
        feats = _run_one(rec, grouped.get(cid, []), no_cover, enriched.get(cid))
        store.write({
            'content_id': cid,
            'platform': rec.get('平台'),
            'basin': rec.get('流域'),
            'topic': rec.get('议题'),
            'features': feats,
            'coverage': {'n_analyzed': len(feats), 'n_total': len(names())},
            'generated_at': now_iso(),
        })
        n += 1
        if n % 50 == 0:
            print(f'  ... 已处理 {n}/{len(records)}')
    print(f'[L1] 完成，特征库写入：{out}')
    return n


def run_selftest(out=None):
    out = out or os.path.join(REPO_ROOT, 'video_features', 'l1_selftest.jsonl')
    store = FeatureStore(out)
    store.reset()
    synth = [
        {'内容ID': 'aweme_test_1', '平台': '抖音', '流域': '长江', '议题': '文旅',
         '标题': 'XX景区游客爆满', '内容': '假期游客太多体验差',
         '点赞数': 1200, '评论数': 300, '转发数': 80, '收藏数': 50,
         '封面': None},
        {'内容ID': 'aweme_test_2', '平台': '抖音', '流域': '黄河', '议题': '生态治理',
         '标题': '河道治理成效', '内容': '水质明显改善',
         '点赞数': 500, '评论数': 20, '转发数': 200, '收藏数': 10,
         '封面': 'http://example.com/cover.jpg'},
        {'内容ID': 'aweme_test_3', '平台': '小红书', '流域': '长江', '议题': '文旅',
         '标题': '无互动内容', '内容': '随手拍',
         '点赞数': 0, '评论数': 0, '转发数': 0, '收藏数': 0, '封面': None},
    ]
    comments = {
        'aweme_test_1': ['太坑人了，差评', '请问怎么购票', '支持整改，点赞',
                          '投诉维权，曝光乱象', '好看，想去'],
        'aweme_test_2': ['水质真的变好了吗？质疑', '点赞支持'],
    }
    # 第一条给上"富化"后的时长/分辨率，验证 meta_profile 能读 ctx
    enriched = {'aweme_test_1': {'duration': 12.5, 'resolution': '640x360'}}
    for rec in synth:
        feats = _run_one(rec, comments.get(rec['内容ID'], []), no_cover=True,
                         extra=enriched.get(rec['内容ID']))
        store.write({
            'content_id': rec['内容ID'], 'platform': rec['平台'],
            'basin': rec['流域'], 'topic': rec['议题'],
            'features': feats, 'coverage': {'n_analyzed': len(feats), 'n_total': len(names())},
            'generated_at': now_iso(),
        })
    print(f'[SELFTEST] 合成 {len(synth)} 条，特征库：{out}')
    for rec in store.load():
        print('  ', rec['content_id'], '->',
              {k: (v.get('status'), list((v.get('kv') or {}).keys())) for k, v in rec['features'].items()})
    return len(synth)


def main():
    p = argparse.ArgumentParser(description='L1 文本+封面层编排器')
    p.add_argument('--selftest', action='store_true', help='离线自检（合成数据）')
    p.add_argument('--platform', default=None, help='按平台过滤，如 抖音')
    p.add_argument('--limit', type=int, default=None, help='最多处理 N 条（显式抽样）')
    p.add_argument('--no-cover', action='store_true', help='跳过封面网络抓取（最稳，离线可用）')
    p.add_argument('--enrich-duration', action='store_true',
                   help='连 mindspider 取播放地址，HTTP Range 只读头部取时长/分辨率（零 ffmpeg）')
    p.add_argument('--out', default=None, help='特征库输出路径（默认：真实跑=l1_features.jsonl，自检=l1_selftest.jsonl）')
    a = p.parse_args()

    print('[L1] 已注册分析器：', names())
    if a.selftest:
        run_selftest(a.out)  # None → l1_selftest.jsonl，绝不覆盖真实特征库
    else:
        run_db(a.platform, a.limit, a.no_cover, a.out or DEFAULT_OUT, enrich=a.enrich_duration)


if __name__ == '__main__':
    main()

