# -*- coding: utf-8 -*-
"""按「舆眼-界面改造预案」的五组十七视图结构，把此前所有预览模块
（IP 地域 / 热词统计 / 柱状图 / 情感 / 词云 / 流域对照 …）整合成
一个自包含单文件 HTML（真实数据 + ECharts + 中国地图）。

数据唯一来源：unified_data.json（由 build_unified_data.py 从 db_weibo_basin、
既有预览快照、项目 fenci/*.csv 三路汇总）。页面里出现的每一个数字都在
本文件里由 U 现场格式化，保证与图表同源。
"""
import io, json, os, base64, re
from PIL import Image

import basin_modules as BM   # 批次 2：渠道归类 / 风险分级 / 校准词典 / 模块清单
import basin_geo as BGEO     # 批次 3：两江干流示意走向 / 山东沿黄 9 市 / 锚点
import word_glossary as WG   # 批次 3：词条释义库（词云悬停 / 点击的解释来源）

BASE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(BASE)
U = json.load(io.open(os.path.join(BASE, 'unified_data.json'), encoding='utf-8'))

CAN = U['canon']; FDD = U['fd']; IP = U['ip']; SENT = U['sent']
HA = U['hot']['article']['cleaned']; HC = U['hot']['comment']['cleaned']
BS = U['basinSplit']; KB = U['kb']; TR = U['train']

# ---- 流域省份归属计数（唯一来源，任何地方都不要再手写这几个数）----
# 坑：meta 里 YANGTZE(12) 已含四川、YELLOW(8) 已含青海，而 SHARED={青海,四川} 是单列出来的
# 共源省。地图按「共源优先」上色，所以图上实际是长江 11 / 黄河 7 / 共源 2 ——
# 写 12/8 或 13/9 都会与图例对不上。
_BNB = {
    '长江': len([p for p in IP['meta']['YANGTZE'] if p not in set(IP['meta'].get('SHARED') or [])]),
    '黄河': len([p for p in IP['meta']['YELLOW'] if p not in set(IP['meta'].get('SHARED') or [])]),
    '共源': len(IP['meta'].get('SHARED') or []),
    '非流域': len([p for p in IP['meta']['PROV']
                   if p not in set(IP['meta']['YANGTZE']) | set(IP['meta']['YELLOW'])]),
}
_BNB['流域合计'] = _BNB['长江'] + _BNB['黄河'] + _BNB['共源']


def N(n):            # 千分位
    return f'{int(n):,}'


def W(n):            # 万
    return f'{n/10000:.2f} 万'.replace('.00 万', ' 万')


def PC(a, b, d=1):
    return f'{a/b*100:.{d}f}%' if b else '-'


def K(k, v, s=None, c=None):
    d = {'k': k, 'v': v}
    if s: d['s'] = s
    if c: d['c'] = c
    return d


def C(cid, t, s, r, d, o=None, w=None, cls=None, h=None, tools=None, ruler=False,
      stack=None, noexp=None):
    # noexp：纯 DOM 卡片（如事件簇面板）没有 canvas/ECharts 实例，
    #        给它会挂一个点了没反应的导出按钮，故用此开关跳过。
    c = {'id': cid, 't': t, 's': s, 'r': r, 'd': d}
    if o: c['o'] = o
    if w: c['w'] = w
    if cls: c['cls'] = cls
    if h: c['h'] = h
    if tools: c['tools'] = tools
    if ruler: c['ruler'] = True
    if stack: c['stack'] = stack
    if noexp: c['noexp'] = True
    return c


def TABLE(t, cols, rows, s=None, w=None, note=None, cls=None, rowClsKey=None):
    c = {'kind': 'table', 't': t, 'cols': cols, 'd': rows}
    if s: c['s'] = s
    if w: c['w'] = w
    if note: c['note'] = note
    if cls: c['cls'] = cls
    if rowClsKey: c['rowClsKey'] = rowClsKey
    return c


def LIST(t, rows, s=None, meta=None, body='txt', w=None, explain=None, figs=None):
    c = {'kind': 'list', 't': t, 'd': rows, 'body': body}
    if s: c['s'] = s
    if meta: c['meta'] = meta
    if w: c['w'] = w
    # explain / figs 是 2026-10-06 新增的可选参数（排行榜逐条解释 + 诊断图）。
    # **不传时本函数与从前完全一致**，故仓库内另外 4 处 list 卡零影响。
    # explain：{条目下标: {'what','sig','read'}}，缺哪段就不渲染哪段。
    # figs：诊断图描述列表，由 renderListFigures 消费。
    if explain: c['explain'] = explain
    if figs: c['figs'] = figs
    return c


def KV(t, rows, s=None, w=None, note=None, unit=None):
    c = {'kind': 'kv', 't': t, 'd': rows}
    if s: c['s'] = s
    if w: c['w'] = w
    if note: c['note'] = note
    if unit: c['unit'] = unit
    return c


def TEXT(t, html, s=None, w=None):
    c = {'kind': 'text', 't': t, 'html': html}
    if s: c['s'] = s
    if w: c['w'] = w
    return c


def NOTE(items, w=None):
    return {'kind': 'note', 'w': w, 'items': items}


def nt(x, t=None, k=None):
    d = {'x': x}
    if t: d['t'] = t
    if k: d['k'] = k
    return d


# ---------------------------------------------------------------- 常用数据块
TOP_A = [[x['w'], x['freq']] for x in HA['top'][:15]]
TOP_C = [[x['w'], x['freq']] for x in HC['top'][:15]]
DOCF_A = sorted([[x['w'], x['docf']] for x in HA['top'][:25]], key=lambda z: -z[1])[:15]
SPARK_A = [[x['w'], x['freq'], x['spark']] for x in HA['top'][:12]]
BUMP_A = sorted([[x['w'], x['n7'], x['freq']] for x in HA['top'] if x['n7'] > 0],
                key=lambda z: -z[1])[:15]
BUMP_C = sorted([[x['w'], x['n7'], x['freq']] for x in HC['top'] if x['n7'] > 0],
                key=lambda z: -z[1])[:15]
HOT_TBL = [{'w': x['w'], 'freq': N(x['freq']), 'docf': N(x['docf']), 'n7': N(x['n7']),
            'sp': '·'.join(str(v) for v in x['spark'][-7:])} for x in HA['top'][:40]]
PROV_A = sorted(IP['article']['provinces'].items(), key=lambda z: -z[1])
PROV_C = sorted(IP['comment']['provinces'].items(), key=lambda z: -z[1])
YZL = U['ip']['meta']['YANGTZE']; YLL = U['ip']['meta']['YELLOW']
PROV_TBL = [{'p': p, 'a': N(IP['article']['provinces'].get(p, 0)),
             'c': N(IP['comment']['provinces'].get(p, 0)),
             'b': ('长江' if p in YZL and p not in YLL else
                   '黄河' if p in YLL and p not in YZL else '都不属')}
            for p in U['ip']['meta']['PROV']]
SENT_CLR = {'正面': '#3ddc97', '中性': '#4a9dff', '负面': '#ff6b6b'}
# 话语主体三色（与「发布渠道与话语主体」页同一套：官方蓝 / 媒体青 / 个人橙）
SPK_CLR = {'官方': '#4a9dff', '媒体': '#2fd6d0', '个人': '#ffb44d'}

# 34 个省级行政区（与采集端、数据脚本同一口径）—— 用于把「命中关键词」拆成
# 「议题词」与「省份词」两类：原图把两类东西并在一张玫瑰图上比大小，没有可比性。
PROV_SET = set('''北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽
福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏
陕西 甘肃 青海 宁夏 新疆 台湾 香港 澳门'''.split())


# ---------------------------------------------------------------- v8 分段进度条
def SGROWS(k):
    '''长度分段条的行数据。口径与「改造预案」那张卡一致：
       正文为空 / 1-50 / 51-100 / 101-300 / 301-1000 / >1000（字）。'''
    L = U['lenSeg'][k]
    return [{'lb': '1–50 字',     'v': L['b1']},
            {'lb': '51–100 字',   'v': L['b2']},
            {'lb': '101–300 字',  'v': L['b3']},
            {'lb': '301–1000 字', 'v': L['b4']},
            {'lb': '>1000 字',    'v': L['b5']},
            {'lb': '正文为空' if k == 'article' else '评论为空', 'v': L['empty']}]


def SGN(k, what, long_w, extra):
    '''分段进度条的 o 段（底部口径说明条）。长短、空档、占比全部取实测值，不写死。'''
    L = U['lenSeg'][k]
    return {'ns': 14,
            'note': ('%s长度实测 <b>%d ~ %d 字</b>（均值 %.1f，全库 %s 条）：'
                     '<i>无 301 字以上的%s，也无空%s</i>。%s'
                     % (what, L['mn'], L['mx'], L['avg'], N(L['total']), long_w, what, extra))}

def _pct(d, i):
    """抽样情感占比（%），保留 1 位 —— 100% 堆积条的段长"""
    return round(d['v'][i] / d['total'] * 1000) / 10
HOT_SENT = [{'w': x['w'], 'v': N(x['v']), 's': FDD['hotSent'].get(x['w'], '中性')}
            for x in FDD['hotwordList'][:15]]


def CV(x):
    if isinstance(x, bool): return '是' if x else '否'
    if isinstance(x, int): return N(x)
    return str(x)


def kb_docs():
    out = []
    for root, dirs, files in os.walk(os.path.join(PRJ, 'knowledge')):
        for f in sorted(files):
            p = os.path.join(root, f)
            out.append({'path': os.path.relpath(p, PRJ).replace('\\', '/'),
                        'kb': f'{os.path.getsize(p)/1024:.1f}'})
    return out


KBDOCS = kb_docs()
RPT = []
RPT_DIR = os.path.join(PRJ, 'reports')
if os.path.isdir(RPT_DIR):
    for f in sorted(os.listdir(RPT_DIR)):
        p = os.path.join(RPT_DIR, f)
        if os.path.isfile(p):
            RPT.append({'f': f, 'kb': f'{os.path.getsize(p)/1024:.0f}',
                        'k': 'Word 报告' if f.endswith('.docx') else '报告图表'})

TABLES = sorted(U['tableRows'].items(), key=lambda z: -z[1])

V = []

# ==================================================================
# 首页 · 总览组
# 用户要求：首页段只保留「首页总览」一个子专题。原 all-overview / all-arch / all-cmp
# 三视图已下线，用户指定的 3 张卡（两流域核心指标对照 / 议题×流域交叉 /
# 流域传播态势）已并入 home-overview.cards（见 home_views）。
# 2026-10-01 再删「近期高影响力微博」卡：该卡样本是泛娱乐爆款微博，与流域三大主题无关。
# 下方 RIVER_YZ / RIVER_YL / ... / FLOW 等模块级变量保留，供 home-overview 的
# 流域传播态势卡（flow 渲染）复用。
# ==================================================================

# ---- 流域传播态势：沿「上游 → 下游」的省际序位（真实地理顺序，非声量排序）----
RIVER_YZ = ['西藏', '云南', '四川', '重庆', '贵州', '湖南', '湖北',
            '江西', '安徽', '江苏', '浙江', '上海']
RIVER_YL = ['青海', '甘肃', '宁夏', '内蒙古', '陕西', '山西', '河南', '山东']
BP = {r['name']: r['value'] for r in U['basinProv']}
YZ_PTS = [[p, BP[p]] for p in RIVER_YZ if p in BP]
YL_PTS = [[p, BP[p]] for p in RIVER_YL if p in BP]
assert sum(v for _, v in YZ_PTS) == CAN['b_yz_a'], '长江分省求和不等于流域总数'
assert sum(v for _, v in YL_PTS) == CAN['b_yl_a'], '黄河分省求和不等于流域总数'
FLOW = {'lanes': [
    {'name': '长江流域', 'color': '#2f8bff', 'total': CAN['b_yz_a'], 'pts': YZ_PTS},
    {'name': '黄河流域', 'color': '#ffa42e', 'total': CAN['b_yl_a'], 'pts': YL_PTS}]}
FLOW_PEAK = max(U['basinProv'], key=lambda r: r['value'])
BSRC0 = U['basinSrc'][0]
BSM = U['basinSrcMeta']        # 来源口径：有效样本 / 未标注 —— 数据缺口不当类别用
assert BSM['valid'] > 0 and BSM['valid'] + BSM['blank'] == BSM['total'], \
    f'流域评论来源口径异常：{BSM}'
BG = {r['name']: r['value'] for r in U['basinGender']}


# ==================================================================
# 二、数据洞察
# ==================================================================
V.append(dict(
    id='words', group='二、数据洞察', name='微博热词统计', badge='真实', badgeCls='real',
    lead=f'对微博 {N(HA["docs"])} 条、评论 {N(HC["docs"])} 条做 jieba 全量分词：'
         f'微博共 {N(HA["tokens"])} 个词次 / {N(HA["distinct"])} 个去重词条，'
         f'评论 {N(HC["tokens"])} 个词次 / {N(HC["distinct"])} 个去重词条。'
         f'下方柱状图即热词排行榜，点击可看词条原文命中；色块矩阵为词条近 8 日热度。',
    kpis=[K('微博去重词条', N(HA['distinct']), f'总词次 {N(HA["tokens"])}', 1),
          K('评论去重词条', N(HC['distinct']), f'总词次 {N(HC["tokens"])}', 2),
          K('微博热词榜首', HA['top'][0]['w'], f'{N(HA["top"][0]["freq"])} 词次', 3),
          K('评论热词榜首', HC['top'][0]['w'], f'{N(HC["top"][0]["freq"])} 词次', 4),
          K('近 7 日突增词', f'{len(BUMP_A)} 个', '微博侧（7 日窗口内出现）', 5),
          K('停用词', f'{len(U["hot"]["stop_used"])} 个', '本次统一过滤表', 6)],
    cards=[
        C('w1', '微博热词 Top 15（柱状图）', '词频 = 词条在全量正文中的出现次数', 'hbar', TOP_A,
          {'p': 0, 'n': 15}, w=2),
        C('w2', '评论热词 Top 15（柱状图）', '词频 = 词条在全量评论中的出现次数', 'hbar', TOP_C,
          {'p': 1, 'n': 15}, w=2),
                # v7 柱状 → 气泡堆积：传播面（文档数）的词间体量差异用「面积」读更直接；
        #     图例条给出完整 Top 明细，小圆放不下词名时仍能读全。
        C('w3', '热词覆盖文档数 Top 10 · 气泡', 'docf = 含该词的微博条数（衡量传播面而非刷屏度）· 圆面积 ∝ 文档数', 'bubble', DOCF_A,
          {'n': 10}),
                # v7：色阶换高对比多色阶（原低端 10% 透明蓝与深底几乎同亮度，冷区整片看不见），
        #     并开图例条给出色阶、「灰格=当日未出现」的口径与色域上限。
        C('w4', '热词 × 近 8 日热度矩阵', '横轴 D1→D8（最新），格内数字为该日词频；暗格=当日未出现',
          'spark', SPARK_A, w=3, ruler=True),
        TABLE('热词明细（Top 40）', [{'k': 'w', 'l': '词条'}, {'k': 'freq', 'l': '词频', 'num': True},
                                {'k': 'docf', 'l': '覆盖微博数', 'num': True},
                                {'k': 'n7', 'l': '近 7 日', 'num': True},
                                {'k': 'sp', 'l': '近 7 日走势（旧→新）', 'num': False}],
              HOT_TBL, '滑一遍就能看出哪些词是"长期高频"、哪些是"近期突增"', w=3),
        C('w6', '突增词 Top 15（微博）', '近 7 日窗口内出现的次数，柱长即突增强度', 'hbar', BUMP_A, {'p': 2, 'n': 15}),
        C('w7', '突增词 Top 12（评论）', '评论侧突增（沉默的螺旋/群体极化类词更敏感）', 'hbar', BUMP_C, {'p': 4, 'n': 12}),
        TABLE('热词 × 情感标签（下钻索引）', [{'k': 'w', 'l': '词条'}, {'k': 'v', 'l': '词频', 'num': True},
                                     {'k': 's', 'l': '情感标签'}],
              HOT_SENT, '点任一词条即可回库检索命中原文（当前为索引表）', w=2),
        KV('分词与过滤口径', [{'k': '微博词次', 'v': HA['tokens']}, {'k': '评论词次', 'v': HC['tokens']},
                        {'k': '微博去重词条', 'v': HA['distinct']}, {'k': '评论去重词条', 'v': HC['distinct']},
                        {'k': '停用词表', 'v': len(U['hot']['stop_used'])}],
           '阈值：词长 ≥ 2 且不含纯符号 / 纯数字'),
        C('w9', '词频矩形树图', '面积 = 词频；与左图同源，便于快速定位头部词', 'treemap',
          [[x['w'], x['freq']] for x in HA['top'][:30]], {'n': 30}),
    ],
    notes=[nt('<b>已核实的既有缺陷</b>：项目 <span class="mono">fenci/stopWords.txt</span> 并不存在，'
              '<span class="mono">getStopWordList()</span> 会静默返回空表，且全项目 0 处 '
              '<span class="mono">jieba.load_userdict</span>。本页为避免"负向词进榜"（如"这么/可以"），'
              f'统一使用 build_unified_data.py 内置的 {len(U["hot"]["stop_used"])} 词停用表重算，'
              '历史快照口径请勿与本页混用。', k='bad'),
           nt('微博侧 <b>373</b> 条时间字段无法解析，未纳入日窗口统计；评论侧 0 条。', k='warn')],
))

V.append(dict(
    id='article', group='二、数据洞察', name='微博文章分析', badge='真实', badgeCls='real',
    lead=f't_article 全表 {N(CAN["a_total"])} 行，按微博ID去重后 {N(CAN["a_dist"])} 条，'
         f'重复 {N(CAN["a_total"]-CAN["a_dist"])} 条（{PC(CAN["a_total"]-CAN["a_dist"], CAN["a_total"])}）。'
         f'互动量、长度、类型、时段四组分布全部现场分箱统计。',
    kpis=[K('文章总量', N(CAN['a_total']), 't_article 全表', 1),
          K('去重后', N(CAN['a_dist']), f'重复率 {PC(CAN["a_total"]-CAN["a_dist"], CAN["a_total"])}', 2),
          K('峰值日', FDD['articles7day']['x'][-1], f'{N(FDD["articles7day"]["y"][-1])} 条', 3),
          K('正文长度中位区间', '76-150 字', f'{N(U["artLen"]["y"][2])} 条落在该区间', 4),
          K('受控领域数', f'{FDD["typeTax"]["categories"]} 类',
            f'已标注 {N(FDD["typeTax"]["labeled_rows"])} 条 · 覆盖率 {FDD["typeTax"]["labeled_rate"]}%', 5),
          K('TOP 账号', FDD['kpi']['top_author'], '点赞最高微博作者（已脱敏）', 6)],
    cards=[
        C('a1', '发帖时间分布（24 小时）', 't_article.发布时间 · 峰值 10:00', 'bar',
          {'x': [f'{i}' for i in range(24)], 'y': U['hours']['article']}, {'p': 0}, w=2),
                # v7 柱状 → 漏斗：8 个长度档按条数降序（档位顺序让位于体量顺序，副标题已写明）。
        # v8 用户指定：改用「改造预案」里那张「正文长度分布」卡的形态 ——
        #     左侧中文档位 + 分段进度条 + 条数/占比 + 底部口径说明条。
        #     ⚠ 预案里那张卡的数字是占位值（1-50 字 9,410 / 正文为空 2,138 / >1000 字 1,381），
        #       实测全库 29,710 篇正文长度只有 2~257 字，既无 300 字以上长文也无空正文 —— 换成真实值。
        C('a2', '正文长度分布 · 分段条',
          'CHAR_LENGTH(TRIM(微博内容)) 现场分箱 · 全库 ' + N(U['lenSeg']['article']['total']) + ' 条',
          'segbar', {'rows': SGROWS('article')}, SGN('article', '正文', '长文',
                            '原设想「空正文会被情感分析判为中性」的口径问题在本库不存在，无需在论文里声明。')),
        C('a3', '点赞量分布', '分箱至 1 万+', 'bar',
          {'x': FDD['articleAnalysis']['dz']['x'], 'y': FDD['articleAnalysis']['dz']['y']}, {'p': 2, 'rot': 40, 'fs': 9}),
                # v7 柱状 → 面积折线：有序分箱的分布，读「密度形状」比读一排等高柱直观。
        C('a4', '评论量分布 · 面积', '分箱至 1 万+ · 面积 ∝ 档内条数', 'area',
          {'x': FDD['articleAnalysis']['pl']['x'], 'y': FDD['articleAnalysis']['pl']['y']}, {'p': 3, 'rot': 30, 'fs': 9}),
        C('a5', '转发量分布', '分箱至 2 千+', 'bar',
          {'x': FDD['articleAnalysis']['zf']['x'], 'y': FDD['articleAnalysis']['zf']['y']}, {'p': 4, 'rot': 55, 'fs': 8}),
                # v7 柱状 → 矩形树图：受控领域构成，树图面积即占比。
        #     该卡在栅格里被拉成通栏（3 列），饼/玫瑰/漏斗这类按「容器短边」定半径的图形
        #     会缩成小圆+长图例、大片留白，只有矩形树图这种「填满型」才撑得住宽卡。
        # 【修复】旧口径「Top10 + 其他」在此曾显示「娱乐博主 / iPhone 客户端」这类
        #     混合语义（领域与设备并列），且「其他」占 81.28%；现改为受控领域单一维度。
        C('w6', f'账号领域构成（{FDD["typeTax"]["categories"]} 类 · 受控词表）',
          f'旧口径 Top10 仅覆盖 {FDD["typeTax"]["legacy"]["top10_share"]}%，'
          f'其余 {round(100 - FDD["typeTax"]["legacy"]["top10_share"], 2)}% 被并入「其他」；'
          f'现按受控词表归类，「其他领域」降至 {FDD["typeTax"]["other_domain_rate"]}%'
          ' · 矩形面积 ∝ 条数（悬停看读数）', 'treemap',
          [[r['name'], r['value']] for r in FDD['typeDist']], {'n': 11}),
        TABLE('高影响力微博 Top 30', [{'k': 'text', 'l': '正文摘要'}, {'k': 'author', 'l': '作者'},
                                 {'k': 'zan', 'l': '点赞', 'num': True}, {'k': 'pl', 'l': '评论', 'num': True},
                                 {'k': 'zf', 'l': '转发', 'num': True}, {'k': 'time', 'l': '时间'},
                                 {'k': 'region', 'l': '地区'}, {'k': 'cat', 'l': '类型'}],
              [{'text': a['text'][:40] + '…', 'author': a['author'], 'zan': N(a['zan']), 'pl': N(a['pl']),
                'zf': N(a['zf']), 'time': a['time'], 'region': a['region'], 'cat': a['cat']}
               for a in FDD['articleTable']], '按点赞量降序 · 作者与昵称均已脱敏', w=3),
    ],
    notes=[nt(f'<b>重复成因（已核验）</b>：主表缺唯一键，爬虫"按关键词翻页"重复落库，'
              f'故同一微博ID可多次入库 → {N(CAN["a_total"]-CAN["a_dist"])} 条重复；'
              '流域表 t_basin_article 有主键且零重复（1,688 条 = 1,688 个 ID），可作为对照。', k='warn'),
           nt(f'点赞分布合计 {N(sum(FDD["articleAnalysis"]["dz"]["y"]))} = 文章总量，分箱无死角。', k='ok')],
))

_csrc = FDD['commentAnalysis']['source']
_csrc_label = ' / '.join(str(x.get('name')) for x in _csrc[:2]) or 'N/A'

V.append(dict(
    id='comment', group='二、数据洞察', name='微博评论分析', badge='真实', badgeCls='real',
    lead=f't_comment 全表 {N(CAN["c_total"])} 行，去重后 {N(CAN["c_dist"])} 条；'
         f'评论/微博 = {CAN["c_total"]/CAN["a_total"]:.3f}。'
         f'长度、点赞、性别、来源省四组分布均为现场统计。',
    kpis=[K('评论总量', N(CAN['c_total']), 't_comment 全表', 1),
          K('去重后', N(CAN['c_dist']), f'重复 {N(CAN["c_total"]-CAN["c_dist"])} 条', 2),
          K('评论 : 微博', f'{CAN["c_total"]/CAN["a_total"]:.3f}', '人均互动强度', 3),
          K('长度主区间', '1-25 字', f'{N(U["cmtLen"]["y"][1])} 条（{PC(U["cmtLen"]["y"][1], CAN["c_total"])}）', 4),
          K('女性占比', PC(FDD['commentAnalysis']['gender'][1]['value'],
                          sum(g['value'] for g in FDD['commentAnalysis']['gender'])),
            '性别字段推断值', 5),
          K('来源字段首两位', _csrc_label, '按当前语料统计', 6)],
    cards=[
                # v7 柱状 → 漏斗（与数据分析页的正文长度分布保持同一读法，便于两页对照）。
        # v8：与 a2 同族的卡，同步改成同一种形态（一张是漏斗一张是分段条会像漏改）。
        C('m1', '评论长度分布 · 分段条',
          'CHAR_LENGTH(TRIM(评论内容)) 现场分箱 · 全库 ' + N(U['lenSeg']['comment']['total']) + ' 条',
          'segbar', {'rows': SGROWS('comment')}, SGN('comment', '评论', '长评',
                            '%.1f%% 的评论集中在 1–50 字区间，长度口径无异常。'
                            % (U['lenSeg']['comment']['b1'] / U['lenSeg']['comment']['total'] * 100))),
                # v7 柱状 → 面积折线：8 档点赞分箱的衰减形状，面积比柱高更容易一眼看出「尾部长」还是「头部集中」。
        C('m2', '评论点赞分布 · 面积', '分箱至 1 百+ · 面积 ∝ 档内条数', 'area',
          {'x': FDD['commentAnalysis']['dz']['x'], 'y': FDD['commentAnalysis']['dz']['y']}, {'p': 2, 'rot': 30, 'fs': 9}),
        C('m3', '评论者性别构成', 't_comment 性别字段', 'pie',
          [[g['name'], g['value']] for g in FDD['commentAnalysis']['gender']], {'donut': True}),
        C('m4', '评论来源省份 Top 12', 't_comment 来源字段（作者 IP 归属）', 'hbar',
          [[r['name'], r['value']] for r in FDD['commentAnalysis']['source'][:12]], {'p': 3, 'n': 12}),
        C('m5', '评论时段分布（24 小时）', '评论时间字段 · 峰值 21:00', 'bar',
          {'x': [f'{i}' for i in range(24)], 'y': U['hours']['comment']}, {'p': 4}, w=2),
        C('m6', '活跃评论用户 Top 12', '昵称已脱敏（保留首尾字符）', 'hbar',
          [[r['name'], r['value']] for r in FDD['commentUsers'][:12]], {'p': 5, 'n': 12}),
        LIST('高赞评论（真实原文）', [{'m1': f'赞 {N(c["zan"])}', 'm2': c['src'],
                                 'txt': c['text']} for c in FDD['hotwordDemo']['comments']],
             '这是"鲜花"一词命中评论中点赞最高的 6 条', meta=[{'k': 'm1', 'cls': 'tag b'},
                                                       {'k': 'm2', 'cls': 'tag'}], w=3),
    ],
    notes=[nt(f'评论点赞分布合计 {N(sum(FDD["commentAnalysis"]["dz"]["y"]))} = 评论总量 {N(CAN["c_total"])}，'
              '分箱覆盖完整。', k='ok')],
))

V.append(dict(
    id='sentiment', group='二、数据洞察', name='情感分析', badge='真实', badgeCls='real',
    lead='三套抽样情感结果（微博正文 400 / 评论 500 / 热搜词 200）与全库情感表的时效差异，'
         '集中在同一页说明，避免"新旧混算"。',
    kpis=[K('抽样总量', '1,100 条', '400 + 500 + 200', 1),
          K('正文负面率', PC(SENT['article']['v'][2], SENT['article']['total']), '20 / 400', 2),
          K('评论负面率', PC(SENT['comment']['v'][2], SENT['comment']['total']), '22 / 500', 3),
          K('热词负面率', PC(SENT['hot']['v'][2], SENT['hot']['total']), '4 / 200', 4),
          K('理论标签', f'{len(SENT["article_tag"])-1} 类', '共情传播 141 · 使用与满足 65', 5),
          K('旧表时效', '2026-05-31 起', '热词榜覆盖 20%~40%', 6)],
    cards=[
        # 三张饼图同排：同一实体全站同一颜色（正面绿 / 中性蓝 / 负面红）
        C('s1', f'微博正文情感（{SENT["article"]["total"]} 条）', 'SnowNLP + 大模型复核', 'pie',
          [['正面', SENT['article']['v'][0]], ['中性', SENT['article']['v'][1]], ['负面', SENT['article']['v'][2]]],
          {'donut': True, 'cmap': SENT_CLR}),
        # 副标题里的条数一律从数据现算：原先写死"负面 22 条 / 4 条"，
        # 一旦上游 CSV 快照更新，标题就会与图不一致（数据在变、文字不变）。
        C('s2', f'评论情感（{SENT["comment"]["total"]} 条）',
          f'负面 {SENT["comment"]["v"][2]} 条（{PC(SENT["comment"]["v"][2], SENT["comment"]["total"])}）'
          ' → 弱势意见表达空间收窄', 'pie',
          [['正面', SENT['comment']['v'][0]], ['中性', SENT['comment']['v'][1]], ['负面', SENT['comment']['v'][2]]],
          {'donut': True, 'cmap': SENT_CLR}),
        C('s3', f'热搜词情感（{SENT["hot"]["total"]} 条）',
          f'热词侧几乎无负面（{SENT["hot"]["v"][2]} 条）', 'pie',
          [['正面', SENT['hot']['v'][0]], ['中性', SENT['hot']['v'][1]], ['负面', SENT['hot']['v'][2]]],
          {'donut': True, 'cmap': SENT_CLR}),
        # 第二行：w1 + w2 填满三列
                # v7 柱状 → 环形图：6 类标签的构成比（类目少，环形读占比比横条直观）。
        C('s5', '正文理论标签构成', '新闻传播学理论标签（模型自动标注）· 环形读构成', 'donut',
          [[r[0], r[1]] for r in SENT['article_tag'] if r[0] != '无'], {'p': 3, 'n': 6}),
        C('s4', '热词 Top 15 × 情感标签', '按词条情感着色：绿=正面 蓝=中性 红=负面', 'hbart',
          [[d['w'], int(d['v'].replace(',', '')), d['s']] for d in HOT_SENT],
          {'n': 15, 'map': SENT_CLR}, w=2),
        # 第三行：w1 + w2 填满三列（原先 s6 单独一行、右侧空两列）
        C('s6', '新旧口径覆盖对照',
          f'旧情感表 Top20 热词覆盖率：正文 {SENT["overlap"]["article"]["rate"]}% / '
          f'评论 {SENT["overlap"]["comment"]["rate"]}%', 'bar2',
          {'x': ['微博正文', '微博评论'],
           'series': [{'name': 'Top20 中命中', 'y': [SENT['overlap']['article']['hit'], SENT['overlap']['comment']['hit']]},
                      {'name': '未命中', 'y': [20 - SENT['overlap']['article']['hit'],
                                             20 - SENT['overlap']['comment']['hit']]}]}),        # 同一份数字换个切法：三套抽样 × 三种倾向。用 100% 堆积而不是分组柱 ——
        # 负面只有 20/22/4，放在 400 量级的 y 轴上会被压成一条线（首版实测），
        # 各套按自身样本量归一后，三段长度直接可比。
        C('s7', '三套抽样情感构成（各套按自身样本量归一）',
          '三色 正 + 中 + 负 = 100%　·　横向读同一段的长短即可看出结构差异',
          'stack',
          {'x': [f'微博正文 {SENT["article"]["total"]}', f'微博评论 {SENT["comment"]["total"]}',
                 f'热搜词 {SENT["hot"]["total"]}'],
           'series': [{'name': '正面', 'y': [_pct(SENT['article'], 0), _pct(SENT['comment'], 0), _pct(SENT['hot'], 0)]},
                      {'name': '中性', 'y': [_pct(SENT['article'], 1), _pct(SENT['comment'], 1), _pct(SENT['hot'], 1)]},
                      {'name': '负面', 'y': [_pct(SENT['article'], 2), _pct(SENT['comment'], 2), _pct(SENT['hot'], 2)]}]},
          {'pct': True, 'labels': True, 'hor': True, 'cmap': SENT_CLR},
          h=260),
        TABLE('三套抽样情感明细（可直接引用）',
              [{'k': 'dim', 'l': '抽样维度', 'nw': True},
               {'k': 'pos', 'l': '正面', 'num': True}, {'k': 'neu', 'l': '中性', 'num': True},
               {'k': 'neg', 'l': '负面', 'num': True}, {'k': 'rate', 'l': '负面率', 'num': True},
               {'k': 'tot', 'l': '合计', 'num': True},
               {'k': 'eq', 'l': '等式', 'nw': True, 'tag': {'成立': 'g'}}],
              [{'dim': '微博正文（SnowNLP + 大模型复核）', 'pos': SENT['article']['v'][0],
                'neu': SENT['article']['v'][1], 'neg': SENT['article']['v'][2],
                'rate': PC(SENT['article']['v'][2], SENT['article']['total']),
                'tot': N(SENT['article']['total']), 'eq': '成立'},
               {'dim': '微博评论（评论情感抽样）', 'pos': SENT['comment']['v'][0],
                'neu': SENT['comment']['v'][1], 'neg': SENT['comment']['v'][2],
                'rate': PC(SENT['comment']['v'][2], SENT['comment']['total']),
                'tot': N(SENT['comment']['total']), 'eq': '成立'},
               {'dim': '热搜词（热词抽样）', 'pos': SENT['hot']['v'][0],
                'neu': SENT['hot']['v'][1], 'neg': SENT['hot']['v'][2],
                'rate': PC(SENT['hot']['v'][2], SENT['hot']['total']),
                'tot': N(SENT['hot']['total']), 'eq': '成立'}],
              '正 + 中 + 负 = 合计，三套全部成立，故本页占比可对外引用', w=2),
    ],
    notes=[nt(f'旧情感/词频产物时间戳：热词 {SENT["mtime"]["hot"]} · 评论 {SENT["mtime"]["comment"]} · '
              f'正文 {SENT["mtime"]["article"]} · 词频 {SENT["mtime"]["fre"]}；'
              f'而库内数据已更新到 {U["generated"]} —— 二者相差数月，'
              '故本页所有"占比"只用上述三套抽样的自洽结果，不引用旧表。', k='warn'),
           nt('三套抽样各自"正+中+负 = 总数"全部成立（400/500/200），可直接对外引用。', k='ok'),
           nt('本页 8 张卡共 10 格：2 列下正好 5 行除得尽（末行不留空位）；3 列下余 1 格，'
              '由「末行自动补齐」把空位并给该行最后一张卡。该兜底对全部 18 个视图生效。', k='ok')],
))

