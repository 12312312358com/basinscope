# -*- coding: utf-8 -*-
"""汇总「舆眼」全功能导航中心 所需真实数据 -> feature_detail_data.json
口径对齐 view/page/page.py 与 dao/*.py
"""
import csv, io, json, os, sys, time
import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from util.category_taxonomy import aggregate_labels   # noqa: E402
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feature_detail_data.json')

def conn():
    return pymysql.connect(host=os.getenv('DB_HOST', 'localhost'),
                           port=int(os.getenv('DB_PORT', '3306')),
                           user=os.getenv('DB_USER', 'root'),
                           password=os.getenv('DB_PASSWORD', ''),
                           database=os.getenv('DB_NAME', 'db_weibo_basin'),
                           charset='utf8mb4', autocommit=True)

def q(cur, sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()

def read_csv(path, nrows=None):
    try:
        with io.open(path, encoding='utf-8-sig', errors='replace') as f:
            rows = [r for r in csv.reader(f) if r and any(str(c).strip() for c in r)]
    except Exception as e:
        print('csv fail', path, e); return [], []
    if not rows: return [], []
    h, body = rows[0], rows[1:]
    if nrows: body = body[:nrows]
    return h, body

D = {'generated': time.strftime('%Y-%m-%d %H:%M:%S')}
c = conn(); cur = c.cursor()

# ---------- 1. 首页 ----------
D['kpi'] = {
    'total_article': q(cur, "SELECT COUNT(*) FROM t_article")[0][0],
    'total_comment': q(cur, "SELECT COUNT(*) FROM t_comment WHERE `评论内容`!=''")[0][0],
    'distinct_article': q(cur, "SELECT COUNT(DISTINCT `微博ID`) FROM t_article")[0][0],
    'top_author': (q(cur, "SELECT `作者昵称` FROM t_article ORDER BY `点赞数` DESC LIMIT 1") or [('暂无',)])[0][0],
    'top_region': (q(cur, "SELECT `发布地区` FROM t_article WHERE `发布地区`!='' AND `发布地区`!='未知' GROUP BY `发布地区` ORDER BY SUM(`点赞数`) DESC LIMIT 1") or [('暂无',)])[0][0],
    'basin_article': q(cur, "SELECT COUNT(*) FROM t_basin_article")[0][0] if q(cur, "SHOW TABLES LIKE 't_basin_article'") else 0,
    'basin_comment': q(cur, "SELECT COUNT(*) FROM t_basin_comment")[0][0] if q(cur, "SHOW TABLES LIKE 't_basin_comment'") else 0,
}

rows = q(cur, """SELECT articleDate, articleTotal FROM (
        SELECT DATE_FORMAT(`发布时间`,'%%Y-%%m-%%d') AS articleDate, COUNT(`微博内容`) AS articleTotal
        FROM t_article GROUP BY articleDate ORDER BY articleDate DESC LIMIT 0,7
    ) t ORDER BY articleDate ASC""")
D['articles7day'] = {'x': [r[0] for r in rows], 'y': [int(r[1]) for r in rows]}

# --- 账号「分类」字段：受控词表归类 -------------------------------------------------
# 【修复说明】原实现是 `GROUP BY 分类` 后按计数降序取 Top10、把其余全部合并成「其他」。
# 但 `分类` 是微博账号标签的自由拼接串（领域 + 认证 + 设备混排），全表 5,116 个互异取值、
# 其中 90.5% 的取值样本数 ≤5，Top10 只能覆盖 18.72% —— 于是 81.28% 的样本被倒进「其他」。
# 现改为三维度受控归类（domain 领域 / cert 认证 / device 设备），不再做 Top-N 截断式归并；
# 未覆盖词元与「原串无领域信息」的行分别记账，见 util/category_taxonomy.py。
_raw_type = list(q(cur, "SELECT `分类`, COUNT(*) FROM t_article GROUP BY `分类`"))
_tax = aggregate_labels(_raw_type)
D['typeDist'] = [{'name': k, 'value': v} for k, v in _tax['domain']['dist_labeled']]
D['typeTotal'] = _tax['domain']['labeled_rows']
D['typeTax'] = {
    'rows_total': _tax['rows_total'],
    'categories': len(_tax['domain']['dist_labeled']),
    'labeled_rows': _tax['domain']['labeled_rows'],
    'labeled_rate': _tax['domain']['labeled_rate'],
    'multi_label_rows': _tax['domain']['multi_label_rows'],
    'other_domain_rate': _tax['audit']['other_domain_rate'],
    'unlabeled_rate': _tax['audit']['unlabeled_rate'],
    'unmapped_rate': _tax['audit']['unmapped_rate'],
    'unmapped_tokens': _tax['audit']['unmapped_tokens'],
    'vocab_ok': _tax['audit']['vocab_ok'],
    'cert': _tax['cert']['dist'][:8],
    'device': _tax['device']['dist'][:8],
    'unmapped': _tax['unmapped']['dist'][:12],
    # 旧口径对照（用于自查页面展示"修复前 vs 修复后"）
    'legacy': {
        'raw_categories': len(_raw_type),
        'top10_share': round(sum(sorted((c for _, c in _raw_type), reverse=True)[:10])
                             / max(_tax['rows_total'], 1) * 100, 2),
    },
}

rows = q(cur, """SELECT commentDate, commentTotal FROM (
        SELECT DATE_FORMAT(`评论时间`,'%%Y-%%m-%%d') AS commentDate, COUNT(*) AS commentTotal
        FROM t_comment GROUP BY commentDate ORDER BY commentDate DESC LIMIT 7
    ) t ORDER BY commentDate ASC""")
D['comment7day'] = {'x': [r[0] for r in rows], 'y': [int(r[1]) for r in rows]}

rows = q(cur, "SELECT `微博内容`,`点赞数` FROM t_article ORDER BY `点赞数` DESC LIMIT 0,6")
D['topArticles'] = [{'text': (r[0] or '')[:90], 'zan': int(r[1] or 0)} for r in rows]

rows = q(cur, "SELECT `昵称`, COUNT(`昵称`) c FROM t_comment WHERE `昵称`!='' GROUP BY `昵称` ORDER BY c DESC LIMIT 0,60")
D['commentUsers'] = [{'name': r[0], 'value': int(r[1])} for r in rows]

# ---------- 2. 微博表列表 ----------
rows = q(cur, """SELECT `微博内容`,`作者昵称`,`点赞数`,`评论数`,`转发数`,`发布时间`,`发布地区`,`分类`
                 FROM t_article ORDER BY `点赞数` DESC LIMIT 0,30""")
D['articleTable'] = [{
    'text': (r[0] or '')[:70], 'author': r[1] or '匿名', 'zan': int(r[2] or 0),
    'pl': int(r[3] or 0), 'zf': int(r[4] or 0),
    'time': (r[5] or '')[:16], 'region': r[6] or '未知', 'cat': r[7] or '未分类'
} for r in rows]

# ---------- 3. 文章量级分布（点赞/评论/转发）----------
rows = q(cur, "SELECT `点赞数`,`评论数`,`转发数` FROM t_article")
R1, R2 = 1000, 100
xDz = [f"{R1*i}-{R1*(i+1)}" for i in range(10)] + ['1万+']
xPl = xDz[:]
xZf = [f"{R2*i}-{R2*(i+1)}" for i in range(20)] + ['2千+']
yDz = [0]*len(xDz); yPl = [0]*len(xPl); yZf = [0]*len(xZf)
for zan, pl, zf in rows:
    try:
        v = int(zan or 0)
        yDz[-1 if v >= 10000 else min(v//R1, len(xDz)-2)] += 1
    except: pass
    try:
        v = int(pl or 0)
        yPl[-1 if v >= 10000 else min(v//R1, len(xPl)-2)] += 1
    except: pass
    try:
        v = int(zf or 0)
        yZf[-1 if v >= 2000 else min(v//R2, len(xZf)-2)] += 1
    except: pass
D['articleAnalysis'] = {'dz': {'x': xDz, 'y': yDz}, 'pl': {'x': xPl, 'y': yPl}, 'zf': {'x': xZf, 'y': yZf}}

# ---------- 4. 评论分析 ----------
rows = q(cur, "SELECT `点赞数`,`性别`,`来源` FROM t_comment WHERE `评论内容`!=''")
R = 5
xDz2 = [f"{R*i}-{R*(i+1)}" for i in range(20)] + ['1百+']
yDz2 = [0]*len(xDz2)
gender = {'男': 0, '女': 0, '未知': 0}
src = {}
for zan, g, s in rows:
    try:
        v = int(zan or 0)
        yDz2[-1 if v > 100 else min(v//R, len(xDz2)-2)] += 1
    except: pass
    gender[g if g in ('男', '女') else '未知'] += 1
    src[s or '未知'] = src.get(s or '未知', 0) + 1
D['commentAnalysis'] = {
    'dz': {'x': xDz2, 'y': yDz2},
    'gender': [{'name': k, 'value': v} for k, v in gender.items()],
    'source': sorted([{'name': k, 'value': v} for k, v in src.items()], key=lambda d: -d['value'])[:6],
}

# ---------- 5. 热词（来自 fenci/comment_fre.csv，与 hotWord 页同源）----------
h, body = read_csv(os.path.join(ROOT, 'fenci', 'comment_fre.csv'))
freq = {}
for r in body:
    try: freq[str(r[0]).strip()] = int(r[1])
    except: pass
D['hotwordList'] = [{'w': k, 'v': v} for k, v in sorted(freq.items(), key=lambda x: -x[1])[:100]]
D['hotwordCount'] = len(freq)

h, body = read_csv(os.path.join(ROOT, 'fenci', 'hot_sent_final.csv'))
hot_sent = {}
if 'word' in h and 'sentiment' in h:
    wi, si = h.index('word'), h.index('sentiment')
    for r in body:
        if len(r) > max(wi, si): hot_sent[str(r[wi]).strip()] = str(r[si]).strip() or '中性'
D['hotSent'] = hot_sent

# 默认热词（最高频）7 日趋势 + 相关评论
if D['hotwordList']:
    dw = D['hotwordList'][0]['w']
    rows = q(cur, """SELECT commentDate, commentTotal FROM (
            SELECT DATE_FORMAT(`评论时间`,'%%Y-%%m-%%d') AS commentDate, COUNT(*) AS commentTotal
            FROM t_comment WHERE LOCATE(%s, `评论内容`)>0 GROUP BY commentDate ORDER BY commentDate DESC LIMIT 7
        ) t ORDER BY commentDate ASC""", (dw,))
    hwTrend = {'x': [r[0] for r in rows], 'y': [int(r[1]) for r in rows]}
    rows = q(cur, "SELECT `评论内容`,`点赞数`,`来源` FROM t_comment WHERE LOCATE(%s,`评论内容`)>0 ORDER BY `点赞数` DESC LIMIT 6", (dw,))
    hwList = [{'text': (r[0] or '')[:80], 'zan': int(r[1] or 0), 'src': r[2] or '未知'} for r in rows]
else:
    dw, hwTrend, hwList = '暂无热词', {'x': [], 'y': []}, []
D['hotwordDemo'] = {'word': dw, 'trend': hwTrend, 'comments': hwList, 'sentiment': hot_sent.get(dw, '中性')}

# ---------- 6. 情感（口径同 sentimentAnalysis 页）----------
def sent_stat(name):
    h, body = read_csv(os.path.join(ROOT, 'fenci', name))
    v = {'正面': 0, '中性': 0, '负面': 0, 'total': 0}
    if 'sentiment' in h:
        i = h.index('sentiment')
        for r in body:
            if len(r) > i:
                s = str(r[i]).strip()
                if s and s.lower() != 'nan':
                    v[s if s in v else '中性'] += 1
                    v['total'] += 1
    return v
D['sentiment'] = {'hot': sent_stat('hot_sent_final.csv'),
                  'comment': sent_stat('comment_sent_final.csv'),
                  'article': sent_stat('article_sent_final.csv')}
h, body = read_csv(os.path.join(ROOT, 'fenci', 'comment_fre.csv'), nrows=15)
D['sentiment']['top15'] = [{'w': str(r[0]).strip(), 'v': int(r[1])} for r in body if len(r) > 1]

# ---------- 7. IP / 流域 ----------
ipf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ip_map_data.json')
if os.path.exists(ipf):
    d = json.load(io.open(ipf, encoding='utf-8'))
    D['ip'] = {
        'article': d['article']['provinces'], 'article_total': d['article']['total'],
        'comment': d['comment']['provinces'], 'comment_total': d['comment']['total'],
        'basin_prov': d.get('meta', {}).get('BASIN_PROV', {}),
    }

# ---------- 8. 表清单 ----------
tabs = [r[0] for r in q(cur, "SHOW TABLES")]
D['tables'] = tabs
D['tableCount'] = len(tabs)

# ---------- 9. 长江 / 黄河流域省份 ----------
CHANGJIANG = ['青海', '西藏', '四川', '云南', '重庆', '湖北', '湖南', '江西', '安徽',
              '江苏', '上海', '贵州', '甘肃', '陕西', '河南', '广西', '广东', '浙江', '福建']
HUANGHE = ['青海', '四川', '甘肃', '宁夏', '内蒙古', '陕西', '山西', '河南', '山东']
D['basin'] = {'changjiang': CHANGJIANG, 'huanghe': HUANGHE}

c.close()
with io.open(OUT, 'w', encoding='utf-8') as f:
    json.dump(D, f, ensure_ascii=False, indent=1)
print('OK ->', OUT)
print(json.dumps({k: (len(v) if hasattr(v, '__len__') else v) for k, v in D.items()}, ensure_ascii=False)[:600])

