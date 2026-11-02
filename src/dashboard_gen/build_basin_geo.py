# -*- coding: utf-8 -*-
"""两流域「专属地图」几何数据 → dashboard_gen/basin_geo_map.json

用途：长江 / 黄河两个专题的「总览」页新增一张地图卡，**只画该河流流经的省级行政区**，
不渲染完整中国地图。

几何来源：
    阿里云 DataV 地理边界 areas_v3 —— https://geo.datav.aliyun.com/areas_v3/bound/<adcode>.json
    （省级**整体轮廓**，不带市级细分；与 static/js/shandong.js / jinan.js 同源同口径）
    原始 json 缓存在 dashboard_gen/_geo_raw/<adcode>.json，本脚本只做「取子集 + 抽稀 + 降精度」，
    **不重绘、不改边界**。

为什么抽稀 / 降精度：
    20 个省轮廓原始合计约 840 KB；4 位小数保留 + Douglas-Peucker 抽稀后约 1/4，
    在 900×620 的卡片内目视无差别（4 位小数 ≈ 11 m，远小于一个像素对应的距离）。
    单文件 HTML 已内联 echarts，体积要克制。

口径说明（写进页面 ruler，不可省）：
    本图省份 = 本项目**数据口径**的流域省份 —— 长江 12 省、黄河 8 省。
    长江干流流经 11 省区市，数据口径另含贵州、浙江（上游 / 太湖流域）；
    黄河干流流经 9 省区，其中共源省「四川」在本作品里归入长江专题，故黄河图 8 省。

用法：python dashboard_gen/build_basin_geo.py
"""
import io
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, '_geo_raw')
DST = os.path.join(BASE, 'basin_geo_map.json')

# adcode -> 项目内简称（与 ip.meta.PROV 同口径）
PROV = {
    '630000': '青海', '540000': '西藏', '510000': '四川', '530000': '云南',
    '500000': '重庆', '420000': '湖北', '430000': '湖南', '360000': '江西',
    '340000': '安徽', '320000': '江苏', '310000': '上海', '520000': '贵州',
    '330000': '浙江', '620000': '甘肃', '640000': '宁夏', '150000': '内蒙古',
    '610000': '陕西', '140000': '山西', '410000': '河南', '370000': '山东',
}

# 数据口径的流域省份（与 build_unified_page.RIVER_YZ / RIVER_YL 完全一致）
YZ = ['西藏', '云南', '四川', '重庆', '贵州', '湖南', '湖北',
      '江西', '安徽', '江苏', '浙江', '上海']
YL = ['青海', '甘肃', '宁夏', '内蒙古', '陕西', '山西', '河南', '山东']
# 两江共源省：青海是长江正源所在省，四川西北有黄河流过。
# 数据口径把它们各归一条江（青海 → 黄河、四川 → 长江），但**地图必须画出来**：
#   ① 地理上它们确实被该河流经，只画数据口径省份就等于漏省；
#   ② 长江源（唐古拉山 91.0/33.5）落在青海境内 —— 青海不画，源头标记就悬在空处。
# 所以地图省份 = 数据口径省份 ∪ 共源省；共源省在这张图上没有本流域样本，另行标注。
SHARED = ['青海', '四川']
MAP_YZ = YZ + [p for p in SHARED if p not in YZ]      # 13 省
MAP_YL = YL + [p for p in SHARED if p not in YL]      # 9 省

NDIGIT = 3          # 坐标保留小数位（3 位 ≈ 111 m，远小于一个像素）
TOL = 0.012         # Douglas-Peucker 容差（度），≈ 1.3 km

# 干流示意走向（经纬度折线，源 → 入海）。与 dashboard_gen/basin_geo.py 同源，
# 仅作「干流大致走向」示意，不用于任何测量；被 R.basinmap 的 lines 系列引用。
RIVER_YZ = [
    [91.0, 33.5], [92.5, 34.2], [94.5, 34.0], [96.5, 33.5], [97.0, 33.0],
    [98.1, 32.9], [99.0, 32.0], [99.9, 31.6], [100.2, 30.2], [100.5, 28.5],
    [101.0, 27.2], [101.7, 26.6], [102.8, 27.5], [104.0, 28.2], [104.6, 28.8],
    [105.4, 28.9], [106.0, 29.2], [106.5, 29.6], [107.4, 29.7], [108.0, 30.3],
    [108.4, 30.8], [109.5, 30.9], [110.5, 30.9], [111.3, 30.7], [112.2, 30.3],
    [113.1, 29.4], [114.3, 30.6], [115.1, 30.2], [116.0, 29.7], [116.6, 30.1],
    [117.0, 30.5], [117.8, 30.9], [118.4, 31.3], [118.8, 32.1], [119.5, 32.2],
    [120.3, 32.1], [120.9, 32.0], [121.5, 31.7], [121.9, 31.4],
]
RIVER_YL = [
    [96.2, 34.9], [98.5, 34.5], [100.2, 34.3], [102.1, 33.9], [103.0, 35.3],
    [103.8, 36.1], [104.6, 36.6], [105.2, 37.5], [106.3, 38.5], [106.8, 39.3],
    [107.4, 40.7], [109.0, 40.7], [109.8, 40.6], [110.8, 40.4], [111.2, 40.3],
    [111.4, 39.2], [111.0, 38.4], [110.7, 37.5], [110.4, 36.6], [110.5, 35.7],
    [110.3, 34.6], [111.4, 34.8], [112.4, 34.8], [113.6, 34.9], [114.3, 34.9],
    [115.0, 35.7], [116.0, 36.4], [116.9, 36.8], [117.8, 37.3], [118.6, 37.6],
    [119.1, 37.8],
]