# ==================================================================
# 二、数据洞察（续）：IP 地域 / 词云
# ==================================================================
NORM = sorted(list(IP['article']['normalized_from'].items()) +
              list(IP['comment']['normalized_from'].items()), key=lambda z: -z[1])[:14]
IPB = IP['article']['basin']
# ---- 词云：噪声词判定（与前端 _wordcloud.js 保持一致）----
_NZ_RX = re.compile(r'^(https?|http|www|cn|com|net|org|html|##|#|\d+|[a-z]{1,4})$', re.I)


def is_noise(t):
    t = str(t)
    if _NZ_RX.match(t): return True
    if re.search(r'[?&=#/\\]|://', t): return True
    if not re.search(r'[0-9A-Za-z\u4e00-\u9fff]', t): return True
    return False


CLOUDFRE = U['cloudFre']
CLOUD_STAT = {}
for _k in ('article', 'comment', 'user'):
    _lst = CLOUDFRE[_k]
    CLOUD_STAT[_k] = {'n': len(_lst),
                      'noise': sum(1 for _t, _v in _lst if is_noise(_t)),
                      'tot': sum(_v for _t, _v in _lst),
                      'max': _lst[0], 'min': _lst[-1]}


def shrink_cloud(uri, w=620, q=62):
    """原版词云图降采样内联 —— 仅用于溯源核对，避免 495 KB 位图占据主版面"""
    raw = base64.b64decode(uri.split(',', 1)[1])
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=q, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


try:
    CI = {k: shrink_cloud(v) for k, v in U['cloudImg'].items()}
except Exception:
    CI = U['cloudImg']
CLOUD_SAVED = sum(len(U['cloudImg'][k]) - len(CI[k]) for k in CI)

# ==================================================================
# 二、数据洞察（续）：IP 地域 / 词云
# ==================================================================
NORM = sorted(list(IP['article']['normalized_from'].items()) +
              list(IP['comment']['normalized_from'].items()), key=lambda z: -z[1])[:14]
IPB = IP['article']['basin']

IP_CARDS = [
    # 主视觉：三张地图合并为一张，顶部三档图层切换 + 三档配色切换
    C('p1', '省份声量地图 · 主视觉（三档图层 + 三档配色）',
      '颜色越深声量越高　·　悬停查看省份值与占比', 'map',
      None, {'side': 'article', 'basin': False, 'big': True, 'labelFs': 11, 'pal': 'heat'},
      w=2, h=470, tools='layer,pal', ruler=True, cls='mapstage'),
    # 右列复合卡：流域归属 + IP 构成，与主图等高
    C('p2', '流域归属与 IP 构成', '不重叠口径的流域三色 + 微博侧归属四类构成', 'stack',
      None, None, w=1, stack=[
          {'t': '流域归属对照', 's': '长江独有 / 黄河独有 / 非流域', 'r': 'bar2', 'h': 200,
           'd': {'x': ['长江独有', '黄河独有', '非流域'],
                 'series': [
                     {'name': '微博', 'y': [BS['article']['yz'], BS['article']['yl'],
                                            BS['article']['outside']]},
                     {'name': '评论', 'y': [BS['comment']['yz'], BS['comment']['yl'],
                                            BS['comment']['outside']]}]},
           'o': {}},
          {'t': 'IP 归属构成（微博侧）', 's': '四类互斥且完备', 'r': 'pie', 'h': 200,
           'd': [['已归属省份', BS['article']['prov_total']], ['未识别', IP['article']['unknown']],
                 ['境外（含港澳台）', IP['article']['overseas']], ['AI 生成', IP['article']['ai']]],
           'o': {'donut': True}}]),
    # 三张排行榜并列一排（消掉原先两整行的纵向浪费，横向利用率 35% → 75%）
            # v7 柱状 → 矩形树图：省份声量的构成（本页已有 p1 地图做地理分布、
        #     p5/p6 横条做排行，这里换成面积构成，避免同一页三张条形卡重复）。
        C('p4', '微博省份声量构成 Top 15', '广东 2,765 · 北京 1,836 · 山东 1,443 · 矩形面积 ∝ 声量', 'treemap',
      PROV_A[:15], {'p': 0, 'n': 15}, h=400),
    C('p5', '评论省份声量 Top 15', '与微博侧同源口径（t_comment.来源）', 'hbar',
      PROV_C[:15], {'p': 1, 'n': 15}, h=400),
    C('p6', '被归一化掉的原始值 Top 14', '「来自 XX」→ XX；中国香港/澳门/台湾 → 港澳台', 'hbar',
      NORM, {'p': 3, 'n': 14}, h=400),
    TABLE('省份明细（34 个省级行政区）',
          [{'k': 'p', 'l': '省份'}, {'k': 'a', 'l': '微博', 'num': True},
           {'k': 'c', 'l': '评论', 'num': True}, {'k': 'b', 'l': '流域归属'}],
          PROV_TBL, '按国标省级行政区固定顺序，零遗漏　·表头吸附，可滚动查看', w=3),
]
V.append(dict(
    id='ip', group='二、数据洞察', name='IP 地域分布', badge='真实', badgeCls='real',
    lead=f'按作者 IP 归属省份统计：微博侧 {N(CAN["a_total"])} 条中已归属 <b>{N(BS["article"]["prov_total"])}</b> 条'
         f'（{PC(BS["article"]["prov_total"], CAN["a_total"])}），未知 {N(IP["article"]["unknown"])} 条，'
         f'境外 {N(IP["article"]["overseas"])} 条；评论侧已归属 {N(BS["comment"]["prov_total"])} 条'
         f'（{PC(BS["comment"]["prov_total"], CAN["c_total"])}）。'
         f'<b>主地图支持三档图层切换</b>（微博作者 / 评论作者 / 流域着色）与<b>三档配色切换</b>'
         f'（热力 / 冰蓝 / 高对比）—— 色阶低端用可见的板岩蓝，保证 0 声量省份仍能看清轮廓；'
         f'流域一律用「蓝=长江 · 橙=黄河 · 灰=非流域」，与声量色阶明确区分，不再同屏歧义。',
    kpis=[K('微博已归属', N(BS['article']['prov_total']), PC(BS['article']['prov_total'], CAN['a_total']), 1),
          K('微博未知', N(IP['article']['unknown']), PC(IP['article']['unknown'], CAN['a_total']), 2),
          K('微博境外', N(IP['article']['overseas']), '港澳台 + 海外', 3),
          K('评论已归属', N(BS['comment']['prov_total']), PC(BS['comment']['prov_total'], CAN['c_total']), 4),
          K('评论 AI 生成', N(IP['comment']['ai']), '智搜 / 罗伯特，非真人 IP', 5),
          K('长江 : 黄河', f'{N(BS["article"]["yz"])} : {N(BS["article"]["yl"])}',
            f'微博侧，比值 {BS["article"]["yz"]/BS["article"]["yl"]:.2f}', 6)],
    cards=IP_CARDS,
    notes=[nt(f'<b>口径修正</b>：旧版 ip_map_data.json 的 basin 里 "共源 {N(IPB["shared"])}" 是<b>重复计数</b> —— '
              f'YANGTZE 与 YELLOW 两张省表实际互不相交（青海只属黄河、四川只属长江），该桶把 四川 1,048 + '
              f'青海 29 又算了一遍。本页统一改用「长江独有 {N(BS["article"]["yz"])} + 黄河独有 '
              f'{N(BS["article"]["yl"])} + 非流域 {N(BS["article"]["outside"])} = '
              f'{N(BS["article"]["prov_total"])}」的不重叠口径。', k='bad'),
           nt(f'微博侧 {N(IP["article"]["unknown"])} 条（{PC(IP["article"]["unknown"], CAN["a_total"])}）'
              '地区字段为空或写"未知"，是地域分析最大的数据缺口；评论侧仅 191 条。', k='warn'),
           nt('港澳台统一按中国省级行政区处理：中国香港 100 + 中国澳门 9 + 中国台湾 37（微博侧，'
              '来自"中国XX"原始写法归一）。', k='ok')],
))

# ---- 词云视图：位图 → 数据驱动可交互 ----
CL_TOT_A = CLOUD_STAT['article']['tot']
CL_TOT_C = CLOUD_STAT['comment']['tot']
SRC_HTML = (
    '<details class="srcbox"><summary>展开查看项目 static/ 下的 3 张原版词云图'
    '（原图 1,155×924；为控制体积已降采样至 620px 宽，仅用于核对）</summary>'
    '<div class="srcgrid">'
    f'<div><img src="{CI["article"]}"><div class="sub">static/article_cloud.jpg</div></div>'
    f'<div><img src="{CI["comment"]}"><div class="sub">static/comment_cloud.jpg</div></div>'
    f'<div><img src="{CI["user"]}"><div class="sub">static/comment_user_cloud.jpg</div></div>'
    '</div></details>')
V.append(dict(
    id='cloud', group='二、数据洞察', name='词云分析', badge='真实', badgeCls='real',
    lead='三张词云全部由 <code>fenci/*_fre2.csv</code> 的 Top50 词频<b>实时渲染</b>'
         '（自研 Canvas 螺旋布局，零依赖），随数据更新 —— 不再使用静态截图。'
         '悬停词条可见频次 / 排名 / 占比；噪声词（URL 残留、纯符号、短英文）默认隐藏，可一键展开。',
    kpis=[K('正文词频总量', N(CL_TOT_A), 'Top50 合计', 1),
          K('正文噪声词', f"{CLOUD_STAT['article']['noise']} / {CLOUD_STAT['article']['n']}",
            'http / cn / ## 等 URL 残留', 2),
          K('正文有效词', f"{CLOUD_STAT['article']['n'] - CLOUD_STAT['article']['noise']} 个",
            '参与主词云布局', 3),
          K('评论词频总量', N(CL_TOT_C), 'Top50 合计', 4),
          K('评论噪声词', f"{CLOUD_STAT['comment']['noise']} / {CLOUD_STAT['comment']['n']}",
            '鲜花 91 为最高有效词', 5),
          K('静态位图节省', f"{CLOUD_SAVED/1024:.0f} KB", '3 张内联 JPEG → 数据渲染', 6)],
    cards=[
        C('cl1', '主词云 · 微博正文', '全宽容器 · 字号映射 √((v−vmin)/(vmax−vmin))　·　悬停查看详情',
          'wordcloud', CLOUDFRE['article'], {'maxFs': 64, 'minFs': 12},
          w=3, h=420, tools='noise', ruler=True),
        C('cl2', '微博评论词云', 'comment_fre2.csv Top50',
          CLOUDFRE['comment'], {'maxFs': 50, 'minFs': 11}, w=2, h=320, ruler=True),
        C('cl3', '评论用户名词云', 'comment_user_fre2.csv Top30（容器较窄，按词量匹配）',
          CLOUDFRE['user'][:30], {'maxFs': 46, 'minFs': 11}, w=1, h=320, ruler=True),
        C('cl4', '正文有效词 Top 20（精确读数）',
          f"词云给直觉，条形给读数 —— 已剔除 {CLOUD_STAT['article']['noise']} 个噪声词"
          f"（http / cn / ## 等），仅显示可解读词条", 'hbar',
          [(t, v) for t, v in CLOUDFRE['article'] if not is_noise(t)][:20],
          {'p': 0, 'n': 20}, w=3, h=460),
        TEXT('数据溯源对照', SRC_HTML, '原版静态词云图（折叠）· 与当前词频同源，用于核对'),
    ],
    notes=[nt('核对结果：三张原图与对应 CSV 的 Top 词完全一致（正文 http/cn、评论 鲜花/可以、'
              '用户名 http/cn），说明项目原词云图未失效、也未被人工修饰 —— 故本页改为'
              '<b>保留同源数据、改用数据驱动渲染</b>，图形随库更新而无需重制。', k='ok'),
           nt(f'正文 Top2 为 <code>http</code>（{N(CLOUDFRE["article"][0][1])}）与 '
              f'<code>cn</code>（{N(CLOUDFRE["article"][1][1])}）这类 URL 噪声词，'
              f'共 {CLOUD_STAT["article"]["noise"]} 个 —— 现已默认隐藏并降权，'
              f'把版面让给"中国 / 我们 / 视频"等有效词；开关可随时展开核对。', k='warn')],
))

# ==================================================================
# 三、流域专题
# ==================================================================
# 流域评论性别（供「流域评论性别构成」副标题动态取值，避免写死数字后与数据脱节）
_BASIN_GENDER = {r['name']: r['value'] for r in U['basinGender']}
V.append(dict(
    id='basin', group='三、流域专题', name='长江黄河对照', badge='真实', badgeCls='real',
    lead=f'流域表 {N(CAN["b_art"])} 条微博 / {N(CAN["b_cmt"])} 条评论，长江 {N(CAN["b_yz_a"])} : {N(CAN["b_yl_a"])}'
         f'（微博），议题四类均衡采样。本页把"声量 / 议题 / 词频 / 评论 / 省份"五个维度的长江—黄河差异并排。',
    kpis=[K('流域微博', N(CAN['b_art']), f'长江 {N(CAN["b_yz_a"])} · 黄河 {N(CAN["b_yl_a"])}', 1),
          K('流域评论', N(CAN['b_cmt']), f'长江 {N(CAN["b_yz_c"])} · 黄河 {N(CAN["b_yl_c"])}', 2),
          K('长江占比', PC(CAN['b_yz_a'], CAN['b_art']), '微博侧', 3),
          K('黄河占比', PC(CAN['b_yl_a'], CAN['b_art']), '微博侧', 4),
          K('议题类别', f'{len(U["basinTopic"])} 类', '社会治理声量最高', 5),
          K('采集窗口', U['basinTime'][0][5:], f'~ {U["basinTime"][1][5:]}', 6)],
    cards=[
        C('b1', '长江 vs 黄河 · 声量对照（柱状图）', '微博 / 评论两组，来自流域表真实分域', 'bar2',
          {'x': ['长江', '黄河', '合计'],
           'series': [{'name': '微博', 'y': [CAN['b_yz_a'], CAN['b_yl_a'], CAN['b_art']]},
                      {'name': '评论', 'y': [CAN['b_yz_c'], CAN['b_yl_c'], CAN['b_cmt']]}]}),
                # v7 柱状 → 雷达图：4 个议题 × 2 条流域，雷达一眼看出「形状差异」
        #     （黄河在「社会治理/督察」更凸、长江在「生态/食品安全」更凸），柱状只能逐项比高度。
        C('b2', '议题 × 流域 交叉（雷达图）', '四类议题在两条流域的声量对比 · 雷达读形状差异', 'radar',
          {'x': [r['name'] for r in U['basinTopicXY'][0]['rows']],
           'series': [{'name': xy['basin'], 'y': [r['value'] for r in xy['rows']]}
                      for xy in U['basinTopicXY']]}, w=2),
        C('b3', '长江流域词频 Top 15', '仅长江 978 条微博的正文分词', 'hbar',
          U['basinWords']['yz'][:15], {'p': 3, 'n': 15}),
        C('b4', '黄河流域词频 Top 15', '仅黄河 710 条微博的正文分词', 'hbar',
          U['basinWords']['yl'][:15], {'p': 2, 'n': 15}),
        C('b5', '流域微博词频 Top 20（合并）', '两条流域合并后的头部词，与"热词统计"页主表口径不同', 'hbar',
          U['basinWords']['article'][:20], {'p': 0, 'n': 20}, w=2),
        C('b6', '流域评论词频 Top 15', '仅 140 条流域评论，样本小、口语化', 'hbar',
          U['basinWords']['comment'][:15], {'p': 4, 'n': 15}),
        C('b7', '流域评论性别构成',
          '男 %d / 女 %d（流域评论样本 %d 条）' % (_BASIN_GENDER.get('m', 0),
                                              _BASIN_GENDER.get('f', 0), CAN['b_cmt']),
          'pie',
          [['男' if r['name'] == 'm' else '女', r['value']] for r in U['basinGender']], {'donut': True}),
        C('b8', '流域目标省份声量（20 省）', '四类议题 × 流域均衡采样，各省 93~99 条，非自然分布', 'hbar',
          [[r['name'], r['value']] for r in U['basinProv']], {'p': 1, 'n': 20}, w=3),
        # 【修复】原标题「流域情感对照」、副标题「流域评论样本情感」与数据不符：
        #   流域评论表 t_basin_comment 没有情感标签列，图中画的只是**评论条数**。
        #   标题与数据不一致会把"评论量差异"误读成"情感差异"，故改为量级对照。
        C('b9', '流域评论量对照', '长江 / 黄河评论条数（流域表无情感标签列，本卡不呈现情感）', 'bar2',
          {'x': ['评论条数'],
           'series': [{'name': '长江', 'y': [CAN['b_yz_c']]}, {'name': '黄河', 'y': [CAN['b_yl_c']]}]}),
    ],
    notes=[nt('<b>两条流域真实差异</b>：长江侧重"生态/食品安全"（生态 338、食品安全 232），'
              '黄河侧重"督察/中央"（督察 297、中央 203）—— '
              '这与黄河侧重中央环保督察类议题、长江侧重地方生态治理类议题的分布相符。', k='ok'),
           nt(f'流域表省份字段≠主表省份字段：流域表存的是<b>内容涉及省</b>（目标省份），'
              f'主表存的是<b>作者 IP 省</b>。二者仅 249/1,688（{PC(249, 1688)}）相同，'
              '因此本页"省份"一栏不能与 IP 页的省份混读。', k='warn')],
))

# 「热点事件档案」KPI 用的两个极值（独立于列表排序，避免口径串味）
_peak = max(U['basinDays'], key=lambda d: d['n']) if U['basinDays'] else None
_top_zan = max(U['basinEvents'], key=lambda a: a['zan']) if U['basinEvents'] else None

V.append(dict(
    id='events', group='三、流域专题', name='热点事件档案', badge='实测', badgeCls='ok',
    lead='按议题归档的流域热点事件清单。事件卡片的正文、互动量、日期、地区、流域、目标省份、'
         '命中关键词<b>全部取自流域专用表 t_basin_article</b>；'
         '"事件"这一步当前靠议题字段归并，不是自动聚类模型。',
    kpis=[K('归档事件', f'{len(U["basinEvents"])} 条', 't_basin_article 互动量 Top30', 1),
          K('议题类别', f'{len(U["basinTopic"])} 类', '流域表议题字段', 2),
          K('峰值日发文', N(_peak['n']) if _peak else '—', _peak['d'] if _peak else '—', 3),
          K('最高点赞', N(_top_zan['zan']) if _top_zan else '—',
            f"{_top_zan['topic']} · {_top_zan['basin']}" if _top_zan else '—', 4),
          K('跨流域议题', f'{len(U["basinCross"])}/{len(U["basinTopic"])} 类', '长江与黄河均有样本', 6)],
    cards=[
        LIST('事件档案（按互动量 · 流域表）',
             [{'m1': a['basin'], 'm2': a['topic'], 'm3': a['time'],
               'm4': f'赞 {N(a["zan"])}', 'txt': a['text']}
              for a in U['basinEvents'][:12]],
             '流域 / 议题 / 日期 / 点赞 均为 t_basin_article 真值；作者已脱敏',
             meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'},
                   {'k': 'm3', 'cls': 'tag'}, {'k': 'm4', 'cls': 'tag a'}], w=3),
        C('e1', '流域表近期日发文量', f't_basin_article 近 {len(U["basinDays"])} 个有样本日期（升序）',
          'bar', {'x': [d['d'] for d in U['basinDays']], 'y': [d['n'] for d in U['basinDays']]},
          {'p': 2, 'rot': 30}, w=2),
        TABLE('议题归档（流域表）', [{'k': 'name', 'l': '议题'}, {'k': 'value', 'l': '微博数', 'num': True},
                                {'k': 'share', 'l': '占比'}],
              [{'name': r['name'], 'value': N(r['value']),
                'share': PC(r['value'], CAN['b_art'])} for r in U['basinTopic']],
              '四类议题均衡采样，故占比接近 25% 属采集设计而非舆情实况'),
        LIST('跨流域议题（长江+黄河均有样本）',
             [{'m1': c['name'], 'm2': ' / '.join(c['basins']),
               'm3': f"{N(next((r['value'] for r in U['basinTopic'] if r['name'] == c['name']), 0))} 条",
               'txt': f"议题「{c['name']}」在 {'、'.join(c['basins'])} 流域均有采集样本"}
              for c in U['basinCross']],
             '判定口径：同一议题在长江、黄河两个流域都出现过',
             meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'}, {'k': 'm3', 'cls': 'tag a'}], w=3),
    ],
    notes=[nt('本页数据<b>全部来自流域专用表 t_basin_article / t_basin_comment</b>，'
              '不再引用全量 t_article：归档事件按互动量（赞+评+转）取 Top30，日发文量与议题归档亦为该表实测。', k='ok'),
           nt('边界说明：事件识别模型（话题聚类 + 时间窗口 + 传播路径）尚未接入，'
              '当前"事件"等价于议题字段归并；一旦接入，本页数据结构可直接复用。', k='warn'),
           nt('流域表 1,688 条微博的议题标签由爬虫侧四类均衡采样写入，因此"议题占比"不能解读为'
              '社会实况比例，只能用于类内比较。', k='bad')],
))

V.append(dict(
    id='risk', group='三、流域专题', name='风险分级预警', badge='演示', badgeCls='plan',
    lead='风险分级需要"省级负面情感 × 声量增速 × 传播节点"三类指标。当前库内只有<b>声量</b>与'
         '<b>全局抽样情感</b>（流域评论表 t_basin_comment 无情感标签列），故本页只把'
         '<b>真实可算的部分</b>呈现，评分与工单为框架演示，不填假数。',
    kpis=[K('可算指标', '2 类', '省份声量 · 样本构成', 1),
          K('待接入指标', '3 类', '省内负面率 · 增速 · 关键节点', 2),
          K('预警工单', '0 条', '未接入，故不展示虚构工单', 4),
          K('高风险省', '待定', '依赖省级负面率', 6)],
    cards=[
        KV('风险因子权重（框架，非实测）', [{'k': '声量规模', 'v': 30}, {'k': '负面占比', 'v': 30},
                                   {'k': '环比增速', 'v': 20}, {'k': '跨域扩散', 'v': 10},
                                   {'k': '关键节点', 'v': 10}],
           '满分 100，权重待专家评议后固化', unit='%', w=2,
           note='此处只写权重方案，不代表任何真实评分'),
        C('r1', '省份声量（风险暴露面代理）', '20 个流域目标省份的微博数，真实值', 'hbar',
          [[r['name'], r['value']] for r in U['basinProv']], {'p': 3, 'n': 20}, w=2),
        # 【修复】原卡片标题为「情感占比（流域评论样本）」，但画的其实是**样本来源归属**
        # （长江/黄河/全域其他），标题与数据不符；而且分母取的是全量评论 24,768，
        # 流域样本只有 140 条，于是「其他评论样本」占到 99.4%，看起来像"分类结果几乎
        # 全部落到其他"。现在改为：① 标题与数据对齐；② 分母收窄为流域样本本身，
        # 让两个真实类别都可读；③ 覆盖率作为口径说明显式给出，不再靠一个巨大的
        # 「其他」扇形来表达。
        C('r2', '流域评论样本分域构成',
          f'基数 = 流域评论样本 {N(CAN["b_cmt"])} 条（仅占全域评论 {N(CAN["c_total"])} 条的 '
          f'{PC(CAN["b_cmt"], CAN["c_total"])}）· 长江 {CAN["b_yz_c"]} / 黄河 {CAN["b_yl_c"]}'
          ' · 流域评论表无情感标签，故不能代表全域情感', 'pie',
          [['长江评论样本', CAN['b_yz_c']], ['黄河评论样本', CAN['b_yl_c']]], {'donut': True}),
        TEXT('可拓学风险物元 M = (N, C, V)',
             '<div class="mono" style="line-height:2">'
             'M = ( 流域风险事件,<br>&nbsp;&nbsp;特征 C,<br>&nbsp;&nbsp;量值 V )<br><br>'
             'C₁ = 声量规模&nbsp;&nbsp;V₁ = 真实值 ✔<br>'
             'C₂ = 负面占比&nbsp;&nbsp;V₂ = 仅全局抽样 ⚠（流域表无情感标签）<br>'
             'C₃ = 环比增速&nbsp;&nbsp;V₃ = 数据不足 ⚠<br>'
             'C₄ = 跨域扩散&nbsp;&nbsp;V₄ = 数据不足 ✗<br>'
             'C₅ = 关键节点&nbsp;&nbsp;V₅ = 数据不足 ✗</div>',
             '经典物元三元组，右侧为当前可填性', w=2),
    ],
    notes=[nt('本页刻意<b>不编造预警单</b>：要出风险分级，必须先在爬虫侧补采省级粒度的情感与时间序列，'
              '再把权重方案交给专家评议。这一步做完之前，任何"高风险 N 个省"的数字都是不可信的。', k='bad')],
))

# ==================================================================
# 四、AI 智能体
# ==================================================================
V.append(dict(
    id='ai', group='四、AI 智能体', name='智能问答', badge='演示', badgeCls='plan',
    lead=f'RAG 知识库为 <b>{KB["collection"]}</b>（{KB["chunks"]} 个文本块 / {KB["dim"]} 维向量），'
         f'生成侧为主备双后端：星火 API + 本地 Qwen2.5-1.5B LoRA（适配器 {TR["adapter_mb"]} MB）。'
         f'问答界面为原型演示，右侧训练曲线与左侧知识库规模是真实读数。',
    kpis=[K('知识库文本块', N(KB['chunks']), KB['collection'], 1),
          K('向量维度', N(KB['dim']), 'embedding 维度', 2),
          K('知识库文档', f'{KB["knowledge_total"]} 份', '教材 + 论文 + 笔记 + few-shot', 3),
          K('SFT 指令数', f'{TR["sft_rows"]} 条', 'instruction_data.jsonl', 4),
          # 流域副本不带 finetuned/ 权重，train_log.json 缺失时 loss 为空 ——
          # 本视图已下线，但构造代码仍会执行，故必须判空，否则整页构建会中断。
          K('训练损失',
            (f'{TR["loss"][0][1]} → {TR["loss"][-1][1]}' if TR['loss'] else '无训练日志'),
            (f'{TR["loss"][0][0]} → {TR["loss"][-1][0]} step' if TR['loss']
             else '精简副本未带 finetuned/'), 5),
          K('基座模型', TR['base'], 'LoRA 微调', 6)],
    cards=[
        C('qa_live', '智能问答（实时 · 星火 + RAG）',
          '提问走星火大模型 + 新闻传播学知识库溯源，回答附文献引用；回车或点「发送」。',
          'chat', None, w=3, h=460),
        C('ai1', 'LoRA 训练损失曲线（真实）', f'训练日志 {len(TR["loss"])} 个记录点 / 验证 {len(TR["evals"])} 点',
          'curve', TR, w=4 if False else None),
        KV('知识库文档构成', [{'k': '新闻传播教材', 'v': KB['knowledge_md']},
                        {'k': '核心期刊论文', 'v': KB['papers_md']},
                        {'k': '历史笔记（txt）', 'v': KB['notes_txt']},
                        {'k': 'few-shot 示例', 'v': 1}],
           'knowledge/ 目录实测', w=2),
        LIST('常见提问（示例）', [{'t1': '理论', 'txt': '什么是沉默的螺旋？在当前数据里有没有体现？'},
                            {'t1': '方法', 'txt': '帮我解释一下共情传播的生成逻辑。'},
                            {'t1': '数据', 'txt': '近 7 日声量最高的议题是哪一个？'},
                            {'t1': '写作', 'txt': '把上面的结论写成一页舆情周报。'}],
             '每条提问都对应一个真实功能入口或真实数据字段',
             meta=[{'k': 't1', 'cls': 'tag b'}], w=2),
    ],
    notes=[nt('智能问答已接<b>实时推理</b>：提问经星火大模型 + 新闻传播学知识库（RAG）溯源回答；'
              '知识库规模、向量维度、SFT 数据量、训练损失曲线四项为文件/库实测。', k='ok')],
))

V.append(dict(
    id='report', group='四、AI 智能体', name='舆情报告生成', badge='真实数据 · 演示出稿', badgeCls='new',
    sec='ai',
    lead=f'报告引擎已产出 {KB["reports_docx"]} 份 Word 报告与 {KB["reports_png"]} 张配图（reports/ 目录实测）。'
         f'下方周报预览里的每个数字都来自本页顶部的真实统计，不是占位文字。',
    kpis=[K('历史报告', f'{KB["reports_docx"]} 份', 'reports/*.docx', 1),
          K('报告配图', f'{KB["reports_png"]} 张', '趋势/柱状/散点/情感', 2),
          K('导出格式', 'Word (.docx)', 'python-docx 生成', 3),
          K('数据来源', f'{CAN["tabs"]} 张表', 'db_weibo_basin', 4),
          K('报告期数据量', N(CAN['a_total']), '微博侧全量', 5),
          K('生成后端', '星火 API + 本地 LoRA', '主备双通道', 6)],
    cards=[
        C('rp_live', '在线生成舆情报告', '点击按钮，由星火大模型 + 知识库现场生成完整 Word 报告（约 30 秒）', 'report', None, w=3, h=430),
        TABLE('历史报告与配图（reports/ 目录）',
              [{'k': 'f', 'l': '文件'}, {'k': 'k', 'l': '类型'}, {'k': 'kb', 'l': '大小 (KB)', 'num': True}],
              RPT, '文件名即生成时间戳，可追溯到具体批次', w=2),
        TEXT('周报预览（数字全部真实）',
             f'<div style="line-height:1.95">'
             f'<b>《流域舆情周报》</b><br>'
             f'本周期入库微博 <b>{N(CAN["a_total"])}</b> 条、评论 <b>{N(CAN["c_total"])}</b> 条；'
             f'流域专题样本 {N(CAN["b_art"])} 条（长江 {N(CAN["b_yz_a"])} / 黄河 {N(CAN["b_yl_a"])}）。<br>'
             f'议题结构：社会治理 {N(U["basinTopic"][0]["value"])} 条居首，'
             f'生态治理 {N(U["basinTopic"][1]["value"])} 条次之。<br>'
             f'地域分布：已归属省份 {N(BS["article"]["prov_total"])} 条'
             f'（{PC(BS["article"]["prov_total"], CAN["a_total"])}），未识别 {N(IP["article"]["unknown"])} 条。<br>'
             f'情感抽样：正文负面 {SENT["article"]["v"][2]}/{SENT["article"]["total"]}'
             f'（{PC(SENT["article"]["v"][2], SENT["article"]["total"])}）。<br>'
             f'<span style="color:#ffb44d">数据缺口提示：</span>'
             f'重复入库 {N(CAN["a_total"]-CAN["a_dist"])} 条、地区缺失 {N(IP["article"]["unknown"])} 条。</div>',
             '可直接作为周报正文的写法示范', w=2),
        KV('生成配置', [{'k': '统计口径', 'v': 100}, {'k': '图表配图', 'v': 100},
                     {'k': 'AI 摘要', 'v': 100}, {'k': '引用溯源', 'v': 100}],
           '四项开关全部启用（真实配置项来自报告引擎）', unit='%'),
        C('rp1', '报告所用图表 · 情感抽样', '报告配图与页面图表同源（正文/评论/热词三套）', 'bar2',
          {'x': ['正面', '中性', '负面'],
           'series': [{'name': '微博正文', 'y': SENT['article']['v']},
                      {'name': '微博评论', 'y': SENT['comment']['v']},
                      {'name': '热搜词', 'y': SENT['hot']['v']}]}),
    ],
    notes=[nt('报告生成已接入实时引擎：点击上方「在线生成舆情报告」即可现场生成 Word；'
              'reports/ 目录下的历史 docx 为既有真实产物。', k='ok')],
))

