# -*- coding: utf-8 -*-
"""作品内短视频智能分析 —— 视觉/文本模型客户端。

设计要点：
1. **不改** service/xinghuo_llm/llm_service.py；本模块自带调用，复用同一套 .env 变量。
2. 视觉：VISION_BASE_URL / VISION_API_KEY / VISION_MODEL（实测 agnes-2.5-flash 为推理模型，
   正文 token 会被 reasoning 吃掉，故 max_tokens 必须给足）。
3. 文本：优先星火（XINGHUO_*，作品自有模型），JSON 解析失败时回退 Agnes 文本模型。
4. 全程只用"拼图 + 文本特征"，不产生任何视频文件（红线①）。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

# 显式路径：stdin/脚本执行下 find_dotenv() 会 AssertionError
_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), '.env')
load_dotenv(_ENV if os.path.exists(_ENV) else '.env')

# 推理模型需要给足 token：实测 reasoning≈1000 + 正文≈120；
# 文本步骤的提示词更长、推理链更长，给少了会"全被 reasoning 吃掉 → 正文为空"。
VISION_MAX_TOKENS = int(os.getenv('INSIGHT_VLM_MAX_TOKENS', '2500'))
TEXT_MAX_TOKENS = int(os.getenv('INSIGHT_TEXT_MAX_TOKENS', '6000'))


# ------------------------------------------------------------------ 脱敏
_PII_PATTERNS = [
    (re.compile(r'1[3-9]\d{9}'), '[手机号]'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), '[邮箱]'),
    (re.compile(r'@[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}'), '[昵称]'),
    (re.compile(r'\d{17}[\dXx]'), '[身份证]'),
]


def mask_pii(text: str) -> str:
    """送模型前脱敏（标题/内容在采集端已脱敏过一次，这里再兜一层）。"""
    if not text:
        return ''
    for pat, rep in _PII_PATTERNS:
        text = pat.sub(rep, text)
    return text


# ------------------------------------------------------------------ JSON 提取
def _extract_json(text: str):
    """从模型输出里抠出第一个完整 JSON 对象（容忍 ```json 围栏与前后废话）。"""
    if not text:
        return None
    s = text.strip()
    s = re.sub(r'^```(?:json)?', '', s).strip()
    s = re.sub(r'```$', '', s).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    # 括号配平扫描
    start = s.find('{')
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except Exception:
                    return None
    return None


# ------------------------------------------------------------------ 视觉
def vision_read_image(image_path: str, prompt: str, retries: int = 2) -> dict:
    """把一张拼图交给视觉模型，返回 {'ok','raw','data','error','model','elapsed'}。"""
    out = {'ok': False, 'raw': '', 'data': None,
           'error': '', 'model': '', 'elapsed': 0.0}
    model = os.getenv('VISION_MODEL', '') or os.getenv('XINGHUO_VISION_MODEL', '')
    base = os.getenv('VISION_BASE_URL', '')
    key = os.getenv('VISION_API_KEY', '')
    out['model'] = model
    if not (model and key):
        out['error'] = 'VISION_MODEL/VISION_API_KEY 未配置'
        return out
    if not os.path.exists(image_path):
        out['error'] = '拼图不存在: %s' % image_path
        return out

    b64 = base64.b64encode(open(image_path, 'rb').read()).decode()
    mime = mimetypes.guess_type(image_path)[0] or 'image/jpeg'
    client = OpenAI(api_key=key, base_url=base or None)
    last = ''
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            r = client.chat.completions.create(
                model=model, max_tokens=VISION_MAX_TOKENS, temperature=0.2,
                messages=[{'role': 'user', 'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url',
                     'image_url': {'url': 'data:%s;base64,%s' % (mime, b64)}}]}])
            out['elapsed'] = round(time.time() - t0, 1)
            raw = (r.choices[0].message.content or '').strip()
            out['raw'] = raw
            data = _extract_json(raw)
            if data:
                out['ok'], out['data'] = True, data
                return out
            last = '返回非 JSON（前 120 字）：%s' % raw[:120] if raw else '返回空'
        except Exception as e:            # noqa: BLE001
            out['elapsed'] = round(time.time() - t0, 1)
            last = '%s: %s' % (type(e).__name__, str(e)[:160])
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    out['error'] = last or '未知失败'
    return out