def _dp(pts, tol):
    """Douglas-Peucker 抽稀；返回保留的点。"""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if seg2 <= 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / seg2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                d2 = (px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2
            if d2 > best:
                best, bi = d2, k
        if best > tol * tol:
            keep[bi] = True
            stack.append((i, bi))
            stack.append((bi, j))
    return [p for p, k in zip(pts, keep) if k]


def _ring(coords):
    out = []
    for c in coords:
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            continue
        p = [round(float(c[0]), NDIGIT), round(float(c[1]), NDIGIT)]
        if not out or p != out[-1]:
            out.append(p)
    # 闭合环：首尾相同 → 去掉尾点交给抽稀，抽稀后补回
    closed = len(out) > 1 and out[0] == out[-1]
    if closed:
        out = out[:-1]
    out = _dp(out, TOL)
    if len(out) < 3:
        out = out[:3]
    out.append(list(out[0]))
    return out


def _round(geom):
    """把 DataV 的 Polygon / MultiPolygon 归一成 MultiPolygon（环坐标抽稀 + 降精度）。"""
    t = geom['type']
    if t == 'Polygon':
        polys = [geom['coordinates']]
    elif t == 'MultiPolygon':
        polys = geom['coordinates']
    else:
        raise ValueError('不支持的几何类型：%s' % t)
    out = []
    for poly in polys:
        rings = []
        for i, r in enumerate(poly):
            rr = _ring(r)
            # 只保留面积像样的环（省会城市中心点等噪点环在抽稀后可能退化成 4 点小方块）
            if i > 0 and _area(rr) < 1e-4:
                continue
            rings.append(rr)
        if rings:
            out.append(rings)
    return {'type': 'MultiPolygon', 'coordinates': out}


def _area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        s += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(s) / 2.0


def load(name, anchor=False):
    code = [k for k, v in PROV.items() if v == name]
    assert len(code) == 1, '省名对不上 adcode：%s' % name
    p = os.path.join(RAW, code[0] + '.json')
    with io.open(p, encoding='utf-8') as f:
        gj = json.load(f)
    f0 = gj['features'][0]
    pr = f0['properties']
    # anchor：地图上放省名标签用的锚点。优先用 centroid（形状重心，比 center 更靠
    # 几何中央 —— center 对细长省（内蒙古、甘肃）会落在边上）。
    ac = pr.get('centroid') or pr.get('center')
    return {'type': 'Feature',
            'properties': {'name': name, 'adcode': pr.get('adcode'),
                           'anchor': [round(ac[0], 4), round(ac[1], 4)]},
            'geometry': _round(f0['geometry'])}


def main():
    out = {}
    for key, provs in (('yz', MAP_YZ), ('yl', MAP_YL)):
        feats = [load(p) for p in provs]
        out[key] = {'type': 'FeatureCollection', 'features': feats}
    out['river'] = {'yz': RIVER_YZ, 'yl': RIVER_YL}
    out['meta'] = {'yz': MAP_YZ, 'yl': MAP_YL, 'data': {'yz': YZ, 'yl': YL},
                   'shared': SHARED,
                   'source': '阿里云 DataV areas_v3（省级整体轮廓）',
                   'riverSource': '干流示意走向（源→入海），仅作走向示意',
                   'tol': TOL, 'ndigit': NDIGIT}
    with io.open(DST, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    n = os.path.getsize(DST)
    print('写出 %s  %.1f KB' % (DST, n / 1024.0))
    for k in ('yz', 'yl'):
        pts = sum(len(r) for ft in out[k]['features']
                  for poly in ft['geometry']['coordinates'] for r in poly)
        print('  %s：%d 省（含共源 %d 省）/ %d 个坐标点'
              % (k, len(out[k]['features']),
                 len([p for p in out[k]['features']
                      if p['properties']['name'] in SHARED]), pts))


if __name__ == '__main__':
    main()
