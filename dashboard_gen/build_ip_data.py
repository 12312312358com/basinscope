# -*- coding: utf-8 -*-
"""归一化 IP 地区数据 → 生成地图用 JSON（只读库，不写库）"""
import json, re, pymysql

PROV = ['北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江','上海','江苏','浙江',
        '安徽','福建','江西','山东','河南','湖北','湖南','广东','广西','海南','重庆','四川',
        '贵州','云南','西藏','陕西','甘肃','青海','宁夏','新疆','台湾','香港','澳门']
LONG = {'内蒙古':'内蒙古自治区','广西':'广西壮族自治区','宁夏':'宁夏回族自治区',
        '新疆':'新疆维吾尔自治区','西藏':'西藏自治区','香港':'中国香港',
        '澳门':'中国澳门','台湾':'中国台湾'}
YANGTZE = ['四川','重庆','湖北','湖南','江西','安徽','江苏','浙江','上海','云南','贵州','西藏']
YELLOW  = ['山东','河南','山西','陕西','内蒙古','宁夏','甘肃','青海']
SHARED  = ['青海','四川']


def norm(raw):
    """剥掉「来自 / 发布于」前缀，统一为中国大陆省份简称"""
    n = (raw or '').strip()
    n = re.sub(r'^(来自|发布于)\s*', '', n).strip()
    if n.startswith('中国') and n[2:] in PROV:
        n = n[2:]
    return n


def is_ai(n):
    return bool(n) and ('AI' in n or '智搜' in n or '罗伯特' in n or '千问' in n)


def load(tbl, col):
    c = pymysql.connect(host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '3306')), user=os.getenv('DB_USER', 'root'), password=os.getenv('DB_PASSWORD', ''),
                        database=os.getenv('DB_NAME', 'db_weibo_basin'), charset='utf8mb4')
    cur = c.cursor()
    cur.execute('SELECT `%s`, COUNT(*) FROM %s GROUP BY `%s`' % (col, tbl, col))
    rows = [(r[0], int(r[1])) for r in cur.fetchall()]
    c.close()
    return rows


def build(rows, label):
    prov = {p: 0 for p in PROV}
    unknown = ai = overseas = 0
    raw_forms = {}
    for raw, v in rows:
        n = norm(raw)
        if n in prov:
            prov[n] += v
        elif is_ai((raw or '').strip()):
            ai += v
            raw_forms['AI生成'] = raw_forms.get('AI生成', 0) + v
        elif not n or n == '未知':
            unknown += v
        else:
            overseas += v
    # 记录被归一化掉的原值（供报告用）
    fixed = {}
    for raw, v in rows:
        n = norm(raw)
        if raw is not None and n != (raw or '').strip() and n in prov:
            fixed[(raw or '').strip()] = fixed.get((raw or '').strip(), 0) + v
    total = sum(prov.values()) + unknown + ai + overseas
    return {
        'label': label, 'total': total,
        'provinces': {p: prov[p] for p in PROV},
        'unknown': unknown, 'ai': ai, 'overseas': overseas,
        'normalized_from': fixed,
        'basin': {
            'yangtze': sum(prov[p] for p in YANGTZE),
            'yellow': sum(prov[p] for p in YELLOW),
            'shared': sum(prov[p] for p in SHARED),
            'outside': sum(prov[p] for p in PROV if p not in YANGTZE and p not in YELLOW),
        },
    }


art = build(load('t_article', '发布地区'), '微博作者')
com = build(load('t_comment', '来源'), '评论作者')

# 颜色与显示名放在 Python 侧（用 \u 转义，杜绝手打中文出错）
meta = {
    'PROV': PROV, 'YANGTZE': YANGTZE, 'YELLOW': YELLOW, 'SHARED': SHARED, 'LONG': LONG,
    'BCLR': ['#2E7BE0', '#E8A33D', '#3F9E6B', '#D8DEE5'],
    'BNAME': ['\u957f\u6c5f\u6d41\u57df', '\u9ec4\u6cb3\u6d41\u57df',
              '\u957f\u6c5f / \u9ec4\u6cb3\uff08\u5171\u6e90\u7701\uff09',
              '\u975e\u6d41\u57df'],
    'BTAG': ['\u957f\u6c5f', '\u9ec4\u6cb3', '\u5171\u6e90', ''],
    'TITLE_BASIN': '\u957f\u6c5f\u9ec4\u6cb3\u6d41\u57df',
}
json.dump({'article': art, 'comment': com, 'meta': meta},
          open('ip_map_data.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

for k, d in (('文章', art), ('评论', com)):
    print('==', k, '总', d['total'], '| 省份合计', sum(d['provinces'].values()),
          '| 未知', d['unknown'], '| AI生成', d['ai'], '| 境外', d['overseas'])
    print('   流域 —— 长江(含共源)', d['basin']['yangtze'], '黄河(含共源)', d['basin']['yellow'],
          '共源', d['basin']['shared'], '非流域', d['basin']['outside'])
    print('   被归一化的原值:', d['normalized_from'])


