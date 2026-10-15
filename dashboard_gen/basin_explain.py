# -*- coding: utf-8 -*-
"""排行榜逐条解释 + 诊断图（2026-10-06 新增，批次 4）。

本模块只做三件事，**不改任何渲染逻辑**：
1. `explain_for()`  —— 把解释文案挂到 LIST() 的 explain 参数
2. `figs_for()`     —— 把诊断图数据算好挂到 LIST() 的 figs 参数
3. `attach()`       —— 视图构建末尾统一调用，给已建好的 list 卡补挂

为什么把图表"算好再传"，而不是在前端现算：
- 比值（评赞比 / 转赞比）数据里没有，是本功能的核心信息，必须后端算才可靠
- 列语义在不同卡里不同（高互动 m1=赞，高扩散 m1=转），前端要猜很容易错
  —— 这里在 Python 侧一次判清，见 _cols()
"""
import math

TOPIC_C = {'医患矛盾': '#b4544f', '文旅': '#c9860a', '生态治理': '#3f8f63'}
PLAT_C = {'微博': '#1f6ee0', '小红书': '#b4544f', '知乎': '#4a7fa8', '抖音': '#2b2118'}

_EXPL = {}          # {(视图id, 卡标题): {下标: (what, sig, read)}}


def register_expl(view_id, title, mapping):
    """登记解释文案。mapping: {下标: (what, sig, read)}"""
    _EXPL[(view_id, title)] = mapping


# ------------------------------------------------------------------ 列语义
def _cols(rows):
    """按**标签文本**逐列判断语义，不按列序假设。

    ⚠ 高互动卡 m1=赞/m2=评/m3=转；高扩散卡 m1=转/m2=赞、m3=是议题。
    早前按固定列序取 m3 当转发，结果拿到字符串、图表全部静默消失。
    返回 {'like':字段键, 'cmt':…, 'fwd':…, 'topic':…, 'plat':…, 'time':…}"""
    if not rows:
        return {}
    s = rows[0]
    out = {}
    for k in ('m1', 'm2', 'm3'):
        v = str(s.get(k, ''))
        if v in ('—', '', 'None'):
            continue
        for u, sem in (('分享', 'fwd'), ('赞', 'like'), ('评', 'cmt'), ('转', 'fwd')):
            if v.startswith(u):
                if sem not in out:      # 同语义首列优先（高扩散 m1=转 胜 m2=赞）
                    out[sem] = k
                break
    out['plat'] = 'm4' if str(s.get('m4')) in PLAT_C else None
    out['topic'] = 'm5' if out['plat'] else 'm4'
    # 时间列逐个试"值前 4 位是数字"的（日期是 '2024-10-11'，10 位不是 4 位）
    out['time'] = None
    for k in ('m6', 'm5'):
        if out['topic'] == k:
            continue
        v = str(s.get(k, ''))
        if len(v) >= 4 and v[:4].isdigit():
            out['time'] = k
            break
    return out


def _num(x):
    """从 '赞 32,236' / '转 4,321' / '分享 441' / '—' 里取整数，取不到返回 None。"""
    t = str(x).replace(',', '').strip()
    for u in ('分享', '赞', '评', '转', '—'):
        t = t.replace(u, '')
    try:
        return int(t)
    except ValueError:
        return None


# ------------------------------------------------------------------ 诊断图
def _fig_scatter(rows, cc):
    """图A 互动结构散点：评赞比 × 转赞比（双对数轴）。"""
    kl, kc, kf = cc.get('like'), cc.get('cmt'), cc.get('fwd')
    if not (kl and kf):
        return None
    pts = []
    for r in rows:
        lk, fw = _num(r.get(kl)), _num(r.get(kf))
        cm = _num(r.get(kc)) if kc else 0
        if not lk or lk <= 0:
            continue
        pts.append({'x': round(fw / lk * 100, 2) if fw else 0,
                    'y': round(cm / lk * 100, 2) if cm else 0,
                    'name': str(r.get('txt', ''))[:18],
                    'tip': '转赞比 %.1f%%' % (fw / lk * 100 if fw else 0)
                           + (('　评赞比 %.1f%%' % (cm / lk * 100)) if cm else ''),
                    'color': TOPIC_C.get(str(r.get(cc['topic'])), '#8a93a3'),
                    'size': 9 if (fw / lk < 2) else 13})
    if not pts:
        return None
    tp = []
    for r in rows:
        t = str(r.get(cc['topic']))
        if t and t not in tp:
            tp.append(t)
    return {'type': 'scatter',
            'title': '图A　互动结构散点',
            'sub': '纵轴＝评赞比，横轴＝转赞比（均为百分比，刻度按量级取对数分布）'
                   '　·　点越靠上＝越被讨论，越靠右＝越被传播',
            'xn': '转赞比 %', 'yn': '评赞比 %', 'd': pts,
            'legend': [{'label': t, 'color': TOPIC_C.get(t, '#8a93a3')} for t in tp],
            'note': '虚线为两轴中位数，把图分四象限：<b>右上＝讨论与传播都强</b>；'
                    '<b>左上＝被讨论但不被传播</b>（争议型）；'
                    '<b>右下＝被传播但不引发讨论</b>（动员型）。'
                    '偏离主群的那些点就是最需要读法说明的条目。'}


