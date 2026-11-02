# -*- coding: utf-8 -*-
"""L3 取音轨：ffmpeg `-vn` 只解音频 → 16k 单声道 PCM(s16le)。

红线①延续：**原始视频不落盘，音轨文件也不落盘**（PCM 只在内存，ASR 用完即丢）。
只做"取音轨"，不做任何声纹/说话人相关处理（红线②强化）。
"""
import subprocess

from probe import _ffmpeg_exe, _hdr_str

_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def extract_audio_pcm(url, headers=None, sr=16000, timeout=120, max_seconds=None):
    """返回 16k 单声道 s16le 的 PCM bytes；失败/无音轨返回 None。

    - 只读网络流，不写任何文件（连临时文件都不写）。
    - `max_seconds`：只取前 N 秒（ASR 省算力；L3 抽样常用）。
    返回字节数 ≈ sr*2*秒数（16k 单声道 s16le ≈ 32 KB/s）。
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        raise RuntimeError('未找到 ffmpeg：请先安装 imageio-ffmpeg 或系统 ffmpeg')
    if headers is None:
        headers = dict(_UA)
    else:
        headers.setdefault('User-Agent', _UA['User-Agent'])
    hstr = _hdr_str(headers)

    cmd = [ffmpeg]
    if hstr:
        cmd += ['-headers', hstr]
    cmd += ['-nostdin']
    if max_seconds:
        cmd += ['-t', str(max_seconds)]
    cmd += ['-i', url, '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', 'pipe:1']
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        return None
    return p.stdout or None


def pcm_seconds(pcm, sr=16000):
    """PCM 字节数 → 秒数（16bit 单声道）。"""
    if not pcm:
        return 0.0
    return round(len(pcm) / (sr * 2), 3)
