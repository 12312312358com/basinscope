# -*- coding: utf-8 -*-
"""L1-1 元数据画像：互动指标比率 + 时长/分辨率（不下载视频）。

覆盖方案 §四 E1（容器元数据）+ E2（平台侧预计算特征）+ §七 阶段1「素材画像基线」。
时长/分辨率来源（优先级从高到低）：
  1) ctx['duration'] / ctx['resolution']：由 l1_runner `--enrich-duration` 用
     `mp4_meta.probe_url`（HTTP Range 只读头部，零 ffmpeg、近乎零视频字节）取得；
  2) 未富化则显式标注"缺失"，不编造（红线③：不外推、不造假）。
"""
from base import BaseAnalyzer, register


def _i(v):
    try:
        return int(float(v or 0))
    except Exception:
        return 0


@register
class MetaProfileAnalyzer(BaseAnalyzer):
    name = 'meta_profile'
    version = '0.2'
    needs = ('metadata',)

    def analyze(self, ctx):
        r = ctx.get('record', {}) or {}
        like = _i(r.get('点赞数'))
        cmt = _i(r.get('评论数'))
        share = _i(r.get('转发数'))
        collect = _i(r.get('收藏数'))
        total = like + cmt + share + collect
        dur = ctx.get('duration')
        res = ctx.get('resolution')
        return {
            '互动总量': total,
            '点赞数': like,
            '评论数': cmt,
            '转发数': share,
            '收藏数': collect,
            '转发_点赞比': round(share / like, 4) if like else None,
            '评论_点赞比': round(cmt / like, 4) if like else None,
            '收藏_点赞比': round(collect / like, 4) if like else None,
            '赞评转结构': [like, cmt, share],
            '时长': dur,
            '分辨率': res,
            '时长状态': 'ok' if dur else '缺失-需E3扩采或地址已失效',
        }