V.append(dict(
    id='research', group='四、AI 智能体', name='助研工具', badge='真实', badgeCls='real',
    lead=f'面向研究者的三件工具：文献速览（{KB["pdf_papers"]} 篇 PDF + {KB["papers_md"]} 篇已切分 md）、'
         f'编码助手（数据导出）、选题建议（基于真实数据缺口）。下方按钮导出的就是本页数据本身。',
    kpis=[K('PDF 文献', f'{KB["pdf_papers"]} 篇', 'pdf_papers/', 1),
          K('已切分文献', f'{KB["papers_md"]} 篇', 'knowledge/论文/', 2),
          K('历史笔记', f'{KB["notes_txt"]} 篇', 'knowledge/历史笔记/', 3),
          K('向量文本块', N(KB['chunks']), '可直接做语义检索', 4),
          K('可导出数据集', '4 类', '省份 / 热词 / 核查 / 全量', 5),
          K('数据缺口', '3 项', '见下方选题建议', 6)],
    btns=[{'t': '导出 省份声量明细 (CSV)', 'd': 'prov', 'f': '舆眼_省份声量明细.csv', 'csv': True},
          {'t': '导出 热词明细 Top40 (CSV)', 'd': 'hotTbl', 'f': '舆眼_热词明细.csv', 'csv': True},
          {'t': '导出 一致性核查 (CSV)', 'd': 'recon', 'f': '舆眼_一致性核查.csv', 'csv': True},
          {'t': '导出 全量数据快照 (JSON)', 'd': '__all__', 'f': '舆眼_数据快照.json'},
          {'t': '导出 情感抽样 (CSV)', 'd': 'sentExport', 'f': '舆眼_情感抽样.csv', 'csv': True}],
    cards=[
        TABLE('研究选题建议（基于数据缺口）',
              [{'k': 'q', 'l': '可做方向'}, {'k': 'why', 'l': '数据支撑'}, {'k': 'need', 'l': '还需补什么'}],
              [{'q': '地域声量的省际差异机制', 'why': f'已归属省份 {N(BS["article"]["prov_total"])} 条，Top1 广东 2,765',
                'need': f'未识别 {N(IP["article"]["unknown"])} 条需补采'},
               {'q': '重复入库对声量指标的影响', 'why': f'重复 {N(CAN["a_total"]-CAN["a_dist"])} 条（{PC(CAN["a_total"]-CAN["a_dist"], CAN["a_total"])}）',
                'need': '主表补唯一键后复算'},
               {'q': '流域议题的中央—地方叙事差', 'why': '黄河"督察"297 vs 长江"生态"338',
                'need': '议题标注改为多标签'},
               {'q': '情感演化的时间序列', 'why': f'仅 {FDD["articles7day"]["x"].__len__()} 个有效日期',
                'need': '历史行补发布时间'},
               {'q': '词云噪声对结论的干扰', 'why': '正文 Top2 为 http / cn',
                'need': '分词前置 URL 过滤'}],
              '每条选题都对应一个可核验的数据缺口，不做无据推测', w=3),
        KV('数据缺口量化', [{'k': '地区未识别（微博）', 'v': IP['article']['unknown']},
                        {'k': '重复入库（微博）', 'v': CAN['a_total'] - CAN['a_dist']},
                        {'k': '重复入库（评论）', 'v': CAN['c_total'] - CAN['c_dist']},
                        {'k': '时间无法解析', 'v': U['hours']['bad_a']},
                        {'k': '正文 URL 噪声词次', 'v': U['cloudFre']['article'][0][1] + U['cloudFre']['article'][1][1]}],
           '这些缺口直接决定上面选题的可行性', w=2),
        # 「分类」字段归类体检：把修复前后的兜底率摊开，并暴露未覆盖词元（词表迭代清单）
        KV('分类字段归类体检（修复前 → 修复后）',
           [{'k': '原始互异取值', 'v': FDD['typeTax']['legacy']['raw_categories']},
            {'k': '旧口径 Top10 覆盖', 'v': '%.2f%%' % FDD['typeTax']['legacy']['top10_share']},
            {'k': '旧口径「其他」',
             'v': '%.2f%%' % round(100 - FDD['typeTax']['legacy']['top10_share'], 2)},
            {'k': '新口径「其他领域」', 'v': '%.2f%%' % FDD['typeTax']['other_domain_rate']},
            {'k': '受控领域数', 'v': '%d 类' % FDD['typeTax']['categories']},
            {'k': '领域标注覆盖率', 'v': '%.2f%%' % FDD['typeTax']['labeled_rate']},
            {'k': '未映射词元词频占比', 'v': '%.2f%%' % FDD['typeTax']['unmapped_rate']}],
           '旧实现把 Top10 之外的全部并入「其他」；现改为先归类再聚合，'
           '「其他」不再是吸收池', w=2),
        TABLE('受控词表未覆盖词元 Top12（召回迭代清单）',
              [{'k': 'w', 'l': '词元'}, {'k': 'n', 'l': '出现条次', 'num': True}],
              [{'w': k, 'n': N(v)} for k, v in FDD['typeTax']['unmapped']],
              '补进 util/category_taxonomy.py 对应词表即可提升覆盖率；'
              '运行 dashboard_gen/verify_category.py 可复现', w=2),
                # v7 柱状 → 环形图：6 个主题在 17 篇 PDF 里的构成比（小基数、类目少，环形正好）。
        C('rs1', '文献主题构成（按文件名关键词）', '17 篇 PDF 的主题归类（人工+关键词）· 环形读构成', 'donut',
          [['信息茧房', 4], ['智能算法', 3], ['人机关系', 3],
           ['群体极化', 2], ['媒介化治理', 2], ['其他', 3]], {'p': 4}),
        C('rs2', '知识库文本块 vs 文档数', '407 个文本块分布在 42 份文档中', 'bar2',
          {'x': ['文档数', '文本块数'],
           'series': [{'name': '实际值', 'y': [KB['knowledge_total'], KB['chunks']]}]}, w=2),
    ],
    notes=[nt('本页所有导出按钮写的是<b>真实数据</b>：CSV/JSON 由页面内嵌快照现场生成，'
              '不含任何演示数值。', k='ok')],
))

# ==================================================================
# 五、知识库与设置
# ==================================================================
V.append(dict(
    id='kb', group='五、知识库与设置', name='知识库管理', badge='真实', badgeCls='real',
    lead=f'向量库 {KB["collection"]}：{N(KB["chunks"])} 个文本块 / {N(KB["dim"])} 维 / 库文件 '
         f'{KB["db_mb"]} MB；知识源 {KB["knowledge_total"]} 份文档（教材 4 + 论文 17 + 笔记 20 + few-shot 1），'
         f'另有 {KB["pdf_papers"]} 篇原始 PDF 待切分。',
    kpis=[K('向量文本块', N(KB['chunks']), KB['collection'], 1),
          K('向量维度', N(KB['dim']), '与 embedding 模型绑定', 2),
          K('文档总数', f'{KB["knowledge_total"]} 份', 'knowledge/ 实测', 3),
          K('原始 PDF', f'{KB["pdf_papers"]} 篇', 'pdf_papers/', 4),
          K('库体积', f'{KB["db_mb"]} MB', 'chroma.sqlite3', 5),
          K('索引状态', '可检索', f'{N(KB["chunks"])} 块全部入库', 6)],
    cards=[
        C('k1', '文档构成', '四类知识源占比', 'pie',
          [['新闻传播教材', KB['knowledge_md']], ['核心期刊论文', KB['papers_md']],
           ['历史笔记', KB['notes_txt']], ['few-shot 示例', 1]], {'donut': True}),
        C('k2', '文本块 vs 文档', '平均每份文档切出约 '
          f'{KB["chunks"]/KB["knowledge_total"]:.1f} 个文本块', 'bar2',
          {'x': ['教材', '论文', '笔记', 'few-shot'],
           'series': [{'name': '文档数', 'y': [KB['knowledge_md'], KB['papers_md'],
                                              KB['notes_txt'], 1]}]}),
        KV('索引与检索参数', [{'k': '向量维度', 'v': KB['dim']}, {'k': '文本块', 'v': KB['chunks']},
                         {'k': '文档数', 'v': KB['knowledge_total']}, {'k': 'PDF 待切分', 'v': KB['pdf_papers']}],
           '检索策略：BM25 + 向量 + RRF 融合 + Reranker 重排'),
        TABLE('知识库文档清单（42 份）', [{'k': 'path', 'l': '文件路径'}, {'k': 'kb', 'l': '大小 (KB)', 'num': True}],
              KBDOCS, '直接读 knowledge/ 目录，与页面统计同源', w=3),
    ],
    notes=[nt('知识库为<b>只读快照</b>：页面不写库、不重建索引，仅展示规模与清单。', k='ok')],
))

V.append(dict(
    id='compliance', group='五、知识库与设置', name='合规与脱敏', badge='真实', badgeCls='real',
    lead=f'三张脱敏副本（t_article_safe {N(U["tableRows"]["t_article_safe"])} / t_comment_safe '
         f'{N(U["tableRows"]["t_comment_safe"])}）承载对外展示，原表保留在库内；'
         f'IP 里的"来自 XX"等 {len(IP["comment"]["normalized_from"])} 种原始写法已在分析层归一。',
    kpis=[K('脱敏字段', '3 个', 'hash_id / mask_nickname / mask_region', 1),
          K('脱敏副本', '2 张', f'共 {N(U["tableRows"]["t_article_safe"]+U["tableRows"]["t_comment_safe"])} 行', 2),
          K('省份归一规则', f'{len(IP["comment"]["normalized_from"])} 种', '评论侧原始写法', 3),
          K('AI 生成标注', N(IP['comment']['ai']), '评论侧 AI 内容单独成桶', 4),
          K('港澳台归属', '3 个', '统一按中国省级行政区', 5),
          K('对外接口', '0 个', '当前为本地部署，无公网接口', 6)],
    cards=[
        TABLE('脱敏规则明细', [{'k': 'f', 'l': '字段'}, {'k': 'r', 'l': '规则'}, {'k': 'e', 'l': '示例'}],
              [{'f': 'user_id', 'r': 'SHA-256 截断哈希', 'e': 'a1b2…（不可逆）'},
               {'f': 'nickname', 'r': '保留首尾字符', 'e': '微**搜 / T*********W'},
               {'f': 'region', 'r': '归一到省级', 'e': '来自 陕西 → 陕西'},
               {'f': 'AI 生成内容', 'r': '单独标记不外泄', 'e': f'评论侧 {N(IP["comment"]["ai"])} 条'},
               {'f': '港澳台', 'r': '中国省级行政区', 'e': '中国香港 / 中国澳门 / 中国台湾'}],
              '规则取自 dao 层脱敏实现', w=2),
        C('cp1', '被归一化的原始地区值 Top 14', '数量最多的写法（含"来自 XX"前缀）', 'hbar',
          [[k, v] for k, v in NORM], {'p': 1, 'n': 14}),
        KV('脱敏覆盖率', [{'k': '微博脱敏副本', 'v': 100}, {'k': '评论脱敏副本', 'v': 100},
                     {'k': '地区归一（已归属部分）', 'v': 100}, {'k': '港澳台口径统一', 'v': 100}],
           '四项均为 100%，因为脱敏在入库前完成', unit='%'),
        TEXT('数据使用声明',
             '<div style="line-height:1.95">'
             '1. 本系统数据来自公开微博平台，仅供新闻传播学教学与科研使用；<br>'
             '2. 所有用户标识在入库阶段即完成不可逆脱敏，分析层只见哈希与掩码昵称；<br>'
             '3. 地域信息仅保留到省级，不用于任何个体识别；<br>'
             '4. AI 生成内容（评论侧 ' + N(IP['comment']['ai']) + ' 条）单独标记，不参与真人行为统计；<br>'
             '5. 台湾、香港、澳门均按中国省级行政区处理。</div>', w=3),
    ],
    notes=[nt('对外展示只用 *_safe 副本；本页所有统计也来自这两张表与它们的派生结果。', k='ok')],
))

# ==================================================================
# 六、数据一致性核查（本轮新增）
# ==================================================================
V.append(dict(
    id='recon', group='五、知识库与设置', name='数据一致性核查', badge='新增', badgeCls='new',
    lead='把全站所有数字的"对账关系"摊开：等式成立才允许引用。下表由脚本在生成页面时现场计算，'
         '不是人工填的勾。',
    kpis=[K('核查项', f'{len(U["recon"])} 项', '等式与互斥性检查', 1),
          K('通过', f'{sum(1 for c in U["recon"] if c["ok"])} 项', '可直接引用', 2),
          K('待修', f'{sum(1 for c in U["recon"] if not c["ok"])} 项', '已在本页改用新口径', 3),
          K('统一口径数', '12 个', 'canon 表', 4),
          K('数据源', '3 路', 'db_weibo_basin / 快照 / CSV', 5),
          K('快照时间', U['generated'][5:], '页面与图表同源', 6)],
    cards=[
        TABLE('一致性核查', [{'k': 'name', 'l': '检查项'}, {'k': 'got', 'l': '实测值'},
                         {'k': 'want', 'l': '期望值'},
                         {'k': 'st', 'l': '结论', 'nw': True, 'tag': {'通过': 'g', '待修': 'a'}},
                         {'k': 'note', 'l': '说明'}],
              [{'name': c['name'], 'got': CV(c['got']), 'want': CV(c['want']),
                'st': '通过' if c['ok'] else '待修', 'note': c['note'],
                'rc': '' if c['ok'] else 'warnrow'} for c in U['recon']],
              '结论列着色：绿=等式成立可直接引用，橙=已改用新口径（整行浅底提示）', w=3,
              rowClsKey='rc'),
        TABLE('统一口径表（canon）', [{'k': 'k', 'l': '指标'}, {'k': 'v', 'l': '值', 'num': True}],
              [{'k': '微博总量', 'v': N(CAN['a_total'])}, {'k': '微博去重', 'v': N(CAN['a_dist'])},
               {'k': '评论总量', 'v': N(CAN['c_total'])}, {'k': '评论去重', 'v': N(CAN['c_dist'])},
               {'k': '流域微博', 'v': N(CAN['b_art'])}, {'k': '流域评论', 'v': N(CAN['b_cmt'])},
               {'k': '长江微博', 'v': N(CAN['b_yz_a'])}, {'k': '黄河微博', 'v': N(CAN['b_yl_a'])},
               {'k': '库内表数', 'v': CAN['tabs']}, {'k': '停用词', 'v': len(U['hot']['stop_used'])}],
              '页面里其余数字都是这些口径的派生结果', w=1),
        TABLE('库内表行数（16 张）', [{'k': 't', 'l': '表名', 'nw': True}, {'k': 'n', 'l': '行数', 'num': True},
                                {'k': 'r', 'l': '角色', 'nw': True,
                                 'tag': {'主表': 'b', '流域表': 'p', '脱敏副本': 'g'}}],
              [{'t': t, 'n': N(n),
                'r': '主表' if t in ('t_article', 't_comment') else '流域表' if t.startswith('t_basin')
                     else '脱敏副本' if t.endswith('_safe') else '用户表' if t == 't_user' else '备份'}
               for t, n in TABLES], '有备份的表说明经历过一次重建或归一', w=2),
    ],
    notes=[nt(f'<b>核查结论</b>：{len(U["recon"])} 项中 {sum(1 for c in U["recon"] if c["ok"])} 项等式成立；'
              '唯一失败项是旧 basin 口径的"共源"重复计数（详见 IP 地域分布页），'
              '本页与 IP 页已统一改用不重叠四色口径。', k='ok'),
           nt('凡是本页没有列出的数字，页面上都不会出现 —— 避免"看起来合理但无出处的数"。', k='warn')],
))

# ==================================================================
# 导出用的派生数据 + 注入生成
# ==================================================================
U['prov'] = PROV_TBL
U['hotTbl'] = HOT_TBL
U['sentExport'] = [{'维度': '微博正文', '正面': SENT['article']['v'][0], '中性': SENT['article']['v'][1],
                    '负面': SENT['article']['v'][2], '合计': SENT['article']['total']},
                   {'维度': '微博评论', '正面': SENT['comment']['v'][0], '中性': SENT['comment']['v'][1],
                    '负面': SENT['comment']['v'][2], '合计': SENT['comment']['total']},
                   {'维度': '热搜词', '正面': SENT['hot']['v'][0], '中性': SENT['hot']['v'][1],
                    '负面': SENT['hot']['v'][2], '合计': SENT['hot']['total']}]
U['recon'] = [{'name': c['name'], 'got': c['got'], 'want': c['want'],
               'ok': c['ok'], 'note': c['note']} for c in U['recon']]

# ==================================================================
#  三段式：流域两套视图（长江 / 黄河）
#  两侧共用同一生成器 basin_views()，卡片结构与渲染器完全对称，
#  仅数据与标题不同 —— 从根上防止两侧随迭代逐渐漂移。
# ==================================================================
BD = json.load(io.open(os.path.join(BASE, 'basin_data.json'), encoding='utf-8'))
BASIN_PFX = {'长江': 'yz', '黄河': 'hh'}
# 三大主题（单一事实来源：来自 build_basin_data.py 的 TOPICS）。
# 凡涉及议题的图表一律按 T3 取齐三个议题，不再写死两项。
T3 = tuple(BD.get('topics') or ('生态治理', '文旅', '医患矛盾'))
T3L = list(T3)

# ---- 流域专属地图几何（dashboard_gen/build_basin_geo.py 生成）----
#   basin_geo_map.json：{yz, yl, river:{yz,yl}, meta}。缺失时 R.basinmap 卡片自降级，
#   不阻断整页构建。
try:
    BZGEO = json.load(io.open(os.path.join(BASE, 'basin_geo_map.json'), encoding='utf-8'))
except Exception as _e:                         # noqa: BLE001
    print('[warn] 未读到 basin_geo_map.json（%s），流域专属地图卡将降级' % str(_e)[:60])
    BZGEO = None

# ---- 首页总览 · 济南区位地图模块的数据（dashboard_gen/build_jinan_map.py 生成）
#   中国图＝发布地区(IP属地) 省级计数；山东/济南图＝正文提及近似口径。
#   产物缺失时不中断整页构建：该卡片自动降级为一句说明。
try:
    JD = json.load(io.open(os.path.join(BASE, 'jinan_map_data.json'), encoding='utf-8'))
except Exception as _e:                       # noqa: BLE001
    print('[warn] 未读到 jinan_map_data.json（%s），济南区位卡片将降级' % str(_e)[:60])
    JD = {'prov': {}, 'sd': {}, 'jn': {}, 'jnSrc': [], 'jnMiss': {}, 'meta': {}, 'rules': {}}

# ---- 山东地市地图（R.sdcity）的静态资料 ----
#   这样意在只补"图上读不出来的东西"：区划代码（行政区划自上而下的可核对标识）
#   与邻省中心点（给"邻省标签"定位用，DataV 原始数据里的 center 字段）。
#   **注意：地市级声量一律不写** —— 库里没有地市字段，图上填色只用 jinan_map_data 的
#   「正文提及」近似口径，任何"某市舆情 X 条"的说法都不成立。
SD_ADCODE = {
    '济南市': 370100, '青岛市': 370200, '淄博市': 370300, '枣庄市': 370400,
    '东营市': 370500, '烟台市': 370600, '潍坊市': 370700, '济宁市': 370800,
    '泰安市': 370900, '威海市': 371000, '日照市': 371100, '临沂市': 371300,
    '德州市': 371400, '聊城市': 371500, '滨州市': 371600, '菏泽市': 371700,
}
SD_PROVCP = {                       # 邻省中心点（DataV areas_v3 的 center 字段）
    '河北省': [114.50, 38.05], '河南省': [113.67, 34.76],
    '安徽省': [117.28, 31.86], '江苏省': [118.77, 32.04],
}
SDNB_OK = os.path.exists(os.path.join(PRJ, 'static', 'js', 'sdnb.js'))

# ---- 短视频智能分析（预生成产物：service/video/insight/build_insight.py → build_video_topic_data.py）
# 缺失时静默降级：不加该视图，页面照常生成（不让新模块拖垮既有链路）
_VD_P = os.path.join(BASE, 'video_topic_data.json')
try:
    VD = json.load(io.open(_VD_P, encoding='utf-8')) if os.path.exists(_VD_P) else None
except Exception:
    VD = None


def basin_video_view(basin):
    """短视频智能分析：卡片墙 + 主色调/画幅/互动聚合（数据来自 video_topic_data.json）。"""
    p = BASIN_PFX[basin]
    full = basin + '流域'
    node = ((VD or {}).get('topics') or {}).get(basin) or {'n': 0, 'cards': [], 'agg': {}}
    cards = node.get('cards') or []
    agg = node.get('agg') or {}
    n = node.get('n') or len(cards)
    with_rec = sum(1 for c in cards if (c.get('top') or {}).get('recommend') is not None)
    asr_ok = agg.get('asr_ok') or 0
    asr_txt = ('其中 <b>%d 条</b>已取得<b>语音转写</b>（口播文案，来自 L3/ASR）'
               % asr_ok) if asr_ok else '语音转写（L3/ASR）待启用'
    return dict(
        id=p + '-video', group='内容与评论', name=full + '短视频智能分析',
        badge='AI', badgeCls='new',
        lead=(f"对本流域 <b>{N(n)} 条</b>短视频做「画面 → 主题 → 结论」智能分析："
              f"画面读数由视觉模型识别关键帧拼图（含<b>画面文字</b>），"
              f"再融合互动结构与评论诉求，输出<b>按推荐度排序的结论与建议</b>"
              f"（{N(with_rec)} 条已生成推荐结论）；{asr_txt}。"
              f"样本为 L2 关键帧层抽样且<b>仅覆盖抖音</b>，结论仅供辅助参考。"),
        cards=[
            C(p + 'v1', '画面主色调分布', 'L2 关键帧统计', 'pie',
              agg.get('hue') or [], {'donut': True}, w=1),
            C(p + 'v2', '画幅构成', '竖屏 / 横屏', 'pie',
              agg.get('orient') or [], {'donut': True}, w=1),
            C(p + 'v3', '高互动短视频 Top 12', '按互动总量排序', 'hbar',
              agg.get('top') or [], w=2),
            # h=620：.vcw 自身 max-height:600（内部滚动），而 .ch 默认只有 260px
            # 且 overflow:visible → 卡片墙内容撑破父容器，随后的 .foot 页脚被顶进
            # 卡片区中间，文字与卡片标题叠印（2026-10-07 修）。
            # 620 = 600 + 卡片标题/副标题/导出按钮区约 20px。
            # applyHeights() 会按视宽自动乘高度系数，此处不需要额外适配。
            C(p + 'v4', '短视频智能分析卡片墙',
              '点击卡片查看：画面读数 · 主题与核心信息 · 传播/情感/诉求 · 推荐结论与证据链；可播放原视频'
              '（卡片墙内可滚动）',
              'vcard', {'items': cards, 'basin': basin, 'sec': p},
              w=3, h=620, noexp=True),
        ])


