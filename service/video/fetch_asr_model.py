# -*- coding: utf-8 -*-
"""从 ModelScope 拉取 ASR 模型（国内可达；huggingface.co / hf-mirror.com 在部分网络下超时）。

faster-whisper 默认走 HuggingFace 下载，若 HF 不可达会 ConnectTimeout。
本脚本直连 ModelScope 的 repo 文件接口，把 CTranslate2 格式的 whisper 模型
拉到工程内目录，之后 WhisperModel(<目录>) 直接本地加载，不再联网。

用法：
    python service/video/fetch_asr_model.py                      # 默认 small
    python service/video/fetch_asr_model.py --model small --out models/whisper/small
    python service/video/fetch_asr_model.py --model tiny         # 只想验证链路
可选模型（ModelScope 上的 Systran/faster-whisper-*）：tiny / base / small(推荐) / medium
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

_API = 'https://www.modelscope.cn/api/v1/models/{repo}/repo/files?Revision=master'
_FILE = 'https://www.modelscope.cn/api/v1/models/{repo}/repo?Revision=master&FilePath={path}'

_NEED = ('model.bin', 'tokenizer.json', 'vocabulary.txt', 'config.json', 'configuration.json')


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=timeout).read()


def list_files(repo):
    d = json.loads(_get(_API.format(repo=repo)).decode('utf-8'))
    files = d.get('Data', {}).get('Files') or d.get('Files') or []
    out = {}
    for f in files:
        name = f.get('Path') or f.get('Name')
        if name:
            out[name] = f.get('Size') or 0
    return out


def fetch(repo, out_dir, only_need=True, retries=3):
    os.makedirs(out_dir, exist_ok=True)
    files = list_files(repo)
    if not files:
        raise SystemExit('ModelScope 上未取到文件列表：%s' % repo)
    names = [n for n in _NEED if n in files] if only_need else sorted(files)
    miss = [n for n in _NEED if n not in files]
    if miss:
        print('[warn] 该仓库缺少文件：%s（可能仍能工作）' % ', '.join(miss))
    total = sum(files.get(n, 0) for n in names)
    print('[asr] 仓库 %s：待下载 %d 个文件，共 %.0f MB' % (repo, len(names), total / 1048576))

    for i, n in enumerate(names, 1):
        dst = os.path.join(out_dir, n)
        if os.path.isfile(dst) and os.path.getsize(dst) > 0:
            print('  [%d/%d] %s 已存在，跳过' % (i, len(names), n))
            continue
        url = _FILE.format(repo=repo, path=n)
        t0 = time.time()
        for attempt in range(1, retries + 1):
            try:
                data = _get(url, timeout=120)
                with open(dst, 'wb') as f:
                    f.write(data)
                dt = time.time() - t0
                sp = len(data) / 1024 / max(dt, 0.001)
                print('  [%d/%d] %-20s %6.1f MB  %.0fs  (%.0f KB/s)'
                      % (i, len(names), n, len(data) / 1048576, dt, sp))
                break
            except Exception as e:                       # noqa: BLE001
                print('  [%d/%d] %s 第%d次失败：%s' % (i, len(names), n, attempt, str(e)[:80]))
                if attempt == retries:
                    raise
                time.sleep(2 * attempt)
    print('[asr] 完成 → %s' % out_dir)
    return out_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='small', help='tiny|base|small|medium')
    ap.add_argument('--repo', default=None, help='自定义 ModelScope 仓库 id')
    ap.add_argument('--out', default=None, help='输出目录（默认 models/whisper/<model>）')
    a = ap.parse_args()

    _PRJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out = a.out or os.path.join(_PRJ, 'models', 'whisper', a.model)
    repo = a.repo or ('Systran/faster-whisper-%s' % a.model)
    print('[asr] 源=%s  目标=%s' % (repo, out))
    fetch(repo, out)
    print('\n[asr] 运行示例（本地加载，不再联网）：')
    print('      ASR_MODEL=%s python service/video/l3_runner.py --limit 3 --max-seconds 30' % out)


if __name__ == '__main__':
    main()