# ------------------------------------------------------------------ 文本
def _text_call(model: str, base: str, key: str, prompt: str, system: str = None):
    client = OpenAI(api_key=key, base_url=base or None)
    msgs = []
    if system:
        msgs.append({'role': 'system', 'content': system})
    msgs.append({'role': 'user', 'content': prompt})
    r = client.chat.completions.create(model=model, messages=msgs,
                                      max_tokens=TEXT_MAX_TOKENS, temperature=0.3)
    return (r.choices[0].message.content or '').strip()


def _is_placeholder(data) -> bool:
    """检测模型把提示词里的占位符（尖括号内容）原样抄回 —— 这类输出视为无效。

    实测：XINGHUO_MODEL=lite 会把 "<结合互动数据的具体说明>"、"<0.55>" 直接抄进答案，
    导致 ④⑤⑦ 等字段成为无意义占位文字。此处拦下并要求换后端重试。
    """
    if not isinstance(data, dict):
        return False
    stack = [data]
    pat = re.compile(r'<[^<>\n]{1,60}>')
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)
        elif isinstance(cur, str):
            if pat.search(cur):
                return True
    return False


def text_reason(prompt: str, system: str = None) -> dict:
    """文本推理。

    实测结论：`XINGHUO_MODEL=lite` 会把提示词里的占位文字原样抄回、枚举字段不单选，
    不足以支撑结构化分析；故**默认优先用推理能力更强的文本模型**（与视觉同端点），
    失败或非 JSON 时再回退星火。可用 INSIGHT_TEXT_PRIMARY=agnes|spark 切换。

    返回 {'ok','raw','data','error','backend','tried'}
    """
    result = {'ok': False, 'raw': '', 'data': None,
              'error': '', 'backend': '', 'tried': []}

    vb, vk = os.getenv('VISION_BASE_URL', ''), os.getenv('VISION_API_KEY', '')
    fm = os.getenv('INSIGHT_TEXT_MODEL', 'agnes-2.5-flash')
    xb, xk = os.getenv('XINGHUO_BASE_URL', ''), os.getenv('XINGHUO_API_PASSWORD', '')
    xm = os.getenv('XINGHUO_MODEL', 'lite')

    order = []
    if (os.getenv('INSIGHT_TEXT_PRIMARY', 'agnes') or 'agnes').lower() == 'spark':
        order = [('星火/%s' % xm, xm, xb, xk), ('回退/%s' % fm, fm, vb, vk)]
    else:
        # 强模型优先；允许主模型重试一次再降级（星火 lite 会抄占位符，故尽量不用）
        order = [('%s' % fm, fm, vb, vk), ('重试/%s' % fm, fm, vb, vk),
                 ('回退星火/%s' % xm, xm, xb, xk)]

    for label, model, base, key in order:
        if not key:
            result['tried'].append('%s: 未配置' % label)
            continue
        try:
            raw = _text_call(model, base, key, prompt, system)
            data = _extract_json(raw)
            okj = bool(data) and not _is_placeholder(data)
            result['tried'].append('%s: %d字 json=%s%s'
                                   % (label, len(raw), 'ok' if data else 'no',
                                      '(含占位符,弃用)' if (data and not okj) else ''))
            if okj:
                result.update(ok=True, raw=raw, data=data, backend=label)
                return result
            result['error'] = ('%s 返回%s' % (label, '含占位符' if data else '非 JSON'))
        except Exception as e:            # noqa: BLE001
            result['tried'].append('%s: %s' % (label, type(e).__name__))
            result['error'] = '%s 调用失败: %s' % (label, str(e)[:140])
    return result
