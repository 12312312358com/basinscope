# -*- coding: utf-8 -*-
"""L3-ASR 分析器：音轨 → 文字转写。

红线②强化：**只做转写，绝不做声纹 / 说话人分离 / 情绪识别**
（音频可含声纹＝生物特征，属个保法敏感项）。

后端**可插拔**（懒加载单例、共享只读，避免重复加载大模型）：
    faster-whisper  →  funasr  →  modelscope  →  都没有则优雅降级 `后端=None`（不报错）。
装哪个用哪个，**不硬依赖**任何 ASR 包——这样代码可以先落地，模型由使用者按需安装。

转写文本会做**脱敏**（手机号/邮箱/@ 昵称）后再入库。
"""
import os
import re

from base import BaseAnalyzer, register

# 懒加载后端单例：{'tried':bool, 'name':str|None, 'model':str|None, 'fn':callable|None}
_BACKEND = {'tried': False, 'name': None, 'model': None, 'fn': None}


def set_backend(name, model, fn):
    """显式注入后端（测试/自定义用）。fn(pcm:int16 bytes, sr:int) -> (text, lang)。"""
    _BACKEND.update({'tried': True, 'name': name, 'model': model, 'fn': fn})


def _load_backend():
    if _BACKEND['tried']:
        return _BACKEND
    _BACKEND['tried'] = True
    # 1) faster-whisper（首选：CPU 友好、体量小）
    try:
        from faster_whisper import WhisperModel
        import numpy as np
        # 模型尺寸：默认 small（中文可用）；ASR_MODEL 既可传尺寸名，也可传本地目录
        size = os.getenv('ASR_MODEL', 'small')
        # 模型落盘目录：默认放工程内 models/whisper（不占 C 盘用户缓存，也便于迁移）
        root = os.getenv('ASR_MODEL_DIR') or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '..',
            'models', 'whisper')
        root = os.path.abspath(root)
        os.makedirs(root, exist_ok=True)
        # 工程内若已有 <root>/<size> 目录（如 models/whisper/small）→ 直接本地加载，不联网
        # （huggingface.co / hf-mirror.com 在部分网络下会 ConnectTimeout）
        local = os.path.join(root, size)
        ref = local if os.path.isdir(local) else size
        m = WhisperModel(ref, device='cpu', compute_type='int8', download_root=root)

        def _fw(pcm, sr):
            a = np.frombuffer(pcm, dtype=np.int16).astype('float32') / 32768.0
            segs, info = m.transcribe(a, language='zh', beam_size=1)
            return ''.join(s.text for s in segs).strip(), getattr(info, 'language', 'zh')
        _BACKEND.update({'name': 'faster-whisper', 'model': size, 'fn': _fw})
        return _BACKEND
    except Exception:
        pass
    # 2) funasr（中文最好，体量大）；3) modelscope pipeline
    for pkg, mn in (('funasr', 'paraformer-zh'),):
        try:
            from funasr import AutoModel
            m = AutoModel(model=os.getenv('ASR_MODEL', 'paraformer-zh'))

            def _fn(pcm, sr, _m=m):
                import numpy as np
                a = np.frombuffer(pcm, dtype=np.int16).astype('float32') / 32768.0
                r = _m.generate(input=a)
                return (r[0].get('text', '') if r else '').strip(), 'zh'
            _BACKEND.update({'name': pkg, 'model': mn, 'fn': _fn})
            return _BACKEND
        except Exception:
            continue
    _BACKEND.update({'name': None, 'model': None, 'fn': None})
    return _BACKEND


_PII_PATTERNS = [
    (re.compile(r'1[3-9]\d{9}'), '[手机号]'),
    (re.compile(r'[\w.\-]+@[\w.\-]+\.\w+'), '[邮箱]'),
    (re.compile(r'(?<!\w)@[\w\-\u4e00-\u9fa5]{2,20}'), '[昵称]'),  # @xxx
]


def mask_text(t):
    t = t or ''
    for pat, rep in _PII_PATTERNS:
        t = pat.sub(rep, t)
    return t


@register
class AsrAnalyzer(BaseAnalyzer):
    name = 'asr'
    version = '0.1'
    needs = ('audio',)

    def analyze(self, ctx):
        pcm = ctx.get('audio_pcm')
        sr = ctx.get('audio_sr') or 16000
        dur = (len(pcm) / (sr * 2.0)) if pcm else 0.0
        if not pcm:
            return {'状态': 'no_audio', '转写文本': '', '字数': 0, '音频时长(秒)': 0,
                    '是否含人声': False, '语速(字/分)': None, '后端': None, '模型': None}
        b = _load_backend()
        if not b['fn']:
            return {'状态': 'no_backend', '转写文本': '', '字数': 0,
                    '音频时长(秒)': round(dur, 2), '是否含人声': None,
                    '语速(字/分)': None, '后端': None, '模型': None,
                    '说明': '未安装 ASR 后端（faster-whisper / funasr），仅完成取音轨'}
        try:
            raw, lang = b['fn'](pcm, sr)
        except Exception as e:
            return {'状态': 'asr_error', '转写文本': '', '字数': 0,
                    '音频时长(秒)': round(dur, 2), '是否含人声': None,
                    '语速(字/分)': None, '后端': b['name'], '模型': b['model'],
                    '说明': str(e)[:120]}
        text = mask_text((raw or '').strip())
        n = len(re.sub(r'\s+', '', text))
        return {
            '状态': 'ok' if text else 'empty',
            '转写文本': text,
            '字数': n,
            '音频时长(秒)': round(dur, 2),
            '是否含人声': bool(n),
            '语速(字/分)': round(n / (dur / 60.0), 1) if dur > 0 else None,
            '后端': b['name'], '模型': b['model'], '语言': lang,
        }
