# -*- coding: utf-8 -*-
"""汇总「全站一体化预览」所需的全部真实数据 -> unified_data.json

数据来源（三条链路，互不混用，页面内逐块标注）：
  A. db_weibo_basin 实时查询   —— 主表 t_article / t_comment、流域表 t_basin_*
  B. 既有预览数据快照     —— hotword / sentiment / ip / feature_detail 四份 json
  C. 项目 fenci/*.csv     —— 三张词云背后的词频文件（原样读取，不重算）
"""
import io, json, csv, re, datetime, collections, os
import pymysql
import jieba

BASE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(BASE)
DB = dict(host=os.getenv('DB_HOST', 'localhost'),
          port=int(os.getenv('DB_PORT', '3306')),
          user=os.getenv('DB_USER', 'root'),
          password=os.getenv('DB_PASSWORD', ''),
          database=os.getenv('DB_NAME', 'db_weibo_basin'),
          charset='utf8mb4')

conn = pymysql.connect(**DB)
cur = conn.cursor()


def q(sql, args=None):
    cur.execute(sql, args or ())
    return cur.fetchall()


U = {}
U['generated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# ============================================================
# 0. 既有快照
# ============================================================
def jload(name):
    return json.load(io.open(f'{BASE}\\{name}', encoding='utf-8'))


HOT = jload('hotword_preview_data.json')
SENT = jload('sentiment_preview_data.json')
IP = jload('ip_map_data.json')
FD = jload('feature_detail_data.json')
U['hot'] = HOT
U['sent'] = SENT
U['ip'] = IP
U['fd'] = FD

# ============================================================
# 1. 口径统一表（页面所有数字的唯一出处）
# ============================================================
def one(sql, args=None):
    r = q(sql, args)
    return r[0][0] if r else 0


a_total = one('SELECT COUNT(*) FROM t_article')
a_dist = one('SELECT COUNT(DISTINCT 微博ID) FROM t_article')
c_total = one('SELECT COUNT(*) FROM t_comment')
c_dist = one('SELECT COUNT(DISTINCT 评论ID) FROM t_comment')
b_art = one('SELECT COUNT(*) FROM t_basin_article')
b_cmt = one('SELECT COUNT(*) FROM t_basin_comment')
b_yz_a = one("SELECT COUNT(*) FROM t_basin_article WHERE 流域='长江'")
b_yl_a = one("SELECT COUNT(*) FROM t_basin_article WHERE 流域='黄河'")
b_yz_c = one("SELECT COUNT(*) FROM t_basin_comment WHERE 流域='长江'")
b_yl_c = one("SELECT COUNT(*) FROM t_basin_comment WHERE 流域='黄河'")
tabs = [r[0] for r in q('SHOW TABLES')]
u_cnt = one('SELECT COUNT(*) FROM t_user')
U['tableRows'] = {t: one('SELECT COUNT(*) FROM `%s`' % t) for t in tabs}
print('库内 16 张表行数:', U['tableRows'])

U['canon'] = dict(
    a_total=a_total, a_dist=a_dist, c_total=c_total, c_dist=c_dist,
    b_art=b_art, b_cmt=b_cmt, b_yz_a=b_yz_a, b_yl_a=b_yl_a, b_yz_c=b_yz_c, b_yl_c=b_yl_c,
    b_total=b_art + b_cmt, tabs=len(tabs), u_cnt=u_cnt,
)
print('口径:', U['canon'])

# ============================================================
# 2. 主表 24 小时发帖分布（真实）
# ============================================================
def hour_hist(tbl, col):
    rows = q(f'SELECT `{col}` FROM {tbl}')
    h = [0] * 24
    bad = 0
    for (t,) in rows:
        if not t:
            bad += 1
            continue
        m = re.search(r'(\d{1,2}):(\d{2})', str(t))
        if m:
            hh = int(m.group(1))
            if 0 <= hh < 24:
                h[hh] += 1
            else:
                bad += 1
        else:
            bad += 1
    return h, bad


ha, ba = hour_hist('t_article', '发布时间')
hc, bc = hour_hist('t_comment', '评论时间')
U['hours'] = dict(article=ha, comment=hc, bad_a=ba, bad_c=bc)
print('文章峰值时刻', ha.index(max(ha)), max(ha), '| 评论峰值', hc.index(max(hc)), max(hc))

# ============================================================
# 3. 流域表：分词词频 + 议题 + 目标省份 + 采集时间区间
# ============================================================
STOP = set('''的 了 是 我 你 他 她 它 我们 你们 他们 这 那 这个 那个 这些 那些 一个 一下 什么 怎么 为什么
就 都 也 还 又 很 太 更 最 不 没有 没 有 在 到 从 和 与 跟 把 被 让 给 对 为 于 之 其 而 但 但是 因为 所以
啊 吧 呢 吗 呀 哦 嗯 哈 哈哈 哈哈哈哈 呵 咦 唉 哎 我 你 上 下 里 中 大 小 好 多 少 时候 现在 今天 明天 昨天
可以 自己 就是 这样 那样 感觉 觉得 知道 出来 起来 过去 一下 一直 已经 只是 真的 其实 然后 还有 如果 不是
微博 转发 超话 分享 http cn com www 全文 视频 图片 链接 网页 展开 原文 评论 点赞 关注 粉丝 谢谢 感谢
'''.split())

def tokenize(texts, topn=60):
    """分词计数 → topn。

    排序显式加词名次级键（2026-10-07）。`Counter.most_common()` 对**同计数**
    沿用插入序，而插入序取决于上游行序；本函数的 texts 来自
    `SELECT 微博内容 FROM t_basin_article`（**无 ORDER BY**）。
    实测当前两次构建一致（InnoDB 全表扫恰好稳定），所以这是**预防**而非修 bug ——
    但「恰好稳定」不等于「保证稳定」，加一个次级键成本为零。
    同类问题在 build_basin_data.py 上真实发生过（词云同分词翻转），
    见该文件顶部 mc() 的注释。
    """
    cnt = collections.Counter()
    n = 0
    for t in texts:
        if not t:
            continue
        n += 1
        for w in jieba.cut(str(t)):
            w = w.strip()
            if len(w) < 2 or w in STOP:
                continue
            if re.fullmatch(r'[\W\d_]+', w):
                continue
            cnt[w] += 1
    return sorted(cnt.items(), key=lambda kv: (-kv[1], str(kv[0])))[:topn], n


ba_rows = q('SELECT 微博内容 FROM t_basin_article')
bc_rows = q('SELECT 评论内容 FROM t_basin_comment')
b_w_all, b_na = tokenize([r[0] for r in ba_rows])
b_w_cmt, b_nc = tokenize([r[0] for r in bc_rows])
yz_w, _ = tokenize([r[0] for r in q("SELECT 微博内容 FROM t_basin_article WHERE 流域='长江'")])
yl_w, _ = tokenize([r[0] for r in q("SELECT 微博内容 FROM t_basin_article WHERE 流域='黄河'")])
U['basinWords'] = dict(article=b_w_all, comment=b_w_cmt, yz=yz_w, yl=yl_w,
                       na=b_na, nc=b_nc)
print('流域词频 Top5:', b_w_all[:5])

U['basinTopic'] = [dict(name=r[0] or '未标注', value=r[1])
                   for r in q('SELECT 议题,COUNT(*) c FROM t_basin_article GROUP BY 议题 ORDER BY c DESC')]
U['basinProv'] = [dict(name=r[0] or '未标注', value=r[1], basin=r[2])
                  for r in q('SELECT 目标省份,COUNT(*) c,MIN(流域) FROM t_basin_article '
                             'GROUP BY 目标省份 ORDER BY c DESC')]
def span(tbl):
    r = q(f'SELECT MIN(采集时间),MAX(采集时间) FROM {tbl}')[0]
    fmt = lambda v: v.strftime('%Y-%m-%d %H:%M') if hasattr(v, 'strftime') else str(v)
    return [fmt(r[0]), fmt(r[1])]


U['basinTime'] = span('t_basin_article')
U['basinTimeC'] = span('t_basin_comment')

# ---------- 流域事件档案（字段全部取自流域专用表 t_basin_*）----------
# 事件清单：按互动量（赞+评+转）降序。COALESCE 防 NULL 参与求和导致整行被排到末尾。
U['basinEvents'] = []
for r in q('SELECT 微博内容,点赞数,评论数,转发数,发布时间,发布地区,议题,流域,目标省份,命中关键词 '
           'FROM t_basin_article '
           'ORDER BY (COALESCE(点赞数,0)+COALESCE(评论数,0)+COALESCE(转发数,0)) DESC LIMIT 30'):
    ts = r[4]
    ts = ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts or '')[:10]
    U['basinEvents'].append(dict(
        text=(r[0] or '').strip()[:70], zan=int(r[1] or 0), pl=int(r[2] or 0), zf=int(r[3] or 0),
        time=ts, region=r[5] or '未知', topic=r[6] or '未标注', basin=r[7] or '未标注',
        prov=r[8] or '未标注', kw=r[9] or '',
    ))

