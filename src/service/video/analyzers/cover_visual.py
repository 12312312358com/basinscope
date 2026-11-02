# -*- coding: utf-8 -*-
"""L1-2 封面视觉：只取封面图（图片），绝不下载视频流。

落实红线①：默认不保存原始视频文件；此处连视频流都不碰，仅用 HTTP 取封面图片字节，
在内存里用 PIL 统计尺寸 / 均值色 / 长宽比，不写盘。若地址返回非图片（可能是视频页/错误页）直接跳过。
"""
import colorsys
import io

from base import BaseAnalyzer, register

try:
    import requests
except Exception:
    requests = None
from PIL import Image, ImageStat

_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

_HUE_BUCKETS = [
    ('红', 0, 15), ('橙', 15, 45), ('黄', 45, 70), ('绿', 70, 160),
    ('青', 160, 200), ('蓝', 200, 260), ('紫', 260, 290), ('品红', 290, 330),
    ('红', 330, 360),
]


def _hue_bucket(r, g, b):
    h, _, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    deg = int(h * 360)
    for name, lo, hi in _HUE_BUCKETS:
        if lo <= deg < hi:
            return name
    return '灰'


@register
class CoverVisualAnalyzer(BaseAnalyzer):
    name = 'cover_visual'
    version = '0.1'
    needs = ('cover_url',)

    def analyze(self, ctx):
        url = ctx.get('cover_url')
        if not url:
            return {'has_cover': False, 'status': '无封面'}
        if requests is None:
            return {'has_cover': False, 'status': 'requests缺失'}
        try:
            resp = requests.get(url, headers=_UA, timeout=8)
            ct = resp.headers.get('Content-Type', '')
            if not ct.startswith('image/'):
                return {'has_cover': False, 'status': '非图片(可能为视频页)', 'content_type': ct[:40]}
            img = Image.open(io.BytesIO(resp.content))
            w, h = img.size
            stat = ImageStat.Stat(img.convert('RGB'))
            mean = [round(x) for x in stat.mean]
            return {
                'has_cover': True,
                'status': 'ok',
                '封面宽': w, '封面高': h,
                '长宽比': round(w / h, 3) if h else None,
                '字节数': len(resp.content),
                'content_type': ct,
                '均值RGB': mean,
                '主色调桶': _hue_bucket(*mean),
            }
        except Exception as e:
            return {'has_cover': False, 'status': 'fetch_failed', 'error': str(e)[:120]}