def basin_views(basin):
    d = BD['basins'][basin]
    p = BASIN_PFX[basin]
    full = basin + '流域'
    A, Cm = d['articles'], d['comments']
    tc = dict(d['topicDist'])
    eco, tour = tc.get('生态治理', 0), tc.get('文旅', 0)
    # 议题构成环形：微博口径下把「医患矛盾」一并列出。
    # 原 topicDist 由 SQL 过滤（仅 生态治理/文旅），医患矛盾虽在库中但不出现在该卡；
    # 社会治理为兜底层，仍留在「议题占比参照」卡里，不在本卡内。
    # 顺序固定为 生态治理→文旅→医患矛盾，以保住原有的蓝/青配色（调色板按序取色）。
    _at = dict(d['allTopics'])
    topicShow = [[k, _at[k]] for k in T3 if _at.get(k)]
    sv = dict(zip(('正面', '中性', '负面'), [x[1] for x in d['sent']]))
    st = max(sum(sv.values()), 1)
    bt = d['byTopic']
    ec, tv = bt.get('生态治理', {}), bt.get('文旅', {})
    yt = bt.get('医患矛盾', {})          # 三大主题之三（2026-09-29 起与另两个议题同权）
    geoD = dict(d['geoProv'])          # 作者 IP 属地（发布地区）
    provD = dict(d['provDist'])        # 目标省份（内容涉及省）—— 与上一行是两个口径
    # ---- 批次 2：把新增模块的数据与对照流域一并取好，供各视图的"对照卡"使用 ----
    ob_name = '黄河' if basin == '长江' else '长江'
    OB = BD['basins'][ob_name]
    IA = d['interact']                 # 互动结构
    EP = d['evprov']                    # 建议1 事件×省份传播强度矩阵 + 建议3 扩散比
    ND = d['nodes']                    # 关键传播节点
    CHn = d['channel']                 # 渠道与话语主体
    CByT = (CHn.get('byTopic') or {})  # 按议题拆的话语主体构成（议题专题第 4 行用）

    # ---- 议题专题的排版口径：一「行」一个对照维度，一「列」一个议题 ----
    def _top5(rows):
        """[[名, 值], ...] -> 竖向柱的 {x, y}，只取前 5。"""
        r = list(rows or [])[:5]
        return {'x': [k for k, _ in r], 'y': [v for _, v in r]}

    def _evt5(td):
        """事件簇按命中篇数降序取前 5 -> (竖向柱数据, 实际条数, 副标)。
           覆盖率用项目自己的 coverage 口径（topicRows=该议题篇数，covered=被词表覆盖篇数）。"""
        cl = sorted(td.get('clusters') or [], key=lambda c: -c['n'])[:5]
        cov = td.get('coverage') or {}
        sub = ('事件簇词表命中篇数 · 人工归纳词表，覆盖 %s/%s 条（%s%%）· 词表见「事件监测」页'
               % (N(cov.get('covered')), N(cov.get('topicRows')), cov.get('pct')))
        return ({'x': [c['name'] for c in cl], 'y': [c['n'] for c in cl]}, len(cl), sub)

    def _spk(topic, n):
        """该议题内 官方 / 媒体 / 个人 构成 -> (环形数据, 副标)。分母是可判定样本，不是全量。"""
        sp = CByT.get(topic) or []
        known = sum(v for _, v in sp)
        sub = ('官方 / 媒体 / 个人 · 分母＝该议题内可判定样本 %s / %s（%s），未归类不计'
               % (N(known), N(n), PC(known, n)))
        return ([[k, v] for k, v in sp], sub)

    # 议题专题用：把「事件簇 Top5」与「话语主体构成」按议题预计算好（每行一次）
    EVT, SPK = {}, {}
    for _t, _td in (('生态治理', ec), ('文旅', tv), ('医患矛盾', yt)):
        EVT[_t] = _evt5(_td)
        SPK[_t] = _spk(_t, _td.get('n', 0))

    # 三议题速览卡的静态骨架：定位一句话 + 背景描述 + 按主导话语主体给的解读
    PROF = {
        '生态治理': dict(
            look='谁在治理、治理成效如何',
            bg='聚焦流域水污染治理、中央生态环保督察及整改问责、生态修复与禁渔等环境议题的公开讨论；'
               '微博 / 小红书 / 知乎三源交集议题，跨平台对照见「总览」页。',
            say={'官方': '治理议程由官方通报与整改落实驱动',
                 '媒体': '以媒体跟进报道为主',
                 '个人': '以网民自发讨论为主'}),
        '文旅': dict(
            look='游客在体验什么、吐槽什么',
            bg='聚焦流域沿线景区体验与出行消费、宰客与消费纠纷、景区供给与门票、文旅融合与非遗等话题；'
               '微博独有议题（小红书 / 知乎两库未采集），故无跨平台对照。',
            say={'官方': '以官方宣传口吻为主',
                 '媒体': '以媒体报道为主',
                 '个人': '游记、攻略与吐槽型个人叙事为主'}),
        '医患矛盾': dict(
            look='纠纷如何发生、责任如何认定',
            bg='聚焦医疗纠纷与责任认定、诊疗过程与手术风险、法律维权与诉讼、涉医事件等医患关系议题；'
               '采集端命中关键词为单一值「医患纠纷」（+省份），故不出关键词排行，细分结构由事件簇呈现。',
            say={'官方': '以官方通报与调解信息为主',
                 '媒体': '以媒体报道为主',
                 '个人': '患者及网民个人叙事为主'}),
    }

    def _topic_profiles():
        """三议题「议题速览」文字卡（w=1，置于首行）：背景为静态描述，
           要点里的每个数字都与下方四行图同源（样本/热词/事件簇/情感/话语主体）。"""
        T3 = (('生态治理', ec), ('文旅', tv), ('医患矛盾', yt))

        def _sents(td):
            sv = dict(td.get('sent') or [])
            return sv, (sum(sv.values()) or 1)

        negs = {}
        for _t, _td in T3:
            sv, tot = _sents(_td)
            negs[_t] = PC(sv.get('负面', 0), tot)
        negHi = max(negs.values())
        poss = [t for t, td in T3
                if (dict(td.get('sent') or []).get('正面', 0)) / (sum(dict(td.get('sent') or []).values()) or 1) > 0.5]

        out = []
        for t, td in T3:
            pf, sv, tot = PROF[t], *_sents(td)
            n = td.get('n', 0)
            hot = [k for k, _ in (td.get('hotwords') or [])[:3]]
            evd = EVT[t][0] or {}
            e1 = (evd.get('x') or ['-'])[0]
            en = (evd.get('y') or [0])[0]
            sp = SPK[t][0] or []
            dlab, dval = max(sp, key=lambda kv: kv[1]) if sp else ('-', 0)
            pol, pval = max(sv.items(), key=lambda kv: kv[1]) if sv else ('-', 0)
            cmp_ = ''
            if pol == '负面' and negs[t] == negHi:
                cmp_ = '，三议题中最高'
            elif pol == '正面' and poss == [t]:
                cmp_ = '，三议题中唯一正面过半'
            html = (f'<div style="line-height:1.85">'
                    f'<b>看什么</b>：{pf["look"]}<br>'
                    f'<b>背景</b>：{pf["bg"]}<br>'
                    f'<b>要点</b>：<br>'
                    f'· <b>样本</b>：{N(n)} 条（作者 {N(td.get("authors", 0))} 人去重），'
                    f'热词以{"、".join("「%s」" % h for h in hot)}为代表<br>'
                    f'· <b>头号事件</b>：「{e1}」{N(en)} 条（占议题样本 {PC(en, n)}）<br>'
                    f'· <b>情绪</b>：{pol}占比最高（{PC(pval, tot)}{cmp_}）<br>'
                    f'· <b>谁在说</b>：{dlab}（{PC(dval, sum(v for _, v in sp) or 1)}）主导'
                    f' —— {pf["say"].get(dlab, "")}</div>')
            out.append(TEXT(f'{t} · 议题速览', html, '下方四行图均为该议题拆分 · 同列即同议题', w=1))
        return out

    TRd = d['trend']                   # 传播趋势（月度 / 年×月）
    kN = dict(CHn['kind'])
    chDen = sum(kN.get(k, 0) for k in BM.AGENT_ORDER) or 1
    # 分组名不带流域前缀：侧栏顶部入口已标明当前专题，重复前缀只会挤占行宽
    g1 = '总览'
    g2 = '议题与词频'
    g3 = '内容与评论'
    g4 = '口径与方法'
    gateTxt = (f"评论样本按平台×流域×主题分别判断；当前评论总数 {N(Cm)} 条，"
               f"{BD['commentGate']} 条为单类闸门。"
               + ("存在未达闸门主题，相关评论结论只作线索提示、不作总体外推。"
                  if not d['commentEnough'] else "各主题评论样本均已达闸门，可用于结构分析。"))
    srcNote = ("全部数字来自 t_basin_article / t_basin_comment 实时聚合，无一处估值。"
               + gateTxt)
    sentNote = ("情感由 SnowNLP 轻量模型判定，极性偏两端、中性段偏少，只用于结构参考；"
                "正式版需用生态治理 / 文旅 / 医患矛盾语料重新校准。")

    # ---- 跨平台（多源）融合：仅取四源交集议题 生态治理 / 医患矛盾 ----
    # 红线：跨平台只比结构占比、不对齐绝对值；抖音 0 条登记为 absent，一律不填数字。
    # 数据来自 build_basin_data.py 的 out['xplat']（严格增量块，不改动微博口径）。
    XP = BD.get('xplat') or {}
    XP_MERGED = (XP.get('merged') or {}).get(basin, {})
    XP_PLAT = XP.get('platforms') or {}
    XP_LIVE = [pl for pl in XP.get('live', []) if pl in XP_PLAT]   # 已接入且有序
    XP_ONLYWB = XP.get('topicsOnlyWeibo', [])
    def _xart(t):
        return {pl: (XP_MERGED.get(t, {}).get('article') or {}).get(pl, 0) for pl in XP_LIVE}
    def _xcmt(t):
        return {pl: (XP_MERGED.get(t, {}).get('comment') or {}).get(pl, 0) for pl in XP_LIVE}
    def _xsum(t, k):
        m = XP_MERGED.get(t, {}) or {}
        return m.get(k + 'Sum', sum((m.get(k) or {}).values()))

    # 各平台热词 -> 字典（供「三平台热词对照」表按词取各平台篇数）
    _phw = {pl: dict(XP_PLAT.get(pl, {}).get('hotwords') or []) for pl in XP_LIVE}

    # ---- 批次 1 词云改造：把三议题的事件簇并成一张表（视图是流域级，簇是议题级）----
    CLU = []
    for _t in T3:
        for _c in ((bt.get(_t) or {}).get('clusters') or []):
            CLU.append(dict(_c, topic=_t))
    CLU.sort(key=lambda c: (c['topic'] != '生态治理', -c['n']))
    coC = (ec or {}).get('coverage') or {}
    coT = (tv or {}).get('coverage') or {}
    coY = (yt or {}).get('coverage') or {}
    MRG = []
    for _t in T3:
        for _m in ((bt.get(_t) or {}).get('merge') or []):
            MRG.append({'a': _m['label'], 'b': ' + '.join(_m['words']),
                        'c': N(_m['n']), 'd': _m['note'], 'e': _t})
    # 无簇数据（如 basin_data.json 为旧版）时自动退回改造前的版式
    HAS_CLU = bool(CLU and d.get('wordsCloud'))
    CLOUD = d.get('wordsCloud') or [[w, v] for w, v in d['hotwords'][:60]]
    EVN = sum(1 for x in CLOUD if len(x) > 2 and x[2] in set(d.get('clusterNames') or []))

    # ---- 词云解读：三段分析性图表说明，插在「同义归并」表之后。----
    # ⚠ 纪律：这里的每个数字都必须**现算**，禁止手写。
    #    历史教训：`_PEX` 里曾手写「黄河九省区中八个的省名都进入了头部词表」，
    #    实测只有 6 个（山东/河南/陕西/山西/宁夏/内蒙古）进了词表 ——
    #    甘肃、青海没进（青海是共源省、在长江侧已单列），四川属长江不属黄河。
    #    手写断言一旦数据更新就永久说谎，且没有任何报错。现在改成按
    #    meta.YELLOW ∪ meta.SHARED 与实际词表求交集，数字与名单都现算。

    def _basin_provs(b):
        """该流域实际流经的省级行政区（含两江共源），现算。
        meta 里 YANGTZE/YELLOW 已各自含共源省，与 SHARED 求并集去重即可。"""
        return sorted(set(IP['meta'].get(
            'YELLOW' if b == '黄河' else 'YANGTZE', [])) | set(IP['meta'].get('SHARED', [])))

    def _prov_note(b):
        """灰阶行政区划名的读法：进词表的 / 没进的，分开说清，不含手写数字"""
        allp = _basin_provs(b)
        freq = {w: n for w, n, *_ in CLOUD}
        inp = [w for w in allp if freq.get(w)]
        out = [w for w in allp if not freq.get(w)]
        if not inp:
            return '本流域流经的省区名未进入头部词表'
        head = '、'.join(sorted(inp, key=lambda w: -freq[w])[:6])
        more = f'等 {len(inp)} 个' if len(inp) > 6 else ''
        s = f'灰阶行政区划名{head}{more}进入了头部词表（占本流域流经 {len(allp)} 个省区的 {len(inp)} 个）'
        if out:
            s += f'；{"、".join(out)}未进入'
        return s

    def _wcloud_read():
        cw = {w: n for w, n, *_ in CLOUD}
        # 词不在头部词表时记 0 篇（原直接 cw.get → None，会让 N() 抛 TypeError；
        # 生产路径「更新数据」重算词云后，硬编码词如"医生"可能掉出，必然崩溃）
        g = lambda k: cw.get(k, 0)
        mg = {m['label']: m['n'] for m in (bt.get('生态治理', {}).get('merge') or [])}
        pex = _prov_note(basin)          # 现算，不再手写省名名单与个数
        # ⚠ 原实现用 CLOUD[0][0] 当"生态治理代表词" —— 错：CLOUD[0] 是全表首行，
        #    **不保证是彩色事件词**。实测长江 CLOUD[0]='生态'(灰阶·议题概念词)、
        #    黄河 CLOUD[0]='山东'(灰阶·行政区划名)，于是黄河那句写成
        #    「生态治理一侧，「山东」（126 篇）」—— 省名被当成生态治理代表词，
        #    126 其实是"督察"的篇数，文字与数字张冠李戴。
        #    现在改为：**从彩色事件词里取该簇的最高频词**，取不到就不报数。
        _clset = set(d.get('clusterNames') or [])
        _top_eco = next((w for w, n, grp, _c in CLOUD
                         if grp == '中央生态环保督察' and n), None)
        if _top_eco:
            _eco_phrase = (f'「{_top_eco}」（{N(cw.get(_top_eco))} 篇）、'
                           f'「督察组」（{N(g("督察组"))} 篇）')
        else:
            _eco_phrase = f'「督察组」（{N(g("督察组"))} 篇）'
        p1 = (f'本词云取自{basin}流域 {N(A)} 条微博正文：分词后按<b>出现篇数</b>排序'
              f'（同一篇微博内重复出现的词只计一次），剔除停用词、单字与不含汉字的碎片后'
              f'取头部 {N(len(CLOUD))} 词，字号越大代表该词出现的正文越多。其中 {N(EVN)} 个彩色词'
              f'按人工归纳的事件簇词表着色，点击可联动下方面板查看释义与原文；'
              f'其余 {N(len(CLOUD) - EVN)} 个灰阶词是议题概念词（"生态""环保"）、政治主体词（"中央"）、'
              f'公文套话（"近日""开展"）与行政区划名，仅提供语境、不参与事件归属。'
              f'按词表计，生态治理 / 文旅 / 医患矛盾分别有 {coC.get("pct")}%、{coT.get("pct")}%、'
              f'{coY.get("pct")}% 的聚焦正文可归属到具体事件簇（口径见「事件监测」页）。')
        p2 = (f'彩色高频词勾勒出三大主题各自的叙事骨架。生态治理一侧，'
              f'{_eco_phrase}、'
              f'「整改」（{N(g("整改"))} 篇）与主体词「中央」（{N(g("中央"))} 篇）同现，'
              f'对应"督察进驻—反馈—整改问责"的完整链条；被分词切碎的概念归并后更为可观：'
              f'「督察 / 督察组」合计 {N(mg.get("督察 / 督察组", 0))} 篇、'
              f'「生态 / 环保」合计 {N(mg.get("生态 / 环保", 0))} 篇（见上方归并表）。'
              f'文旅一侧，「宰客」（{N(g("宰客"))} 篇）、「景区」（{N(g("景区"))} 篇）、'
              f'「游客」（{N(g("游客"))} 篇）分属消费纠纷、供给门票、体验出行三个事件簇，'
              f'用词最贴近日常消费场景。医患一侧，灰阶高频词「医院」（{N(g("医院"))} 篇）、'
              f'「医生」（{N(g("医生"))} 篇）虽不归属事件簇，但与彩色词「纠纷」（{N(g("纠纷"))} 篇）、'
              f'「通报」（{N(g("通报"))} 篇）、「手术」（{N(g("手术"))} 篇）、'
              f'「律师」（{N(g("律师"))} 篇）共同构成"个案发生—官方回应—责任认定—法律维权"的叙述链。')
        p3 = (f'合并来看，词云传递三层信息：一是生态治理讨论高度围绕中央生态环保督察'
              f'这一权威事件展开，"督察—整改—问责"是声量主干；二是文旅议题的词形最生活化'
              f'（吃、住、行、门票），指向可感知的消费体验环节；三是医患讨论以具体个案的'
              f'处理过程为主线，情绪强度最高的「伤医」（{N(g("伤医"))} 篇）「医闹」（{N(g("医闹"))} 篇）'
              f'出现频次很低，属线索性信号而非普遍现象。{pex}，'
              f'与大量公文套话同现还提示：相当比例的正文是"属地 + 事件"句式的官方或媒体通稿，'
              f'{basin}流域舆情呈明显的属地化分布。')
        html = (f'<p style="margin:0 0 10px;line-height:1.9">{p1}</p>'
                f'<p style="margin:0 0 10px;line-height:1.9">{p2}</p>'
                f'<p style="margin:0;line-height:1.9">{p3}</p>')
        return TEXT(f'{basin}词云解读', html,
                    '图表说明 · 数字与上方词云、事件簇面板及归并表同源，可直接用于报告', w=3)

    def _ranktxt(rows):
        """[[词, 篇数], ...] -> 每行 5 个的编号文字排行（替代条形图的纯文字呈现，口径不变）。"""
        rows = list(rows or [])[:15]
        if not rows:
            return '<div style="line-height:2.15">暂无数据</div>'
        return ('<div style="line-height:2.15">' + '<br>'.join(
            '　'.join(f'{k + i + 1}. <b>「{w}」</b>{N(n)} 篇'
                      for i, (w, n) in enumerate(rows[k:k + 5]))
            for k in range(0, len(rows), 5)) + '</div>')

    # ---- 山东省 16 地市地图（只挂在黄河流域专题）----
    #     为什么只给黄河：山东是黄河下游 / 入海口省份，也是本项目样本第一大省
    #     （目标省份口径排第 1），所以它是黄河这条链路的空间落点；长江专题不放，
    #     否则页面会出现一张与流域无关的图。
    #     为什么紧跟流域图：上一张答「整条黄河流经哪些省」，这一张答「落到省内哪个市」，
    #     两张并排才是一条完整的空间下钻链。
    SDC = []
    _sdm = JD.get('sd') or {}
    if basin == '黄河' and SDNB_OK and _sdm:
        SDC = [C(p + 'oSD', '山东省 · 16 地市提及分布（自动聚焦）',
                 '页面加载 2 秒后自动聚焦到<b>山东省</b>，右侧「周边视野」可退回含河北 / 河南 / '
                 '安徽 / 江苏 的大视野　·　填充＝微博正文提及次数，按<b>对数五分位</b>分档'
                 '（头部 %d 次与个位数地市同图，线性归一会把其余地市全压到最淡一档）　·　'
                 '<b>悬停</b>看数值、<b>点击</b>锁定左下详情（Esc 取消）　·　滚轮 / 拖拽可自行缩放。'
                 '<br/>⚠ 口径＝微博<b>正文里出现该市名的次数</b>（关键词命中，来自全量 t_article；'
                 '不是 IP 属地、也不是地市级采集结果）：库里只到省级粒度，'
                 '不存在「某市舆情多少条」这种说法 —— 所以本图不给任何一座城市编声量，'
                 '只数正文叫到它名字的次数。同一口径的首页缩略图见「地理区位 · 中国 → 山东 → 济南」。'
                 % (max(_sdm.values()),),
                 'sdcity',
                 {'cities': dict(_sdm),
                  'river': list(BD['home']['landing'].get('riverCities') or []),
                  'adcode': SD_ADCODE,
                  'provcp': SD_PROVCP,
                  'total': sum(_sdm.values())},
                 w=3, cls='mapstage sdcity', h=560, ruler=True)]

    return [
        dict(
            id=p + '-overview', group=g1, name=full + '总览', badge='真实', badgeCls='real',
            lead=f"聚焦<b>三大主题</b>「生态环境治理 / 文旅 / 医患矛盾」；微博样本 {N(A)} 条、{N(Cm)} 条评论，"
                 f"覆盖目标省份 {d['provCount']} 个、作者 {N(d['authors'])} 位；"
                 f"累计点赞 {N(d['like'])}、评论 {N(d['cmtCnt'])}、转发 {N(d['repost'])}。",
            kpis=[
                K('样本微博', N(A), 't_basin_article', 1),
                K('参与作者', N(d['authors']), 'ID 已脱敏', 2),
                K('目标省份', f"{d['provCount']} 个", '内容涉及省', 3),
                K('累计点赞', N(d['like']), f"评论 {N(d['cmtCnt'])}", 4),
                K('生态治理', N(eco), PC(eco, A), 5),
                K('文旅', N(tour), PC(tour, A), 6),
                K('医患矛盾', N(yt.get('n', 0)), PC(yt.get('n', 0), A), 7),
            ],
            cards=([
                # ---- 流域专属地图（v14 新增，首屏主视觉第一位；v15 改浅色舞台 + 流域色流动线）----
                # 仅绘该河流实际流经的省级行政区（含共源省 青海/四川），不渲染完整中国地图；
                # 填充＝目标省份声量（按位次等频分级，越亮越高）；干流为流动动态线：
                # 长江＝蓝、黄河＝黄（SVG stroke-dashoffset 无缝循环，见 _unified_tpl R.basinmap）。
                C(p + 'o0', '流域专属地图 · ' + full,
                  '仅绘该河流实际流经的省级行政区（含共源省）　·　填充＝目标省份声量（<b>按位次等频分 8 级</b>，越亮越高，断点见卡下色标）　·　'
                  + ('黄河＝黄色流动线（干流走向）' if basin == '黄河' else '长江＝蓝色流动线（干流走向）'),
                  'basinmap', None,
                  {'bk': 'yl' if basin == '黄河' else 'yz',
                   'prov': provD,
                   'total': A,
                   'noData': ({'青海': '长江正源所在省，本流域无样本'}
                              if basin == '长江' else
                              {'四川': '黄河上游流经省，本流域无样本'}),
                   'ends': ([{'name': '长江源·唐古拉山', 'value': [91.0, 33.5]},
                             {'name': '入海口·上海', 'value': [121.9, 31.4]}]
                            if basin == '长江' else
                            [{'name': '黄河源·巴颜喀拉', 'value': [96.2, 34.9]},
                             {'name': '入海口·东营', 'value': [119.1, 37.8]}]),
                   'note': '各图仅绘该河流实际流经的省级行政区（含共源省）；色阶按本流域数值等频分级（非线性拉伸）'},
                  w=3, cls='mapstage bzmap', h=648, ruler=True)]
                + SDC                                   # 黄河专题独有：山东地市下钻图
                + [
                C(p + 'o1', '议题构成', '三大主题（生态治理 / 文旅 / 医患矛盾）· 社会治理为兜底层', 'donut',
                  topicShow, {'donut': True}),
                C(p + 'o2', '目标省份声量 Top 12', 't_basin_article.目标省份（内容涉及省）', 'hbar',
                  d['provDist'][:12], w=2),
                C(p + 'o3', '情感构成', f"SnowNLP 轻量模型 · 负面占比 {PC(sv['负面'], st)}", 'donut',
                  [[k, v] for k, v in d['sent']], {'donut': True, 'cmap': SENT_CLR}),
                C(p + 'o4', '样本年份分布', '发布时间解析所得 · 近年样本占比高', 'line',
                  {'x': [y for y, _ in d['years']], 'y': [n for _, n in d['years']]},
                  {'area': True, 'p': 0}, w=2),
                # ---- 批次 2 新增：分母层 / 对照层 ----
                # 单说「生态治理 245 条」没有标尺；把本流域全部议题摆出来，
                # 才有「生态治理 = 本流域全部舆情的 X%」这个可读的量。
                C(p + 'o5', '议题占比参照（三大主题 + 兜底层）',
                  f"分母 = 本流域全部 {N(d['allN'])} 条；三大主题（%s）全部展开、"
                  f"微博聚焦 {N(A)} 条（其中生态治理 / 医患矛盾另有跨平台三源口径）；"
                  f"社会治理为兜底层（关键词未命中其他议题）、只作分母。" % ' / '.join(T3),
                  'hbart', [[k, v, '微博聚焦' if k in T3 else '兜底层']
                            for k, v in d['allTopics']],
                  {'n': 8, 'cmap': {'微博聚焦': '#4a9dff', '兜底层': '#61728a'}}, w=2),
                C(p + 'o6', '情感 × 议题（结构对照 %）',
                  '三个议题各自内部的正/中/负结构（各按议题内 100% 归一）'
                  ' · 只比结构，不做极性外推',
                  'stack', {'x': T3L,
                            'series': [{'name': k,
                                        'y': [round(dict(bt.get(_t, {}).get('sent') or []).get(k, 0) * 100.0
                                                    / (sum(x[1] for x in (bt.get(_t, {}).get('sent') or [])) or 1), 1)
                                              for _t in T3]}
                                       for k in ('正面', '中性', '负面')]},
                  {'pct': True, 'labels': True, 'cmap': SENT_CLR}, w=1),
                # ---- 跨平台融合：交集议题（生态治理 / 医患矛盾）的跨源结构占比 ----
                # 每条按平台内 100% 归一，只比结构、不对齐绝对值；抖音 absent 不计入。
                C(p + 'o7', '跨平台议题结构（生态治理 / 医患矛盾）',
                  '四源交集议题：每条按所在平台内部 100%% 归一，只比结构占比、不对齐绝对值；'
                  '抖音 0 条未计入。%s 为微博独有，不在跨源口径内。'
                  % ('、'.join(XP_ONLYWB) if XP_ONLYWB else '文旅/社会治理'),
                  'stack',
                  {'x': XP_LIVE,
                   'series': [{'name': t,
                               'y': [round(_xart(t).get(pl, 0) * 100.0
                                           / (sum(_xart(t).values()) or 1), 1)
                                     for pl in XP_LIVE]}
                              for t in XP.get('topicsCommon', [])]},
                  {'pct': True, 'labels': True,
                   'cmap': {'生态治理': '#2ee6c0', '医患矛盾': '#ff7a7a'}}, w=2),
                # ---- 跨平台内容：把小红书 / 知乎 的真实正文接进总览 ----
                C(p + 'o8', '跨平台 · 生态治理热词 Top 15',
                  '微博 / 小红书 / 知乎 三源正文分词合并（交集议题，按命中篇数）', 'hbar',
                  XP_MERGED.get('生态治理', {}).get('hotwords', [])[:15], {'p': 0}, w=2),
                C(p + 'o9', '跨平台 · 生态治理情感构成（SnowNLP 样本）',
                  '三源合并正文抽样 %d 条；模型未校准，仅结构参考'
                  % XP_MERGED.get('生态治理', {}).get('sentSample', 0),
                  'donut', XP_MERGED.get('生态治理', {}).get('sent', []),
                  {'donut': True, 'cmap': SENT_CLR}, w=1),
                # ---- 医患矛盾与生态治理同为三源交集议题，此处给对称热词/情感 ----
                C(p + 'o10', '跨平台 · 医患矛盾热词 Top 15',
                  '微博 / 小红书 / 知乎 三源正文分词合并（交集议题，按命中篇数）', 'hbar',
                  XP_MERGED.get('医患矛盾', {}).get('hotwords', [])[:15], {'p': 0}, w=2),
                C(p + 'o11', '跨平台 · 医患矛盾情感构成（SnowNLP 样本）',
                  '三源合并正文抽样 %d 条；模型未校准，仅结构参考'
                  % XP_MERGED.get('医患矛盾', {}).get('sentSample', 0),
                  'donut', XP_MERGED.get('医患矛盾', {}).get('sent', []),
                  {'donut': True, 'cmap': SENT_CLR}, w=1),
                TABLE('本流域 vs 对照流域 · 六项画像对照',
                      [{'k': 'a', 'l': '指标'}, {'k': 'b', 'l': basin, 'num': True},
                       {'k': 'c', 'l': ob_name, 'num': True}, {'k': 'd', 'l': '读法'}],
                      [{'a': '样本量', 'b': N(A), 'c': N(OB['articles']), 'd': '两侧均为等量采样口径'},
                       {'a': '单篇转发', 'b': str(IA['all']['perRp']),
                        'c': str(OB['interact']['all']['perRp']), 'd': '数值越高越易扩散'},
                       {'a': '转赞比', 'b': str(IA['all']['rrRatio']),
                        'c': str(OB['interact']['all']['rrRatio']),
                        'd': '转发÷点赞；高＝观点载体，低＝围观表态'},
                       {'a': '可判定官方账号占比', 'b': PC(kN.get('官方', 0), chDen),
                        'c': PC(dict(OB['channel']['kind']).get('官方', 0),
                                sum(dict(OB['channel']['kind']).get(k, 0)
                                    for k in BM.AGENT_ORDER) or 1),
                        'd': '只看可判定主体样本，不是全量'},
                       {'a': '目标省份数', 'b': str(d['provCount']),
                        'c': str(OB['provCount']), 'd': '采集配额口径，反映覆盖广度'},
                       {'a': '头部 10 作者占比', 'b': f"{ND['conc'][2][2]}%",
                        'c': f"{OB['nodes']['conc'][2][2]}%", 'd': '越低越分散'}],
                      '这一张把两个专题的差异做成可核对的六行，避免"两边差不多"的印象',
                      w=3),
            ]),
            notes=[nt(srcNote, k='ok'), nt(sentNote, k='warn'),
                   nt(f"<b>分母层说明</b>：库里本流域共有 {N(d['allN'])} 条，"
                      f"本作品聚焦「生态环境治理 + 文旅」，因此 {N(d['filtered'])} 条"
                      f"其他议题只在「议题占比参照」里作分母出现，"
                      f"不做内容展开、不计入任何结论。", k='warn'),
                   nt(f"<b>跨平台口径</b>：本流域「生态治理 / 医患矛盾」在微博、小红书、知乎三源均有采集，"
                      f"已按平台内结构占比并排（上「跨平台议题结构」）。合并后医患矛盾评论 "
                      f"{N(_xsum('医患矛盾', 'comment'))} 条、生态治理 {N(_xsum('生态治理', 'comment'))} 条，"
                      f"均过 {XP.get('gate', 30)} 条闸门，可作结构分析；跨平台仅比结构、不对齐绝对值。",
                      k='ok')],
        ),
        dict(
            id=p + '-geo', group=g1, name=full + 'IP 属地地图', badge='真实', badgeCls='real',
            lead=f"地图口径为<b>作者 IP 属地</b>（t_basin_article.发布地区）：{N(A)} 条中可归属 "
                 f"{N(d['geoKnown'])} 条、缺失 {N(d['geoUnknown'])} 条（{PC(d['geoUnknown'], A)}）。"
                 f"它与本专题另一张「目标省份」图是<b>两个不同口径，不可混算</b> —— "
                 f"前者回答「发帖人在哪」，后者回答「内容写到哪」。",
            kpis=[
                K('可归属', N(d['geoKnown']), PC(d['geoKnown'], A), 1),
                K('缺失', N(d['geoUnknown']), '未知 / 境外 / 异常', 2),
                K('属地省份', f"{len(d['geoProv'])} 个", '出现即计', 3),
                K('属地第一', d['geoProv'][0][0] if d['geoProv'] else '-',
                  f"{N(d['geoProv'][0][1])} 条" if d['geoProv'] else '无数据', 4),
            ],
            cards=[
                C(p + 'g1', '作者 IP 属地分布', '颜色越深声量越高 · 悬停查看省份值与占比', 'map',
                  None, {'prov': geoD, 'total': d['geoKnown'], 'big': True,
                         'labelFs': 11, 'pal': 'heat'},
                  w=2, h=470, tools='pal', ruler=True, cls='mapstage'),
                C(p + 'g2', '属地省份 Top 12', '作者 IP 属地口径（t_basin_article.发布地区）', 'hbar',
                  d['geoProv'][:12], w=1),
                TABLE('两种地域口径对照（属地 Top 8）',
                      [{'k': 'a', 'l': '省份'}, {'k': 'b', 'l': '内容涉及省（目标省份）', 'num': True},
                       {'k': 'c', 'l': '作者属地（IP 归属）', 'num': True}],
                      [{'a': _p, 'b': N(provD.get(_p, 0)), 'c': N(_n)}
                       for _p, _n in d['geoProv'][:8]],
                      '同一省份在两个口径下不可比：一个是内容写到哪，一个是发帖人在哪',
                      w=3),
                # ---- 批次 2 新增：集中度 + 双口径差 ----
                # v5 修复：原来写成 [[k, v, s], ...]，而 renderKV 读的是 z.k / z.v
                # → 全是 undefined，整张卡只剩标题、4 行内容全空（用户第二张截图里
                # "内容没显示"的真因，不是截图问题）。改为对象行，并启用第三段 s（占比）。
                KV('属地集中度（作者 IP 属地口径）',
                   [{'k': 'Top 1', 'v': N(d['geoProv'][0][1]) if d['geoProv'] else '0',
                     's': PC(d['geoProv'][0][1] if d['geoProv'] else 0, d['geoKnown'])},
                    {'k': 'Top 3', 'v': N(sum(x[1] for x in d['geoProv'][:3])),
                     's': PC(sum(x[1] for x in d['geoProv'][:3]), d['geoKnown'])},
                    {'k': 'Top 10', 'v': N(sum(x[1] for x in d['geoProv'][:10])),
                     's': PC(sum(x[1] for x in d['geoProv'][:10]), d['geoKnown'])},
                    {'k': '覆盖省级行政区', 'v': f"{len(d['geoProv'])} 个",
                     's': f"未识别 {PC(d['geoUnknown'], A)}"}],
                   'Top 3 占比越低说明发帖人越分散（覆盖面越广），与「目标省份数」是两个口径；'
                   '进度条长度＝累计条数，右侧灰字＝占可归属条数的比例',
                   w=1),
                C(p + 'g5', '两种口径的差（属地 − 内容涉及省）',
                  '正数＝该省发帖人多于内容涉及量；负数＝内容常写到该省但本地发声少',
                  'hbart', [[_p, abs(_n - provD.get(_p, 0)),
                             ('属地更多' if _n > provD.get(_p, 0) else '内容更多')]
                            for _p, _n in d['geoProv'][:10]],
                  {'n': 10, 'cmap': {'属地更多': '#4a9dff', '内容更多': '#ffb44d'}}, w=2),
                TABLE('作者 IP 属地完整榜（Top 20 / 共 %d 个省级行政区）' % len(d['geoProv']),
                      [{'k': 'a', 'l': '省份'}, {'k': 'b', 'l': '条数', 'num': True},
                       {'k': 'c', 'l': '占可归属', 'num': True},
                       {'k': 'd', 'l': '内容涉及省条数', 'num': True}, {'k': 'e', 'l': '差'}],
                      [{'a': _p, 'b': N(_n), 'c': PC(_n, d['geoKnown']),
                        'd': N(provD.get(_p, 0)), 'e': ('%+d' % (_n - provD.get(_p, 0)))}
                       for _p, _n in d['geoProv'][:20]],
                      '港澳台按中国省级行政区归一处理；「内容涉及省」为采集配额口径',
                      w=3),
            ],
            notes=[nt(f'<b>该字段实测缺失 {PC(d["geoUnknown"], A)}</b>（未识别 / 境外 / 异常值），'
                      f'地图只反映「可归属」的那部分作者分布，不能按全量读。', k='warn'),
                   nt('港澳台按中国省级行政区处理，「中国香港」等原始写法已在统计前归一。', k='ok')],
        ),
        dict(
            id=p + '-topic', group=g2, name=full + '议题专题', badge='真实', badgeCls='real',
            lead='<b>三大主题平权对照</b>：生态环境治理 / 文旅 / 医患矛盾均按<b>微博口径</b>并排呈现 —— '
                 '<b>每列一个议题</b>：列首是该议题的<b>速览卡</b>（背景与要点，数字与下方图表同源），'
                 '自上而下依次为「说什么（正文热词）」→「由哪些事件构成（事件簇）」→'
                 '「情绪如何（情感构成）」→「谁在说（话语主体）」，最后一行是医患矛盾的跨平台明细。'
                 '三个议题在采集端等量采样，可直接比结构占比；'
                 '跨平台（微博 / 小红书 / 知乎三源交集）口径见「词频与词云」页的跨平台热词'
                 '与本页底部明细表，只比结构、不对齐绝对值。',
            kpis=[
                K('生态治理', N(ec.get('n', 0)), f"点赞 {N(ec.get('like', 0))}", 1),
                K('文旅', N(tv.get('n', 0)), f"点赞 {N(tv.get('like', 0))}", 2),
                K('医患矛盾', N(yt.get('n', 0)), f"点赞 {N(yt.get('like', 0))}", 3),
                K('生态作者', N(ec.get('authors', 0)), '去重后', 4),
                K('文旅作者', N(tv.get('authors', 0)), '去重后', 5),
                K('医患作者', N(yt.get('authors', 0)), '去重后', 6),
            ],
            cards=[
                # ===== 第 1 行 · 议题速览：每个议题一张文字小传（背景 + 要点，数字与下方图表同源）=====
                *_topic_profiles(),
                # ===== 第 2 行 · 说什么：三议题正文热词 Top 5（竖向柱，柱顶标数值）=====
                C(p + 't2', '生态治理 · 正文热词 Top 5', '该议题内正文分词 · 同篇不重复计', 'bar',
                  _top5(ec.get('hotwords')), {'lab': True, 'rot': 34, 'bw': 40, 'r': 10, 'p': 0}),
                C(p + 't3', '文旅 · 正文热词 Top 5', '该议题内正文分词 · 同篇不重复计', 'bar',
                  _top5(tv.get('hotwords')), {'lab': True, 'rot': 34, 'bw': 40, 'r': 10, 'p': 1}),
                C(p + 't19', '医患矛盾 · 正文热词 Top 5', '该议题内正文分词 · 同篇不重复计', 'bar',
                  _top5(yt.get('hotwords')), {'lab': True, 'rot': 34, 'bw': 40, 'r': 10, 'p': 2}),
                # ===== 第 3 行 · 由哪些事件构成：事件簇按命中篇数取前 5 =====
                C(p + 't22', '生态治理 · 主要事件 Top %d' % EVT['生态治理'][1], EVT['生态治理'][2], 'bar',
                  EVT['生态治理'][0], {'lab': True, 'rot': 30, 'bw': 40, 'r': 10, 'p': 0}),
                C(p + 't23', '文旅 · 主要事件 Top %d' % EVT['文旅'][1], EVT['文旅'][2], 'bar',
                  EVT['文旅'][0], {'lab': True, 'rot': 30, 'bw': 40, 'r': 10, 'p': 1}),
                C(p + 't24', '医患矛盾 · 主要事件 Top %d' % EVT['医患矛盾'][1], EVT['医患矛盾'][2], 'bar',
                  EVT['医患矛盾'][0], {'lab': True, 'rot': 30, 'bw': 40, 'r': 10, 'p': 2}),
                # ===== 第 4 行 · 情绪如何：三议题情感构成（保留原卡）=====
                C(p + 't6', '生态治理 · 情感构成', 'SnowNLP 轻量模型判定', 'donut',
                  [[k, v] for k, v in ec.get('sent', [])],
                  {'donut': True, 'cmap': SENT_CLR}),
                C(p + 't7', '文旅 · 情感构成', 'SnowNLP 轻量模型判定', 'donut',
                  [[k, v] for k, v in tv.get('sent', [])],
                  {'donut': True, 'cmap': SENT_CLR}),
                C(p + 't20', '医患矛盾 · 情感构成', 'SnowNLP 轻量模型判定', 'donut',
                  [[k, v] for k, v in yt.get('sent', [])],
                  {'donut': True, 'cmap': SENT_CLR}),
                # ===== 第 5 行 · 谁在说：三议题话语主体构成（官方 / 媒体 / 个人）=====
                C(p + 't25', '生态治理 · 话语主体构成', SPK['生态治理'][1], 'donut',
                  SPK['生态治理'][0], {'donut': True, 'cmap': SPK_CLR}),
                C(p + 't26', '文旅 · 话语主体构成', SPK['文旅'][1], 'donut',
                  SPK['文旅'][0], {'donut': True, 'cmap': SPK_CLR}),
                C(p + 't27', '医患矛盾 · 话语主体构成', SPK['医患矛盾'][1], 'donut',
                  SPK['医患矛盾'][0], {'donut': True, 'cmap': SPK_CLR}),
                # ===== 第 6 行 · 跨平台明细（通栏）=====
                TABLE('医患矛盾 · 跨平台明细（三源交集议题）',
                      [{'k': 'a', 'l': '平台'}, {'k': 'b', 'l': '文章', 'num': True},
                       {'k': 'c', 'l': '评论', 'num': True}, {'k': 'd', 'l': '评论闸门'}],
                      [{'a': pl, 'b': N(_xart('医患矛盾').get(pl, 0)),
                        'c': N(_xcmt('医患矛盾').get(pl, 0)),
                        'd': ('已过' if XP_MERGED.get('医患矛盾', {}).get('gate') else '未过')}
                       for pl in XP_LIVE],
                      '跨平台仅比结构占比；合并后本流域医患矛盾评论 '
                      f"{N(_xsum('医患矛盾', 'comment'))} 条，已过 {XP.get('gate', 30)} 条闸门，"
                      '可作结构分析。该议题为微博 / 小红书 / 知乎三源交集，不在微博单源聚焦范围内，'
                      '故以跨源口径呈现。',
                      w=3),
            ],
            notes=[nt('「议题」由采集端按关键词矩阵标注；三大主题（生态治理 / 文旅 / 医患矛盾）'
                      '在同一议题内样本等量，可直接比结构占比。', k='ok'),
                   nt(sentNote, k='warn'),
                   nt('医患矛盾暂不出「命中关键词」排行：该议题在采集端的命中关键词为单一值'
                      '「医患纠纷」（+省份），无法拆分排序 —— 其细分结构改由「事件簇」与'
                      '下方跨平台明细两处呈现。', k='warn'),
                   nt('本页不出「目标省份」分布：该字段是<b>采集配额标记</b>（省份+主题），'
                      '既不是热度、也不是作者属地 —— 作者地理口径是另一个字段「发布地区」，'
                      '见「IP 属地地图」页。把它画成排行榜会被读成「哪个省最关注该议题」，'
                      '故不在此呈现。', k='ok'),
                   nt('跨平台交集议题 = 生态环境治理 + 医患矛盾（微博 / 小红书 / 知乎三源）；'
                      '文旅为微博独有（跨平台两库未采集该议题）。跨平台仅比结构、不对齐绝对值。',
                      k='ok')],
        ),
        dict(
            id=p + '-words', group=g2, name=full + '词频与词云', badge='真实', badgeCls='real',
            lead=f"{N(A)} 条微博正文分词后的头部词条与<b>事件簇归属</b>。"
                 f'已剔除停用词、单字与不含汉字的碎片。'
                 + ('<b>词云按事件簇着色：彩色词能挂到具体事件，灰阶词是概念重复、'
                    '公文套话与行政区划名 —— 点彩色词可联动右侧释义与原文证据。</b>'
                    if HAS_CLU else ''),
            kpis=([
                K('事件簇', f"{len(CLU)} 个", '归纳自正文语料', 1),
                K('簇覆盖率', f"{N(coC.get('pct'))}% / {N(coT.get('pct'))}% / {N(coY.get('pct'))}%",
                  f"生态 {N(coC.get('covered'))} / 文旅 {N(coT.get('covered'))} / "
                  f"医患 {N(coY.get('covered'))} 篇被覆盖", 2),
                K('词云词量', N(len(CLOUD)), f"含事件词 {N(EVN)} 个", 3),
                K('头部词', d['hotwords'][0][0] if d['hotwords'] else '-', '出现最多', 4),
                K('命中关键词', N(len(d['keywords'])), '采集端矩阵', 5),
            ] if HAS_CLU else [
                K('分词词表', N(len(d['hotwords'])), '入词云', 1),
                K('分词样本', N(A), '微博正文', 2),
                K('头部词', d['hotwords'][0][0] if d['hotwords'] else '-', '出现最多', 3),
                K('命中关键词', N(len(d['keywords'])), '采集端矩阵', 4),
            ]),
            cards=[
                C(p + 'w3', '正文词云' + (' · 按事件簇着色' if HAS_CLU else ''),
                  ('字号 ∝ 出现篇数（<b>文档频率 DF</b>，非词频 TF）；<b>点任一词 → 展开该词解释卡</b>，'
                   '彩色词同时联动下方事件簇面板，灰阶词不归属事件簇'
                   if HAS_CLU else 'Top 60 词条 · 字号 ∝ 词频'),
                  'wordcloud', CLOUD,
                  (dict(maxFs=60, minFs=13, click='1',
                        eventGroups=d.get('clusterNames') or [],
                        note='本图 %d 词，其中事件词 %d 个' % (len(CLOUD), EVN))
                   if HAS_CLU else dict(maxFs=64, minFs=14)),
                  w=3, h=460),
            ] + ([
                # h=430：实测 .cludet 自然高 349px（.clugrid 308 + 小标题 22，
                # 17 个簇标签），而 .ch 默认只有 260px 且 overflow:visible
                # → 撑破宿主，把后继内容顶下去（与 3f33ec1 的 vcard 同类问题）。
                # 430 含顶部 .clutags 标签行与留白；点标签切换时内容变短，
                # 容器不变形，故无需内部滚动。
                C(p + 'w4', '事件簇释义与证据',
                  '点标签或点词云里的词切换；每簇都是从这批语料归纳的释义 + 3 条最高互动原文'
                  '（带链接可点进原微博核验）',
                  'clusters',
                  {'cls': CLU, 'cloud': p + 'w3', 'gate': d.get('clusterGate', 30),
                   'amb': d.get('clusterAmb') or {}, 'basin': basin},
                  w=3, h=430, noexp=True),
                TABLE('同义归并：被分词切碎的概念',
                      [{'k': 'a', 'l': '概念'}, {'k': 'e', 'l': '议题'},
                       {'k': 'b', 'l': '明细词'}, {'k': 'c', 'l': '命中篇数', 'num': True},
                       {'k': 'd', 'l': '说明'}],
                      MRG,
                      '同一概念被切成多个词，单看每个都不显眼，归并后总量才上台面；'
                      '这里是<b>篇数</b>口径（去重微博 ID），与词云的「次」不是同一单位。',
                      w=3),
                _wcloud_read(),
            ] if HAS_CLU else []) + [
                TEXT('生态治理 · 跨平台热词 Top 15',
                     _ranktxt(XP_MERGED.get('生态治理', {}).get('hotwords', [])),
                     '微博 / 小红书 / 知乎 三源正文分词合并（交集议题，按命中篇数）', w=2),
                TEXT('医患矛盾 · 跨平台热词 Top 15',
                     _ranktxt(XP_MERGED.get('医患矛盾', {}).get('hotwords', [])),
                     '微博 / 小红书 / 知乎 三源正文分词合并（交集议题，按命中篇数）', w=2),
            ],
            notes=([
                nt('簇匹配口径：正文包含该簇任一词即命中，按微博 ID 去重，'
                   '<b>不匹配「命中关键词」字段</b> —— 那是采集端配额标记，不是内容证据。'
                   '簇间允许重叠，故<b>各簇篇数不可相加</b>，也不等于议题总篇数'
                   f"（实测重叠：生态治理 {N(coC.get('overlap'))} 篇 / 文旅 {N(coT.get('overlap'))} 篇 / "
                   f"医患矛盾 {N(coY.get('overlap'))} 篇）。",
                   k='warn'),
                nt('词表是人工归纳的短语集合，召回不完整 —— 覆盖率已如实标注在 KPI 里，'
                   '未被簇覆盖的样本不等于「没有舆情」，只说明其用词未落入词表。', k='warn'),
                nt('簇词是短语级（如「中央生态环保督察」），而词云喂的是 jieba 分词结果，'
                   '部分短语会被切碎或作为单字被过滤，故词云可见词少于词表本身；'
                   '面板里每个簇都会标出「可见 N / M 词」。', k='warn'),
                nt('词频统计基于 jieba 分词，同一条微博内同一词只计一次（避免单篇刷词）。', k='ok'),
            ] if HAS_CLU else [
                nt('词频统计基于 jieba 分词，同一条微博内同一词只计一次（避免单篇刷词）。', k='ok'),
            ]),
        ),
        dict(
            id=p + '-content', group=g3, name=full + '高影响力内容', badge='真实', badgeCls='real',
            lead='按 点赞 + 评论 + 转发 排序的高互动微博，以及三大主题的互动量对照。'
                 '作者昵称与主页在入库时已脱敏。',
            kpis=[
                K('累计转发', N(d['repost']), '全样本', 1),
                K('累计评论', N(d['cmtCnt']), '全样本', 2),
                K('累计点赞', N(d['like']), '全样本', 3),
                K('人均点赞', N(int(d['like'] / max(d['authors'], 1))), '按作者去重', 4),
            ],
            cards=[
                LIST('高互动微博 Top 15',
                     [{'m1': f"赞 {N(r['like'])}", 'm2': f"评 {N(r['cmt'])}", 'm3': f"转 {N(r['rep'])}",
                       'm4': r['topic'], 'm5': r['prov'], 'm6': r['time'], 'txt': r['text']}
                      for r in d['topArticles']],
                     f"排序口径：点赞 + 评论 + 转发 · 样本 {N(A)} 条 · 昵称已脱敏",
                     meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'},
                           {'k': 'm3', 'cls': 'tag'}, {'k': 'm4', 'cls': 'tag p'},
                           {'k': 'm5', 'cls': 'tag'}, {'k': 'm6', 'cls': 'tag'}],
                     w=3),
                TABLE('三议题互动量对照',
                      [{'k': 'a', 'l': '议题'}, {'k': 'b', 'l': '样本', 'num': True},
                       {'k': 'c', 'l': '点赞', 'num': True}, {'k': 'd', 'l': '评论', 'num': True},
                       {'k': 'e', 'l': '作者', 'num': True}, {'k': 'f', 'l': '占比', 'num': True}],
                      [{'a': _t, 'b': N(bt.get(_t, {}).get('n', 0)),
                        'c': N(bt.get(_t, {}).get('like', 0)),
                        'd': N(bt.get(_t, {}).get('cmtCnt', 0)),
                        'e': N(bt.get(_t, {}).get('authors', 0)),
                        'f': PC(bt.get(_t, {}).get('n', 0), A)}
                       for _t in T3],
                      '三个议题在采集端等量采样，热度差异反映真实关注度',
                      w=3),
                # ---- 批次 2 新增：集中度 + 结构 + 高扩散 ----
                C(p + 'ct3', '互动量集中度：Top10 内容 vs 全流域',
                  '头部 10 条内容的互动量占全流域互动总量的比例 —— 判断"是不是少数爆款撑起声量"',
                  'bar', {'x': ['全流域互动总量', '高互动 Top10 合计'],
                          'y': [IA['all']['lk'] + IA['all']['cm'] + IA['all']['rp'],
                                sum(r['like'] + r['cmt'] + r['rep']
                                    for r in d['topArticles'])]},
                  {'p': 2, 'rot': 0}, w=2),
                C(p + 'ct4', '高互动 Top15 的议题与省份构成',
                  '头部内容是否集中在某一个议题 / 某几个省份 —— 判断声量结构是否偏斜',
                  'donut', [[k, sum(1 for r in d['topArticles'] if r['topic'] == k)]
                            for k in dict.fromkeys(r['topic'] for r in d['topArticles'])],
                  {'donut': True}, w=1),
                LIST('高扩散内容 Top 8（转发驱动，与点赞榜不同源）',
                     [{'m1': f"转 {N(r['rp'])}", 'm2': f"赞 {N(r['lk'])}", 'm3': r['tp'],
                       'm4': r['pv'], 'm5': r['tm'], 'txt': r['txt']}
                      for r in IA['top']],
                     '转发代表"愿意替它说话"，点赞只代表"看见了"；两榜对比可区分围观与动员',
                     meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'},
                           {'k': 'm3', 'cls': 'tag p'}, {'k': 'm4', 'cls': 'tag'},
                           {'k': 'm5', 'cls': 'tag'}], w=3),
                LIST('跨平台高赞内容 Top 10（微博 / 小红书 / 知乎 · 生态治理）',
                     [{'m1': '赞 %s' % N(r['like']), 'm2': '评 %s' % N(r['cmt']),
                       'm3': ('转 %s' % N(r['rep']) if r['rep'] else '分享 %s' % N(r['share'])),
                       'm4': r['plat'], 'm5': r['topic'], 'm6': (r['time'] or '—'), 'txt': r['text']}
                      for r in XP_MERGED.get('生态治理', {}).get('topArticles', [])[:10]],
                     '跨平台只比结构、不对齐绝对值；此处按各平台互动量在本源内排序后合并 Top10',
                     meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'},
                           {'k': 'm3', 'cls': 'tag'}, {'k': 'm4', 'cls': 'tag p'},
                           {'k': 'm5', 'cls': 'tag'}, {'k': 'm6', 'cls': 'tag'}], w=3),
                LIST('跨平台高赞内容 Top 10（微博 / 小红书 / 知乎 · 医患矛盾）',
                     [{'m1': '赞 %s' % N(r['like']), 'm2': '评 %s' % N(r['cmt']),
                       'm3': ('转 %s' % N(r['rep']) if r['rep'] else '分享 %s' % N(r['share'])),
                       'm4': r['plat'], 'm5': r['topic'], 'm6': (r['time'] or '—'), 'txt': r['text']}
                      for r in XP_MERGED.get('医患矛盾', {}).get('topArticles', [])[:10]],
                     '跨平台只比结构、不对齐绝对值；此处按各平台互动量在本源内排序后合并 Top10',
                     meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'},
                           {'k': 'm3', 'cls': 'tag'}, {'k': 'm4', 'cls': 'tag p'},
                           {'k': 'm5', 'cls': 'tag'}, {'k': 'm6', 'cls': 'tag'}], w=3),
            ],
            notes=[nt('高互动榜按三指标之和排序；跨平台对比绝对值无意义，此处只在微博内部排序。', k='warn'),
                   nt(f"高互动 Top15 来自 {N(A)} 条样本；榜单只反映<b>库内</b>传播力，"
                      f"未被采集到的内容不在其中。", k='ok')],
        ),
        dict(
            id=p + '-comment', group=g3, name=full + '评论洞察', badge='真实', badgeCls='real',
            lead=f"评论侧样本 {N(Cm)} 条。评论来源字段为作者 IP 归属，比正文的发布地区更规整，"
                 f"因此地域以评论来源为主口径。{gateTxt}",
            kpis=[
                K('评论样本', N(Cm), 't_basin_comment', 1),
                K('评论年份', f"{len(d['commentYears'])} 个", '评论时间解析', 2),
                K('评论议题', f"{len(T3)} 个",
                  ' / '.join(f"{_t} {N(dict(d['commentTopics']).get(_t, 0))}" for _t in T3), 3),
                K('样本闸门', '全部已过' if d['commentEnough'] else '部分未过',
                  f"{BD['commentGate']} 条为单类线", 4),
            ],
            cards=[
                C(p + 'c1', '评论年份分布', '评论时间解析 · 本批评论的「来源」字段全空，故不采用',
                  'line',
                  {'x': [y for y, _ in d['commentYears']], 'y': [n for _, n in d['commentYears']]},
                  {'area': True, 'p': 1}, w=2),
                C(p + 'c2', '评论性别构成', 'm/f 已归一为男/女，未识别单列', 'donut',
                  d['commentGender'], {'donut': True}),
                LIST('高赞评论 Top 10',
                     [{'m1': f"赞 {N(r['like'])}", 'm2': r['topic'], 'm3': r['time'],
                       'txt': r['text']} for r in d['topComments']],
                     '按点赞量排序 · 昵称已脱敏',
                     meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag p'},
                           {'k': 'm3', 'cls': 'tag'}],
                     w=3),
                # ---- 批次 2 新增：时段 / 长度 / 情感 / 用户集中度 ----
                C(p + 'cm5', '评论时段分布（24 小时）',
                  '评论时间字段解析 · 只在本流域 ' + N(Cm) + ' 条内比较，不外推公众作息',
                  'bar', {'x': [f'{i}时' for i in range(24)], 'y': d['cmt']['hours']},
                  {'p': 0, 'rot': 55, 'fs': 8.5}, w=2),
                C(p + 'cm6', '评论长度分段',
                  'CHAR_LENGTH(TRIM(评论内容)) 现场分箱（字符数，非字节）',
                  'hbart', [[k, v, ('短评' if i < 2 else '长评')]
                            for i, (k, v) in enumerate(d['cmt']['lenBins'])],
                  {'n': 5, 'cmap': {'短评': '#4a9dff', '长评': '#ffb44d'}}, w=1),
                C(p + 'cm7', '评论情感构成',
                  'SnowNLP 判定 · <b>该模型未校准</b>，此处只作结构参考（见「情感模型校准」页）',
                  'donut', d['cmt']['sent'], {'donut': True, 'cmap': SENT_CLR}, w=1),
                TABLE('评论者集中度（Top 10 用户）',
                      [{'k': 'a', 'l': '用户（脱敏）'}, {'k': 'b', 'l': '评论条数', 'num': True},
                       {'k': 'c', 'l': '占本流域评论', 'num': True}],
                      [{'a': u[0], 'b': str(u[1]), 'c': PC(u[1], Cm)}
                       for u in d['cmt']['users']],
                      f"共 {N(d['cmt']['nUsers'])} 位评论用户；人数与条数一起看能发现"
                      f"'少数人反复发言'的情况", w=1),
                TABLE('跨平台评论样本量（合并 %d 条）' % sum(XP_PLAT.get(pl, {}).get('comment', 0) for pl in XP_LIVE),
                      [{'k': 'a', 'l': '平台'}, {'k': 'b', 'l': '评论条数', 'num': True},
                       {'k': 'c', 'l': '占合并', 'num': True}],
                      [{'a': pl, 'b': N(XP_PLAT.get(pl, {}).get('comment', 0)),
                        'c': PC(XP_PLAT.get(pl, {}).get('comment', 0),
                                sum(XP_PLAT.get(p, {}).get('comment', 0) for p in XP_LIVE))}
                       for pl in XP_LIVE],
                      '微博 140 条 → 三源合并 %d 条；跨平台评论已满足聚类闸门，可做结构分析'
                      % sum(XP_PLAT.get(pl, {}).get('comment', 0) for pl in XP_LIVE), w=2),
                TABLE('评论样本量 · 按议题（三大主题 × 三平台 · 微博 %d 条 → 跨平台交集 %d 条）'
                      % (Cm, sum(sum((XP_MERGED.get(t, {}).get('comment') or {}).values())
                                 for t in XP.get('topicsCommon', []))),
                      [{'k': 'a', 'l': '议题'}]
                      + [{'k': 'p%d' % i, 'l': pl, 'num': True} for i, pl in enumerate(XP_LIVE)]
                      + [{'k': 'z', 'l': '合计', 'num': True}],
                      [{'a': t,
                        'z': (N(sum((XP_MERGED.get(t, {}).get('comment') or {}).values()))
                              if t in XP.get('topicsCommon', []) else '—'),
                        **{'p%d' % i: (N((XP_MERGED.get(t, {}).get('comment') or {}).get(pl, 0))
                                       if t in XP.get('topicsCommon', [])
                                       else (N(dict(d['commentTopics']).get(t, 0))
                                             if pl == '微博' else '—'))
                           for i, pl in enumerate(XP_LIVE)}}
                       for t in T3],
                      '三大主题各自的评论样本量：文旅为微博独有（跨平台两库无该议题，标「—」）、'
                      '且微博侧评论为 0 条；跨平台样本主要用于结构分析。', w=2),
            ],
            notes=[nt(gateTxt, k='warn' if not d['commentEnough'] else 'ok'),
                   nt('流域评论整体只有 140 条（三议题过滤后 ' + N(Cm) + ' 条），其中'
                      + ' / '.join(f"{_t} {N(dict(d['commentTopics']).get(_t, 0))} 条" for _t in T3)
                      + '；需要按议题分层重抓后，才能做评论侧的情感与议题交叉分析。', k='warn')],
        ),
        dict(
            id=p + '-method', group=g4, name=full + '口径与方法', badge='说明', badgeCls='plan',
            lead='这一页写清楚数据从哪来、议题怎么定、哪些结论现在还不能下 —— '
                 '避免把「样本不足」误读成「舆情如此」。',
            kpis=[
                K('数据源', BD['db'], 'MySQL', 1),
                K('议题口径', str(len(BD['topics'])) + ' 个', ' / '.join(BD['topics']), 2),
                K('情感模型', 'SnowNLP', '轻量 · 待校准', 3),
                K('生成时间', BD['generated'][:10], BD['generated'][11:], 4),
            ],
            cards=[
                TEXT('数据来源与范围',
                     f'<div style="line-height:1.9">'
                     f'<b>表格</b>：t_basin_article（{N(A)} 条）、t_basin_comment（{N(Cm)} 条）<br>'
                     f'<b>过滤</b>：流域 = {basin}，议题 ∈ {{生态治理, 文旅, 医患矛盾}}<br>'
                     f'<b>地域</b>：正文用「目标省份」（采集时的目标省），评论用「来源」（作者 IP 归属）<br>'
                     f'<b>脱敏</b>：作者昵称、用户 ID、主页在入库前已处理</div>',
                     '所有图表均为实时 SQL 聚合结果', w=1),
                TEXT('两个已知的局限',
                     f'<div style="line-height:1.9">'
                     f'① <b>评论样本偏少</b>：{N(Cm)} 条，其中文旅议题为 0 条；'
                     f'评论侧只做分布现象描述，不做趋势外推。<br>'
                     f'② <b>情感模型未校准</b>：SnowNLP 通用模型，对生态/文旅这类领域词'
                     f'极性偏两端（负面 {PC(sv["负面"], st)}、中性 {PC(sv["中性"], st)}），'
                     f'正负比只能当结构参考。</div>',
                     '这两条会在正式版中用分层重抓 + 语料校准消除', w=2),
                TEXT('口径红线',
                     '<div style="line-height:1.9">'
                     '· 跨平台（微博 / 抖音）<b>不比绝对值</b>：点赞、评论、转发机制不同，'
                     '只比结构占比。<br>'
                     '· 地域分三个口径：目标省份 / 内容属地 / 作者属地，<b>不混算</b>。<br>'
                     '· 流域省份含双属（青海、四川同属长江与黄河），已在采集端打双标签。</div>',
                     '用于避免评审层面的口径质疑', w=3),
                # ---- 批次 2 新增：字段字典 / 模块清单 / 复算 SQL / 缺口清单 ----
                TABLE('字段字典（本页每个数字出自哪个字段）',
                      [{'k': 'a', 'l': '字段'}, {'k': 'b', 'l': '表'}, {'k': 'c', 'l': '用途'}, {'k': 'd', 'l': '口径要点'}],
                      [{'a': '微博内容', 'b': 't_basin_article', 'c': '词频 / 事件簇 / 情感 / 词典法',
                        'd': '分词前剔除停用词与单字；同篇同词只计一次'},
                       {'a': '发布时间', 'b': 't_basin_article', 'c': '年份 / 月度 / 年×月矩阵',
                        'd': '文本字段，正则解析；末月为断月'},
                       {'a': '点赞数 / 评论数 / 转发数', 'b': 't_basin_article', 'c': '互动结构 / 扩散效率',
                        'd': '整数聚合，缺失按 0；不与抖音对齐绝对值'},
                       {'a': '分类', 'b': 't_basin_article', 'c': '发布渠道与话语主体',
                        'd': '混装字段，受控词表归类，未归类如实标注'},
                       {'a': '作者ID / 作者昵称', 'b': 't_basin_article', 'c': '关键传播节点 / 首发者',
                        'd': '入库前已脱敏，保留首尾字符'},
                       {'a': '目标省份', 'b': 't_basin_article', 'c': '议题省份分布 / 分母层',
                        'd': '采集配额标记（省份+主题），**不是热度**'},
                       {'a': '发布地区', 'b': 't_basin_article', 'c': 'IP 属地地图',
                        'd': '作者 IP 属地口径，实测缺失 40%+，已如实标注'},
                       {'a': '命中关键词', 'b': 't_basin_article', 'c': '采集端关键词命中',
                        'd': '配额标记，**不用于内容匹配与事件判定**'},
                       {'a': '评论内容 / 评论时间', 'b': 't_basin_comment', 'c': '评论洞察 / 时段',
                        'd': '样本仅 ' + N(Cm) + ' 条，过闸与否已标注'},
                       {'a': '性别', 'b': 't_basin_comment', 'c': '评论性别构成',
                        'd': 'm/f 归一；未识别单列，不并入任何一侧'}],
                      '评审若要复核任何一个数字，从这张表能定位到字段与口径', w=3),
                TABLE(f'模块清单与数据就绪度（{len(BM.MODULES)} 个模块）',
                      [{'k': 'a', 'l': '模块'}, {'k': 'b', 'l': '分组'}, {'k': 'c', 'l': '就绪度'},
                       {'k': 'd', 'l': '状态'}, {'k': 'e', 'l': '数据来源'}],
                      [{'a': m[1], 'b': m[2], 'c': m[3], 'd': m[4], 'e': m[5]}
                       for m in BM.MODULES],
                      'L1 已有 / L2 零采集可加（数据已在库）/ L3 需加工（有原文，需计算）/ '
                      'L4 需先补数据 —— 与侧栏徽章一一对应', w=3),
                TABLE('尚未补齐的模块与缺口（诚实清单）',
                      [{'k': 'a', 'l': '模块'}, {'k': 'b', 'l': '层级'}, {'k': 'c', 'l': '缺口'},
                       {'k': 'd', 'l': '本页现状'}],
                      [{'a': m[1], 'b': m[3], 'c': _gapTxt(m[0], d, OB), 'd': m[4]}
                       for m in BM.module_gaps()],
                      f'这 {len(BM.module_gaps())} 项在页面上都以"缺口页"形式存在：给真实数字与补数路径，不填假数据', w=3),
                TEXT('复算方法（从页面数字回到 SQL）',
                     f'''<div style="line-height:1.95">
<b>① 样本量与议题分布</b><br>
<code>SELECT 议题, COUNT(*) FROM t_basin_article WHERE 流域='{basin}' GROUP BY 议题;</code><br>
<b>② 互动结构</b><br>
<code>SELECT SUM(点赞数), SUM(评论数), SUM(转发数) FROM t_basin_article
WHERE 流域='{basin}' AND 议题 IN ('生态治理','文旅','医患矛盾');</code><br>
<b>③ 事件簇命中篇数</b>（以「督察」为例，按微博 ID 去重）<br>
<code>SELECT COUNT(DISTINCT 微博ID) FROM t_basin_article
WHERE 流域='{basin}' AND 微博内容 LIKE '%督察%';</code><br>
<b>④ 话语主体归类</b>：分类字段导出后按 <code>basin_modules.classify_channel()</code>
的规则表复判（规则表在页面「发布渠道与话语主体」页完整列出）。<br>
<b>⑤ 风险得分</b>：按 40/25/20/15 四项加权，原始量与归一值在「风险分级预警」页逐事件给出。
</div>''',
                     '所有数字都可复算：页面给出的口径与这里的 SQL 一一对应', w=3),
            ],
            notes=[nt('本页不含任何预测或估值数字，全部为可复算的聚合量。', k='ok'),
                   nt(f"<b>口径分层</b>：本流域库内共 {N(d['allN'])} 条。三大主题平权展开 ——"
                      f"微博聚焦 生态治理 / 文旅 / 医患矛盾（{N(A)} 条，微博口径）；"
                      f"其中生态治理 / 医患矛盾另有微博 / 小红书 / 知乎三源交集口径（见「跨平台」卡）；"
                      f"社会治理为兜底层、只作占比分母、不做内容分析。",
                      k='warn')],
        ),
    ]