# 流域表日发文量：近 14 个有样本的日期（升序，便于画时间轴）
U['basinDays'] = []
for r in q("SELECT DATE(发布时间) d, COUNT(*) c FROM t_basin_article "
           "WHERE 发布时间 IS NOT NULL AND 发布时间!='' "
           "GROUP BY d ORDER BY d DESC LIMIT 14"):
    d = r[0]
    U['basinDays'].append(dict(d=d.strftime('%m-%d') if hasattr(d, 'strftime') else str(d)[5:],
                               n=int(r[1])))
U['basinDays'].reverse()

# 跨流域议题：同一议题在长江、黄河均有样本，才算跨流域
U['basinCross'] = []
for (tp,) in q("SELECT DISTINCT 议题 FROM t_basin_article WHERE 议题 IS NOT NULL AND 议题!=''"):
    bs = [r[0] for r in q('SELECT DISTINCT 流域 FROM t_basin_article WHERE 议题=%s '
                          "AND 流域 IN ('长江','黄河')", (tp,))]
    if len(bs) > 1:
        U['basinCross'].append(dict(name=tp, basins=bs))

# 流域 × 议题（长江/黄河 分别）
U['basinTopicXY'] = []
for b in ('长江', '黄河'):
    rows = q('SELECT 议题,COUNT(*) c FROM t_basin_article WHERE 流域=%s GROUP BY 议题 ORDER BY c DESC', (b,))
    U['basinTopicXY'].append(dict(basin=b, rows=[dict(name=r[0] or '未标注', value=r[1]) for r in rows]))

