# -*- coding: utf-8 -*-
"""L3 音频层 · 编排器 / CLI

流程：读 L2 特征库 → 挑"已成功抽到帧的视频"子集 → 取音轨（ffmpeg `-vn`，不落盘）
      → `asr` 分析器转写 → 写 `l3_features.jsonl`。

红线：① 不保存原始视频，**也不保存音轨**（PCM 走内存，ASR 完即丢）；
      ② **只转写，不做声纹 / 说话人分离 / 情绪识别**。

后端：可插拔（faster-whisper → funasr），未装则优雅降级 `后端=None`（不报错）。

用法：
    # 离线自检（mock 后端 + 合成 PCM，不连库、不联网）
    python service/video/l3_runner.py --selftest
    # 只看挑了哪些样本
    python service/video/l3_runner.py --dry-sample --limit 20
    # 真实跑（未装 ASR 后端时会优雅降级）
    python service/video/l3_runner.py --limit 20 --max-seconds 60
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from registry import names  # noqa: E402
import analyzers.asr as _asr  # noqa: E402  （导入即注册 name='asr'）
from audio import extract_audio_pcm, pcm_seconds  # noqa: E402
from store import FeatureStore, now_iso  # noqa: E402
from l2_runner import _ms_engine, _fetch_video_url  # noqa: E402  复用 mindspider 取地址

REPO_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
DEFAULT_SRC = os.path.join(REPO_ROOT, 'video_features', 'l2_features.jsonl')
DEFAULT_OUT = os.path.join(REPO_ROOT, 'video_features', 'l3_features.jsonl')
_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
       'Referer': 'https://www.douyin.com/'}


def _load_src(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def pick(records, limit=None):
    """挑已抽到帧的视频（=真实视频），按互动量降序，取前 limit。"""
    ok = [r for r in records if (r.get('frames_count') or 0) > 0]

    def score(r):
        return ((r.get('l1_meta') or {}).get('互动总量') or 0)
    ok.sort(key=score, reverse=True)
    return ok[:limit] if limit else ok


def _analyze(rec, url, max_seconds):
    pcm = extract_audio_pcm(url, headers=_UA, max_seconds=max_seconds)
    kv = _asr.AsrAnalyzer().analyze({'audio_pcm': pcm, 'audio_sr': 16000})
    return kv, pcm_seconds(pcm or b'')


def run_selftest(out=None):
    out = out or os.path.join(REPO_ROOT, 'video_features', 'l3_selftest.jsonl')
    # mock 后端：不联网、不装模型，验证「取音轨→分析器→落库」链路 + 脱敏
    _asr.set_backend('mock', 'mock-1',
                     lambda pcm, sr: ('这是一段测试转写，联系 13800138000 或 @小明。', 'zh'))
    store = FeatureStore(out)
    store.reset()
    synth = [{'content_id': 'mock_1', 'basin': '长江', 'topic': '文旅', 'sec': 5.0},
             {'content_id': 'mock_2', 'basin': '黄河', 'topic': '生态治理', 'sec': 12.0}]
    for s in synth:
        pcm = b'\x00\x00' * int(16000 * s['sec'])   # 合成静音 PCM（15.9KB/s）
        kv = _asr.AsrAnalyzer().analyze({'audio_pcm': pcm, 'audio_sr': 16000})
        store.write({'content_id': s['content_id'], 'platform': 'mock',
                     'basin': s['basin'], 'topic': s['topic'],
                     'audio_seconds': pcm_seconds(pcm),
                     'features': {'asr': {'version': _asr.AsrAnalyzer.version,
                                          'kv': kv, 'status': 'ok'}},
                     'generated_at': now_iso()})
    print(f'[SELFTEST] 合成 {len(synth)} 条（mock 后端），特征库：{out}')
    for r in store.load():
        kv = r['features']['asr']['kv']
        print('  ', r['content_id'], '| 后端=%s' % kv.get('后端'), '| 字数=%s' % kv.get('字数'),
              '| 语速=%s' % kv.get('语速(字/分)'), '| 文本=%s' % (kv.get('转写文本') or '')[:40])
    return len(synth)


def run(src=None, limit=None, max_seconds=None, out=DEFAULT_OUT, dry=False):
    recs = _load_src(src or DEFAULT_SRC)
    if not recs:
        print('[L3] 未找到 L2 特征库：', src or DEFAULT_SRC, '（先跑 l2_runner）')
        return 0
    chosen = pick(recs, limit)
    print(f'[L3] 源 {len(recs)} 条 → 候选 {len(chosen)} 条（已抽到帧的视频）')
    if dry:
        for r in chosen[:30]:
            print('  ', r['content_id'], r.get('basin'), r.get('topic'),
                  'frames=%s' % r.get('frames_count'),
                  '互动=%s' % (r.get('l1_meta') or {}).get('互动总量'))
        print(f'  ... 共 {len(chosen)} 条')
        return len(chosen)

    eng = None
    try:
        eng = _ms_engine()
        print('[L3] 已连接 mindspider 取播放地址')
    except Exception as e:
        print('[L3] mindspider 不可达：', str(e)[:100])

    store = FeatureStore(out)
    store.reset()
    n = 0
    for r in chosen:
        cid = r['content_id']
        url = _fetch_video_url(cid, eng) if eng is not None else None
        status = 'missing'
        kv = {'状态': 'no_url'}
        aud_s = 0.0
        if url:
            kv, aud_s = _analyze(r, url, max_seconds)
            status = 'ok' if aud_s > 0 else 'no_audio'
        store.write({'content_id': cid, 'platform': r.get('platform'),
                     'basin': r.get('basin'), 'topic': r.get('topic'),
                     'audio_url_status': status, 'audio_seconds': aud_s,
                     'asr_backend': kv.get('后端'),
                     'features': {'asr': {'version': _asr.AsrAnalyzer.version,
                                          'kv': kv, 'status': 'ok'}},
                     'generated_at': now_iso()})
        n += 1
        if n % 10 == 0:
            print(f'  ... 已处理 {n}/{len(chosen)}')
    print(f'[L3] 完成，特征库写入：{out}')
    return n


def main():
    p = argparse.ArgumentParser(description='L3 音频层编排器')
    p.add_argument('--selftest', action='store_true', help='离线自检（mock 后端，不联网）')
    p.add_argument('--dry-sample', action='store_true', help='只打印挑中的样本')
    p.add_argument('--limit', type=int, default=None, help='最多处理 N 条（显式抽样）')
    p.add_argument('--max-seconds', type=float, default=None,
                   help='每条只取前 N 秒音轨（ASR 省算力；L3 抽样常用）')
    p.add_argument('--src', default=DEFAULT_SRC, help='L2 特征库路径')
    p.add_argument('--out', default=None, help='L3 特征库输出路径')
    a = p.parse_args()
    print('[L3] 已注册分析器：', names())
    if a.selftest:
        run_selftest(a.out)
        return
    if a.dry_sample:
        run(a.src, a.limit, a.max_seconds, a.out or DEFAULT_OUT, dry=True)
        return
    run(a.src, a.limit, a.max_seconds, a.out or DEFAULT_OUT)


if __name__ == '__main__':
    main()
