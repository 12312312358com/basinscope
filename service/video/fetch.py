# -*- coding: utf-8 -*-
"""L2 拉流 + 关键帧抽取：原始视频流只过 ffmpeg，绝不落盘（红线①）。

链路（方案 §6b.1 ②→③→④）：
    ① ffmpeg 直接打开播放地址（http demuxer 支持 Range 寻址，moov 在尾部也能抽帧）
    ② `-skip_frame nokey` 只解 I 帧，输出 JPEG 到临时目录
    ③ 读入内存后立即删除临时 JPEG；原始视频流全程不落盘
    ④ 若 I 帧 < min_frames，退化为均匀抽帧（可选，需显式传 fallback_fps）

关键点：让 ffmpeg 自己打开 URL，而不是用 requests 把视频体灌进 stdin(pipe:0)。
原因：mp4 的 moov 原子常在文件尾部，pipe 无法 seek 会导致 ffmpeg 抽帧失败；
直接给 URL 时 ffmpeg 的 http demuxer 会用 Range 请求补读 moov，更稳。
返回的每一帧是 (pts, jpeg_bytes)：pts 来自 `-frame_pts 1` 的文件名，
配合 probe 的 time_base 可换算成秒（见 analyzers/keyframe.py）。
"""
import os
import re
import shutil
import subprocess
import tempfile

from probe import _ffmpeg_exe, _hdr_str

_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def extract_keyframes(url, headers=None, scale=480, qv=3, max_frames=20,
                      timeout=120, min_frames=3, fallback_fps=None):
    """流式抽 I 帧，返回 [(pts, jpeg_bytes), ...]（已按 pts 升序）。

    原始视频流不落盘（ffmpeg 只读网络流、只写 JPEG 到临时目录，读后立即删）。
    返回空列表的情形：地址返回非视频（抖音错误页/403 落地页）、网络异常、ffmpeg 不可用——
    调用方应据此标记该条内容为 skip。
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg or (ffmpeg == 'ffmpeg' and shutil.which('ffmpeg') is None):
        raise RuntimeError('未找到 ffmpeg：请先安装 imageio-ffmpeg 或系统 ffmpeg')
    if headers is None:
        headers = dict(_UA)
    else:
        headers.setdefault('User-Agent', _UA['User-Agent'])
    hstr = _hdr_str(headers)

    tmp = tempfile.mkdtemp(prefix='kf_')
    try:
        frames = _run_iframe_pass(ffmpeg, url, hstr, scale, qv, tmp, timeout)
        if len(frames) < min_frames and fallback_fps:
            frames = _run_uniform_pass(ffmpeg, url, hstr, scale, qv,
                                       fallback_fps, tmp, timeout)
        # 关键：超过上限时【均匀】抽稀，而不是取最早的 N 帧——
        # 否则长视频只覆盖开头（实测 1295s 的片子 308 个 I 帧只保前 20 → 覆盖率 4.5%）。
        return _evenly(frames, max_frames)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _evenly(frames, k):
    """从 frames 里均匀取 k 帧（保首尾），用于在帧数上限内覆盖整段时间线。"""
    n = len(frames)
    if n <= k or k <= 0:
        return frames
    if k == 1:
        return [frames[0]]
    idx = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return [frames[i] for i in idx]


def extract_uniform(url, headers=None, fps=1.0, scale=480, qv=3, max_frames=120,
                    timeout=180):
    """均匀抽帧（每 1/fps 秒一帧），用于与 L2 的 I 帧做「代表性」对照。

    原始视频不落盘（只读网络流、只写 JPEG 到临时目录、读后即删）。
    返回 [(序号, jpeg_bytes), ...]；序号从 1 递增，可按 (i-1)/N 映射到相对时间位置。
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg or (ffmpeg == 'ffmpeg' and shutil.which('ffmpeg') is None):
        raise RuntimeError('未找到 ffmpeg：请先安装 imageio-ffmpeg 或系统 ffmpeg')
    if headers is None:
        headers = dict(_UA)
    else:
        headers.setdefault('User-Agent', _UA['User-Agent'])
    hstr = _hdr_str(headers)

    tmp = tempfile.mkdtemp(prefix='uf_')
    try:
        frames = _run_uniform_pass(ffmpeg, url, hstr, scale, qv, fps, tmp, timeout)
        return frames[:max_frames]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run_iframe_pass(ffmpeg, url, hstr, scale, qv, tmp, timeout):
    out_pat = os.path.join(tmp, '%d.jpg')
    cmd = [ffmpeg]
    if hstr:
        cmd += ['-headers', hstr]
    cmd += ['-nostdin', '-skip_frame', 'nokey', '-i', url,
            '-vsync', 'vfr', '-frame_pts', '1',
            '-vf', 'scale=%d:-1' % scale, '-q:v', str(qv),
            '-f', 'image2', out_pat]
    return _run(cmd, tmp, timeout)


def _run_uniform_pass(ffmpeg, url, hstr, scale, qv, fps, tmp, timeout):
    out_pat = os.path.join(tmp, 'u_%d.jpg')
    cmd = [ffmpeg]
    if hstr:
        cmd += ['-headers', hstr]
    cmd += ['-nostdin', '-i', url,
            '-vf', 'fps=%s,scale=%d:-1' % (fps, scale), '-q:v', str(qv),
            '-f', 'image2', out_pat]
    return _run(cmd, tmp, timeout)


def _run(cmd, tmp, timeout):
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        # 超时（如视频体过大/网络慢）→ 视为本批抽帧失败，交由调用方 skip
        return []
    if proc.returncode != 0:
        # 非视频内容（HTML 错误页）/ 403 / 网络错误 → 优雅返回空，不抛异常
        return []
    return _collect(tmp)


def _collect(tmp):
    out = []
    for fn in os.listdir(tmp):
        if not fn.endswith('.jpg'):
            continue
        fp = os.path.join(tmp, fn)
        try:
            with open(fp, 'rb') as f:
                data = f.read()
        except Exception:
            continue
        if not data:
            continue
        m = re.match(r'(\d+)', fn)
        pts = int(m.group(1)) if m else len(out)
        out.append((pts, data))
    out.sort(key=lambda x: x[0])
    return out
