# -*- coding: utf-8 -*-
"""首页总览「济南区位」地图模块的数据层 → dashboard_gen/jinan_map_data.json

三张图各自的**真实数据来源**（三者口径不同，页面必须分别标注，不可混读）：

1) 中国图（上）　＝ 微博**发布地区（作者 IP 属地）**计数，省级粒度
   来源：db_weibo_basin.t_article.发布地区（全表 29,710 条）
   注意：只有「全国省级」才知道每省多少条；山东 = 1,443 条。

2) 山东图（右下）＝ 微博**正文提及**山东各地市的次数，地市级粒度（近似口径）
   来源：t_article.微博内容 LIKE '%<市名>%'
   为什么不用 IP 属地：微博 IP 属地只到省，库里**没有**地市级字段，
   所以这里换成「文本提及」，并在页面明确写清是与 IP 属地不同的口径。

3) 济南图（左下）＝ 微博**正文提及**济南各区县的次数，区县级粒度（近似口径）
   来源：t_article.微博内容 LIKE '%<区县名>%'
   实测数据稀薄（全区县合计仅十余条），页面必须标注"样本稀薄、不足以代表区县热度"。

合规：中国地图沿用既有 static/js/china.js（含南海诸岛附图）与山东/济南边界，
      不换源、不重绘、不改边界；本脚本只做数值统计，不产生任何地图几何。

用法：python dashboard_gen/build_jinan_map.py
"""
import io
import json
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(BASE, 'jinan_map_data.json')

DB = os.getenv('DB_NAME', 'db_weibo_basin')

# 山东 16 地市（与 static/js/shandong.js 的 name 一致，带「市」后缀）
SD_CITIES = ['济南市', '青岛市', '淄博市', '枣庄市', '东营市', '烟台市', '潍坊市', '济宁市',
             '泰安市', '威海市', '日照市', '临沂市', '德州市', '聊城市', '滨州市', '菏泽市']
# 济南 12 区县（与 static/js/jinan.js 的 name 一致）
JN_DISTRICTS = ['历下区', '市中区', '槐荫区', '天桥区', '历城区', '长清区',
                '章丘区', '济阳区', '莱芜区', '钢城区', '平阴县', '商河县']

# 文本检索用的简称（「济南市」的正文多数写作「济南」）
SD_ALIAS = {'济南市': '济南', '青岛市': '青岛', '淄博市': '淄博', '枣庄市': '枣庄',
            '东营市': '东营', '烟台市': '烟台', '潍坊市': '潍坊', '济宁市': '济宁',
            '泰安市': '泰安', '威海市': '威海', '日照市': '日照', '临沂市': '临沂',
            '德州市': '德州', '聊城市': '聊城', '滨州市': '滨州', '菏泽市': '菏泽'}

# t_article.发布地区 → china.js 里的省名（少数取值需要归一）
PROV_FIX = {'中国香港': '香港', '中国台湾': '台湾', '中国澳门': '澳门'}
# china.js 的省级名称集合（34 个省级行政区口径）
PROV_NAMES = ['北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江', '上海', '江苏',
              '浙江', '安徽', '福建', '江西', '山东', '河南', '湖北', '湖南', '广东', '广西',
              '海南', '重庆', '四川', '贵州', '云南', '西藏', '陕西', '甘肃', '青海', '宁夏',
              '新疆', '台湾', '香港', '澳门']


def engine():
    from sqlalchemy import create_engine
    host = os.getenv('DB_HOST', 'localhost')
    user = os.getenv('DB_USER', 'root')
    pwd = os.getenv('DB_PASSWORD', '')
    return create_engine('mysql+pymysql://%s:%s@%s:3306/%s?charset=utf8mb4'
                         % (user, pwd, host, DB))


