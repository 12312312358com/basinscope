# -*- coding: utf-8 -*-
"""作品内短视频智能分析 —— 编排器（步 1：先出 10 条完整结果供评估）。

流程（每条视频）：
  ① 读 L2 证据（拼图路径 / 关键帧统计 / 互动 / 评论）
  ② 拼图 → 视觉模型（读画面：主体/场景/画面文字/视觉主题/议题倾向）
  ③ 汇总 [E1]~[E6] 证据 → 文本模型（六维分析 + 3~5 条候选结论 + 建议）
  ④ 服务端算「推荐度」→ 取 top-1 作为推荐结论（防幻觉：evidence 必须命中给定编号）
  ⑤ 落库（JSON / Markdown / 缓存）

用法：
    # 默认 10 条（长江 5 + 黄河 5，议题均衡），出完整结果供评估
    python service/video/insight/build_insight.py

    # 指定条数与输出
    python service/video/insight/build_insight.py --limit 10 --md video_features/insight_preview.md

    # 跳过视觉（离线演练链路，只跑文本）
    python service/video/insight/build_insight.py --limit 3 --no-vlm
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_VDIR = os.path.dirname(_HERE)
_PRJ = os.path.dirname(os.path.dirname(_VDIR))
sys.path.insert(0, _VDIR)

from db import get_engine            # noqa: E402  (service/video/db.py)
from sqlalchemy import text          # noqa: E402

from clients import mask_pii, vision_read_image, text_reason    # noqa: E402
from prompts import (PROMPT_VERSION, VLM_SYSTEM, VLM_PROMPT,    # noqa: E402
                     TEXT_SYSTEM, TEXT_PROMPT_TMPL)

L2_PATH = os.path.join(_PRJ, 'video_features', 'l2_features.jsonl')
L3_PATH = os.path.join(_PRJ, 'video_features', 'l3_features.jsonl')
FRAMES = os.path.join(_PRJ, 'video_features', 'frames')
CACHE = os.path.join(_PRJ, 'video_features', '_insight_cache.jsonl')
# 正式产物（供作品页面消费）；评估用的 preview 用 --json/--md 覆盖
OUT_JSON = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.json')
OUT_MD = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.md')

# 证据类别（用于"证据充分度"打分）
EV_CAT = {'E1': '画面', 'E2': '文本', 'E3': '来源', 'E4': '传播', 'E5': '评论',
          'E6': '视觉', 'E7': '口播'}


# ---------------------------------------------------------------- 读数据
def load_l2():
    if not os.path.exists(L2_PATH):
        raise SystemExit('缺少 L2 特征库：%s' % L2_PATH)
    recs = [json.loads(l) for l in io.open(L2_PATH, encoding='utf-8') if l.strip()]
    return [r for r in recs if r.get('frames_sheet')]


def load_l3():
    """L3 语音转写索引（可选）：{content_id: {转写文本, 音频时长, 字数, 后端}}。"""
    out = {}
    if not os.path.exists(L3_PATH):
        return out
    for line in io.open(L3_PATH, encoding='utf-8'):
        if not line.strip():
            continue
        r = json.loads(line)
        kv = ((r.get('features') or {}).get('asr') or {}).get('kv') or {}
        out[str(r.get('content_id'))] = {
            '转写文本': kv.get('转写文本') or '',
            '音频时长': kv.get('音频时长(秒)'),
            '字数': kv.get('字数'),
            '后端': kv.get('后端'),
        }
    return out


def load_articles(ids):
    """从 t_bettafish_article 取文本元信息（标题/内容/作者/时间/链接）。"""
    out = {}
    if not ids:
        return out
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT `内容ID`,`标题`,`内容`,`作者昵称`,`发布时间`,`内容链接`,`命中关键词` "
            "FROM `t_bettafish_article` WHERE `内容ID` IN (%s)"
            % ','.join("'%s'" % i for i in ids))).mappings().all()
    for r in rows:
        out[str(r['内容ID'])] = dict(r)
    return out


def _num(v):
    try:
        return int(v)
    except Exception:
        return 0


# ---------------------------------------------------------------- 选样本
def pick(recs, limit=10):
    """双流域 × 双议题均衡挑样本（各流域内按互动总量降序）。"""
    if limit <= 0:
        return recs
    plan = [('长江', '生态治理', 3), ('长江', '文旅', 2),
            ('黄河', '生态治理', 2), ('黄河', '文旅', 3)]
    chosen, used = [], set()
    for basin, topic, want in plan:
        pool = [r for r in recs
                if (r.get('basin') or '') == basin and (r.get('topic') or '') == topic
                and r['content_id'] not in used]
        pool.sort(key=lambda r: -_num((r.get('l1_meta') or {}).get('互动总量')))
        for r in pool[:want]:
            chosen.append(r)
            used.add(r['content_id'])
    # 不足则按互动量补齐
    if len(chosen) < limit:
        rest = [r for r in recs if r['content_id'] not in used]
        rest.sort(key=lambda r: -_num((r.get('l1_meta') or {}).get('互动总量')))
        chosen += rest[:limit - len(chosen)]
    return chosen[:limit]


# ---------------------------------------------------------------- 证据块
def build_evidence(rec, art, vlm, asr=None):
    """产出 [E1]~[E7] 文本块 + 结构化证据 id 集合。"""
    kv = ((rec.get('features') or {}).get('keyframe') or {}).get('kv') or {}
    lm = rec.get('l1_meta') or {}
    lc = rec.get('l1_comment') or {}
    senti = lc.get('情感分布') or {}
    demand = lc.get('诉求分布') or {}

    e = {}
    if vlm:
        txt = vlm.get('画面文字') or ''
        if isinstance(txt, (list, tuple)):
            txt = '、'.join(str(x) for x in txt)
        e['E1'] = ('画面读数（视觉模型对关键帧拼图的识别）：\n'
                   '    主体：%s\n    场景：%s\n    画面文字：%s\n    视觉主题：%s\n'
                   '    议题倾向：%s（置信 %s）' % (
                       vlm.get('主体', ''), vlm.get('场景', ''),
                       txt or '（无）',
                       vlm.get('视觉主题', ''), vlm.get('议题倾向', ''),
                       vlm.get('置信', '')))
    else:
        e['E1'] = '画面读数：未取得（视觉模型未启用或调用失败）'
    e['E2'] = '标题与正文（已脱敏）：%s' % mask_pii((art or {}).get('标题') or '（无）')
    e['E3'] = '来源：作者 %s｜发布 %s｜平台 %s' % (
        (art or {}).get('作者昵称') or '未知',
        str((art or {}).get('发布时间') or '未知')[:19],
        rec.get('platform') or '')
    e['E4'] = ('互动结构：互动总量 %s｜点赞 %s｜评论 %s｜转发 %s｜收藏 %s｜'
               '转发/点赞 %.2f｜评论/点赞 %.2f' % (
                   lm.get('互动总量'), lm.get('点赞数'), lm.get('评论数'),
                   lm.get('转发数'), lm.get('收藏数'),
                   lm.get('转发_点赞比') or 0, lm.get('评论_点赞比') or 0))
    e['E5'] = ('评论洞察：评论数 %s｜情感 正面%s/中性%s/负面%s｜负面占比 %s｜'
               '诉求 %s｜过闸门 %s｜声明：%s' % (
                   lc.get('评论数'), senti.get('正面', 0), senti.get('中性', 0),
                   senti.get('负面', 0), lc.get('负面占比'), demand or '无',
                   '是' if lc.get('样本过闸门') else '否（仅作现象提示）',
                   lc.get('外推声明') or '无'))
    e['E6'] = ('客观视觉指标：时长 %ss｜分辨率 %s｜主色调 %s｜均值亮度 %s｜'
               '色彩丰富度 %s｜关键帧 %s 帧' % (
                   kv.get('时长(秒)'), kv.get('分辨率'), kv.get('主色调'),
                   kv.get('均值亮度'), kv.get('均值色彩丰富度'), kv.get('frames_count')))

    # E7 口播文案（L3/ASR）—— 主题与核心信息最直接的证据；可能只覆盖开头
    txt = (asr or {}).get('转写文本') or ''
    if txt:
        dur, aud = kv.get('时长(秒)'), (asr or {}).get('音频时长')
        cover = ''
        try:
            if dur and aud and float(aud) + 1 < float(dur):
                cover = '（注意：仅覆盖前 %ss / 全长 %ss，不代表整条视频）' % (aud, dur)
        except Exception:
            cover = ''
        e['E7'] = ('口播原文转写（ASR，已脱敏）%s：%s' % (cover, txt))
    else:
        e['E7'] = '口播原文转写：未取得（该内容无音轨 / 未转写）'

    block = '\n'.join('[%s] 类别=%s ｜ %s' % (k, EV_CAT.get(k, '?'), v)
                      for k, v in e.items())
    return block, e


# ---------------------------------------------------------------- 打分
def _visual_conflict(vlm_text, kv):
    """轻量一致性规则：画面描述与客观指标矛盾 → 返回冲突说明，否则 None。"""
    try:
        b = float(kv.get('均值亮度'))
    except Exception:
        return None
    t = vlm_text or ''
    if b < 60 and ('明亮' in t or '清晰明亮' in t):
        return '画面描述称"明亮"，但均值亮度仅 %.0f' % b
    if b > 150 and ('昏暗' in t or '偏暗' in t):
        return '画面描述称"昏暗/偏暗"，但均值亮度达 %.0f' % b
    return None


CAT4 = ('画面', '文本', '传播', '评论', '视觉', '口播')

# 枚举型字段：个别弱模型会把占位尖括号或多选项原样抄回，这里统一收口
_ENUM_KEYS = (('主题', '议题倾向'), ('传播', '类型'),
              ('客观视觉', '画幅'), ('情感诉求', '情感'))


def _clean_enum(v):
    if not isinstance(v, str):
        return v
    v = v.strip()
    for ch in ('<', '>', '＜', '＞', '《', '》', '"', "'", '`'):
        v = v.replace(ch, '')
    v = v.strip()
    for sep in ('/', ' 或 ', '或'):
        if sep in v:
            v = v.split(sep)[0].strip()
    return v


def normalize_analysis(data):
    """就地清洗枚举字段，返回清洗后的 dict。"""
    if not isinstance(data, dict):
        return data
    for parent, child in _ENUM_KEYS:
        node = data.get(parent)
        if isinstance(node, dict) and child in node:
            node[child] = _clean_enum(node[child])
    return data


def score_conclusions(data, ev_ids, vlm, kv):
    """服务端计算推荐度并排序；返回 (结论列表, 一致性说明)。"""
    conflict = _visual_conflict(
        '%s %s %s' % ((vlm or {}).get('主体', ''), (vlm or {}).get('场景', ''),
                      (vlm or {}).get('视觉主题', '')), kv)
    conf_flag = (data.get('一致性') or '一致')
    consistency = 0.4 if conflict else (1.0 if '一致' in conf_flag else 0.6)

    out = []
    for c in (data.get('结论') or []):
        if not isinstance(c, dict):
            continue
        refs = [str(x).strip().upper() for x in (c.get('evidence') or [])]
        valid = [r for r in refs if r in ev_ids]
        cats = {ev_ids[r] for r in valid}
        ev_score = min(len(cats & set(CAT4)), 4) / 4.0
        try:
            conf = float(c.get('confidence') or 0)
        except Exception:
            conf = 0.0
        try:
            act = float(c.get('actionability') or 0)
        except Exception:
            act = 0.0
        conf = min(max(conf, 0.0), 1.0)
        act = min(max(act, 0.0), 1.0)
        score = 0.40 * conf + 0.25 * act + 0.20 * ev_score + 0.15 * consistency
        # 防幻觉：无有效证据 → 降权 50%
        if not valid:
            score *= 0.5
        out.append({
            'claim': c.get('claim') or '',
            'evidence': valid or refs,
            'evidence_all_valid': bool(valid) and len(valid) == len(refs),
            'evidence_cats': sorted(cats),
            'confidence': round(conf, 2),
            'actionability': round(act, 2),
            'recommend': round(score, 3),
        })
    out.sort(key=lambda x: -x['recommend'])
    return out, consistency, conflict


# ---------------------------------------------------------------- 单条
def analyze_one(rec, art, use_vlm=True, offline_text=False, asr=None):
    cid = rec['content_id']
    kv = ((rec.get('features') or {}).get('keyframe') or {}).get('kv') or {}
    sheet = os.path.join(_PRJ, 'video_features', rec.get('frames_sheet') or '')

    res = {'content_id': cid, 'basin': rec.get('basin'), 'topic': rec.get('topic'),
           'platform': rec.get('platform'),
           'title': ((art or {}).get('标题') or '')[:120],
           'link': (art or {}).get('内容链接') or '', 'prompt_version': PROMPT_VERSION,
           'vlm': None, 'vlm_status': 'skipped', 'analysis': None,
           'backend': '', 'conclusions': [], 'consistency': None, 'conflict': None}

    # ① 视觉
    if use_vlm:
        t0 = time.time()
        v = vision_read_image(sheet, VLM_PROMPT)
        res['vlm_status'] = 'ok' if v['ok'] else 'failed'
        res['vlm_error'] = v['error'] or ''
        res['vlm_elapsed'] = v['elapsed']
        res['vlm'] = v['data'] if v['ok'] else None
        res['cache_raw_vlm'] = v['raw']
    else:
        res['vlm_error'] = '未启用'
        res['cache_raw_vlm'] = ''

    # ② 文本
    block, ev = build_evidence(rec, art, res['vlm'], asr)
    prompt = TEXT_PROMPT_TMPL.format(evidence_block=block)
    if offline_text:
        t = {'ok': False, 'error': 'offline', 'backend': '', 'tried': [],
             'raw': '', 'data': None}
    else:
        t = text_reason(prompt, TEXT_SYSTEM)
    res['backend'] = t.get('backend') or ''
    res['text_error'] = t.get('error') or ''
    res['cache_raw_text'] = t.get('raw', '')
    res['evidence_block'] = block
    res['analysis'] = normalize_analysis(t.get('data'))
    if not t.get('ok') and not offline_text:
        # 未拿到 JSON（推理 token 被截空 / 瞬时失败）→ 再试一次
        t = text_reason(prompt, TEXT_SYSTEM)
        res['backend'] = t.get('backend') or ''
        res['text_error'] = t.get('error') or ''
        res['cache_raw_text'] = t.get('raw', '')
        res['analysis'] = normalize_analysis(t.get('data'))
    if t.get('ok'):
        cons, consistency, conflict = score_conclusions(t['data'], EV_CAT, res['vlm'], kv)
        # 结论过少（模型偷懒）→ 追加一次"补足"重试
        if len(cons) < 2 and not offline_text:
            p2 = prompt + ('\n\n【上次输出的"结论"少于 3 条。请补足为 3~5 条，'
                           '每条至少引用 2 个不同类别的证据，并保持 JSON 结构完整。】')
            t2 = text_reason(p2, TEXT_SYSTEM)
            if t2.get('ok'):
                c2, _cs2, cf2 = score_conclusions(t2['data'], EV_CAT, res['vlm'], kv)
                if len(c2) > len(cons):
                    res['analysis'] = normalize_analysis(t2['data'])
                    res['cache_raw_text'] = t2.get('raw', '')
                    res['backend'] = (res['backend'] or '') + ' +补足重试'
                    cons, conflict = c2, (cf2 or conflict)
        res['conclusions'] = cons
        res['consistency'] = consistency
        if conflict:
            res['conflict'] = conflict
    return res


# ---------------------------------------------------------------- 渲染
def render_md(results, meta):
    L = []
    L.append('# 短视频智能分析 · 10 条完整结果（评估版）\n')
    L.append('> 样本：L2 关键帧层有画面的视频（8% 非随机抽样，**仅抖音**）。'
             '画面读数由视觉模型对关键帧拼图识别；结论由大模型生成并按「推荐度」排序，仅供辅助参考。')
    L.append('> 提示词版本：`%s`｜本批条数：**%d**\n' % (meta['prompt_version'], len(results)))
    L.append('---\n')
    for i, r in enumerate(results, 1):
        a = r.get('analysis') or {}
        th = a.get('主题') or {}
        pr = a.get('传播') or {}
        se = a.get('情感诉求') or {}
        vi = a.get('客观视觉') or {}
        v = r.get('vlm') or {}
        L.append('## 第 %d 条 · %s' % (i, (r.get('title') or '（无标题）')[:40]))
        L.append('')
        L.append('- **内容ID**：`%s`｜**流域**：%s｜**议题**：%s｜**平台**：%s'
                 % (r['content_id'], r.get('basin'), r.get('topic'), r.get('platform')))
        L.append('- **来源链接**：%s' % (r.get('link') or '（无）'))
        L.append('- **模型链路**：视觉=%s（%s）｜文本=%s' % (
            r.get('vlm_status'), r.get('vlm_elapsed'),
            r.get('backend') or ('失败：%s' % r.get('text_error'))))
        L.append('')
        L.append('### ① 画面内容（视觉模型读取）')
        if v:
            L.append('- **主体**：%s' % v.get('主体', ''))
            L.append('- **场景**：%s' % v.get('场景', ''))
            _txt = v.get('画面文字') or ''
            if isinstance(_txt, (list, tuple)):
                _txt = '；'.join(str(x) for x in _txt)
            L.append('- **画面文字**：%s' % (_txt or '（无）'))
            L.append('- **视觉主题**：%s' % v.get('视觉主题', ''))
            L.append('- **议题倾向**：%s（置信 %s）' % (v.get('议题倾向', ''), v.get('置信', '')))
        else:
            L.append('- ⚠️ 未取得画面读数（%s）' % (r.get('vlm_error') or '未启用'))
        L.append('')
        L.append('### ② 主题与核心信息')
        L.append('- **主题标签**：%s' % (th.get('标签') or '—'))
        L.append('- **议题倾向**：%s' % (th.get('议题倾向') or '—'))
        for c in (th.get('核心信息') or []):
            L.append('- 核心信息：%s' % c)
        L.append('- 置信：%s' % th.get('置信', '—'))
        L.append('')
        L.append('### ③ 传播画像')
        L.append('- **扩散类型**：%s' % (pr.get('类型') or '—'))
        L.append('- **解读**：%s' % (pr.get('解读') or '—'))
        L.append('')
        L.append('### ④ 情感与诉求')
        L.append('- **情感**：%s｜**负面占比**：%s' % (se.get('情感') or '—', se.get('负面占比') or '—'))
        L.append('- **主要诉求**：%s' % ('、'.join(se.get('主要诉求') or []) or '—'))
        L.append('- **解读**：%s' % (se.get('解读') or '—'))
        L.append('')
        L.append('### ⑤ 客观视觉指标（用于交叉校验画面描述）')
        L.append('- **画幅**：%s｜**主色调**：%s｜**亮度**：%s' % (
            vi.get('画幅') or '—', vi.get('主色调') or '—', vi.get('亮度') or '—'))
        L.append('- **解读**：%s' % (vi.get('解读') or '—'))
        if r.get('conflict'):
            L.append('- ⚠️ **一致性提示**：%s（建议人工复核）' % r['conflict'])
        L.append('')
        cs = r.get('conclusions') or []
        L.append('### ⑥ ★ 推荐结论（推荐度最高）')
        if cs:
            top = cs[0]
            L.append('**推荐度 %.3f**（置信 %.2f · 可操作性 %.2f · 证据类别 %s）'
                     % (top['recommend'], top['confidence'], top['actionability'],
                        '、'.join(top['evidence_cats']) or '无'))
            L.append('')
            L.append('> %s' % top['claim'])
            L.append('')
            L.append('**证据链**：%s' % ('、'.join('[%s]' % e for e in top['evidence']) or '无'))
            if not top['evidence_all_valid']:
                L.append('> ⚠️ 该结论的证据编号未全部命中给定证据，已按规则降权。')
            if len(cs) > 1:
                L.append('')
                L.append('**备选结论**：')
                for k, c in enumerate(cs[1:], 2):
                    L.append('- （推荐度 %.3f · 置信 %.2f）%s ｜证据：%s'
                             % (c['recommend'], c['confidence'], c['claim'],
                                '、'.join('[%s]' % e for e in c['evidence']) or '无'))
        else:
            L.append('⚠️ 未生成结论（文本模型失败：%s）' % (r.get('text_error') or '未知'))
        L.append('')
        L.append('### ⑦ 建议')
        for s in (a.get('建议') or []):
            L.append('- %s' % s)
        L.append('')
        L.append('### ⑧ 声明')
        L.append('- 样本为 L2 关键帧层 8% **非随机**抽样且**仅覆盖抖音**，单条结论不构成总体规律。')
        L.append('- 画面读数来自关键帧拼图（非原始视频）；分析由大模型生成，仅供辅助参考。')
        L.append('')
        L.append('---')
        L.append('')
    return '\n'.join(L)


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description='短视频智能分析（六维 + 推荐结论）')
    ap.add_argument('--limit', type=int, default=10, help='本批条数（0 表示全部）')
    ap.add_argument('--force', action='store_true', help='忽略已有结果，全部重跑')
    ap.add_argument('--only', default=None, help='只跑指定 内容ID（逗号分隔），并与已有结果合并')
    ap.add_argument('--renormalize', action='store_true',
                    help='不调模型：把已有 JSON 的枚举字段清洗一遍并重出报告')
    ap.add_argument('--no-vlm', action='store_true', help='跳过视觉模型（离线演练）')
    ap.add_argument('--offline-text', action='store_true', help='不调文本模型（只验证证据组装）')
    ap.add_argument('--json', default=OUT_JSON, help='结构化输出')
    ap.add_argument('--md', default=OUT_MD, help='可读报告输出')
    a = ap.parse_args()

    recs = load_l2()

    # 只做枚举清洗与重出报告（零模型调用）
    if a.renormalize:
        d0 = json.load(io.open(a.json, encoding='utf-8'))
        for it in d0.get('items', []):
            it['analysis'] = normalize_analysis(it.get('analysis'))
        io.open(a.json, 'w', encoding='utf-8').write(
            json.dumps(d0, ensure_ascii=False, indent=2))
        io.open(a.md, 'w', encoding='utf-8').write(render_md(d0['items'], d0['meta']))
        print('[insight] 已清洗 %d 条枚举字段并重出报告' % len(d0.get('items', [])))
        return

    if a.only:
        want = {x.strip() for x in a.only.split(',') if x.strip()}
        chosen = [r for r in recs if r['content_id'] in want]
    else:
        chosen = pick(recs, a.limit)

    # 断点续跑：读出已有结果，跳过已完成的 cid（长跑必备）
    prev = {}
    if os.path.exists(a.json) and not a.force:
        try:
            d0 = json.load(io.open(a.json, encoding='utf-8'))
            prev = {it['content_id']: it for it in d0.get('items', [])
                    if it.get('conclusions') and not it.get('placeholder')
                    and it.get('prompt_version') == PROMPT_VERSION}
        except Exception:
            prev = {}
    todo = [r for r in chosen if r['content_id'] not in prev]
    print('[insight] 样本池 %d 条 → 本批 %d 条（已完成跳过 %d 条）%s'
          % (len(recs), len(todo), len(prev),
             '｜指定 cid 补跑' if a.only else '｜长江/黄河 × 生态/文旅 均衡'))

    arts = load_articles([r['content_id'] for r in todo])
    l3 = load_l3()
    print('[insight] L3 转写可 join = %d 条（作为证据 E7 参与分析）' % len(l3))
    done = list(prev.values())
    new_items = []
    t0 = time.time()

    def _dump():
        """边跑边落盘：中途中断也不丢已完成的结果。原子写入（临时文件 + os.replace）。"""
        _tmp = a.json + '.tmp'
        items = sorted(done, key=lambda it: (it.get('basin') or '',
                                             it.get('topic') or '',
                                             -( (it.get('conclusions') or [{}])[0].get('recommend') or 0)))
        m = {'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
             'prompt_version': PROMPT_VERSION, 'n': len(items),
             'elapsed_sec': round(time.time() - t0, 1),
             'note': ('L2 关键帧层抽样（仅抖音）；画面读数来自关键帧拼图，非原始视频；'
                      '分析由大模型生成，仅供辅助参考；无参考文献输出。')}
        io.open(_tmp, 'w', encoding='utf-8').write(
            json.dumps({'meta': m, 'items': items}, ensure_ascii=False, indent=2))
        os.replace(_tmp, a.json)          # 原子替换：崩溃也不会留下半截/空文件
        io.open(a.md, 'w', encoding='utf-8').write(render_md(items, m))
        return m

    for i, rec in enumerate(todo, 1):
        cid = rec['content_id']
        print('  [%2d/%2d] %s %s/%s …' % (i, len(todo), cid, rec.get('basin'), rec.get('topic')),
              end='', flush=True)
        r = analyze_one(rec, arts.get(str(cid)), use_vlm=not a.no_vlm,
                        offline_text=a.offline_text, asr=l3.get(cid))
        done.append(r)
        new_items.append(r)
        print(' vlm=%s text=%s 结论=%d' % (r['vlm_status'], r['backend'] or 'x',
                                          len(r['conclusions'])), flush=True)
        _dump()          # 每完成一条即落盘

    meta = _dump() if done else {'n': 0, 'prompt_version': PROMPT_VERSION}

    # 注：产物已由 _dump() 逐条原子写入，此处不再重复写（历史上这里留过一处
    # 旧变量名 results 的冗余写入，崩溃时会先把 JSON 截成 0 字节 —— 已删除）。
    # 缓存原始响应（供复用，避免重复付费）
    with io.open(CACHE, 'a', encoding='utf-8') as f:
        for r in new_items:
            f.write(json.dumps({
                'cid': r['content_id'], 'prompt_version': PROMPT_VERSION,
                'vlm_raw': r.get('cache_raw_vlm', ''),
                'text_raw': r.get('cache_raw_text', ''),
                'ts': time.strftime('%Y-%m-%dT%H:%M:%S')}, ensure_ascii=False) + '\n')

    ok_v = sum(1 for r in done if r.get('vlm_status') == 'ok')
    ok_t = sum(1 for r in done if r.get('conclusions'))
    print('\n[insight] 完成：累计 %d 条；视觉成功 %d，结论生成 %d；本轮耗时 %.0fs'
          % (len(done), ok_v, ok_t, meta.get('elapsed_sec', 0)))
    print('[insight] 结构化：%s' % a.json)
    print('[insight] 可读报告：%s' % a.md)
    print('[insight] 缓存：%s' % CACHE)


if __name__ == '__main__':
    main()