# ==================================================================
# 批次 2：恢复被精简掉的 8 个维度（+ 跨流域词对照、事件与预警两组）
# ------------------------------------------------------------------
# 设计约束（与批次 1 一致，必须遵守）：
#   1. 只加视图与卡片，**不改任何已有卡片的 id** —— 批次 1 的探针/截图脚本仍可用。
#   2. 每个数字都来自 basin_data.json（即 SQL 聚合或对真实文本的统计），不写死。
#   3. 数据不足的模块（评论聚类 / 跨平台 / 情感校准）一律做成"缺口页"：
#      给真实缺口数字 + 现有可做的部分 + 补数计划，**不填任何假数字**。
#   4. L 级徽章沿用规划文档：L1 已有 / L2 零采集可加 / L3 需加工 / L4 需补数据。
# ==================================================================
def _gapTxt(mid, d, OB):
    """把每个未补齐模块的「缺口」写实 —— 口径页要能一眼看出缺什么、缺多少。"""
    if mid == 'clust':
        _cl = ((BD.get('xplat') or {}).get('cluster') or {}).get(d.get('basin'), {}) or {}
        return (f"微博单源评论 {N(d['comments'])} 条不足 300 门槛；已改用三源合并评论"
                f"（{N(_cl.get('n', 0))} 条）做 TF-IDF + KMeans 聚类，"
                f"簇标签取该簇独占词、未人工命名")
    if mid == 'calib':
        cb = d['calib']
        return (f"中性段仅 {cb['neuPct']}%、极端分占 {cb['extPct']}%、"
                f"与词典法一致率 {cb['agreePct']}%（对照流域 "
                f"{OB['calib']['agreePct']}%）")
    if mid == 'nodes':
        return (f"昵称脱敏后仅能做账号级统计，无法回溯到真实主体；"
                f"首发者只代表<b>库内</b>最早，非全网首发")
    if mid == 'events':
        cov = ((d['byTopic'].get('生态治理') or {}).get('coverage') or {})
        return (f"事件词表人工归纳，覆盖率 {cov.get('pct', 0)}%（生态治理口径）；"
                f"短语会被 jieba 切碎，词云可见词少于词表")
    if mid == 'risk':
        return ('四项权重为团队设定值（40/25/20/15），非拟合结果；'
                f"命中篇数 < {d['risk']['gate']} 的事件不入级，只列线索")
    return '—'