def _fig_hbar_ratio(rows, cc):
    """高扩散卡降级图：无「评」列，评赞比恒 0 → 散点会贴底成直线（无意义）。
    改画单轴：逐条转赞比横条。"""
    kl, kf = cc.get('like'), cc.get('fwd')
    if not (kl and kf):
        return None
    d, hi = [], 0
    for r in rows:
        lk, fw = _num(r.get(kl)), _num(r.get(kf))
        if not lk:
            continue
        tr = round(fw / lk * 100, 1) if fw else 0
        if tr > 100:
            hi += 1
        d.append({'name': str(r.get('txt', ''))[:14] or '（无正文）',
                  'value': tr,
                  'itemStyle': {'color': TOPIC_C.get(str(r.get(cc['topic'])), '#8a93a3')}})
    if not d:
        return None
    d.sort(key=lambda z: -z['value'])
    return {'type': 'hbar', 'title': '图A　转赞比排序',
            'sub': '本卡原始表<b>没有「评论」列</b>，故不出评赞比 × 转赞比散点，'
                   '改用单轴：逐条转赞比（转发 ÷ 点赞）',
            'd': d, 'p': 0,
            'note': ('<b style="color:var(--red)">%d 条超过 100%%</b>，'
                     '即转发数多于点赞数 —— 这是本表最需要读法说明的现象，'
                     '详见对应条目的「读法」。' % hi) if hi
                    else '各条分布相对均衡，无异常离群值。'}


def _fig_topic(rows, cc):
    """图B 议题构成 × 传播强度。"""
    kt = cc.get('topic')
    kl, kc, kf = cc.get('like'), cc.get('cmt'), cc.get('fwd')
    if not (kt and (kl or kc or kf)):
        return None
    agg, order = {}, []
    for r in rows:
        t = str(r.get(kt) or '未分类')
        if t not in agg:
            agg[t] = {'l': 0, 'c': 0, 'f': 0, 'n': 0}
            order.append(t)
        a = agg[t]
        a['l'] += _num(r.get(kl)) or 0 if kl else 0
        a['c'] += _num(r.get(kc)) or 0 if kc else 0
        a['f'] += _num(r.get(kf)) or 0 if kf else 0
        a['n'] += 1
    d = [{'name': '%s（%d 条）' % (t, agg[t]['n']),
          'value': agg[t]['l'] + agg[t]['c'] + agg[t]['f'],
          'itemStyle': {'color': TOPIC_C.get(t, '#8a93a3')}} for t in order]
    d.sort(key=lambda z: -z['value'])
    return {'type': 'hbar', 'title': '图B　议题构成 × 传播强度',
            'sub': '条长＝该议题下所有条目的赞+评+转合计　·　'
                   '右端括号内＝该议题的条目数',
            'd': d, 'p': 0,
            'note': '这张图回答"<b>哪个议题在驱动本榜</b>"。'
                    '两流域的答案完全不同（长江医患主导、黄河文旅主导），'
                    '只看排行榜结构是看不出来的。'}