def main():
    from sqlalchemy import text
    eng = engine()
    with eng.connect() as c:
        total = c.execute(text('SELECT COUNT(*) FROM `t_article`')).scalar() or 0

        # ---- ① 中国图：发布地区（IP 属地）省级计数 ----
        rows = c.execute(text(
            "SELECT `发布地区`, COUNT(*) FROM `t_article` "
            "WHERE `发布地区` IS NOT NULL AND `发布地区`<>'' GROUP BY `发布地区`")).fetchall()
        prov, unknown, overseas = {}, 0, 0
        unknown_vals = []
        for k, n in rows:
            if k == '未知':
                unknown = n
                continue
            nm = PROV_FIX.get(k, k)
            if nm in PROV_NAMES:
                prov[nm] = prov.get(nm, 0) + n
            else:                     # 境外 / 无法归到省级行政区的取值（如「马来西亚」）
                overseas += n
                unknown_vals.append('%s %d' % (k, n))

        # ---- ② 山东图：正文提及各地市次数 ----
        sd = {}
        for city in SD_CITIES:
            kw = SD_ALIAS.get(city, city.replace('市', ''))
            sd[city] = c.execute(text(
                'SELECT COUNT(*) FROM `t_article` WHERE `微博内容` LIKE :k'),
                {'k': '%' + kw + '%'}).scalar() or 0

        # ---- ③ 济南图：正文提及各区县次数 ----
        jn = {}
        for d in JN_DISTRICTS:
            jn[d] = c.execute(text(
                'SELECT COUNT(*) FROM `t_article` WHERE `微博内容` LIKE :k'),
                {'k': '%' + d + '%'}).scalar() or 0

        # ---- 济南相关总量 + 讨论来源地 ----
        # 注意：**不能**写 `GROUP BY 发布地区 ORDER BY 2 DESC LIMIT 8` 直接出榜单 ——
        # 「未知」（作者未公开 IP / 采集缺失）会作为一个"地区"挤进排行，甚至排到第 2
        # （2026-09-28 实测：山东 185 / 未知 37 / 北京 19 …），把四川等真实省份挤出 Top6，
        # 页面于是出现"未知"这种非地点条目。口径必须与上方中国图完全一致：
        # 先剔除 未知 / 空 / 境外，再对真实省级声量排序；缺失量单列上报，不参与排行。
        jn_total = c.execute(text(
            "SELECT COUNT(*) FROM `t_article` WHERE `微博内容` LIKE '%济南%'")).scalar() or 0
        rows_src = c.execute(text(
            "SELECT COALESCE(`发布地区`, ''), COUNT(*) FROM `t_article` "
            "WHERE `微博内容` LIKE '%济南%' GROUP BY `发布地区`")).fetchall()
        jn_prov, jn_unknown, jn_other, jn_other_vals = {}, 0, 0, []
        for k, n in rows_src:
            if not k or k == '未知':           # 空值 / 「未知」＝缺失，不是地区
                jn_unknown += n
                continue
            nm = PROV_FIX.get(k, k)
            if nm in PROV_NAMES:
                jn_prov[nm] = jn_prov.get(nm, 0) + n
            else:                              # 境外 / 无法归到省级行政区（如「加拿大」）
                jn_other += n
                jn_other_vals.append('%s %d' % (k, n))
        jn_src = sorted(jn_prov.items(), key=lambda z: -z[1])
        sd_ip = c.execute(text(
            "SELECT COUNT(*) FROM `t_article` WHERE `发布地区`='山东'")).scalar() or 0

    data = {
        'meta': {
            'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'db_weibo_basin.t_article（全表 %d 条）' % total,
            'total': total,
            'unknown': unknown,
            'overseas': overseas,
            'sdIp': sd_ip,
            'jnTotal': jn_total,
            'provinces': len(prov),
        },
        'prov': prov,
        'sd': sd,
        'jn': jn,
        # jnSrc：**仅真实省级行政区**的声量排行（已剔除 未知/空/境外），可直接当榜单用
        'jnSrc': [[k, v] for k, v in jn_src[:8]],
        # jnMiss：同口径下的缺失量，页面须以脚注单列，不得混进上面的排行
        'jnMiss': {
            'unknown': jn_unknown,             # 发布地区为空或写「未知」
            'other': jn_other,                 # 境外 / 无法归到省级行政区
            'otherVals': jn_other_vals[:6],
            'provTotal': sum(jn_prov.values()),  # 可归省的合计（＝总提及 − 缺失）
            'total': jn_total,
            'provinces': len(jn_prov),
        },
        'rules': {
            'china': '微博发布地区（作者 IP 属地）计数 · 省级粒度',
            'sd': '微博正文提及次数的近似口径（本项目无地市级 IP 数据）',
            'jn': '微博正文提及次数的近似口径（样本稀薄，不代表区县热度）',
            'jnSrc': '仅统计可归到省级行政区的发布地区；「未知」/空/境外单列脚注，不参与排行',
            'excluded': '「未知」%d 条、境外/无法归省 %d 条未计入中国图（%s）'
                        % (unknown, overseas, '、'.join(unknown_vals[:6])),
        },
    }
    with io.open(DST, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    print('[jinan_map] 写出 %s（%.1f KB）' % (os.path.relpath(DST, os.path.dirname(BASE)),
                                             os.path.getsize(DST) / 1024.0))
    print('[jinan_map] 中国图省数 = %d（山东 %s）· 山东地市 济南 %s / 青岛 %s · '
          '济南区县合计 %d · 含「济南」微博 %d'
          % (len(prov), prov.get('山东'), sd.get('济南市'), sd.get('青岛市'),
             sum(jn.values()), jn_total))
    print('[jinan_map] 济南来源地 Top6 = %s · 缺失（未知/空）%d 条、境外 %d 条'
          % ('、'.join('%s%d' % (k, v) for k, v in jn_src[:6]),
             jn_unknown, jn_other))
    # 原写法 '[jinan_map] 口径：& '.join(...) 会把分隔符当"前缀"复制到每一项之间，
    # 日志里出现四条互相穿插的 `[jinan_map] 口径：&`，读不出来。改为先拼接再前缀。
    print('[jinan_map] 口径：' + ' ｜ '.join(data['rules'][k] for k in ('china', 'sd', 'jn', 'jnSrc')))


if __name__ == '__main__':
    main()

