# -*- coding: utf-8 -*-
"""L2 关键帧分析器：对抽出的关键帧做 PIL 视觉统计 + 跨帧聚合。

输入 ctx：
    ctx['frames'] : [(pts, jpeg_bytes), ...]  由 fetch.extract_keyframes 提供
    ctx['probe']  : {duration, width, height, ...}  由 probe.probe 提供（可为空）
    ctx['record'] : 一条内容记录（dict，可选，仅用于标注）
    ctx['comments'] / ctx['cover_url'] : 同 L1（本分析器不使用）

落实红线：
    ① 原始视频流不落盘——帧已存在于内存（fetch 阶段），本分析器只读字节、不写盘；
    ② 不做人脸/声纹识别，只做整帧色彩/亮度统计；
    ③ 抽样结论由 runner 统一标注样本量，不外推。
"""
import io
import statistics
from collections import Counter

from base import BaseAnalyzer, register
from PIL import Image, ImageStat

# 与 cover_visual 一致的色相分桶，保证"封面视觉"与"关键帧视觉"口径可比
_HUE_BUCKETS = [
    ('红', 0, 15), ('橙', 15, 45), ('黄', 45, 70), ('绿', 70, 160),
    ('青', 160, 200), ('蓝', 200, 260), ('紫', 260, 290), ('品红', 290, 330),
    ('红', 330, 360),
]


def _hue_bucket(r, g, b):
    import colorsys
    h, _, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    deg = int(h * 360)
    for name, lo, hi in _HUE_BUCKETS:
        if lo <= deg < hi:
            return name
    return '灰'


@register
class KeyframeAnalyzer(BaseAnalyzer):
    name = 'keyframe'
    version = '0.1'
    needs = ('frames',)

    def analyze(self, ctx):
        frames = ctx.get('frames') or []
        probe = ctx.get('probe') or {}
        if not frames:
            return {'frames_count': 0, 'has_video': False, 'status': 'no_frames'}

        per = []
        for pts, b in frames:
            try:
                img = Image.open(io.BytesIO(b)).convert('RGB')
            except Exception:
                continue
            w, h = img.size
            stat = ImageStat.Stat(img)
            mean = stat.mean
            std = stat.stddev
            brightness = float(sum(mean) / 3.0)
            # 色彩丰富度（Hasler-Süsstrunk 简化：RGB 通道标准差均值）
            colorfulness = float((std[0] + std[1] + std[2]) / 3.0)
            per.append({
                'pts': pts,
                'w': w, 'h': h,
                'brightness': round(brightness, 1),
                'colorfulness': round(colorfulness, 1),
                'hue': _hue_bucket(int(mean[0]), int(mean[1]), int(mean[2])),
            })
        if not per:
            return {'frames_count': 0, 'has_video': True, 'status': 'decode_failed'}

        brights = [p['brightness'] for p in per]
        cols = [p['colorfulness'] for p in per]
        hue_counter = Counter(p['hue'] for p in per)
        ts = self._timestamps(per, probe)

        bright_std = round(statistics.pstdev(brights), 2) if len(brights) > 1 else 0.0
        bright_trend = round(brights[-1] - brights[0], 1)
        mean_hue = max(hue_counter.items(), key=lambda kv: kv[1])[0]

        return {
            'frames_count': len(per),
            'has_video': True,
            'status': 'ok',
            '分辨率': '%dx%d' % (per[0]['w'], per[0]['h']),
            '时长(秒)': round(probe['duration'], 1) if probe.get('duration') else None,
            '帧时间戳(秒)': [round(t, 2) for t in ts],
            '均值亮度': round(sum(brights) / len(brights), 1),
            '亮度标准差': bright_std,
            '亮度趋势_末减首': bright_trend,
            '均值色彩丰富度': round(sum(cols) / len(cols), 1),
            '主色调': mean_hue,
            '主色调分布': dict(hue_counter),
            '说明': '跨关键帧聚合；时间戳为 pts×time_base 或均匀近似，精度±GOP/2',
        }

    @staticmethod
    def _timestamps(per, probe):
        n = len(per)
        tb = probe.get('time_base')
        dur = probe.get('duration')
        if tb and dur:
            return [p['pts'] * tb for p in per]
        if dur:
            return [(i + 0.5) / n * dur for i in range(n)]
        # 无时长信息：用帧序号占位，结论仅限相对顺序
        return [i + 1 for i in range(n)]