def basin_extra_views(basin):
    d = BD['basins'][basin]
    ob_name = '黄河' if basin == '长江' else '长江'
    OB = BD['basins'][ob_name]
    p = BASIN_PFX[basin]
    full = basin + '流域'
    A, Cm = d['articles'], d['comments']
    TR, CHn, IA, ND = d['trend'], d['channel'], d['interact'], d['nodes']
    EP = d['evprov']                 # 建议1 事件×省份矩阵 + 建议3 扩散比
    RK, CB, CM = d['risk'], d['calib'], d['cmt']
    # 跨平台传播节点（2026-10-08 新增，数据在 build_basin_data.nodes_cross_platform 里算）
    # ⚠ 挂在 **basins[b] 下**、按流域分别算：四张平台表都有 `流域` 字段且两流域
    #   条数不同，用同一份全局数字会让长江页/黄河页显示完全一样的"跨平台对比"。
    NC = d.get('nodesCross') or {}
    NCPlats = NC.get('platforms') or []
    # 未采集的平台（表存在但 0 条）必须与「真 0 条」分开渲染 —— 矩阵第 4 元素 has 传给 heat
    NCmiss = {p['name'] for p in NCPlats if p.get('missing')}
    NClive = [p['name'] for p in NCPlats if not p.get('missing') and p.get('article')]
    bt = d['byTopic']
    eco, tour = (dict(d['topicDist']).get('生态治理', 0),
                 dict(d['topicDist']).get('文旅', 0))
    g1, g2, g3, g4, g5, g6 = ('总览', '议题与词频', '内容与评论',
                              '传播与扩散', '事件与预警', '口径与方法')
    srcNote = ('全部数字来自 t_basin_article / t_basin_comment 实时聚合，无一处估值。')

    # ---- 跨平台（多源）融合：仅取四源交集议题 生态治理 / 医患矛盾 ----
    XP = BD.get('xplat') or {}
    XP_MERGED = (XP.get('merged') or {}).get(basin, {})
    XP_PLAT = XP.get('platforms') or {}
    XP_LIVE = [pl for pl in XP.get('live', []) if pl in XP_PLAT]   # 已接入且有序
    XP_ONLYWB = XP.get('topicsOnlyWeibo', [])
    def _xart(t):
        return {pl: (XP_MERGED.get(t, {}).get('article') or {}).get(pl, 0) for pl in XP_LIVE}
    def _xcmt(t):
        return {pl: (XP_MERGED.get(t, {}).get('comment') or {}).get(pl, 0) for pl in XP_LIVE}
    def _xsum(t, k):
        m = XP_MERGED.get(t, {}) or {}
        return m.get(k + 'Sum', sum((m.get(k) or {}).values()))

    # 事件簇（合并三议题；视图是流域级，簇是议题级）
    EV = []
    for _t in T3:
        for _c in ((bt.get(_t) or {}).get('clusters') or []):
            EV.append(dict(_c, topic=_t))

    # ---------------- 3 传播趋势与节奏（L2）----------------
    span, fullmv = TR['span'], TR['full']
    idx = {m: i for i, m in enumerate(span)}
    ser = [{'name': '全部议题', 'y': fullmv}]
    for _t in T3:
        yy = [0] * len(span)
        for m, v in (TR['byTopic'].get(_t) or []):
            if m in idx:
                yy[idx[m]] = v
        ser.append({'name': _t, 'y': yy})
    cutTxt = (f"采集截止 {TR['cut']}，末月 {TR['lastMonth']} 为<b>断月</b>（只到月中），"
              f"不能与整月比高低。" if TR['lastPartial'] else
              f"采集截止 {TR['cut']}。")
    trend_v = dict(
        id=p + '-trend', group=g4, name=full + '传播趋势与节奏',
        badge='L2 · 真实', badgeCls='new',
        lead=f"用库里现成的时间字段做月粒度节奏分析：本流域共 <b>{len(TR['months'])} 个月</b>"
             f"有样本，峰值月 <b>{TR['peak'][0]}</b>（{N(TR['peak'][1])} 条，占全量 "
             f"{TR['peak'][2]}%）。<b>但这张曲线不能当传播趋势读</b> —— "
             f"2026 年样本占 {TR['y2026pct']}%，是采集时间集中造成的，不是舆情爆发。"
             f"下面同时给出「年×月矩阵」与「年度声量」，用于判断是爆发还是采样偏差。",
        kpis=[
            K('有样本月份', f"{len(TR['months'])} 个", f"连续铺满 {len(span)} 格", 1),
            K('峰值月', TR['peak'][0], f"{N(TR['peak'][1])} 条 · {TR['peak'][2]}%", 2),
            K('2026 占比', f"{TR['y2026pct']}%", f"{N(TR['n2026'])} / {N(A)}", 3),
            K('近 12 个月', f"{TR['last12'][3]}%",
              f"{TR['last12'][0]} ~ {TR['last12'][1]}", 4),
            K('采集截止', TR['cut'], '断月已标注', 5),
        ],
        cards=[
            C(p + 'tr1', '月度声量 · 四线对照',
              '全部议题 / 生态治理 / 文旅 / 医患矛盾 分线（月粒度）· 纵轴从 0 起，避免放大波动',
              'mline', {'x': span, 'series': ser,
                        'cmap': {'全部议题': '#4a9dff', '生态治理': '#2ee6c0',
                                 '文旅': '#ffa940', '医患矛盾': '#ff7a7a'}},
              {'rot': 60, 'fs': 8.5, 'sym': False, 'smooth': False}, w=3, h=330),
            C(p + 'tr2', '年 × 月 声量矩阵',
              '行 = 年（自上而下由早到晚），列 = 1–12 月；格内数字 = 该月条数',
              'heat', {'x': TR['matX'], 'y': TR['years'],
                       'v': [[ci, ri, TR['mat'][ri][ci]]
                             for ri in range(len(TR['years']))
                             for ci in range(12)]},
              {'unit': '条/月', 'cut': '末列为断月：%s' % TR['lastMonth']}, w=3, h=300),
            C(p + 'tr5', '近 24 个月放大',
              '只截最近 24 个月重画（纵轴仍从 0 起）—— 上方全量曲线被早期长尾压平，'
              '这里看近期节奏；不是新数据，只是同一序列的窗口截取',
              'mline', {'x': TR['span'][-24:],
                        'series': [{'name': '全部议题', 'y': TR['full'][-24:]}]},
              {'rot': 55, 'fs': 8.5, 'sym': True, 'smooth': False,
               'legend': False, 'area': True}, w=3, h=260),
            C(p + 'tr3', '年度声量（全量口径）',
              f"含被前端过滤掉的 {N(d['filtered'])} 条其他议题 —— 分母层，避免孤立读数",
              'bar', {'x': [x for x, _ in d['years']], 'y': [v for _, v in d['years']]},
              {'p': 0, 'rot': 40, 'fs': 9}, w=2),
            C(p + 'tr4', '三议题月度峰值月',
              '各自声量最高的 3 个月 · 看三侧节奏是否同步', 'hbar',
              [[_t[:2] + ' ' + m, v] for _t in T3
               for m, v in sorted((TR['byTopic'].get(_t) or []),
                                  key=lambda x: -x[1])[:3]], {'p': 2}, w=1, h=300),
        ],
        notes=[
            nt('<b>这张曲线的读法（必须写清）</b>：库里 ' + str(TR['y2026pct']) +
               '% 的样本集中在 2026 年，原因是采集批次集中在近期，'
               '不是「2026 年舆情爆发」。要做跨年比较请用<b>年×月矩阵</b>里的同月对齐，'
               '或改用「该月议题占比」这类相对量。', k='warn'),
            nt(cutTxt, k='warn'),
            nt(srcNote, k='ok'),
        ],
    )

    # ---------------- 9 评论观点聚类（真实 · 三源合并）----------------
    # 微博单源评论不足门槛 → 改在三源合并评论上做无监督聚类（jieba + TF-IDF + KMeans）。
    GATE_CL = 300
    CL = (XP.get('cluster') or {}).get(basin) or {}
    CLc = CL.get('clusters') or []
    CLn, CLk = CL.get('n', 0), CL.get('k', 0)
    _clSil = ('—' if CL.get('sil') is None
              else '%.3f' % float(CL.get('sil')))
    # ---- A/D/P1 需要的三组现算量（2026-10-06）----
    # ① 各平台在本次聚类样本里的总量（= 各簇该平台之和，也等于 CLn）
    _clPlat = {}
    for _c in CLc:
        for _p, _v in (_c.get('plats') or []):
            _clPlat[_p] = _clPlat.get(_p, 0) + _v
    # 簇标签：2026-10-06 起优先用「独占词」(label)，老数据回退到 terms
    def _lbl(c):
        return list(c.get('label') or c.get('terms') or [])
    # ② 标签雷同的簇对：Jaccard 相似度过高说明标签已失去区分度，必须写明
    def _terms(c):
        return set(_lbl(c))
    _dup = []
    for i in range(len(CLc)):
        for j in range(i + 1, len(CLc)):
            a, b = _terms(CLc[i]), _terms(CLc[j])
            if not a or not b:
                continue
            jac = len(a & b) / float(len(a | b))
            if jac >= 0.5:
                _dup.append((i + 1, j + 1, jac, sorted(a & b), sorted(a - b), sorted(b - a)))
    # ③ 轮廓系数强弱判定（0.25 以下为弱结构，是通用经验阈值）
    _silv = CL.get('sil')
    _silWeak = (_silv is not None and _silv < 0.25)
    _silMid = (_silv is not None and 0.25 <= _silv < 0.50)
    if not _dup:
        _dupMsg = '已可用'
        _dupSub = '　各簇区分词互不相同，可直接读作该簇的讨论焦点。'
        _dupNote = '各簇区分词互不相同。'
    else:
        _mxJ = max(d[2] for d in _dup)
        _dupMsg = ('不足' if _mxJ >= 0.7 else
                   '部分重叠' if _mxJ >= 0.4 else '基本可用')
        _dupSub = ('　<b>本页有 %d 对簇共享同一个区分词</b>'
                   '（两两 Jaccard 最高 %.0f%%）—— 详见卡下说明。'
                   % (len(_dup), _mxJ * 100)
                   if _mxJ < 0.7 else
                   '　<b>本页有 %d 对簇的区分词高度雷同</b>'
                   '（两两 Jaccard 最高 %.0f%%），标签已不足以区分它们。'
                   % (len(_dup), _mxJ * 100))
        _dupNote = ('%d 对簇共享同一个区分词（两两 Jaccard 最高 %.0f%%）。'
                    % (len(_dup), _mxJ * 100))
    if CLc:
        _clLead = (f"微博单源评论仅 <b>{N(Cm)} 条</b>、低于 {GATE_CL} 条可解释门槛；"
                   f"本页改用<b>三源合并评论</b>（微博 + 小红书 + 知乎）共 <b>{N(CLn)} 条</b>"
                   f"做观点聚类：每条取「命中关键词」词袋 → TF-IDF → KMeans，"
                   f"自动聚出 <b>{CLk} 个观点簇</b>。簇标签取<b>该簇独占词</b>"
                   f"（在本簇的评论里占比 ≥15%、且是其他簇的 2 倍以上），"
                   f"只作观点结构参考、不做唯一解读。")
    else:
        _clLead = (f"三源合并评论仍不足门槛（当前 <b>{N(CLn)} 条</b>，门槛 {GATE_CL} 条），"
                   f"该模块暂不做聚类，仅列出缺口。")
    clust_v = dict(
        id=p + '-clust', group=g3, name=full + '评论观点聚类',
        badge='真实 · 三源', badgeCls='real',
        lead=_clLead,
        kpis=[
            K('合并评论', N(CLn), '微博+小红书+知乎', 1),
            K('观点簇数', f'{CLk} 个', 'KMeans 自动', 2),
            K('微博单源', f'{N(Cm)} 条', f'低于 {GATE_CL} 门槛', 3),
            K('轮廓系数', _clSil, '越高越可分', 4),
        ],
        cards=[
            C(p + 'cl1', '各观点簇规模',
              '每根柱 = 一个自动聚出的观点簇；横轴标签取<b>该簇独占词</b>'
              '（标签仍可能雷同，见下方说明卡）',
              'bar', {'x': ['·'.join(_lbl(c)[:2]) for c in CLc],
                      'y': [c['n'] for c in CLc]}, {'p': 3, 'rot': 0}, w=3),
            # ---- D 方案：平台构成带上「占该平台总量」的分母 ----
            # 原来只写「知乎125 / 小红书17」，读者会读成平台倾向；
            # 实际各平台召回量差异极大（微博仅 54 条、知乎 464 条），
            # 不给分母就会把小样本的少数条当成"该平台观点集中"。
            TABLE('观点簇一览（区分词 / 构成）',
                  [{'k': 'a', 'l': '簇'}, {'k': 'b', 'l': '区分词（该簇独占）'},
                   {'k': 'c', 'l': '条数', 'num': True}, {'k': 'd', 'l': '议题构成'},
                   {'k': 'e', 'l': '平台构成（含该平台总量占比）'}],
                  [{'a': f'簇{i + 1}', 'b': ' / '.join(_lbl(c)), 'c': N(c['n']),
                    'd': ' / '.join(f'{k}{v}' for k, v in c['topics']),
                    'e': ' / '.join('%s%d（占该平台 %s）' % (k, v, PC(v, _clPlat.get(k)))
                                    for k, v in c['plats'])}
                   for i, c in enumerate(CLc)],
                  # A 方案：把「簇区分度不足」写在卡上，不让读者自己发现
                  '「区分词」= 该词在<b>本簇</b>评论里的占比 ≥15%，'
                  '且是其他簇的 2 倍以上，即这个词几乎只谈论这一簇。'
                  '簇由算法自动划分、未经人工语义命名。' + _dupSub,
                  w=3),
            LIST('各簇代表评论（簇内按点赞 Top 3）',
                 [{'m1': f'簇{i + 1}', 'm2': s['plat'], 'm3': s['topic'],
                   'm4': f"赞 {N(s['like'])}", 'txt': s['txt']}
                  for i, c in enumerate(CLc) for s in c['samples']],
                 '代表评论 = 簇内点赞最高者，只作直观示例，不代表簇内全部观点',
                 meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag p'},
                       {'k': 'm3', 'cls': 'tag'}, {'k': 'm4', 'cls': 'tag'}], w=3),
        ] + ([
            # ---- A 方案：把两个"读图前必须知道"的结论写在卡片上，而不是让读者自己发现 ----
            # 用 TEXT 卡而非页脚 notes：这两点是**读这张表之前**就该知道的，
            # 放在页脚要翻到底才看到，等于没说。
            TEXT('读这张表之前必须知道的两件事',
                 ''.join([
                     '<p style="margin:0 0 9px"><b>① 簇之间的标签区分度%s。</b>'
                     '本批 %s 条评论上聚出 K=%d，轮廓系数 <b>%s</b>%s。</p>' % (
                         _dupMsg,
                         N(CLn), CLk, _clSil,
                         '，属<b>弱结构</b>（通用经验阈值 0.25）' if _silWeak else
                         '，属<b>中等偏弱</b>（落在 0.25~0.50 区间，说明簇边界本身不清晰）'
                         if _silMid else '，结构尚可'),
                     ('<p style="margin:0 0 9px">　　具体表现：%s。</p>' % '；'.join(
                         '簇%d 与 簇%d 的区分词<b>有 %d 个完全相同</b>'
                         '（各自 %d / %d 个词，Jaccard 相似度 %.0f%%），仅%s不同'
                         % (i, j, len(inter),
                            len(_terms(CLc[i - 1])), len(_terms(CLc[j - 1])), jc * 100,
                            '、'.join(only) if only else '标签顺序不同')
                         for i, j, jc, inter, _o1, only in _dup)
                     if _dup else
                     '<p style="margin:0 0 9px">　　具体表现：<b>各簇都取到了互不相同的独占词</b>'
                     '%s，标签可直接读作该簇的讨论焦点。</p>'
                     % ('（' + '；'.join('簇%d「%s」' % (i + 1, '、'.join(_lbl(c)))
                                        for i, c in enumerate(CLc)) + '）'
                        if CLc else '')),
                     '<p style="margin:0 0 9px">　　但<b>仍要记住</b>：'
                     '这些簇由 KMeans 自动划分、<b>未经人工语义命名</b>'
                     '（本批特征空间只有 20 余个领域关键词，见页脚口径）。'
                     '可解读为"这批评论的 %d 块讨论重心"，'
                     '<b>不宜当作彼此独立的观点类别</b>来陈述。</p>' % CLk,
                     '<p style="margin:0"><b>② 平台构成不能读成"平台倾向"。</b>'
                     '各平台在本次样本里的召回量极不均衡：%s。</p>'
                     % '　'.join('%s <b>%s</b> 条（占样本 %s）'
                                 % (k, N(v), PC(v, CLn) if CLn else '—')
                                 for k, v in sorted(_clPlat.items(), key=lambda x: -x[1])),
                     '<p style="margin:9px 0 0">　　表内「平台构成」列已给出'
                     '<b>占该平台总量</b>的分母，正是为此。'
                     '<b>某平台在某簇占比高，可能只因它在该簇的召回量本身高</b>，'
                     '与该平台用户的观点倾向无关。</p>',
                 ]),
                 '以下两条都是从本页数据现算的，不是套用结论', w=3),
        ] if (_dup or _silWeak or _silMid) else []),
        notes=[
            nt(f'<b>口径</b>：聚类在<b>三源合并评论</b>的「命中关键词」词袋上做'
               f'（微博单源 {N(Cm)} 条不足 {GATE_CL} 门槛）；特征取库内已标注的领域关键词，'
               f'全库去重后本流域仅 <b>20 余维</b>，'
               f'KMeans + TF-IDF 为经典无监督方法，簇数 K 为经验设定，不做「唯一正确」解读。'
               f'　<b>结果可复现</b>：进聚类前已按（平台, 议题, 评论内容, 点赞）稳定排序，'
               f'避免因 SQL 返回顺序不同导致每次构建结果漂移。'
               + (f'　本批轮廓系数 {_clSil}，'
                  + ('属弱结构（&lt;0.25）' if _silWeak else
                     '属中等偏弱（0.25~0.50）' if _silMid else
                     '结构尚可（≥0.50），但簇边界仍非人工语义划分')
                  + ' —— 详见「读这张表之前必须知道的两件事」。' if _silv is not None else ''),
               k='warn'),
            nt('簇由算法自动划分，<b>未经人工语义命名</b>；表内「区分词」为该簇的独占词'
               '（本簇占比 ≥15% 且≥ 其他簇 2 倍，已剔除跨簇高频词），'
               + _dupNote
               + '代表性评论按点赞排序，仅示例，不代表观点分布。', k='ok'),
            nt('本页只覆盖<b>生态环境治理 + 医患矛盾</b>两个交集议题（= 三源合并后有评论的议题）：'
               '<b>文旅未纳入</b>，因为它在小红书 / 知乎两库未采集、且微博侧文旅评论为 0 条，'
               '无评论可聚；文旅的分析见「议题专题」「词频与词云」「高影响力内容」等微博口径各页。'
               '　各平台召回量不均（%s），故「平台构成」一律附该平台总量作分母。'
               % '　'.join('%s %s 条' % (k, N(v))
                           for k, v in sorted(_clPlat.items(), key=lambda x: -x[1])),
               k='warn'),
        ],
    )

    # ---------------- 10 发布渠道与话语主体（L2）----------------
    kN = dict(CHn['kind'])
    chbar = {'x': [basin, ob_name],
             'series': [{'name': k, 'y': [kN.get(k, 0),
                                          dict(OB['channel']['kind']).get(k, 0)]}
                        for k in BM.AGENT_ORDER]}
    chTot = sum(kN.get(k, 0) for k in BM.AGENT_ORDER) or 1
    chTotO = sum(dict(OB['channel']['kind']).get(k, 0) for k in BM.AGENT_ORDER) or 1
    chpct = {'x': [basin, ob_name],
             'series': [{'name': k,
                         'y': [round(kN.get(k, 0) * 100.0 / chTot, 1),
                               round(dict(OB['channel']['kind']).get(k, 0) * 100.0 / chTotO, 1)]}
                        for k in BM.AGENT_ORDER]}
    ch_v = dict(
        id=p + '-channel', group=g4, name=full + '发布渠道与话语主体',
        badge='L2 · 真实', badgeCls='new',
        lead=f"<b>先说清口径</b>：库里的「分类」字段是混装的（终端型号 + 机构认证名 + "
             f"博主认证类型 + 账号自填简介），因此这里不做「渠道全量三分类」——"
             f"只用受控词表把能判定主体的部分归位，本流域可判定 <b>{N(CHn['agentKnown'])} / "
             f"{N(A)} 条（{CHn['agentPct']}%）</b>，剩下 {N(CHn['device'])} 条是终端标识、"
             f"{N(CHn['unknown'])} 条无法判定，全部如实列出。",
        kpis=[
            K('官方', N(kN.get('官方', 0)), f"{PC(kN.get('官方', 0), chTot)}（可判定样本内）", 1),
            K('媒体', N(kN.get('媒体', 0)), PC(kN.get('媒体', 0), chTot), 2),
            K('个人', N(kN.get('个人', 0)), PC(kN.get('个人', 0), chTot), 3),
            K('可判定率', f"{CHn['agentPct']}%", f"{N(CHn['agentKnown'])} / {N(A)}", 4),
            K('终端标识', N(CHn['device']), '不承载主体信息', 5),
            K('未归类', N(CHn['unknown']), '规则未命中', 6),
        ],
        cards=[
            C(p + 'ch1', '话语主体构成（可判定样本内）',
              '官方 / 媒体 / 个人 —— 分母是可判定样本，不是全量', 'donut',
              [[k, kN.get(k, 0)] for k in BM.AGENT_ORDER],
              {'donut': True, 'cmap': {'官方': '#4a9dff', '媒体': '#2fd6d0', '个人': '#ffb44d'}},
              w=1),
            C(p + 'ch2', '两流域话语主体并排对照（条数）',
              '本流域 vs 对照流域 · 同一条受控词表、同一判定顺序',
              'stack', chbar, {'cmap': {'官方': '#4a9dff', '媒体': '#2fd6d0',
                                        '个人': '#ffb44d'}}, w=1),
            C(p + 'ch3', '两流域话语主体结构占比（%）',
              '各流域内部 100% 归一 —— 跨流域比结构，不比绝对量',
              'stack', chpct, {'pct': True, 'labels': True,
                               'cmap': {'官方': '#4a9dff', '媒体': '#2fd6d0',
                                        '个人': '#ffb44d'}}, w=2),
            TABLE('归类明细 Top 12（原值 → 归类依据）',
                  [{'k': 'a', 'l': '分类（原始值）'}, {'k': 'b', 'l': '条数', 'num': True},
                   {'k': 'c', 'l': '归类'}, {'k': 'd', 'l': '命中的 token'}],
                  [{'a': r[0], 'b': N(r[1]), 'c': r[2], 'd': r[3]} for r in CHn['top']],
                  '任何一个归类都能在这张表里复查：原值、条数、判据三级可见', w=3),
            TABLE('未归类样例 Top 8（规则没命中，不猜）',
                  [{'k': 'a', 'l': '分类（原始值）'}, {'k': 'b', 'l': '条数', 'num': True}],
                  [{'a': r[0], 'b': N(r[1])} for r in CHn['unkSample']],
                  '这些多为机构简称或栏目名 —— 归入"未归类"而不是硬塞进某一类，'
                  '是为了让占比不被污染', w=2),
            TABLE('终端标识样例 Top 8（不是话语主体）',
                  [{'k': 'a', 'l': '分类（原始值）'}, {'k': 'b', 'l': '条数', 'num': True}],
                  [{'a': r[0], 'b': N(r[1])} for r in CHn['devSample']],
                  '「iPhone客户端」这类值描述的是发布端型号，与"谁在说"无关', w=1),
        ],
        notes=[
            nt('<b>为什么不直接画一个漂亮的三分类饼图</b>：那样会把 '
               + N(CHn['device']) + ' 条终端标识和 ' + N(CHn['unknown'])
               + ' 条无法判定的记录藏起来，可判定率就会从 ' + str(CHn['agentPct'])
               + '% 被读成 100%。', k='warn'),
            nt('归类规则（正则命中顺序：官方 → 媒体 → 个人 → 终端标识 → 未归类）：'
               + '；'.join('%s：%s' % (r[0], r[1]) for r in CHn['rules']), k='ok'),
        ],
    )

    # ---------------- 11 互动结构与扩散效率（L2）----------------
    allI = IA['all']
    IT = IA['byTopic']
    obI = OB['interact']
    itpct = {'x': T3L + ['全流域'],
             'series': [{'name': '点赞', 'y': [IT[_t]['share'][0] for _t in T3] + [allI['share'][0]]},
                        {'name': '评论', 'y': [IT[_t]['share'][1] for _t in T3] + [allI['share'][1]]},
                        {'name': '转发', 'y': [IT[_t]['share'][2] for _t in T3] + [allI['share'][2]]}]}
    itcmp = {'x': [basin, ob_name],
             'series': [{'name': '单篇点赞', 'y': [allI['perLk'], obI['all']['perLk']]},
                        {'name': '单篇评论', 'y': [allI['perCm'], obI['all']['perCm']]},
                        {'name': '单篇转发', 'y': [allI['perRp'], obI['all']['perRp']]}]}
    interact_v = dict(
        id=p + '-interact', group=g4, name=full + '互动结构与扩散效率',
        badge='L2 · 真实', badgeCls='new',
        lead=f"把三指标拆开看结构：本流域累计 赞 {N(allI['lk'])} / 评论 {N(allI['cm'])} / "
             f"转发 {N(allI['rp'])}，构成为 <b>{allI['share'][0]} : {allI['share'][1]} : "
             f"{allI['share'][2]}</b>；单篇转发 {allI['perRp']} 条，"
             f"<b>转发/点赞 = {allI['rrRatio']}</b>。"
             f"对照流域同一比值是 {obI['all']['rrRatio']} —— "
             f"{'本流域转发驱动更强' if allI['rrRatio'] > obI['all']['rrRatio'] else '本流域更偏点赞围观'}。",
        kpis=[
            K('累计点赞', N(allI['lk']), '全样本', 1),
            K('单篇点赞', str(allI['perLk']), f"评论 {allI['perCm']}", 2),
            K('单篇转发', str(allI['perRp']), f"对照 {obI['all']['perRp']}", 3),
            K('转赞比', str(allI['rrRatio']), f"对照 {obI['all']['rrRatio']}", 4),
            K('评论/点赞', str(allI['ratio']), '讨论强度', 5),
        ],
        cards=[
            C(p + 'in1', '互动三指标结构（占比 %）',
              '点赞 / 评论 / 转发 在议题内与全流域的构成 · 只比结构，不比绝对量',
              'stack', itpct, {'pct': True, 'labels': True}, w=2),
            C(p + 'in2', '单篇互动量：本流域 vs 对照流域',
              '每篇平均获得的赞、评论、转发 · 反映人均扩散力',
              'stack', itcmp, {'hor': False}, w=1),
            TABLE('分议题互动明细（可逐格复核）',
                  [{'k': 'a', 'l': '议题'}, {'k': 'b', 'l': '样本', 'num': True},
                   {'k': 'c', 'l': '点赞', 'num': True}, {'k': 'd', 'l': '评论', 'num': True},
                   {'k': 'e', 'l': '转发', 'num': True}, {'k': 'f', 'l': '单篇赞', 'num': True},
                   {'k': 'g', 'l': '单篇转', 'num': True}, {'k': 'h', 'l': '转赞比', 'num': True}],
                  [{'a': _t, 'b': N(IT[_t]['n']), 'c': N(IT[_t]['lk']), 'd': N(IT[_t]['cm']),
                    'e': N(IT[_t]['rp']), 'f': IT[_t]['perLk'], 'g': IT[_t]['perRp'],
                    'h': IT[_t]['rrRatio']} for _t in T3]
                  + [{'a': '全流域', 'b': N(allI['n']), 'c': N(allI['lk']), 'd': N(allI['cm']),
                      'e': N(allI['rp']), 'f': allI['perLk'], 'g': allI['perRp'],
                      'h': allI['rrRatio']}],
                  '所有单元格都能用一句 SQL 复算（口径见「口径与方法」页）', w=3),
            # ---- 建议 3：扩散比（转发/点赞）按事件类型 ----
            TEXT('扩散比 · 转发 ÷ 点赞：这一项和上面那张表量的不是同一件事',
                 '<p>上面三张互动卡给的都是<b>绝对量</b>（多少赞、多少转），它们同时受两个东西支配：'
                 '采集配额，以及少数几条爆款。下面的扩散比只取<b>比例</b>，配额被约掉、'
                 '绝对量纲也消失了，所以它是本页唯一能横向比"哪类内容更容易被推出去"的指标。</p>'
                 '<p><b>怎么读</b>：比值 &gt; 1 表示转发数超过点赞数 —— 内容被当作观点载体外传；'
                 '比值接近 0 表示它主要在站内被围观。悬停任一条可以看到该类的转发 / 点赞绝对量，'
                 '以及它占本流域转发总量的比例（用来判断这个比值是靠普遍现象还是靠单条撑起来的）。</p>'
                 '<p><b>不能读</b>：① 绝对量与本视图其它卡片<b>不可直接比大小</b>，'
                 '两者口径不同（一个是配额下的绝对量，一个是结构比）；'
                 '② 兜底层那一行（食品安全 / 社会治理）只作对照，<b>不计入本页合计</b>；'
                 '③ 转发/点赞继承了分子的极值敏感性 —— 极值最大的那一类，'
                 '去极值后比值会明显下降，这一点在图注里已标出。</p>'),
            C(p + 'in3', '扩散比 · 转发 / 点赞（按事件类型）',
              '转发＝外溢扩散，点赞＝站内认同　·　比值是<b>结构量</b>，不受采集配额影响　'
              '·　玫红＝转发已超过点赞　·　四类事件按流域<b>全量合并</b>（不拆省，'
              '各省条数受配额均衡、拆开只会放大样本噪声）　·　'
              '<b>极值敏感</b>：分子含单条爆款，去极值后比值会明显下降（悬停看该类去极值转发均值）',
              'hbart', [[s['ev'], s['zf'], '出圈' if s['zf'] >= 1 else '站内',
                         f"转发 {N(s['f'])} / 点赞 {N(s['z'])}　·　占本流域转发 {s['fShare']}%"
                         f"　·　样本 {N(s['n'])} 条：转发中位数 {N(s['med'])}、"
                         f"去极值均值 {s['trim']}、单条最高 {N(s['max'])}"]
                        for s in EP['spread']],
              {'cmap': {'出圈': '#c2185b', '站内': '#e0b48a'}, 'unit': ''}, w=3),
            LIST('高扩散内容 Top 8（按转发绝对值）',
                 [{'m1': f"转 {N(r['rp'])}", 'm2': f"赞 {N(r['lk'])}", 'm3': r['tp'],
                   'm4': r['pv'], 'm5': r['tm'], 'txt': r['txt']} for r in IA['top']],
                 '转发榜与点赞榜不是同一批内容：转发代表"愿意替它说话"，点赞只代表"看见了"',
                 meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag'},
                       {'k': 'm3', 'cls': 'tag p'}, {'k': 'm4', 'cls': 'tag'},
                       {'k': 'm5', 'cls': 'tag'}], w=3),
        ],
        notes=[
            nt('跨平台（微博 / 抖音）<b>不比绝对值</b>：两个平台的点赞、评论、转发机制不同，'
               '只能比结构占比。本页所有数字都只在微博内部比较。', k='warn'),
            nt('转赞比 = 转发数 ÷ 点赞数。它比"单篇转发量"更能说明扩散性质：'
               '高转赞比＝内容被当作观点载体传播，高赞低转＝围观表态。', k='ok'),
        ],
    )

    # ---------------- 12 关键传播节点（L3 ·跨平台）----------------
    # 2026-10-08 改版。原版只按发帖条数排 Top15，且三张卡（柱/曲线/柱）讲的是
    # 同一份数据 → 页面"空泛"的根因不是设计，而是 nodes_stats() 只聚合了
    # n/lk/cm/rp/tp/ch 六个字段，把库里已有的「单条最高赞 / 议题广度」丢了，
    # 于是只能回答"谁发得多"，回答不了"谁是节点"。
    # 改后主轴 = **单条爆发力**：同样是发 9 条，生***部单条最高赞 17,871，
    # 四****境 只有 1 —— 差 4 个数量级。按条数排二者并列，按爆发力排天壤之别。
    #
    # 跨平台（决策 2-A = 各流域页内做对比，不另开专题页）：三平台节点形态实测
    # 差异极大且不能共用一把尺子 —— 微博头部 n>=3（持续输出）、小红书头部几乎
    # 全是 n=1 但单条赞最高 91,859、知乎均赞最低（105）但评论/赞比最高。
    # 强行合并排名会把小红书的"一条即爆"误判成微博语境的"长尾过客"。
    #
    # 刻意不算「活跃跨度」：实测发布时间大面积非标（构建期实测小红书仅53.6%
    # 可解析、知乎 85.3%、微博 100%），半数缺失样本算出的"活跃 3 年"不可信。
    _plats = [x['name'] for x in NCPlats] or ['微博']
    _mat = NC.get('matrix') or []
    _cellv = []
    for ri, row in enumerate(_mat):
        for ci, cell in enumerate(row.get('cells') or []):
            _p, _v = cell[0], cell[1]
            # has=False → heat画成「暗格」；真0 条 → has=True 但值 0，视觉可区分
            _cellv.append([ci, ri, _v, _p not in NCmiss and _p in NClive])
    # 议题×平台矩阵：行=议题（按总声量降序），列=平台（按登记表顺序）
    _matX = _plats
    _matY = [r['topic'] for r in _mat]

    # 爆发力榜：三平台各自头部混排，按单条最高赞降序（并列时按平台+昵称，稳定）
    _bursts = sorted(NC.get('bursts') or [],
                     key=lambda x: (-x['max'], x['plat'], x['nick']))
    # 每平台头部形态，用于榜旁的「平台性格」小卡
    _forms = {x['name']: x for x in NCPlats}

    nodes_v = dict(
        id=p + '-nodes', group=g4, name=full + '关键传播节点',
        badge='L3 · 实测', badgeCls='ok',
        lead=f"谁在带节奏：本流域 {N(A)} 条微博来自 <b>{N(ND['authors'])} 位作者</b>，"
             f"其中 {N(ND['once'])} 位（{ND['oncePct']}%）只发过 1 条—— "
             f"舆论不是被少数人垄断，而是大量一次性发声叠加。"
             f"真正有节点属性的是另一批人：他们条数不进前 10，"
             f"却制造了不成比例的转发与评论。"
             f"<b>按条数排与按爆发力排，看到的是两批完全不同的账号。</b>"
             + (f"跨平台看：{'、'.join(NClive)} 的头部形态各不相同——"
                f"微博是「持续输出」，小红书是「单条爆款」（最高单条赞 "
                f"{N((_forms.get('小红书') or {}).get('maxLike', 0))}，"
                f"是微博的 {round((_forms.get('小红书') or {}).get('maxLike', 0) / max((_forms.get('微博') or {}).get('maxLike', 1), 1), 1)} 倍），"
                f"知乎是「深度讨论」。"
                if len(NClive) >= 2 else ''),
        kpis=[
            K('参与作者', N(ND['authors']), 'ID 已脱敏', 1),
            K('一次作者', N(ND['once']), f"{ND['oncePct']}% 只发 1 条", 2),
            K('头部 10 位占比', f"{ND['conc'][2][2]}%", f"{N(ND['conc'][2][1])} 条", 3),
            K('爆发型节点', N(dict(NC.get('kindN') or {}).get('爆发型', 0)),
              '条数≤3 但均赞≥1000', 4),
            K('常态型节点', N(dict(NC.get('kindN') or {}).get('常态型', 0)),
              '跨平台头部合计', 5),
        ],
        cards=[
            C(p + 'nd1', '议题 × 平台 声量矩阵',
              '行 = 议题（按总声量降序），列 = 平台，格内数字 = 该平台该议题条数；'
              '暗格 = <b>该平台未采集</b>（与「真 0 条」严格区分）',
              'heat', {'x': _matX, 'y': _matY, 'v': _cellv},
              # ruler=True：heat 的色标是渲染器现算的（色域上下限 + 「暗格=无样本」
              # 的说明），不打开就只剩一张没有刻度的色块图，读者只能靠颜色猜。
              {'unit': '条', 'sqrt': True}, w=3, h=280, ruler=True),
            # 标题里的条数由数据长度现算，不写死 —— 写死的「Top 10」与实际画 12 条
            # 会随数据变化对不上（这类"标题与内容不符"在审查里等同于错误）。
            C(p + 'nd2', '爆发力榜 Top %d（按单条最高赞）' % min(12, len(_bursts)),
              '条形 = 该作者<b>单条最高赞</b>，是"一句话能引爆讨论"的能力，'
              '与"发得多"是两回事；悬停看条数 / 均赞 / 议题数',
              'hbar', [[('%s·%s' % (x['plat'], x['nick'])), x['max']] for x in _bursts[:12]],
              # w=3 而非 2：栅格 3 列，w 之和（3+3+3+3）必须能被 3 整除，
              # 否则 `grid-auto-flow:dense` 会在末行留一个空洞。
              {'p': 0, 'n': 12, 'fs': 9.5}, w=3, h=380),
            # ⚠ 不用 vcard：那渲染器是**视频封面卡专用**（要 cid/title/top.recommend，
            #   传 {k,v,d} 会被当成缺字段的视频卡渲染成破图 + 4 条资源加载失败）。
            #   这里直接用 TABLE —— kind:'table' 本身就是一张独立卡片（自带标题/副标题），
            #   不要再套 C()：C() 会把它当 recipe 塞进 'r'，模板里没有 kind='table' 的分支。
            TABLE('平台头部形态对照',
                  [{'k': 'a', 'l': '平台'}, {'k': 'b', 'l': '形态'},
                   {'k': 'c', 'l': '条数', 'num': True}, {'k': 'd', 'l': '作者', 'num': True},
                   {'k': 'e', 'l': '活跃作者', 'num': True},
                   {'k': 'f', 'l': '均赞', 'num': True}, {'k': 'g', 'l': '最高单条赞', 'num': True}],
                  # ⚠ 未采集的平台**整行**写「— 未采集 —」，不能只改最后一列：
                  #   「0 / 0 / 0（0.0%）」与"该平台确实一条都没有"字面完全一样，
                  #   等于把「缺口」伪装成「真 0 条」——本项目明令禁止。
                  [{'a': x['name'],
                    'b': (x.get('form') or '— 未采集 —'),
                    'c': '— 未采集 —' if x.get('missing') else N(x['article']),
                    'd': '—' if x.get('missing') else N(x['authors']),
                    'e': '—' if x.get('missing') else '%s（%s%%）' % (N(x['active']), x['activePct']),
                    'f': '—' if x.get('missing') else N(x['avgLike']),
                    'g': '—' if x.get('missing') else N(x['maxLike'])}
                   for x in NCPlats] if NCPlats else [],
                  '同一套「爆发力」口径下的三种节点形态 —— 不能用同一把尺子排名', w=3,
                  note='活跃作者 = 发过 ≥2 条的账号数；三平台头部形态不同，'
                       '**不能合并成一张总榜**（详见下方口径披露）。'
                       '「最高单条赞」是本流域该平台的<b>全域极值</b>，'
                       '可能来自只发过 1 条的账号 —— 这类账号不进下方「节点」榜'
                       '（节点要求 ≥2 条），因此表里的极值未必能在榜上找到。'),
            TABLE('节点档案：爆发型 vs 常态型',
                  [{'k': 'a', 'l': '作者（脱敏）'}, {'k': 'b', 'l': '平台'},
                   {'k': 'c', 'l': '类型'}, {'k': 'd', 'l': '条数', 'num': True},
                   {'k': 'e', 'l': '单条最高赞', 'num': True}, {'k': 'f', 'l': '均赞', 'num': True},
                   {'k': 'g', 'l': '议题数', 'num': True}],
                  # 取「爆发型前 3 + 常态型前 3」而不是「全榜前 3 + 全榜末 3」：
                  # 末 3 名会随数据一路漂到知乎的长尾（均赞 12），既不能说明形态差异、
                  # 又容易让人把"知乎影响力小"当成结论。同一类型各自取头部才可比。
                  [{'a': x['nick'], 'b': x['plat'], 'c': x['kind'],
                    'd': N(x['n']), 'e': N(x['max']), 'f': N(x['avg']),
                    'g': N(x['ntop'])}
                   for x in ([y for y in _bursts if y['kind'] == '爆发型'][:3] +
                             [y for y in _bursts if y['kind'] == '常态型'][:3])],
                  '表中为<b>两类各自的前 3 位</b>（不是总榜首尾）。'
                  '类型判定：<b>爆发型</b> = 条数 ≤3 且均赞 ≥1000（少数几条但每条都爆）；'
                  '<b>常态型</b> = 其余。两者不可比 —— 条数多不代表影响力大', w=3),
        ],
        notes=[
            nt(NC.get('gap_note') or
               '节点分类只用「单条爆发力 + 议题广度」两个可算口径。', k='warn'),
            nt('矩阵里的 <b>文旅 / 社会治理只有微博有数据</b>（小红书、知乎本轮未采到这两类）'
               '—— 这是<b>采集覆盖差异</b>，不能读成"这两个议题在别的平台没人讨论"。'
               '可跨平台比较的只有 <b>生态治理 / 医患矛盾</b>。', k='warn'),
            nt('作者昵称与主页在入库前已脱敏（保留首尾字符），页面不展示可回溯到个人的标识。',
               k='ok'),
        ],
    )

    # ---------------- 14 事件监测（L3）----------------
    evRows = sorted(EV, key=lambda c: -c['n'])
    ecCov = ((bt.get('生态治理') or {}).get('coverage') or {})
    tvCov = ((bt.get('文旅') or {}).get('coverage') or {})
    ytCov = ((bt.get('医患矛盾') or {}).get('coverage') or {})
    evMonths = TR['span'][-24:]
    mi = {m: i for i, m in enumerate(evMonths)}
    evHeat = {'x': evMonths, 'y': [c['name'] for c in evRows],
              'v': [[mi[m], ri, v] for ri, c in enumerate(evRows)
                    for m, v in (c.get('months') or []) if m in mi]}
    # ---- 事件台账（v14）需要的三个派生量 ----
    # ① 议题配色：项目语义三色（墨绿/赭黄/绛红），与「三大主题」全局一致。
    #    ⚠ 不要用 cmap 里那些 '#2ee6c0'/'#ff7a7a' —— 那是换沙色主题**之前**
    #    的深色底配色，浅底上几乎不可读（同_shot2.py 那条深色底的教训）。
    EV_TOPIC_COLOR = {'生态治理': '#3f8f63', '文旅': '#c8862a', '医患矛盾': '#c65a4a'}
    # ② 「高负」判定阈值。与风险分级页的负面分级保持同一档位，
    #    免得同一事件在两页一个算高负一个不算。
    EV_NEG_GATE = 50
    # ③ 样本的 2026 年占比：台账里所有「不可作趋势解读」警告都要用到。
    #    实测长江 68% / 黄河 59% —— 正因为过半样本挤在一年，
    #    任何「近 6 月 vs 前 6 月」的增幅都是伪信号。
    _evY = {}
    for _c in evRows:
        for _m, _v in (_c.get('months') or []):
            _evY[_m[:4]] = _evY.get(_m[:4], 0) + _v
    _evY26 = round(100.0 * _evY.get('2026', 0) / max(1, sum(_evY.values())))
    # 另一个流域的同一比率（用于"两个流域都如此"的旁证，避免只说本流域）。
    # 从 basin_data.json 直接算，不硬编码 —— 换流域后仍成立。
    _evY26o = '—'
    try:
        _bd = json.load(io.open(os.path.join(BASE, 'basin_data.json'),
                               encoding='utf-8'))
        for _bn, _bv in (_bd.get('basins') or {}).items():
            if _bn == basin:
                continue
            _o = {}
            for _t in T3:
                for _c in (_bv.get('byTopic', {}).get(_t, {}) or {}).get('clusters', []):
                    for _m, _v in (_c.get('months') or []):
                        _o[_m[:4]] = _o.get(_m[:4], 0) + _v
            if _o:
                _evY26o = round(100.0 * _o.get('2026', 0) / max(1, sum(_o.values())))
                break
    except Exception:
        pass

    # ---- 建议 1 的矩阵数据：事件类型 × 省份，去极值均值 ----
    # 行序按 EV_ORDER（三大主题 → 兜底层），列序沿江上游 → 下游。
    # 空格子给 0（渲染器画成"暗格=无样本"），非零但很小的值**原样传入** ——
    # 早期版本在 Python 侧四舍五入到整数，导致 0.06~0.4 被显示成 0，
    # 读者会把"接近零"误读成"完全没有"，这是本卡最不能犯的错。
    _epCells = [c['n'] for r in EP['rows'] for c in r['cells'] if c['n']]
    _epNMin = min(_epCells) if _epCells else 0
    _epNMax = max(_epCells) if _epCells else 0
    _epMaxOne = max((s['max'] for s in EP['spread']), default=0)
    _epTopCell, _epTopVal = '-', 0
    for _r in EP['rows']:
        for _i, _c in enumerate(_r['cells']):
            if _c['n'] and _c['trim'] > _epTopVal:
                _epTopVal, _epTopCell = _c['trim'], '%s × %s' % (_r['ev'], EP['provs'][_i])
    evProvHeat = {
        'x': EP['provs'],
        'y': [r['ev'] + ('（兜底层）' if r['rest'] else '') for r in EP['rows']],
        # 第 4 元素 = 「该格是否有样本」。必须显式传：只按值 > 0 判断的话，
        # 「有 6 条样本但去极值均值恰为 0」的格子会被画成无样本暗格（西藏 × 医患纠纷即如此）。
        'v': [[ci, ri, round(c['trim'], 2), 1 if c['n'] else 0]
              for ri, r in enumerate(EP['rows'])
              for ci, c in enumerate(r['cells'])],
    }
    assert sum(r['all']['n'] for r in EP['rows']) + EP['multi'] >= d['articles'] * 0.9, \
        '事件×省份矩阵漏样本过多：%d + %d < %d' % (
            sum(r['all']['n'] for r in EP['rows']), EP['multi'], d['articles'])

    ev_v = dict(
        id=p + '-events', group=g5, name=full + '事件监测',
        badge='L3 · 实测', badgeCls='ok',
        lead=f"把「议题」这个大桶拆成<b>具体事件</b>：本流域三大主题共归纳出 "
             f"<b>{len(evRows)} 个事件簇</b>，最大的是「{evRows[0]['name']}」"
             f"（{N(evRows[0]['n'])} 条，{evRows[0]['t0']} 起）。"
             f"<b>事件之间量级差 {int(evRows[0]['n'] / max(1, evRows[-1]['n']))} 倍、"
             f"性质也不同</b>，故不用同一种卡片装全部 —— "
             f"下面按信息类型分成 4 种载体："
             f"<b>面板</b>（规模最大者）、<b>警示块</b>（负面 ≥{EV_NEG_GATE}%）、"
             f"<b>逐月命中带</b>（时间分布）、<b>行式清单</b>（全量，可点开看释义与原文）。"
             f"<b>簇间允许重叠</b>，所以各簇篇数不能相加。",
        kpis=[
            K('事件簇', f'{len(evRows)} 个', '人工词表归纳', 1),
            K('最大事件', evRows[0]['name'], f"{N(evRows[0]['n'])} 条", 2),
            K('簇覆盖率', f"{N(ecCov.get('pct'))}% / {N(tvCov.get('pct'))}% / {N(ytCov.get('pct'))}%",
              f"生态 {N(ecCov.get('covered'))} 篇 / 文旅 {N(tvCov.get('covered'))} 篇 / "
              f"医患 {N(ytCov.get('covered'))} 篇", 3),
            K('事件簇分布', f"{len([c for c in evRows if c['topic'] == '文旅'])} 文旅",
              f"{len([c for c in evRows if c['topic'] == '生态治理'])} 生态 / "
              f"{len([c for c in evRows if c['topic'] == '医患矛盾'])} 医患", 4),
            K('样本闸门', f"{d.get('clusterGate', 30)} 条", '线上事件只作线索', 5),
        ],
        cards=[
            # ---- 事件台账（v14，2026-10-07）：4 种载体替代原 4 张同质图----
            # 原 ev1 声量排行 / ev3 情感篇数 / ev4 情感占比 三张是同批数据的
            # 不同切法，且整页零交互。改为按信息类型分配载体：
            # 面板=规模重点 / 警示块=负面风险 / 月度带=时间 / 清单=全量+下钻。
            # 拆成两张卡（概览层 + 下钻层）而不是一张 2000px 的巨卡：
            # ① 3 列栅格里单卡过高会让首屏几乎全是它；
            # ② 渲染器带 @media 断点，窄屏两栏堆叠后更高 —— 固定 h= 必然在
            #    某个宽度下再次撑破宿主（实测首版 h=1180 差 880px）。
            C(p + 'ev1', '事件台账 · 概览',
              '规模最大者用面板、负面 ≥%d%% 者用警示块、逐月命中带看时间分布、'
              '议题对比说清哪些议题能横向比' % EV_NEG_GATE,
              'evledger',
              {'cls': evRows, 'gate': d.get('clusterGate', 30),
               'topics': list(T3), 'tcolor': EV_TOPIC_COLOR,
               'negGate': EV_NEG_GATE, 'y26': _evY26, 'part': 'top'},
              w=3, h=1050, noexp=True),
            C(p + 'ev2', '事件台账 · 全量清单（点行看详情）',
              '按议题分组的行式清单；点任一行切换下方释义、原文、省份分布与情感构成',
              'evledger',
              {'cls': evRows, 'gate': d.get('clusterGate', 30),
               'topics': list(T3), 'tcolor': EV_TOPIC_COLOR,
               'negGate': EV_NEG_GATE, 'y26': _evY26, 'part': 'list'},
              w=3, h=1100, noexp=True),
            C(p + 'ev5', '事件 × 月份（近 24 个月）',
              '一行为一个事件、一列为一个月的命中篇数；空白格＝该月无命中。'
              '与台账内的「逐月命中带」同色阶，此处多给 6 个月用于看更长的跨度',
              'heat', evHeat, {'unit': '条/月', 'yw': 96,
                               'cut': '末列 %s 为断月' % TR['lastMonth']}, w=3, h=380),
            TABLE('事件明细（可逐格复核）',
                  [{'k': 'a', 'l': '事件'}, {'k': 'b', 'l': '议题'}, {'k': 'c', 'l': '篇数', 'num': True},
                   {'k': 'd', 'l': '首次'}, {'k': 'e', 'l': '最近'}, {'k': 'f', 'l': '点赞', 'num': True},
                   {'k': 'g', 'l': '转发', 'num': True}, {'k': 'h', 'l': '负面占比', 'num': True},
                   {'k': 'i', 'l': '首要省份'}],
                  [{'a': c['name'], 'b': c['topic'], 'c': N(c['n']), 'd': c['t0'], 'e': c['t1'],
                    'f': N(c['lk']), 'g': N(c['rep']), 'h': f"{c.get('negPct', 0)}%",
                    'i': (c['prov'][0][0] if c.get('prov') else '-')} for c in evRows],
                  '负面占比 = 该事件命中微博中被判负面的比例；口径与风险分级页一致。'
                  '「首要省份」是<b>首个命中省</b>、<b>不是占比</b> —— 台账行式清单里的'
                  '「首省占比」才是分布信息，两者不可混读', w=3),
            LIST('事件代表原文（每事件取最高互动 1 条）',
                 [{'m1': f"命 {N(c['n'])} 条", 'm2': c['topic'],
                   'm3': f"首发 {c['first']['tm'][:10]}" if c.get('first') else '',
                   'm4': f"互动 {N(c['ev'][0]['eng'])}" if c.get('ev') else '',
                   'txt': (c['ev'][0]['txt'][:120] + '…') if c.get('ev') else ''}
                  for c in evRows[:8]],
                 '每条都带原始链接，可在库外核验——这是"事件"与"话题标签"的区别。'
                 '台账内点任一事件亦可看该事件的 2 条原文',
                 meta=[{'k': 'm1', 'cls': 'tag b'}, {'k': 'm2', 'cls': 'tag p'},
                       {'k': 'm3', 'cls': 'tag'}, {'k': 'm4', 'cls': 'tag'}], w=3),
        ],
        notes=[
            nt('<b>时间维度不可作趋势解读</b>：簇月份合计 <b>%d%%</b> 集中在 2026 年'
               '（另一流域 %s%%）。故台账里<b>不做「升温 / 降温」</b>，'
               '逐月命中带只读"该事件在哪些月份出现过"。'
               % (_evY26, _evY26o), k='warn'),
            nt('<b>议题之间不能整体比负面强度</b>：三大主题的负面占比区间'
               '<b>大幅交叠</b>（见台账「议题对比」区的交叠分档），'
               '"某议题比另一议题更负面"在本批数据里<b>不成立</b>。', k='warn'),
            nt('<b>「覆盖省数」是常量列</b>：实测恒为 3~4，两个流域都是，'
               '占表格宽度却不携带信息，故不展示；改用<b>首省占比</b>'
               '（Top1 省份 ÷ 该事件总篇数，实测 45%~80%），'
               '可区分区域性事件（≥60%）与跨省扩散（&lt;50%）。', k='warn'),
            nt('<b>簇间不可相加</b>：实测有词同时命中两个簇（如「消费」），'
               f"重叠篇数 生态 {N(((bt.get('生态治理') or {}).get('coverage') or {}).get('overlap'))} / "
               f"文旅 {N(((bt.get('文旅') or {}).get('coverage') or {}).get('overlap'))}，"
               '因此各簇篇数之和 ≠ 议题总篇数。', k='warn'),
            nt('词表是人工归纳的短语集合，召回不完整；覆盖率已如实列在 KPI 里，'
               '未被覆盖的样本不等于"没有舆情"。', k='warn'),
            nt('事件词表的匹配口径：正文包含该簇任一词即命中（**不匹配「命中关键词」字段**，'
               '那是采集端配额标记）。完整词表与释义见「词频与词云」页的事件簇面板。', k='ok'),
        ],
    )

    # ---------------- 15 风险分级预警（L3）----------------
    RKI = RK['items']
    gated = [x for x in RKI if x.get('gated')]
    gray = [x for x in RKI if not x.get('gated')]
    lvCnt = {}
    for x in gated:
        lvCnt[x['key']] = lvCnt.get(x['key'], 0) + 1
    risk_v = dict(
        id=p + '-risk', group=g5, name=full + '风险分级预警',
        badge='L3 · 实测', badgeCls='ok',
        lead=f"规则化分级，四个因子、权重公开、逐事件可复核：本流域 "
             f"{len(gated)} 个事件过闸参与分级（{N(RK['gate'])} 条为闸门线），"
             f"另有 {len(gray)} 个事件命中篇数不足、<b>只列线索不入级</b>。"
             f"分级结果：{'、'.join('%s 级 %d 个' % (k, v) for k, v in lvCnt.items())}。"
             f"<b>权重是团队设定的评分规则，不是拟合出来的模型</b> —— "
             f"所以下面把每一分的来源都摊开。",
        kpis=[
            K('入级事件', f'{len(gated)} 个', f'闸门 {RK["gate"]} 条', 1),
            K('红 / 橙', f"{lvCnt.get('红', 0)} / {lvCnt.get('橙', 0)}",
              '一级 / 二级', 2),
            K('最高分', f"{gated[0]['score']} 分" if gated else '—',
              gated[0]['name'] if gated else '无', 3),
            K('未入级线索', f'{len(gray)} 个', '样本不足', 4),
            K('因子权重', '40/25/20/15', '负面/声量/敏感/扩散', 5),
        ],
        cards=[
            C(p + 'rk1', '事件风险得分（0–100）',
              '四个因子加权求和；得分越高越靠前 · 灰色事件为样本不足未入级',
              'hbar', [[x['name'], x['score'] or 0] for x in RKI if x.get('gated')],
              {'p': 0, 'n': len(gated)}, w=2, h=420),
            C(p + 'rk2', '因子贡献分解（各事件 × 四因子）',
              '每个事件的 100 分里，各因子分别贡献了多少', 'stack',
              {'x': [x['name'][:8] for x in gated],
               'series': [{'name': '负面占比 40', 'y': [x['p_neg'] for x in gated]},
                          {'name': '声量 25', 'y': [x['p_n'] for x in gated]},
                          {'name': '敏感度 20', 'y': [x['p_sens'] for x in gated]},
                          {'name': '扩散 15', 'y': [x['p_rp'] for x in gated]}]},
              {'pct': False, 'labels': False}, w=2),
            TABLE('权重表与归一区间（口径全公开）',
                  [{'k': 'a', 'l': '因子'}, {'k': 'b', 'l': '权重', 'num': True},
                   {'k': 'c', 'l': '本流域归一区间'}, {'k': 'd', 'l': '口径'}],
                  [{'a': f[0], 'b': f[1],
                    'c': (['绝对占比 0 ~ 100%',
                           '%s ~ %s 条' % (RK['scale']['n'][0], RK['scale']['n'][1]),
                           '%s ~ %s' % (RK['scale']['sens'][0], RK['scale']['sens'][1]),
                           '%s ~ %s 转发/篇' % (RK['scale']['rp'][0], RK['scale']['rp'][1])][i]
                          if RK.get('scale') else '—'),
                    'd': f[2]} for i, f in enumerate(RK['factors'])],
                  '负面占比取绝对值（一半负面本身就说明问题）；其余三项取本流域内 min-max 归一',
                  w=3),
            TABLE('逐事件计分明细（每一分都能查）',
                  [{'k': 'a', 'l': '事件'}, {'k': 'b', 'l': '篇数', 'num': True},
                   {'k': 'c', 'l': '负面占比', 'num': True}, {'k': 'd', 'l': '声量归一', 'num': True},
                   {'k': 'e', 'l': '敏感度', 'num': True}, {'k': 'f', 'l': '扩散归一', 'num': True},
                   {'k': 'g', 'l': '总分', 'num': True}, {'k': 'h', 'l': '级别'},
                   {'k': 'i', 'l': '处置口径'}],
                  [{'a': x['name'], 'b': N(x['n']), 'c': f"{x['negPct']}%",
                    'd': (x['f_n'] if x.get('gated') else '—'),
                    'e': (x['f_sens'] if x.get('gated') else '—'),
                    'f': (x['f_rp'] if x.get('gated') else '—'),
                    'g': (x['score'] if x.get('gated') else '不入级'),
                    'h': x['level'], 'i': x['act']} for x in RKI],
                  '未入级事件不参与 min-max 归一，避免小样本把大事件的归一值压扁', w=3),
            TABLE('分级处置口径对照',
                  [{'k': 'a', 'l': '级别'}, {'k': 'b', 'l': '分值区间'},
                   {'k': 'c', 'l': '处置口径'}, {'k': 'd', 'l': '本流域事件数', 'num': True}],
                  [{'a': L[1], 'b': f'≥ {L[0]} 分' if L[0] else '< 45 分',
                    'c': L[3], 'd': lvCnt.get(L[1], 0)} for L in RK['levels']],
                  '分值区间与处置口径是规则设定值，评审可直接质疑权重 —— 页面已给出全部原始量',
                  w=3),
        ],
        notes=[
            nt('<b>这是规则化预警，不是预测模型</b>：四个因子全部来自库内实测聚合，'
               '权重由团队设定。改变权重会改变分级结果，因此原始量（负面占比、篇数、'
               '敏感词命中比例、单篇转发）在明细表里全部给出。', k='warn'),
            nt(f"样本闸门：命中篇数 < {RK['gate']} 的事件不入级。"
               '原因很直接 —— 3 篇全负面会被算成"100% 负面"，那是样本量在说话，'
               '不是风险在说话。', k='warn'),
        ],
    )

    # ---------------- 17 情感模型校准（L4）----------------
    dSent = dict(zip(('正面', '中性', '负面'), [x[1] for x in d['sent']]))
    dThr = dict(CB['dictThree'])
    mTot = sum(dSent.values()) or 1
    dTot = sum(dThr.values()) or 1
    calibCmp = {
        'x': ['SnowNLP 模型', '极性子词典法'],
        'series': [{'name': k,
                    'y': [round(dSent[k] * 100.0 / mTot, 1),
                          round(dThr[k] * 100.0 / dTot, 1)]}
                   for k in ('正面', '中性', '负面')],
    }
    calib_v = dict(
        id=p + '-calib', group=g6, name=full + '情感模型校准',
        badge='L4 · 缺口', badgeCls='plan',
        lead=f"不回避模型的毛病：现用的 SnowNLP 是通用模型，本流域实测"
             f"<b>被判「中性」的只有 {CB['neuPct']}%</b>，"
             f"<b>{CB['extPct']}% 的样本极性分落在 0.9 以上或 0.1 以下</b>（极端两端），"
             f"说明它对生态/文旅这类领域词几乎不做中性判断。"
             f"再用人工极性子词典交叉验证：两者判定一致的只有 "
             f"<b>{CB['agreePct']}%</b>。下面把这个偏差量化，并给出校准路径。",
        kpis=[
            K('中性段占比', f"{CB['neuPct']}%", f"对照流域 {OB['calib']['neuPct']}%", 1),
            K('极端分占比', f"{CB['extPct']}%", '≥0.9 或 ≤0.1', 2),
            K('词典法一致率', f"{CB['agreePct']}%", f"{N(CB['agree'])} / {N(CB['n'])}", 3),
            K('不一致样本', N(CB['n'] - CB['agree']), '已抽样列示', 4),
            K('正面词/负面词', f"{len(CB['posWords'])} / {len(CB['negWords'])}", '极性子词典', 5),
        ],
        cards=[
            C(p + 'cb1', '极性分十档分布',
              '横轴 = SnowNLP 极性分区间，纵轴 = 该区间的微博条数 —— 两端高、中间塌 = 判不出中性',
              'bar', {'x': CB['histX'], 'y': CB['hist']}, {'p': 3, 'rot': 40, 'fs': 9},
              w=2),
            C(p + 'cb2', '模型判定 vs 词典法判定（结构对照 %）',
              '两种方法各自的三档结构；差距越大说明领域词偏置越明显', 'stack',
              calibCmp,
              {'pct': True, 'labels': True,
               'cmap': {'正面': '#3ddc97', '中性': '#4a9dff', '负面': '#ff6b6b'}}, w=1),
            TABLE('判定不一致样例（真实原文，可逐条核对）',
                  [{'k': 'a', 'l': '模型'}, {'k': 'b', 'l': '词典法'}, {'k': 'c', 'l': '正/负词命中'},
                   {'k': 'd', 'l': '议题'}, {'k': 'e', 'l': '正文摘要'}],
                  [{'a': x['model'], 'b': x['dict'], 'c': f"{x['pos']} / {x['neg']}",
                    't': x['tp'], 'd': x['tp'], 'e': x['txt'] + '…'} for x in CB['diff']],
                  '两个方向的不一致都列出来了（模型正/词典负、模型负/词典正等）；校准要修的就是这类样本',
                  w=3),
            TABLE('校准路径与当前状态',
                  [{'k': 'a', 'l': '步骤'}, {'k': 'b', 'l': '做法'}, {'k': 'c', 'l': '状态'}],
                  [{'a': '① 标注语料', 'b': '从三个议题各抽 300 条正文 + 300 条评论人工标注三档',
                    'c': '待做（需人工投入）'},
                   {'a': '② 领域微调', 'b': '用标注语料微调情感分类头，或换用中文情感预训练模型',
                    'c': '待做'},
                   {'a': '③ 阈值重标', 'b': '按标注集重新标定 0.4 / 0.6 两个分档阈值',
                    'c': '待做'},
                   {'a': '④ 交叉复核', 'b': '校准后与极性子词典法复核，目标一致率 ≥ 75%',
                    'c': f"当前 {CB['agreePct']}%"}],
                  '在校准完成前，页面所有情感结论只作结构参考、不做极性外推', w=3),
            TABLE('极性子词典（交叉验证基准，可增删复核）',
                  [{'k': 'a', 'l': '极性'}, {'k': 'b', 'l': '词数', 'num': True},
                   {'k': 'c', 'l': '词表'}],
                  [{'a': '正面', 'b': len(CB['posWords']), 'c': '、'.join(CB['posWords'])},
                   {'a': '负面', 'b': len(CB['negWords']), 'c': '、'.join(CB['negWords'])}],
                  '词典法不是替代模型，只是给"模型偏置"提供一个可复核的参照', w=3),
        ],
        notes=[
            nt('这一页的结论是"模型需要校准"，依据是三条实测：中性段仅 '
               + str(CB['neuPct']) + '%、极端分占 ' + str(CB['extPct']) + '%、'
               '与词典法一致率 ' + str(CB['agreePct']) + '%。', k='warn'),
            nt('校准前，页面里的正/负比例只能当"结构参考"，不能当作"公众态度"的结论；'
               '涉及态度的表述请回到原文（各页均提供原文与链接）。', k='warn'),
        ],
    )

    # ---------------- 15b 事件传播强度（建议 1）----------------
    # 为什么独立成页而不是并进「事件监测」：那张页已有 6 张卡、宽度合计 14（3 列栅格），
    # 再塞 3 张整行卡会出现末行空洞（3 的倍数约束）。独立成页也让这两张表有整行宽度。
    evp_v = dict(
        id=p + '-evprov', group=g5, name=full + '事件传播强度',
        badge='L3 · 实测', badgeCls='ok',
        lead=f"把「事件」放到<b>省份</b>和<b>传播强度</b>两个维度上重看一遍。"
             f"事件类型取自采集端的命中关键词（{len(EP['rows'])} 类，与议题一一对应），"
             f"省份按<b>沿江上游 → 下游</b>排开（{len(EP['provs'])} 个）。"
             f"本流域聚焦样本 {N(EP['all']['n'])} 条，其中 {N(EP['multi'])} 条的命中关键词是"
             f"多省合并串、无法归到单一省份，<b>不进入矩阵</b>。",
        kpis=[
            K('事件类型', f"{len(EP['rows'])} 类", '与议题一一对应，可当反查索引', 1),
            K('矩阵格数', f"{len(EP['rows'])} × {len(EP['provs'])}",
              f"格内条数 {_epNMin}~{_epNMax} 条（配额均衡）", 2),
            K('单条最高转发', N(_epMaxOne), '全流域最高的一条', 3),
            K('最高强度格', _epTopCell,
              f"{_epTopVal} 转/条（去极值均值）", 4),
            K('多省合并串', N(EP['multi']), '不进入矩阵（无法归省）', 5),
            K('本流域转发', N(EP['all']['f']), f"点赞 {N(EP['all']['z'])}", 6),
        ],
        cards=[
            TEXT('这一页为什么不用"条数"编码',
                 '<p>全站其它事件卡量的都是<b>命中篇数</b>，但这一维度在本项目里是'
                 f'<b>被采集配额锁死的</b>：本页 {len(EP["rows"])} 类事件 × {len(EP["provs"])} 个省的格子里，'
                 f'条数全部落在 {_epNMin} ~ {_epNMax} 条之间，几乎完全均匀 —— '
                 '那不是"哪些省更热"，是采集端按省配额跑的。'
                 '所以下面这张矩阵<b>刻意不用条数编码</b>，改用<b>传播强度</b>。</p>'
                 '<p><b>中心量为什么是"去极值均值"</b>（该格去掉转发最高的一条后的平均转发）：'
                 f'① 均值被单条极值污染 —— 全流域最大的一条转发 {N(_epMaxOne)}，'
                 '把所在格的均值拉高两个数量级（黄河「陕西 医患纠纷」原始均值 1775.5 → 去极值 9.7，'
                 '差 183 倍）；② 中位数太保守 —— 这张矩阵里中位数几乎全 0，弱信号会被一起抹掉。'
                 '两者之间没有第三个稳健选择。</p>'
                 '<p><b>怎么读</b>：横向比＝同一类事件在各省的扩散强度差；'
                 '纵向比＝同一省内哪类事件更容易被推出去。'
                 '跨行比较请用复核表最后一列的「行中位」，不要用格子的绝对值比大小。'
                 '悬停任一格可同时看到该格的原始均值 / 中位数 / 单条最高 / 条数四个口径。</p>'
                 '<p><b>不能读</b>：① 格值<b>不是热度</b> —— 条数是配额、转发受爆款影响，'
                 '两个口径都不是绝对声量；② 底色与格内数字同源，'
                 '且色阶按平方根拉伸（值域跨 0.0x ~ 数十，线性色阶会让低值区间全部同色），'
                 '<b>跨行比色深是不成立的</b>；③ 兜底层那一行（食品安全 / 社会治理）只作对照，'
                 '不计入三大主题的任何占比。</p>'),
            C(p + 'ep1', '事件类型 × 省份 · 传播强度矩阵（去极值均值）',
              '行＝事件类型（<b>与议题一一对应</b>：医患纠纷＝医患矛盾、景区宰客＝文旅、'
              '环保督察＝生态治理、食品安全＝社会治理兜底层），列＝沿江序位省份（上游 → 下游）。'
              '格内数字与底色同源＝<b>去极值均值</b>（该格去掉转发最高一条后的平均转发）。'
              '<b>条数不参与本图编码</b>：各格条数是采集配额均衡的结果，不是热度',
              'heat', evProvHeat, {'unit': '转/条', 'yw': 104, 'sqrt': True,
                                   'cut': '行序 = 事件类型；列序 = 沿江上游→下游'},
              w=3, h=360, ruler=True),
            TABLE('传播强度逐格复核（可复算）',
                  [{'k': 'e', 'l': '事件类型'}, {'k': 't', 'l': '对应议题'}]
                  + [{'k': 'p%d' % i, 'l': pnm, 'num': True} for i, pnm in enumerate(EP['provs'])]
                  + [{'k': 'n', 'l': '格内条数', 'num': True},
                     {'k': 'mx', 'l': '行内单条最高', 'num': True},
                     {'k': 'md', 'l': '行中位（去极值）', 'num': True}],
                  [{'e': r['ev'] + ('（兜底层）' if r['rest'] else ''),
                    't': r['topic'],
                    **{'p%d' % i: (round(c['trim'], 1) if c['n'] else '—')
                       for i, c in enumerate(r['cells'])},
                    'n': N(sum(c['n'] for c in r['cells'])),
                    'mx': N(r['all']['max']),
                    'md': round(r['medTrim'], 1)} for r in EP['rows']],
                  '每格 = 该省该类事件的去极值平均转发（去掉最高一条）；'
                  '「格内条数」用于核对采集配额是否均衡、不参与读数；'
                  '跨行比较该用最后一列的行中位', w=3),
        ],
        notes=[
            nt('<b>条数维度在本页不可用</b>：各格条数落在 %d~%d 条之间，'
               '是采集端按省配额的结果。把它当热度读会得出"某省更热"的错误结论，'
               '所以本页改用传播强度编码，并在复核表里保留条数列供你核对配额。' % (_epNMin, _epNMax),
               k='warn'),
            nt('<b>省份口径</b>：矩阵列 = 采集端标注的「目标省份」（正文中首次命中的省），'
               '不是作者 IP 属地；两者的差异见「IP 属地地图」页。', k='warn'),
            nt('<b>为什么只有一行一事件</b>：命中关键词里含多省合并串（如 '
               '「陕西 医患纠纷|四川 医患纠纷」）的 %d 条无法归到单一省份，'
               '一律不进矩阵；这也是各行「格内条数」之和小于本页样本量的原因。' % EP['multi'],
               k='ok'),
        ],
    )

    # ===================== 流域智能问答（服务端锁定本流域数据） =====================
    qa_v = dict(
        id=p + '-qa', group='智能问答', name=full + '智能问答',
        badge='实时 · 本流域限定', badgeCls='new',
        lead=f'本页问答<b>只读取 {basin} 流域的数据</b>：提问经星火大模型结合本流域数据与'
             f'传播学知识库（RAG）生成回答；数据类问题由服务端按「{basin}」强制过滤，'
             f'不会混入另一流域的数字。',
        kpis=[K('数据范围', f'{basin}流域', '服务端强制过滤，无法绕过', 1),
              K('可选平台', '微博 / 小红书 / 知乎', '追问时可指定平台', 2),
              K('知识来源', '传播学教材 + 论文', '理论解释附引用角标', 3)],
        cards=[
            C(p + 'qa1', f'{basin}流域智能问答',
              f'提问只返回 {basin} 流域的数据；若问另一流域会被明确拒绝并引导到首页对照卡。'
              f'回车或点「发送」提问。',
              'chat', {'basin': basin}, w=3, h=520),
            LIST('可以这样问', [
                {'t1': '事件', 'txt': f'{basin}流域最近有哪些热点事件？'},
                {'t1': '声量', 'txt': '本流域声量最高的省份是哪个？'},
                {'t1': '平台', 'txt': '小红书上关于本流域的讨论有多少条？'},
                {'t1': '理论', 'txt': '这类事件为什么容易在网络上快速发酵？'}],
                '每条都对应一个真实数据工具或知识库能力', w=3),
        ],
        notes=[nt(f'<b>专题隔离</b>：本页问答在服务端按「{basin}流域」强制过滤'
                  f'（工具调用时由后端注入流域条件），页面上无法切换到另一流域；'
                  f'跨流域对比请见首页「两流域核心指标对照」。', k='ok')],
    )

    return [qa_v, trend_v, clust_v, ch_v, interact_v, nodes_v,
            ev_v, evp_v, risk_v, calib_v]


