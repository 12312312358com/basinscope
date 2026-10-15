# -*- coding: utf-8 -*-
"""只读：生成「微博热词统计分析」预览数据。一次分词，派生「清洗前/清洗后」两套口径。"""
import re, sys, json, collections, datetime
import pymysql, jieba
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass
jieba.setLogLevel(60)

conn = pymysql.connect(host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '3306')), user=os.getenv('DB_USER', 'root'), password=os.getenv('DB_PASSWORD', ''),
                       database=os.getenv('DB_NAME', 'db_weibo_basin'), charset='utf8mb4')
cur = conn.cursor()

STOP = set('''的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 这个 这样 那里 这里 什么 怎么
可以 我们 你们 他们 她们 它们 如何 因为 所以 但是 如果 虽然 还是 已经 就是 真的 觉得 知道 现在 今天 明天 昨天 时候 时间 感觉
微博 转发 评论 点赞 链接 全文 视频 展开 网页 http https cn com www 分享 来自 详情 查看 原文 更多 话题 超话 热搜
不是 那么 之后 之前 里面 出来 起来 上去 下去 过来 只是 那样 多少 为什么
宝宝 期待 允悲 doge call 微笑 嘻嘻 哈哈 呵呵 加油 支持 喜欢 爱了 太棒 真棒 不错 好看 有趣 笑死 离谱 无语 服了'''.split())
NUM = re.compile(r'\d')
CLN = re.compile(r'[\W_]+')
BADFMT = re.compile(r'^[A-Z][a-z]{2} ')

def raw_tokens(text):
    for s in jieba.cut(str(text)):
        s = s.strip()
        if len(s) < 2 or NUM.search(s) or CLN.fullmatch(s): continue
        yield s

def parse_dt(v):
    if not v: return None
    s = str(v).strip()
    if BADFMT.match(s):
        return None                      # 微博英文格式，记为「格式异常」
    for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try: return datetime.datetime.strptime(s, f)
        except Exception: pass
    return None

def run(sql, label):
    cur.execute(sql)
    rows = cur.fetchall()
    res = {}
    for mode in ('raw', 'cleaned'):
        res[mode] = {'freq': collections.Counter(), 'docf': collections.Counter(),
                     'recent': collections.Counter(), 'prev': collections.Counter(),
                     'daily': collections.defaultdict(collections.Counter)}
    dts, bad = [], 0
    for r in rows:
        txt = r[0]; dt = parse_dt(r[1]); dts.append(dt)
        if dt is None and r[1]: bad += 1
        tk_all = list(raw_tokens(txt))
        tk_cln = [w for w in tk_all if w.lower() not in STOP]
        for mode, tk in (('raw', tk_all), ('cleaned', tk_cln)):
            b = res[mode]
            b['freq'].update(tk); b['docf'].update(set(tk))
            if dt: b['daily'][dt.date()].update(tk)
    valid = [d for d in dts if d]
    tmax = max(valid) if valid else None
    c1 = tmax - datetime.timedelta(days=7); c0 = tmax - datetime.timedelta(days=14)
    for i, dt in enumerate(dts):
        if not dt: continue
        tk_all = list(raw_tokens(rows[i][0]))
        tk_cln = [w for w in tk_all if w.lower() not in STOP]
        for mode, tk in (('raw', tk_all), ('cleaned', tk_cln)):
            b = res[mode]; st = set(tk)
            if dt > c1: b['recent'].update(st)
            elif dt > c0: b['prev'].update(st)

    out = {}
    for mode in ('raw', 'cleaned'):
        b = res[mode]; freq, docf = b['freq'], b['docf']
        top = []
        for w, c in freq.most_common(20):
            p, n = b['prev'].get(w, 0), b['recent'].get(w, 0)
            top.append({'w': w, 'freq': c, 'docf': docf[w], 'p7': p, 'n7': n,
                        'chg': round((n - p) / p * 100, 1) if p >= 5 else None,
                        'spark': [b['daily'][d].get(w, 0) for d in
                                  sorted(k for k in b['daily'] if k >= tmax.date() - datetime.timedelta(days=20))]})
        out[mode] = {'docs': len(rows), 'tokens': sum(freq.values()), 'distinct': len(freq),
                     'tmax': str(tmax)[:16], 'bad_time': bad,
                     'win_new': f'{c1.date()} ~ {tmax.date()}', 'win_old': f'{c0.date()} ~ {c1.date()}',
                     'top': top}
    print(f"[{label}] 文档{out['raw']['docs']} | 清洗前 总词频{out['raw']['tokens']} 去重{out['raw']['distinct']}"
          f" | 清洗后 总词频{out['cleaned']['tokens']} 去重{out['cleaned']['distinct']} | 时间格式异常 {bad}")
    print('   清洗前Top8:', [t['w'] for t in out['raw']['top'][:8]])
    print('   清洗后Top8:', [t['w'] for t in out['cleaned']['top'][:8]])
    return out

A = "SELECT `微博内容`,`发布时间` FROM t_article WHERE `微博内容` IS NOT NULL AND `微博内容`<>''"
C = "SELECT `评论内容`,`评论时间` FROM t_comment WHERE `评论内容` IS NOT NULL AND `评论内容`<>''"
data = {'generated': str(datetime.datetime.now())[:19],
        'article': run(A, '文章'), 'comment': run(C, '评论')}
data['stop_used'] = sorted(STOP)
json.dump(data, open('hotword_preview_data.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('\n写出 hotword_preview_data.json  大小 %.0f KB' % (len(json.dumps(data, ensure_ascii=False)) / 1024))
conn.close()


