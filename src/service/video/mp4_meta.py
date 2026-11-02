# -*- coding: utf-8 -*-
"""纯 Python MP4 头部解析：取时长/分辨率（**零 ffmpeg 依赖、近乎零视频字节**）。

落实方案 §四 E1「只解析容器元数据」：用 HTTP Range 只取文件头（或 moov 所在尾块），
在内存里解析 `moov/mvhd`（时长、时基）与 `tkhd`（宽高），**不下载完整视频体、不落盘**。
这样 L1 的「元数据画像·时长」不再依赖 ffmpeg（方案 §6b.6 本要求 ffmpeg，这里给了零依赖的等价实现）。

只处理 MP4/MOV 系（抖音、微博视频主流程均为 mp4）。解析失败返回 None，由调用方标"未取到"。
"""
import struct

_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def probe_url(url, headers=None, timeout=12, head_bytes=262144, tail_bytes=524288):
    """用 Range 读头部（必要时补读尾部）解析出 {duration, timescale, width, height, bytes_read, source}。

    duration 单位：秒（float）。失败返回 None（不抛异常）。
    """
    try:
        import requests
    except Exception:
        return None
    hdrs = dict(_UA if headers is None else {**headers, 'User-Agent': headers.get('User-Agent', _UA['User-Agent'])})

    buf, got = _range_get(url, hdrs, timeout, 0, head_bytes - 1)
    if buf is None:
        return None
    total_read = got
    res = _parse(buf)
    if not res or not res.get('duration'):
        # moov 不在头部（mdat 在前）→ 补读尾部
        b2, got2 = _range_get(url, hdrs, timeout, None, tail_bytes)  # bytes=-N
        if b2 is not None:
            total_read += got2
            r2 = _parse(b2)
            if r2 and r2.get('duration'):
                res = r2
    if not res or not res.get('duration'):
        return None
    res['bytes_read'] = total_read
    res['source'] = 'mp4_range'
    return res


def _range_get(url, headers, timeout, start, end):
    import requests
    rng = 'bytes=%s-%s' % (start, end) if start is not None else 'bytes=-%d' % end
    try:
        r = requests.get(url, headers={**headers, 'Range': rng}, timeout=timeout)
    except Exception:
        return None, 0
    if r.status_code not in (200, 206):
        return None, 0
    return r.content, len(r.content)


def _iter_boxes(buf, start=0, end=None):
    n = len(buf)
    if end is None or end > n:
        end = n
    i = start
    while i + 8 <= end:
        size = struct.unpack('>I', buf[i:i + 4])[0]
        btype = buf[i + 4:i + 8]
        hdr = 8
        if size == 1:
            if i + 16 > end:
                break
            size = struct.unpack('>Q', buf[i + 8:i + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - i
        if size < hdr or i + size > n:
            # 声明的 size 超出已读缓冲（尾部 moov 被截断）→ 停止，避免解析残缺载荷
            break
        yield btype, i + hdr, i + size
        i += size


def _find_moov(buf):
    """返回 (moov 载荷起点, moov 结束) 或 None。兼容 moov 在头/尾两种情形。"""
    idx = buf.find(b'moov')
    while idx != -1:
        if idx >= 4:
            size = struct.unpack('>I', buf[idx - 4:idx])[0]
            box_start = idx - 4
            if size >= 8:
                return idx + 4, min(box_start + size, len(buf))
        idx = buf.find(b'moov', idx + 1)
    return None


def _parse(buf):
    loc = _find_moov(buf)
    if not loc:
        return None
    moov_start, moov_end = loc
    out = {}
    for btype, ps, pe in _iter_boxes(buf, moov_start, moov_end):
        if btype == b'mvhd':
            mv = _parse_mvhd(buf[ps:pe])
            if mv:
                out.update(mv)
        elif btype == b'trak':
            w_h = _parse_trak(buf, ps, pe)
            if w_h and not out.get('width'):
                out.update(w_h)
    return out or None


def _parse_mvhd(p):
    if len(p) < 20:
        return None
    ver = p[0]
    try:
        if ver == 1:
            timescale = struct.unpack('>I', p[20:24])[0]
            duration = struct.unpack('>Q', p[24:32])[0]
        else:
            timescale = struct.unpack('>I', p[12:16])[0]
            duration = struct.unpack('>I', p[16:20])[0]
    except Exception:
        return None
    if not timescale:
        return None
    return {'duration': round(duration / timescale, 3), 'timescale': timescale}


def _parse_trak(buf, ps, pe):
    for btype, s, e in _iter_boxes(buf, ps, pe):
        if btype == b'tkhd':
            wh = _parse_tkhd(buf[s:e])
            if wh:
                return wh
    return None


def _parse_tkhd(p):
    if len(p) < 84:
        return None
    ver = p[0]
    try:
        if ver == 1:
            w_off, h_off = 88, 92
        else:
            w_off, h_off = 76, 80
        if len(p) < h_off + 4:
            return None
        w = struct.unpack('>I', p[w_off:w_off + 4])[0] / 65536.0
        h = struct.unpack('>I', p[h_off:h_off + 4])[0] / 65536.0
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return {'width': int(round(w)), 'height': int(round(h))}