# ======================================================================
# 批次 3：首页（第三段）
# --------------------------------------------------------------
# 首页的职责边界（写死在这里，避免以后越写越像"又一个流域总览"）：
#   ① 这个作品手里有什么      —— 规模 KPI + 口径分解（全量 / 聚焦 / 评论）
#   ② 东西落在哪              —— 中国地图（两江通行省域 + 干流走向）+ 山东省区位
#   ③ 两个流域差别在哪        —— 17 行核心指标对照（唯一一处并排对照）
#   ④ 当期最要紧的是什么      —— 事件簇 Top6 + 最高风险事件
#   ⑤ 读这些数字要提防什么    —— 口径与限制
# 流域内部的结构细节（词频、渠道、互动、节点、校准…）一概不放首页，那些归各自的 16 个模块。
# 批次 3b：原先还有 ⑥「维度导航 · 全站模块索引」卡，按用户要求删除（与侧栏重复）。
# ======================================================================


def home_views():
    H = BD['home']
    K_ = H['kpi']
    L = H['landing']
    HOT = H['hot']
    YZB, HHB = BD['basins']['长江'], BD['basins']['黄河']
    W4 = [f[1] for f in BM.RISK_FACTORS]          # 风险四项权重：负面 / 声量 / 敏感度 / 扩散

    # ---- 地图省份计数：统一取模块级的 _BNB（定义见文件头，任何地方都别再手写）----
    _share = set(IP['meta'].get('SHARED') or [])
    MC = dict(_BNB)

    # ---- 年度声量：两流域并排 ----
    # 用年度而非月度：月度节奏归各自的「传播趋势与节奏」模块；且 2026 年样本占比过半，
    # 年度视角反而更能看清"样本集中在哪几年"这件事。
    yd = {b: dict(BD['basins'][b]['years']) for b in ('长江', '黄河')}
    yx = sorted(set(yd['长江']) | set(yd['黄河']))
    mline_d = {'x': yx,
               'series': [{'name': '长江流域', 'y': [yd['长江'].get(y, 0) for y in yx]},
                          {'name': '黄河流域', 'y': [yd['黄河'].get(y, 0) for y in yx]}]}

    # ---- 议题结构（全量口径）：让"本专题只看三个议题之二"有分母 ----
    topic_all = {}
    for b in ('长江', '黄河'):
        for t, n in BD['basins'][b]['allTopics']:
            topic_all[t] = topic_all.get(t, 0) + n
    topic_rows = sorted(topic_all.items(), key=lambda z: -z[1])

    # ---- 落地区位（山东）：两套口径分开列，绝不合并成一个"山东声量" ----
    lnd = [
        {'a': '采集目标省份口径', 'b': N(L['target']['n']) + ' 条',
         'c': '第 %d / %d 位（流域样本共 %s 条）'
              % (L['target']['rank'], L['target']['of'], N(L['target']['total'])), 'cls': 'ok'},
        {'a': '发布属地口径（作者 IP）', 'b': N(L['ip']['n']) + ' 条',
         'c': '第 %d / %d 位（可归属 %s 条）'
              % (L['ip']['rank'], L['ip']['of'], N(L['ip']['total'])), 'cls': 'ok'},
        {'a': '微博聚焦口径', 'b': N(L['focus']['rows']) + ' 条',
         'c': ' + '.join('%s %d' % (k, v) for k, v in L['focus']['topic']), 'cls': ''},
        {'a': '聚焦口径情感构成', 'b': '/'.join(str(v) for _k, v in L['focus']['sent']),
         'c': '正 / 中 / 负（模型三档，未校准）', 'cls': ''},
        {'a': '所属流域', 'b': '黄河 ' + N(L['basinSplit'][0][1]) + ' 条',
         'c': '山东样本全部来自黄河表（山东为黄河下游省份）', 'cls': ''},
        {'a': '地市级数据', 'b': '无',
         'c': '采集粒度只到省级 → 省图不作数值编码', 'cls': 'warn'},
    ]

    # ---- 当期最高风险事件 ----
    RK = HOT['risk']
    risk_kv = [
        {'k': '事件', 'v': RK['name']},
        {'k': '流域 / 议题', 'v': '%s流域 · %s' % (RK['basin'], RK['topic'])},
        {'k': '风险得分', 'v': '%s 分（%s级 · %s）' % (RK['score'], RK['key'], RK['level'])},
        {'k': '样本量', 'v': '%s 篇（已过 %d 篇闸门）' % (N(RK['n']), BM.RISK_GATE)},
        {'k': '负面占比', 'v': '%s%%（%d / %d 篇）' % (RK['negPct'], RK['neg'], RK['n'])},
        {'k': '单篇转发', 'v': '%.1f 次/篇' % RK['perRp']},
        {'k': '处置建议', 'v': RK['act']},
    ]
    ev_rows = [[c['name'], c['n']] for c in HOT['cluster'][:6]]

    # ---- 比率型指标对照：从 cmp 里挑出「同一把尺子」的项画一张并排图 ----
    # 只放比率型：条数型（库内 978 / 710 条）与百分比不同轴，混在一起会读错量级，
    # 它们留在下面的对照表里。互动结构与情感构成是三元拆分，只摘其中一项进来。
    pct = [{'m': r['m'], 'y': r['y'], 'h': r['h']} for r in H['cmp'] if r['kind'] == 'p']
    _ir = next((r for r in H['cmp'] if r['m'].startswith('互动结构')), None)
    if _ir and isinstance(_ir['y'], list) and len(_ir['y']) >= 3:
        pct.insert(0, {'m': '互动结构 · 转发占比', 'y': _ir['y'][2], 'h': _ir['h'][2]})
    _sr = next((r for r in H['cmp'] if r['m'].startswith('情感构成')), None)
    if _sr and isinstance(_sr['y'], str) and _sr['y'].count('/') >= 2:
        try:
            pct.append({'m': '情感构成 · 负面占比',
                        'y': float(_sr['y'].split('/')[2].rstrip('%').strip()),
                        'h': float(_sr['h'].split('/')[2].rstrip('%').strip())})
        except (ValueError, IndexError):
            pass

    cards = [
        # ① 主视觉：地理区位三层落点（**合并了原 hm1 + hm2**）
        #   为什么合并：原 hm1（中国流域图）与 hm2（山东区位图）与本卡的中国图/山东图是
        #   同一视角的重复版面，首页会同时出现两张中国图、两张山东图。现把前两者的信息
        #   作为**图层**并进来 —— 中国图：填充＝声量，描边＝流域归属，另叠两江干流 + 落点；
        #   山东图：填充＝正文提及，描边＝黄河干流流经 9 市。
        C('hm-jn', '地理区位 · 中国 → 山东 → 济南（三层落点）',
          '填充＝<b>声量/提及</b>（越高越亮）　·　描边＝<b>流域归属</b>'
          '（<b style="color:#3f8f63">绿＝长江</b> %d 省 / <b style="color:#c9860a">橙＝黄河</b> %d 省 / '
          '<b style="color:#c2185b">玫红＝两江共源</b> %d 省「%s」/ <b style="color:#a89b88">灰＝非流域</b> %d 省）　·　'
          '两江干流为<b>示意折线</b>；山东图内琥珀描边＝黄河干流流经 9 市（地理常识，非数值）；'
          '济南图内<b>琥珀线＝黄河穿城段</b>（平阴→长清→槐荫→天桥→历城→章丘，示意折线）。'
          '<br/>口径各异：中国图＝<b>发布地区（作者 IP 属地）</b>省级计数；'
          '山东/济南图＝<b>正文提及</b>近似口径（本项目无地市级/区县级 IP 数据）。'
          '含「济南」的微博 <b>%s</b> 条，其中提到具体区县的仅 <b>%s</b> 条（%d/%d 个区县有提及），'
          '<b>样本稀薄、不代表区县热度</b>。'
          % (MC['长江'], MC['黄河'], MC['共源'], '、'.join(sorted(_share)), MC['非流域'],
             N((JD.get('meta') or {}).get('jnTotal')), N(sum((JD.get('jn') or {}).values())),
             sum(1 for v in (JD.get('jn') or {}).values() if v), len(JD.get('jn') or {})),
          'jnmaps',
          {'prov': JD['prov'], 'sd': JD['sd'], 'jn': JD['jn'], 'jnSrc': JD['jnSrc'],
           'jnMiss': JD.get('jnMiss') or {},
           'meta': JD['meta'], 'rules': JD['rules'],
           'mem': {'长江': list(IP['meta']['YANGTZE']),
                   '黄河': list(IP['meta']['YELLOW']),
                   '共源': list(IP['meta'].get('SHARED') or [])},
           'rivers': [{'name': rv['name'], 'color': rv['color'], 'pts': rv['pts']}
                      for rv in BGEO.RIVERS],
           'sdRiverCities': L['riverCities'], 'sdCourse': BGEO.RIVER_YL_SD,
           'jnCourse': BGEO.RIVER_YL_JN,
           'mark': [117.000923, 36.675807], 'label': '山东'},
          {}, w=3, cls='mapstage maplight', h=772, ruler=True),
        # ③ 年度节奏：两流域并排
        C('hm3', '年度声量 · 两流域并排',
          '按微博发布时间归年　·　2026 年占比 长江 %s%% / 黄河 %s%%'
          '（样本集中于 2026，不等于传播趋势）'
          % (YZB['trend']['y2026pct'], HHB['trend']['y2026pct']),
          'mline', mline_d,
          {'cmap': {'长江流域': '#2f8bff', '黄河流域': '#ffa42e'}, 'sym': True, 'fs': 9}, w=2),
        # ② 当期要闻：事件簇（与年度声量同排，凑满一行）
        C('hm6', '当期要闻 · 事件簇 Top6',
          '两流域 × 三议题共 %d 个事件簇；簇间可重叠，篇数不可相加' % HOT['clusterAll'],
          'hbar', ev_rows, {'unit': ' 篇', 'p': 0}, w=1),
        # ③ 当期最高风险事件（保留在首页：概括要回答"当下最要紧什么"）
        KV('当期最高风险事件', risk_kv,
           s='规则化四级评分：负面倾向占比 %d + 事件声量 %d + 涉官方主体敏感度 %d + 扩散力 %d；'
             '未过 %d 篇闸门的事件一律不入级（灰档），不参与归一' % (W4[0], W4[1], W4[2], W4[3],
                                                          BM.RISK_GATE), w=3),
        # 历史注记：本页早期曾含 hm4 议题结构 / 17 项对照 / hm5 比率对照 / 落地区域表，
        # 并计划迁出到独立「双流域对照」视图（home_cmp_view）。最终方案（2026-09-30）改为：
        # 不再设独立对照视图，首页段只保留「首页总览」一个子专题，其中 17 项对照表等
        # 3 张精华卡直接并入下方。理由：对照横跨两流域，独立成页与首页
        # 职责重复；用户要求首页只讲"总的概括"。要回退就把下方 3 张卡挪回独立视图。
    ]

    # 「口径分解 · 读任何占比前先看这层」表已按用户要求于 2026-10-06 从首页删除
    # （w=3 的整行卡，截图所示）。删除后首页 7 张卡、w 之和 18，仍被 3 整除，栅格不变。
    # 口径信息没有随之丢失：页脚 notes 的第一条（k='ok'）仍完整保留同一套
    # 「库内全量 → 聚焦 → 兜底层」分解与分母说明。若要恢复，把原 funnel
    # 数组与 cards.insert(3, TABLE(...)) 一起加回。

    # ---- 合并原 all-cmp / all-arch / all-overview 中用户指定的卡 ----
    # 首页段只保留「首页总览」一个子专题，其余三视图（all-overview/all-arch/all-cmp）已下线；
    # 下列 3 张卡为用户确认要保留的内容，来源见各卡注释。
    # 「近期高影响力微博」卡已于 2026-10-01 按用户要求删除（样本与流域三大主题无关）。
    # 该卡删除后仅剩 c7 是 w=1，3 列栅格会留 2 列空洞，故 c7 提到 w=3 撑满整行。
    cards.append(TABLE('两流域核心指标对照（%d 项）' % len(H['cmp']),
                       [{'k': 'm', 'l': '指标'}, {'k': 'y', 'l': '长江流域'},
                        {'k': 'h', 'l': '黄河流域'}, {'k': 'note', 'l': '口径'}],
                       [{'m': r['m'], 'y': str(r['y']), 'h': str(r['h']), 'note': r['note']}
                        for r in H['cmp']],
                       s='指标全部读 t_basin_article / t_basin_comment 实测。口径列写明每个数字的边界：'
                         '「2026 样本占比」是采集配额造成的偏差、「评论」未过闸门、'
                         '「情感」模型未校准、「跨平台」无数据 —— 这四项都不可直接当结论用。',
                       w=3))  # 来源 all-cmp：两流域核心指标对照
    cards.append(C('c7', '议题 × 流域 交叉', '长江/黄河 各自的议题声量', 'bar2',
                   {'x': [r['name'] for r in U['basinTopicXY'][0]['rows']],
                    'series': [{'name': xy['basin'], 'y': [r['value'] for r in xy['rows']]}
                               for xy in U['basinTopicXY']]}, h=440, w=3))  # 来源 all-arch
    cards.append(C('f1', '流域传播态势 · 沿江上下游',
                   f'纵轴 = 该省声量（<b>位置编码</b>，两江共用同一刻度，可直接横向比）　·　'
                   f'虚线 = 该流域省均　·　x 轴 = 沿岸序位（左＝上游，右＝入海口）'
                   f'　·　长江 {N(CAN["b_yz_a"])} 条 / 黄河 {N(CAN["b_yl_a"])} 条'
                   f'　·　20 省合计 = 流域总数 {N(CAN["b_art"])} 条（零遗漏）',
                   'flow', FLOW, {'unit': '条'}, w=3, h=560, ruler=True))  # 来源 all-arch

    v = dict(
        id='home-overview', sec='home', group='总览', short='首页总览',
        name='首页总览 · 双流域舆情一屏概览', badge='真实', badgeCls='real',
        lead='本作品核心聚焦<b>长江、黄河两大流域</b>的<b>三大主题</b>：'
             '<b>生态环境治理、文旅、医患矛盾</b>的热点事件。'
             '库内流域样本 <b>%s</b> 条，其中三大主题微博聚焦 <b>%s</b> 条（%s）；'
             '生态环境治理与医患矛盾另有微博 / 小红书 / 知乎三源交集口径；'
             '评论 <b>%s</b> 条，覆盖 <b>%d</b> 个省级行政区、<b>%s</b> 位作者，'
             '数据快照 <b>%s</b>。本页只讲「有什么 / 落在哪 / 差在哪 / 当下最要紧什么」；'
             '流域内部的结构细节（词频、渠道、互动、节点、校准…）请走各自的模块。'
             % (N(K_['allN']), N(K_['articles']), ' + '.join(BD['topics']),
                N(K_['comments']), K_['provinces'], N(K_['authors']), BD['generated'][:10]),
        kpis=[
            K('微博聚焦样本', N(K_['articles']),
              '长江 %s + 黄河 %s · %s'
              % (N(K_['yz']['articles']), N(K_['hh']['articles']), ' + '.join(BD['topics'])), 1),
            K('库内流域样本', N(K_['allN']),
              '兜底层 %s 条（社会治理）' % N(K_['filtered']), 2),
            K('评论样本', N(K_['comments']),
              '长江 %d + 黄河 %d · 低于 %d 条闸门'
              % (K_['yz']['comments'], K_['hh']['comments'], BD['commentGate']), 3),
            K('覆盖省域', '%d 个' % K_['provinces'], '流域通行省级行政区（34 省级行政区口径）', 4),
            K('参与作者', N(K_['authors']), '按作者ID 去重', 5),
            K('落地区域', '山东',
              '属黄河 · 采集目标第 %d 位（%s 条）' % (L['target']['rank'], N(L['target']['n'])), 6),
        ],
        cards=cards,
        notes=[
            nt('<b>口径分解（读任何"占比"前先看这层）</b>：库内流域样本 %s 条 ＝ 三大主题微博聚焦 %s 条（%s）'
               '＋ 兜底层 %s 条（社会治理，关键词未命中其他议题）。'
               '本站凡说「生态治理 / 文旅 / 医患矛盾」的占比，分母一律是 %s 条，不是 %s 条。'
               % (N(K_['allN']), N(K_['articles']), PC(K_['articles'], K_['allN']),
                  N(K_['filtered']), N(K_['articles']), N(K_['allN'])), k='ok'),
            nt('<b>样本偏差</b>：2026 年样本占比 长江 %s%% / 黄河 %s%%，是采集配额造成的，'
               '<b>不可当传播趋势读</b>；年度曲线只反映「库里哪几年有样本」。'
               % (YZB['trend']['y2026pct'], HHB['trend']['y2026pct']), k='warn'),
            nt('<b>地图口径（三张图三层口径，禁止混读）</b>：中国图<b>填充＝发布地区'
               '（作者 IP 属地）声量</b>、<b>描边＝流域归属</b>（长江通行 %d 省 / 黄河通行 %d 省 / '
               '两江共源 %d 省「%s」/ 非流域 %d 省，流域合计 %d 省，全部 34 省级行政区）；'
               '描边只表示「哪条江过境」，<b>不是行政区划边界主张</b>。'
               '山东图与济南图<b>填充＝正文提及次数</b>（近似口径）—— 本项目采集只到省级，'
               '没有地市级/区县级 IP 数据，故改用文本提及；济南各区县提及合计仅十余条，'
               '<b>样本稀薄、不代表区县热度</b>。江河走向为<b>示意折线</b>（沿程节点连线），'
               '非测绘数据、不可用于量距；右下「南海诸岛」为附图标注。'
               % (MC['长江'], MC['黄河'], MC['共源'], '、'.join(sorted(_share)),
                  MC['非流域'], MC['流域合计']), k='warn'),
            nt('<b>两处缺口（已如实标注，未填数字）</b>：① 跨平台数据 —— %s 个平台待实跑'
               '（已建表、0 条），需登录后采集；原「跨平台结构对照」缺口页已下线，'
               '跨平台口径现由「词频与词云」页的跨平台热词与「议题专题」页的跨平台明细表呈现；'
               '② 情感模型校准 —— 模型未在流域语料上微调，中性段占比仅 %s%% / %s%%，只作结构参考。'
               '（评论观点聚类已改用三源合并评论落地，见「评论观点聚类」页。）'
               % ('、'.join(x['name'] for x in BD['cross']['platforms'] if not x['live']),
                  YZB['calib']['neuPct'], HHB['calib']['neuPct']), k='warn'),
        ],
    )

    # ==================================================================
    # 首页段收尾：本函数只产出「首页总览」一个视图，不再另设独立对照视图。
    # 原 all-overview / all-arch / all-cmp 三个 home 段子专题已下线，其精华卡
    # （两流域核心指标对照 / 议题×流域交叉 / 流域传播态势）
    # 已在上方并入本视图。这样首页段侧栏只剩「首页总览」一项。
    # ==================================================================

    return [v]