def _fig_year(rows, cc):
    """图C 条目发布年份分布 —— 支撑"榜单是历史累积而非当下热度"。"""
    kt = cc.get('time')
    if not kt:
        return None
    agg, order = {}, []
    for r in rows:
        y = str(r.get(kt) or '')[:4]
        if not (len(y) == 4 and y.isdigit()):
            continue
        if y not in agg:
            agg[y] = 0
            order.append(y)
        agg[y] += 1
    if not agg:
        return None
    order.sort()
    d = [{'name': y, 'value': agg[y], 'itemStyle': {'color': '#7c5ea8'}} for y in order]
    old = sum(v for y, v in agg.items() if y < '2025')
    tot = sum(agg.values())
    return {'type': 'hbar', 'title': '图C　条目发布年份分布',
            'sub': '支撑一条读法：榜单<b>不是当下热度</b>，'
                   '而是历史高互动内容的累积',
            'd': d, 'p': 0,
            'note': '%d 条中 <b>%d 条</b>发布于 2025 年之前。'
                    '它们的互动量在采集时被计入，但<b>不代表该议题现在仍然如此</b>'
                    ' —— 引用时必须带上年份。' % (tot, old)}


def _fig_plat(rows, cc):
    """图D 平台构成（仅跨平台卡）。"""
    kp = cc.get('plat')
    kl, kc = cc.get('like'), cc.get('cmt')
    if not (kp and kl):
        return None
    agg, order = {}, []
    for r in rows:
        p = str(r.get(kp) or '未标注')
        if p not in agg:
            agg[p] = {'l': 0, 'c': 0, 'n': 0}
            order.append(p)
        a = agg[p]
        a['l'] += _num(r.get(kl)) or 0
        a['c'] += _num(r.get(kc)) or 0 if kc else 0
        a['n'] += 1
    d = []
    for p in order:
        a = agg[p]
        cr = a['c'] / a['l'] * 100 if a['l'] else 0
        d.append({'name': '%s（%d 条）' % (p, a['n']),
                  'value': a['n'],
                  'itemStyle': {'color': PLAT_C.get(p, '#8a93a3')}})
        d[-1]['cr'] = cr
    d.sort(key=lambda z: -z['value'])
    avg = sum(x['cr'] for x in d) / len(d) if d else 0
    return {'type': 'hbar', 'title': '图D　平台构成与评赞比',
            'sub': '条长＝该平台进榜的条目数（不是点赞数）　·　'
                   '本平台平均评赞比 %.1f%%' % avg,
            'd': d, 'p': 0,
            'note': '⚠ <b>各平台的赞数机制不同源</b>，条长只反映'
                    '"进了榜的条目数"，不代表热度。'
                    '卡片副标题的"只比结构、不对齐绝对值"正指此。'}


def figs_for(card):
    """给一张 list 卡算诊断图。数据不足就少出图，绝不硬造。"""
    rows = card.get('d') or []
    cc = _cols(rows)
    if not cc:
        return None
    out = []
    sc = _fig_scatter(rows, cc) if cc.get('cmt') else _fig_hbar_ratio(rows, cc)
    if sc:
        out.append(sc)
    for fn in (_fig_topic, _fig_year, _fig_plat):
        f = fn(rows, cc)
        if f:
            out.append(f)
    return out or None


# ------------------------------------------------------------------ 挂载
def explain_for(view_id, card):
    m = _EXPL.get((view_id, card.get('t')))
    if not m:
        return None
    return {i: {'what': w, 'sig': s, 'read': r}
            for i, (w, s, r) in m.items()}


def attach(views, get_id):
    """给 views 里每张 list 卡补挂 explain 与 figs。

    get_id(view) -> view id。用法：在 build_unified_page 组装 VIEWS 之后调用一次。

    ⚠ 只处理 _EXPL 里登记过的卡。早期版本对**所有** list 卡都跑 figs_for()，
    结果另外 4 处（高赞评论 / 簇代表评论 / 高扩散 / 事件代表原文）也被挂了图——
    它们不在本次需求范围内，擅自加东西等于改动扩散。
    「登记表里没有的卡，连 figs 都不给」是本功能的边界纪律。"""
    n_ex = n_fig = 0
    for v in views:
        vid = get_id(v)
        for c in (v.get('cards') or []):
            if c.get('kind') != 'list':
                continue
            if (vid, c.get('t')) not in _EXPL:      # 未登记 → 一律不动
                continue
            e = explain_for(vid, c)
            if e:
                c['explain'] = e
                n_ex += len(e)
            f = figs_for(c)
            if f:
                c['figs'] = f
                n_fig += len(f)
    return {'explain': n_ex, 'figs': n_fig}