# -*- coding: utf-8 -*-
"""L2 探针：拿视频时长 / 分辨率 / 码率（近乎零字节）。

优先用 ffprobe（若存在）；本机现状无 ffprobe（方案 §八），退化为用 ffmpeg 解析 stderr 的
`Duration:` / `Stream ... Video:` 行。两个入口都只读取头部元数据（faststart 的 mp4 只需少量字节），
**原始视频体不被下载、不落盘**（落实红线①）。

ffmpeg 二进制来源：优先用项目内 imageio-ffmpeg 自带的 ffmpeg（方案 §6b.6 推荐 pip 方式，不碰系统）。
"""
import json
import re
import shutil
import subprocess


def _ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return shutil.which('ffmpeg') or 'ffmpeg'


def _ffprobe_exe():
    return shutil.which('ffprobe') or None


def _hdr_str(headers):
    """requests 风格 headers -> ffmpeg -headers 'k: v\\r\\n' 字符串。"""
    if not headers:
        return None
    return ''.join('%s: %s\r\n' % (k, v) for k, v in headers.items())


def probe(url, headers=None, timeout=30):
    """返回 {duration, width, height, codec, fps, bitrate, time_base, source}。

    全程不写盘。ffprobe 优先；失败或不存在时退化为 ffmpeg stderr 解析。
    任何失败都抛异常，由调用方决定降级（None）或重试。
    """
    exe = _ffmpeg_exe()
    hstr = _hdr_str(headers)
    fp = _ffprobe_exe()
    if fp:
        try:
            return _probe_ffprobe(fp, url, hstr, timeout)
        except Exception:
            pass
    return _probe_ffmpeg_stderr(exe, url, hstr, timeout)


def _probe_ffprobe(fp, url, hstr, timeout):
    cmd = [fp, '-v', 'error']
    if hstr:
        cmd += ['-headers', hstr]
    cmd += [
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,codec_name,avg_frame_rate,r_frame_rate,time_base,duration',
        '-show_entries', 'format=duration,bit_rate',
        '-of', 'json', url,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    info = json.loads(out.stdout or '{}')
    stream = (info.get('streams') or [{}])[0]
    fmt = info.get('format') or {}
    dur = _num(stream.get('duration') or fmt.get('duration'))
    tb = stream.get('time_base')  # 形如 '1/90000'
    tb_sec = _timebase_to_sec(tb)
    w = _num(stream.get('width'))
    h = _num(stream.get('height'))
    afr = stream.get('avg_frame_rate') or stream.get('r_frame_rate') or ''
    fps = _frac_to_float(afr)
    return {
        'duration': dur,
        'width': w,
        'height': h,
        'codec': stream.get('codec_name'),
        'fps': round(fps, 3) if fps else None,
        'bitrate': _num(fmt.get('bit_rate')),
        'time_base': tb_sec,
        'source': 'ffprobe',
    }


def _probe_ffmpeg_stderr(exe, url, hstr, timeout):
    cmd = [exe, '-hide_banner']
    if hstr:
        cmd += ['-headers', hstr]
    cmd += ['-i', url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # 超时也尝试解析已输出的 stderr（已读到 moov 的情况）
        out = None
    text = (out.stderr if out else '') or ''
    dur = None
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', text)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    w = h = None
    m = re.search(r'Stream.*?Video.*?(\d{2,5})x(\d{2,5})', text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    codec = None
    m = re.search(r'Video:\s*(\w+)', text)
    if m:
        codec = m.group(1)
    return {
        'duration': dur,
        'width': w,
        'height': h,
        'codec': codec,
        'fps': None,
        'bitrate': None,
        'time_base': None,
        'source': 'ffmpeg_stderr',
    }


def _num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _frac_to_float(s):
    if not s or '/' not in s:
        try:
            return float(s)
        except (TypeError, ValueError):
            return None
    a, b = s.split('/', 1)
    try:
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _timebase_to_sec(tb):
    if not tb or '/' not in tb:
        return None
    a, b = tb.split('/', 1)
    try:
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