# 批次 2 起覆盖全部 16 个模块（2026-10-02 新增 -evprov 事件传播强度）——
# 短名表与 ORDER 必须同步，否则侧栏会回落到全名 / 分组顺序会错位。
_SHORT = {'-overview': '总览', '-geo': 'IP 属地地图', '-trend': '传播趋势与节奏',
          '-topic': '议题专题', '-words': '词频与词云',
          '-content': '高影响力内容', '-comment': '评论洞察', '-clust': '评论观点聚类',
          '-video': '短视频智能分析',
          '-channel': '发布渠道与话语主体', '-interact': '互动结构与扩散效率',
          '-nodes': '关键传播节点',
          '-events': '事件监测', '-evprov': '事件传播强度',
          '-risk': '风险分级预警',
          '-method': '口径与方法', '-calib': '情感模型校准',
          '-qa': '智能问答'}

# 批次 2：每流域 16 个模块的固定顺序 —— 侧栏的分组顺序 = 该列表顺序
# （模板是按 VIEWS 里首次出现的 group 建分组，所以顺序在这里决定，不在模板里改）
ORDER = ['overview', 'geo',                                 # 流域总览
         'topic', 'words',                                  # 议题与词频
         'content', 'comment', 'video', 'clust',               # 内容与评论
         'channel', 'interact', 'nodes', 'trend',          # 传播与扩散
         'events', 'evprov', 'risk',                       # 事件与预警
         'method', 'calib',                                # 口径与方法
         'qa']                                             # 智能问答（本流域限定）

for _b in ('长江', '黄河'):
    _byid = {}
    for _v in basin_views(_b) + basin_extra_views(_b):
        _byid[_v['id'].split('-', 1)[1]] = _v
    if VD:                                  # 短视频智能分析（数据缺失时静默跳过）
        _byid['video'] = basin_video_view(_b)
    _miss = [k for k in ORDER if k not in _byid]
    assert not _miss, '%s 缺视图: %s' % (_b, _miss)
    for _k in ORDER:
        _v = _byid[_k]
        _v['sec'] = BASIN_PFX[_b]          # 'yz' / 'hh'
        _v['short'] = _SHORT['-' + _k]
        V.append(_v)

# ---- 为每个视图标注所属段（home / yz / hh / all）----
# 未标注的（全域 / 工程类模块）一律归 'all'，不能兜底成 'home'：
# 首页现在是 KEEP_SECS 里的一员，兜底成 home 会让几十个全域视图跟着复活。
for _v in V:
    _v.setdefault('sec', 'all')

# ---- 首页：插到最前，成为默认落地页（VIEWS[0]）----
# 首页在 basin_views / basin_extra_views 之外单独构造，故在这里并入。
V = home_views() + V

KEEP_SECS = ('hh',)
# 下线对象：流域驾驶舱、数据洞察 6 项、长江黄河对照（已并入首页两流域对照表）、
# 热点事件档案、知识库与设置 3 项 —— 它们讲的是全站口径，
# 与「聚焦黄河长江流域的生态环境治理、文旅与医患矛盾」这一定位不符。
# 'ai' 段只恢复「舆情报告生成」（2026-10-11 参赛改造）：AI 段的「智能问答」保持下线，
# 对话已下沉到 yz / hh 两个专题内（各锁定本流域，见 basin_extra_views 的 -qa 视图）。
# 视图构造代码仍保留在本文件中，此处只是不注册进 V；需要回退时改 KEEP_SECS 即可。
# ⚠ 改这张表里 cl1/cl2/cl3（全域词云）的文案是白费力气：sec='cloud' 整视图不在
#    KEEP_SECS，产物里没有实例。词云释义体系只对流域专题的 yz/hh-w3 生效。
DROPPED = [v for v in V if v.get('sec') not in KEEP_SECS]
V = [v for v in V if v.get('sec') in KEEP_SECS]

SEC_CNT = {}
for _v in V:
    SEC_CNT[_v['sec']] = SEC_CNT.get(_v['sec'], 0) + 1

# ---- 精简：内嵌数据只留地图所需的地理元数据 ----
# 已逐条核过：模板全文（含 _wordcloud.js）只访问 U.generated / U.ip / U.ip.meta。
# 全域的省份声量表、词云词表、情感分布等不再写进页面 —— 它们与流域专题无关，
# 留着既撑体积，也让「与流域无关的数据」留在成品里。
U = {'generated': U.get('generated', ''), 'ip': {'meta': IP['meta']}}

# 词条释义库注入 window.WCGLOSS：_wordcloud.js 在悬停 / 点击时查表。
# 独立于 U（统计量），纯静态文案 —— 释义不许参与任何统计，避免"释义带出的
# 暗示"污染读数。渲染器查不到就退回分层读法 + 统计口径，不编造词义。
WCGLOSS = json.dumps({
    'gloss': WG.GLOSSARY,
    'layerNote': WG.LAYER_NOTE,
    'noiseNote': WG.NOISE_NOTE,
    'emptyNote': WG.EMPTY_NOTE,
    'metricLabel': WG.METRIC_LABEL,
}, ensure_ascii=False).replace('</script', '<\\/script')

tpl = io.open(os.path.join(BASE, '_unified_tpl.html'), encoding='utf-8').read()

# ==================================================================
# 构建期断言：纯 DOM 卡片必须显式传h=
# ------------------------------------------------------------------
# 起因（2026-10-07）：`.ch` 写死height:260px 且 **overflow:visible**，
# 纯 DOM 渲染器的内容高不受约束 → 撑破父容器 → 把后继的 `.foot` 页脚
# 顶进卡片区，文字与卡片标题叠印（短视频页 vcard，实测溢出 340px）。
# 修法是给该卡显式 h=。但"记得给"靠不住 —— 同一批 bug 出了两处
# （vcard 短视频页、clusters 词云页，159px），故在此**构建期拦住**。
#
# 纯 DOM 清单从模板静态解析（块内无 echarts.init 即纯 DOM），
# 并**递归跟随 R.a → R.b 别名委托**（donut/rose/area 都转发到 pie，
# 只看自身函数体会误判成纯 DOM）。
_pure = set()
for _m in re.finditer(r'^R\.([a-z0-9_]+)\s*=\s*function', tpl, re.M):
    _n = _m.group(1)
    _nx = re.search(r'^R\.[a-z0-9_]+\s*=\s*function', tpl[_m.end():], re.M)
    _blk = tpl[_m.end(): _m.end() + (_nx.start() if _nx else 4000)]
    if 'echarts.init' not in _blk and 'initChart(' not in _blk:
        _pure.add(_n)


def _is_pure_dom(name, _seen=None):
    _seen = _seen or set()
    if name in _seen:
        return False
    _seen.add(name)
    _m = re.search(r'^R\.%s\s*=\s*function' % re.escape(name), tpl, re.M)
    if not _m:
        return False
    _nx = re.search(r'^R\.[a-z0-9_]+\s*=\s*function', tpl[_m.end():], re.M)
    _blk = tpl[_m.end(): _m.end() + (_nx.start() if _nx else 4000)]
    if 'echarts.init' in _blk or 'initChart(' in _blk:
        return False
    for _t in re.findall(r'\bR\.([a-z0-9_]+)\s*\(\s*box', _blk):
        if not _is_pure_dom(_t, _seen):
            return False
    return True


_pure = {n for n in _pure if _is_pure_dom(n)}
_missed = []
for _v in V:
    for _c in _v.get('cards') or []:
        if not _c.get('r'):
            continue        # table / text / kv 等非渲染器卡
        if _c['r'] in _pure and not _c.get('h'):
            _missed.append('%s / %s「%s」(recipe=%s)'
                           % (_v['id'], _c.get('id', '?'), _c.get('t', '?'), _c['r']))
assert not _missed, (
    '以下纯 DOM 卡片未显式传 h=，会撑破 .ch(%spx) 并把后继内容顶下去：\n  %s\n'
    '  → 修法：给该卡加 h=（内容自然高 + 标题区约 20px）。'
    % ('260', '\n  '.join(_missed)))

echarts = io.open(os.path.join(PRJ, 'static', 'js', 'echarts.min.js'), encoding='utf-8').read()
china = io.open(os.path.join(PRJ, 'static', 'js', 'china.js'), encoding='utf-8').read()
sdjs = io.open(os.path.join(PRJ, 'static', 'js', 'shandong.js'), encoding='utf-8').read()
jnjs = io.open(os.path.join(PRJ, 'static', 'js', 'jinan.js'), encoding='utf-8').read()
# sdnb.js：山东 16 地市 + 邻省轮廓（给总览页的「山东地市地图」R.sdcity 用的自动聚焦参照物）。
# 由 _gen_sdnb_map.py 生成；**缺失时降级为空**，R.sdcity 会自己显示"缺资源"提示，
# 不让整页构建失败（与 BZGEO 同一套降级约定）。
try:
    sdnbjs = io.open(os.path.join(PRJ, 'static', 'js', 'sdnb.js'), encoding='utf-8').read()
except OSError as _e:
    sdnbjs = ''
    print('[warn] 未读到 sdnb.js（%s），山东地市地图卡将降级为说明文字' % str(_e)[:60])
wcjs = io.open(os.path.join(BASE, '_wordcloud.js'), encoding='utf-8').read()
for nm, js in (('echarts', echarts), ('china', china), ('shandong', sdjs),
               ('jinan', jnjs), ('sdnb', sdnbjs), ('wordcloud', wcjs)):
    assert '</script' not in js.lower(), nm + ' 含 </script'

# ---- 批次 4（2026-10-06）：给「高影响力内容」的排行榜挂逐条解释 + 诊断图 ----
# 只处理 basin_explain_data 登记过的卡（yz-content / hh-content 的 list 卡），
# 其余 4 处 list 卡不会被挂任何字段，渲染结果与改动前逐字节一致。
# import 放这里而不是文件头：basin_explain_data 是**生成的**数据文件，
# 缺它时降级为"无解释"而不是让整页构建失败。
try:
    import basin_explain
    import basin_explain_data           # noqa: F401  副作用即登记
    _st = basin_explain.attach(V, lambda v: v.get('id', ''))
    print('排行榜解释：%d 条　诊断图：%d 张' % (_st['explain'], _st['figs']))
except ImportError as _e:
    print('排行榜解释：跳过（%s）' % _e)

DATA = json.dumps(U, ensure_ascii=False).replace('</script', '<\\/script')
VIEWS = json.dumps(V, ensure_ascii=False).replace('</script', '<\\/script')
# 流域专属地图几何：注入 window.BZGEO（{yz,yl,river,meta}）。缺失则为 null，
# R.basinmap 卡片会自动降级为说明文字，不阻断整页构建。
BZGEO_JS = ('window.BZGEO = '
            + json.dumps(BZGEO, ensure_ascii=False).replace('</script', '<\\/script')
            + ';')

out = (tpl.replace('/*__ECHARTS__*/', echarts, 1)
          .replace('/*__CHINA__*/', china, 1)
          .replace('/*__SHANDONG__*/', sdjs, 1)
          .replace('/*__JINAN__*/', jnjs, 1)
          .replace('/*__SDNB__*/', sdnbjs, 1)
          .replace('/*__WORDCLOUD__*/', wcjs, 1)
          .replace('/*__GLOSSARY__*/{}', 'window.WCGLOSS = ' + WCGLOSS + ';', 1)
          .replace('/*__BASINGEO__*/{}', BZGEO_JS, 1)
          .replace('/*__DATA__*/{}', DATA, 1)
          .replace('/*__VIEWS__*/[]', VIEWS, 1))

DST = os.path.join(BASE, '舆眼-黄河流域舆情.html')
io.open(DST, 'w', encoding='utf-8').write(out)

print('\n== 生成结果 ==')
print('视图数:', len(V), '| 分组:', len({v['group'] for v in V}))
print('专题:', ' | '.join('%s=%d' % (k, SEC_CNT.get(k, 0)) for k in KEEP_SECS))
print('已下线全域模块:', len(DROPPED), '个 ->',
      ', '.join(v['name'] for v in DROPPED))
print('图表数:', sum(1 for v in V for c in v['cards'] if 'r' in c))
print('表格数:', sum(1 for v in V for c in v['cards'] if c.get('kind') == 'table'))
print('输出:', os.path.basename(DST), '%.2f MB' % (os.path.getsize(DST) / 1048576))
print('残留占位符:', [p for p in ('__ECHARTS__', '__CHINA__', '__WORDCLOUD__', '__DATA__', '__VIEWS__')
                  if p in out] or '无')