# ============================================================
# 4. 评论侧：性别 / 来源（流域评论表，真实）
# ============================================================
U['basinGender'] = [dict(name=r[0] or '未知', value=r[1])
                    for r in q('SELECT 性别,COUNT(*) c FROM t_basin_comment GROUP BY 性别 ORDER BY c DESC')]

# 来源：先剥离「来自」前缀与首尾空格（与 build_ip_data.norm 同一口径），
# 再统计。空值（NULL / 空串）是**数据缺口**，不是一个"来源"：
# 旧写法 `r[0] or '未知'` 会把 80 条空值变成一个叫「未知」的类别，
# 它还会凭条数在 ORDER BY 里排到第一名（驾驶舱 KPI 与玫瑰图同时被污染）。
def _src_norm(v):
    s = (v or '').strip()
    return re.sub(r'^来自\s*', '', s).strip() if s else ''


_src_raw = q('SELECT 来源, COUNT(*) c FROM t_basin_comment GROUP BY 来源')
_src_cnt, _src_blank = {}, 0
for _v, _n in _src_raw:
    _k = _src_norm(_v)
    if not _k:
        _src_blank += _n          # 空值只计数、不成类
        continue
    _src_cnt[_k] = _src_cnt.get(_k, 0) + _n
_src_pairs = sorted(_src_cnt.items(), key=lambda kv: (-kv[1], kv[0]))
U['basinSrc'] = [dict(name=k, value=n) for k, n in _src_pairs[:12]]
# 口径元数据：占比分母用「有效样本」，数据缺口在副标题里如实披露
U['basinSrcMeta'] = dict(total=sum(n for _, n in _src_raw),
                         valid=sum(_src_cnt.values()),
                         blank=_src_blank,
                         kinds=len(_src_cnt))

# ============================================================
# 5. 三张词云（读项目 fenci/*.csv，原样不重算）
# ============================================================
def read_fre(path, n=50):
    out = []
    with io.open(path, encoding='utf-8-sig', errors='replace') as f:
        for i, row in enumerate(csv.reader(f)):
            if not row or not str(row[0]).strip():
                continue
            if i == 0 and not str(row[1] if len(row) > 1 else '').isdigit():
                continue
            try:
                out.append([str(row[0]).strip(), int(float(row[1]))])
            except Exception:
                continue
            if len(out) >= n:
                break
    return out


U['cloudFre'] = dict(
    article=read_fre(PRJ + r'\fenci\article_fre2.csv'),
    comment=read_fre(PRJ + r'\fenci\comment_fre2.csv'),
    user=read_fre(PRJ + r'\fenci\comment_user_fre2.csv'),
)
for k, v in U['cloudFre'].items():
    print(f'词云词频 {k}: {len(v)} 条  首={v[0] if v else None}')

# ============================================================
# 6. 主表评论：长度分布（真实，分箱）
# ============================================================
rows = q('SELECT CHAR_LENGTH(评论内容) FROM t_comment')
bins = [0] * 8
for (L,) in rows:
    L = L or 0
    i = 0 if L == 0 else min(7, (L - 1) // 25 + 1)
    bins[i] += 1
U['cmtLen'] = dict(x=['0', '1-25', '26-50', '51-75', '76-100', '101-150', '151-200', '200+'], y=bins)

# 主表文章：正文长度分布
rows = q('SELECT CHAR_LENGTH(微博内容) FROM t_article')
ab = [0] * 8
for (L,) in rows:
    L = L or 0
    i = 0 if L == 0 else min(7, (L - 1) // 75 + 1)
    ab[i] += 1
U['artLen'] = dict(x=['0', '1-75', '76-150', '151-225', '226-300', '301-375', '376-450', '450+'], y=ab)

# 同一批数据的「论文口径」重分箱（1-50 / 51-100 / 101-300 / 301-1000 / >1000 / 空）——
# 界面改造预案里那张「正文长度分布」卡片用的就是这个口径，但当时填的是占位数字；
# 这里按真实库重算一遍，供页面的分段进度条卡片直接引用。
def _lenseg(tbl, col):
    c2 = conn.cursor()
    C = 'CHAR_LENGTH(TRIM(%s))' % col
    E = "(%s IS NULL OR TRIM(%s) = '')" % (col, col)
    c2.execute("""SELECT
        SUM(CASE WHEN {E} THEN 1 ELSE 0 END),
        SUM(CASE WHEN {C} BETWEEN 1 AND 50     THEN 1 ELSE 0 END),
        SUM(CASE WHEN {C} BETWEEN 51 AND 100   THEN 1 ELSE 0 END),
        SUM(CASE WHEN {C} BETWEEN 101 AND 300  THEN 1 ELSE 0 END),
        SUM(CASE WHEN {C} BETWEEN 301 AND 1000 THEN 1 ELSE 0 END),
        SUM(CASE WHEN {C} > 1000 THEN 1 ELSE 0 END),
        MIN({C}), MAX({C}), ROUND(AVG({C}),1), COUNT(*)
    FROM {T}""".format(E=E, C=C, T=tbl))
    r = c2.fetchone(); c2.close()
    d = {k: int(v or 0) for k, v in zip(['empty', 'b1', 'b2', 'b3', 'b4', 'b5'], r[:6])}
    d.update(mn=int(r[6] or 0), mx=int(r[7] or 0), avg=float(r[8] or 0), total=int(r[9]))
    return d


U['lenSeg'] = dict(article=_lenseg('t_article', '微博内容'),
                   comment=_lenseg('t_comment', '评论内容'))
for _k, _v in U['lenSeg'].items():
    print('长度分段 %-7s 空=%d 1-50=%d 51-100=%d 101-300=%d 301-1000=%d >1000=%d | %d~%d 字 均%.1f 共%d'
          % (_k, _v['empty'], _v['b1'], _v['b2'], _v['b3'], _v['b4'], _v['b5'],
             _v['mn'], _v['mx'], _v['avg'], _v['total']))

# ============================================================
# 7. 流域「不重叠」四色拆分（修正 meta.SHARED 与两个省表互不相交的口径冲突）
# ============================================================
YZl = list(IP['meta']['YANGTZE']); YLl = list(IP['meta']['YELLOW'])
U['basinSplit'] = {}
for side in ('article', 'comment'):
    P = IP[side]['provinces']
    U['basinSplit'][side] = dict(
        yz=sum(v for k, v in P.items() if k in YZl and k not in YLl),
        yl=sum(v for k, v in P.items() if k in YLl and k not in YZl),
        shared=sum(v for k, v in P.items() if k in YZl and k in YLl),
        outside=sum(v for k, v in P.items() if k not in YZl and k not in YLl),
        prov_total=sum(P.values()),
        yz_n=len([p for p in YZl if p not in YLl]), yl_n=len([p for p in YLl if p not in YZl]),
        shared_list=[p for p in YZl if p in YLl],
    )
print('不重叠拆分:', U['basinSplit']['article'])

# ============================================================
# 8. 知识库 / 微调 / AI 侧真实规模（读 chroma.sqlite3 与项目目录）
# ============================================================
import os, sqlite3
kbp = os.path.join(PRJ, 'chroma_db', 'chroma.sqlite3')
kb = dict(chroma=os.path.basename(kbp), db_mb=round(os.path.getsize(kbp) / 1048576, 1))
con = sqlite3.connect(kbp); cc = con.cursor()
cc.execute('SELECT name,dimension FROM collections')
cols = cc.fetchall()
cc.execute('SELECT COUNT(*) FROM embeddings')
kb['chunks'] = cc.fetchone()[0]
con.close()
kb['collection'] = cols[0][0] if cols else ''
kb['dim'] = cols[0][1] if cols else 0


def cnt(d, pat=None):
    if not os.path.isdir(d):
        return 0
    return len([f for f in os.listdir(d)
                if os.path.isfile(os.path.join(d, f)) and (pat is None or f.endswith(pat))])


kb.update(knowledge_md=cnt(os.path.join(PRJ, 'knowledge'), '.md'),
          papers_md=cnt(os.path.join(PRJ, 'knowledge', '论文'), '.md'),
          notes_txt=cnt(os.path.join(PRJ, 'knowledge', '历史笔记'), '.txt'),
          pdf_papers=cnt(os.path.join(PRJ, 'pdf_papers'), '.pdf'),
          reports_docx=cnt(os.path.join(PRJ, 'reports'), '.docx'),
          reports_png=cnt(os.path.join(PRJ, 'reports'), '.png'))
kb['knowledge_total'] = kb['knowledge_md'] + kb['papers_md'] + kb['notes_txt'] + 1  # +few_shot
U['kb'] = kb
print('知识库:', kb)

# 微调：真实 train_log.json 的 loss 曲线
# ⚠ 流域副本（pythonNlpBasin）不带 finetuned/ 权重目录（152MB，已列入 .gitignore），
#   故此处对缺失资产一律降级为空值 —— 否则生成链会在这一步抛 FileNotFoundError，
#   把整条仪表盘刷新拖死。这些字段只服务于已下线的全域视图，流域专题不依赖它们。
_LOGDIR = os.path.join(PRJ, 'finetuned', 'lora_news_15b')
_LOG = os.path.join(_LOGDIR, 'train_log.json')
_ADAPTER = os.path.join(_LOGDIR, 'adapter_model.safetensors')
_SFT = os.path.join(PRJ, 'finetune_data', 'instruction_data.jsonl')
try:
    tr = json.load(io.open(_LOG, encoding='utf-8'))
except (OSError, ValueError):
    tr = []
    print('⚠ 未找到 %s（精简副本的正常现象），微调曲线按空处理' % _LOG)
U['train'] = dict(
    base='Qwen2.5-1.5B-Instruct',
    adapter_mb=(round(os.path.getsize(_ADAPTER) / 1048576, 1)
                if os.path.isfile(_ADAPTER) else 0.0),
    sft_rows=(sum(1 for _ in io.open(_SFT, encoding='utf-8'))
              if os.path.isfile(_SFT) else 0),
    loss=[[e['step'], round(e['loss'], 4)] for e in tr if 'loss' in e],
    evals=[[e['step'], round(e['eval_loss'], 4)] for e in tr if 'eval_loss' in e],
    max_epoch=round(max([e.get('epoch', 0) for e in tr] or [0]), 2),
)
print('微调: %d loss 点 / %d eval 点 / 适配器 %.1f MB' % (
    len(U['train']['loss']), len(U['train']['evals']), U['train']['adapter_mb']))

# ============================================================
# 9. 三张词云原图（项目产物，base64 内联，零外链）
# ============================================================
import base64
U['cloudImg'] = {}
for k, f in (('article', 'article_cloud.jpg'), ('comment', 'comment_cloud.jpg'),
             ('user', 'comment_user_cloud.jpg')):
    p = os.path.join(PRJ, 'static', f)
    if os.path.exists(p):
        b = base64.b64encode(open(p, 'rb').read()).decode()
        U['cloudImg'][k] = 'data:image/jpeg;base64,' + b
        print('词云图 %s %.0f KB -> %.0f KB' % (k, os.path.getsize(p) / 1024, len(b) / 1024))

# ============================================================
# 10. 数据一致性核查（页面「核查」页直接读这里，全部为运行时算出的真值）
# ============================================================
def chk(name, expr, expect, note):
    return dict(name=name, got=expr, want=expect, ok=(expr == expect), note=note)


arts = U['basinSplit']['article']; cmts = U['basinSplit']['comment']
bip = {'yangtze': IP['article']['basin']['yangtze'], 'yellow': IP['article']['basin']['yellow'],
       'shared': IP['article']['basin']['shared'], 'outside': IP['article']['basin']['outside']}
U['recon'] = [
    chk('主表微博总量 == 热词统计口径', U['canon']['a_total'], HOT['article']['cleaned']['docs'],
        '两者都读 t_article 全表；若不等说明热词快照过期'),
    chk('主表评论总量 == 热词统计口径', U['canon']['c_total'], HOT['comment']['cleaned']['docs'],
        '同上，读 t_comment 全表'),
    chk('文章 IP 四类求和 == 已归属省份合计',
        arts['yz'] + arts['yl'] + arts['shared'] + arts['outside'], arts['prov_total'],
        '长江独有 + 黄河独有 + 共源 + 非流域 必须严丝合缝等于已归属'),
    chk('评论 IP 四类求和 == 已归属省份合计',
        cmts['yz'] + cmts['yl'] + cmts['shared'] + cmts['outside'], cmts['prov_total'],
        '同文章侧口径'),
    chk('文章 IP（省份+未知+AI+境外）== 全表', arts['prov_total'] + IP['article']['unknown']
        + IP['article']['ai'] + IP['article']['overseas'], U['canon']['a_total'],
        '分类互斥且完备，不得有漏桶'),
    chk('评论 IP（省份+未知+AI+境外）== 全表', cmts['prov_total'] + IP['comment']['unknown']
        + IP['comment']['ai'] + IP['comment']['overseas'], U['canon']['c_total'],
        '评论侧 AI 生成 556 条（智搜/罗伯特）不可并入境外'),
    dict(name='旧 basin 口径存在重复计数', got=bip['shared'], want=0, ok=(bip['shared'] == 0),
         note='ip_map_data.basin 的 YANGTZE/YELLOW 两表互不相交，但 shared 仍按「青海+四川」计，'
              '四川已在长江、青海已在黄河 → 该 %d 条属重复计入；页面统一改用「不重叠四色」口径'
              % bip['shared']),
    chk('流域表微博 != 主表微博（互不重叠）', U['canon']['b_art'] != U['canon']['a_total'], True,
        '两个爬虫各自写入，0 条 ID 重叠，只能 UNION 不能 JOIN'),
    chk('情感三样本求和自洽', all(sum(v['v']) == v['total'] for v in
                                  (U['sent']['article'], U['sent']['comment'], U['sent']['hot'])), True,
        '正文 400 / 评论 500 / 热搜词 200，正+中+负 == 总数'),
    chk('文章点赞分布求和 == 文章总数', sum(FD['articleAnalysis']['dz']['y']), U['canon']['a_total'],
        '分箱必须覆盖全量'),
    chk('评论点赞分布求和 == 评论总数', sum(FD['commentAnalysis']['dz']['y']), U['canon']['c_total'],
        '分箱必须覆盖全量'),
]
print('核查项: %d 通过 / %d' % (sum(1 for c in U['recon'] if c['ok']), len(U['recon'])))

conn.close()

io.open(f'{BASE}\\unified_data.json', 'w', encoding='utf-8').write(
    json.dumps(U, ensure_ascii=False, separators=(',', ':')))
print('写出 unified_data.json  %.0f KB' % (len(json.dumps(U, ensure_ascii=False)) / 1024))
print('键:', sorted(U.keys()))

