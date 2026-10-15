"""
    微博帖子数据访问对象 (已修复字段匹配与逻辑优化)
"""
from util import dbUtil
import os
import json

# ===================== 平台 / 流域 路由（参赛改造：对话按专题隔离） =====================
# 文章表：平台 -> 列配置。流域 / 跨平台表的省份列统一用 `目标省份`（口径一致）。
_ART_TABLES = {
    '微博':   {'tbl': 't_basin_article',  'txt': '微博内容', 'like': '点赞数',
               'au': '作者昵称', 'cat': '分类',     'area': '目标省份'},
    '小红书': {'tbl': 't_xhs_article',    'txt': '正文',     'like': '点赞数',
               'au': '作者昵称', 'cat': '话题标签', 'area': '目标省份'},
    '知乎':   {'tbl': 't_zhihu_article',  'txt': '正文',     'like': '点赞数',
               'au': '作者昵称', 'cat': '话题标签', 'area': '目标省份'},
    '抖音':   {'tbl': 't_douyin_article', 'txt': '视频标题', 'like': '点赞数',
               'au': '作者昵称', 'cat': '话题标签', 'area': '目标省份'},
}
_DEFAULT_PLATFORM = '微博'

# 评论表：平台 -> 列配置（评论类工具用）
_CMT_TABLES = {
    '微博':   {'tbl': 't_basin_comment',  'nick': '昵称', 'txt': '评论内容', 'like': '点赞数'},
    '小红书': {'tbl': 't_xhs_comment',    'nick': '昵称', 'txt': '评论内容', 'like': '点赞数'},
    '知乎':   {'tbl': 't_zhihu_comment',  'nick': '昵称', 'txt': '评论内容', 'like': '点赞数'},
    '抖音':   {'tbl': 't_douyin_comment', 'nick': '昵称', 'txt': '评论内容', 'like': '点赞数'},
}


def _cmt_ctx(platform=None, basin=None):
    """评论表上下文：微博 + 无流域 → t_comment（旧行为）；否则走流域/平台评论表。"""
    platform = platform or _DEFAULT_PLATFORM
    if platform == '微博' and not basin:
        return {'tbl': 't_comment', 'nick': '昵称', 'txt': '评论内容',
                'like': '点赞数', 'bcol': None}
    cfg = dict(_CMT_TABLES.get(platform, _CMT_TABLES[_DEFAULT_PLATFORM]))
    cfg['bcol'] = '流域'
    return cfg


def _art_ctx(platform=None, basin=None):
    """解析文章类查询用的表与列。
    微博 + 未指定流域 → 沿用原始 t_article（发布地区口径），保持历史行为不变；
    其余情况 → 走对应平台表；basin 非空时按 `流域` 过滤。"""
    platform = platform or _DEFAULT_PLATFORM
    if platform == '微博' and not basin:
        return {'tbl': 't_article', 'txt': '微博内容', 'like': '点赞数',
                'au': '作者昵称', 'cat': '分类', 'area': '发布地区', 'bcol': None}
    cfg = dict(_ART_TABLES.get(platform, _ART_TABLES[_DEFAULT_PLATFORM]))
    cfg['bcol'] = '流域'
    return cfg


def getArticleByArcType(arcType):
    """
    根据微博类别查询微博帖子信息
    """
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        # 字段名和数据库完全匹配：`分类`
        sql = "SELECT * FROM t_article WHERE `分类` = %s"
        cursor.execute(sql, (arcType,))
        return cursor.fetchall()
    except Exception as e:
        print("根据分类查询微博失败：", e)
        return []
    finally:
        if con: dbUtil.closeCon(con)


def getAllArticle():
    """
    查询所有帖子信息 (按点赞数降序)
    """
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        sql = "SELECT * FROM t_article ORDER BY `点赞数` DESC"
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print("查询所有文章失败：", e)
        return []
    finally:
        if con: dbUtil.closeCon(con)


def getTotalArticle(platform=None, basin=None):
    """
    获取帖子总数（可按平台 / 流域过滤）
    """
    c = _art_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = "SELECT count(*) FROM `%s` WHERE `%s`=%%s" % (c['tbl'], c['bcol'])
            cursor.execute(sql, (basin,))
        else:
            sql = "SELECT count(*) FROM `%s`" % c['tbl']
            cursor.execute(sql)
        res = cursor.fetchone()
        return res[0] if res else 0
    except Exception as e:
        print("查询总数失败：", e)
        return 0
    finally:
        if con: dbUtil.closeCon(con)


def getTopAuthor(platform=None, basin=None):
    """
    获取点赞最高微博作者（可按平台 / 流域过滤）
    """
    c = _art_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = "SELECT `%s` FROM `%s` WHERE `%s`=%%s ORDER BY `%s` DESC LIMIT 0,1" % (
                c['au'], c['tbl'], c['bcol'], c['like'])
            cursor.execute(sql, (basin,))
        else:
            sql = "SELECT `%s` FROM `%s` ORDER BY `%s` DESC LIMIT 0,1" % (c['au'], c['tbl'], c['like'])
            cursor.execute(sql)
        res = cursor.fetchone()
        return res[0] if res else "暂无"
    except Exception as e:
        print("查询最高作者失败：", e)
        return "暂无"
    finally:
        if con: dbUtil.closeCon(con)


def getTopRegion(platform=None, basin=None):
    """
    获取声量最高的省份 / 地区。
    - 未指定流域（微博兼容旧行为）：按 `发布地区` 的点赞数总和（IP 属地口径）；
    - 指定流域 / 平台：按 `目标省份` 的发帖条数（声量=发帖量），与看板口径一致。
    """
    c = _art_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        area = c['area']
        if basin and c.get('bcol'):
            sql = ("SELECT `%s`, COUNT(*) AS ac FROM `%s` "
                   "WHERE `%s`=%%s AND `%s` IS NOT NULL AND `%s`!='' AND `%s`!='未知' "
                   "GROUP BY `%s` ORDER BY ac DESC LIMIT 0,1") % (
                area, c['tbl'], c['bcol'], area, area, area, area)
            cursor.execute(sql, (basin,))
        else:
            sql = ("SELECT `%s`, SUM(`%s`) AS ac FROM `%s` "
                   "WHERE `%s`!='' AND `%s`!='未知' "
                   "GROUP BY `%s` ORDER BY ac DESC LIMIT 0,1") % (
                area, c['like'], c['tbl'], area, area, area)
            cursor.execute(sql)
        res = cursor.fetchone()
        return res[0] if res else "暂无"
    except Exception as e:
        print("查询城市失败：", e)
        return "暂无"
    finally:
        if con: dbUtil.closeCon(con)


def getArticleTopZan(platform=None, basin=None):
    """
    获取点赞最高的6条帖子（可按平台 / 流域过滤）
    """
    c = _art_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = "SELECT `%s`,`%s` FROM `%s` WHERE `%s`=%%s ORDER BY `%s` DESC LIMIT 0,6" % (
                c['txt'], c['like'], c['tbl'], c['bcol'], c['like'])
            cursor.execute(sql, (basin,))
        else:
            sql = "SELECT `%s`,`%s` FROM `%s` ORDER BY `%s` DESC LIMIT 0,6" % (
                c['txt'], c['like'], c['tbl'], c['like'])
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print("查询热门帖子失败：", e)
        return []
    finally:
        if con: dbUtil.closeCon(con)


def get7DayArticle(platform=None, basin=None):
    """
    获取最近7天帖子数量（可按平台 / 流域过滤；升序，让图表 X 轴从左到右）
    """
    c = _art_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        # 使用子查询先降序取7天，再在外层升序排列，保证图表X轴时间从左到右递增
        use_b = bool(basin and c.get('bcol'))
        # 带参查询时 % 必须转义为 %%，否则 pymysql 会把它当占位符（历史踩坑）
        fmt = '%%Y-%%m-%%d' if use_b else '%Y-%m-%d'
        wf = f"WHERE `{c['bcol']}`=%s" if use_b else ''
        sql = f"""
            SELECT articleDate, articleTotal FROM (
                SELECT DATE_FORMAT(`发布时间`,'{fmt}') AS articleDate, COUNT(`{c['txt']}`) AS articleTotal
                FROM `{c['tbl']}` {wf}
                GROUP BY articleDate
                ORDER BY articleDate DESC
                LIMIT 0,7
            ) AS temp ORDER BY articleDate ASC
        """
        if use_b:
            cursor.execute(sql, (basin,))
        else:
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print("查询7天数据失败：", e)
        return []
    finally:
        if con: dbUtil.closeCon(con)


def getArticleTypeAmount(platform=None, basin=None):
    """
    获取帖子类别数量（可按平台 / 流域过滤）
    """
    c = _art_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = "SELECT `%s`, COUNT(*) FROM `%s` WHERE `%s`=%%s GROUP BY `%s`" % (
                c['cat'], c['tbl'], c['bcol'], c['cat'])
            cursor.execute(sql, (basin,))
        else:
            sql = "SELECT `%s`, COUNT(*) FROM `%s` GROUP BY `%s`" % (c['cat'], c['tbl'], c['cat'])
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print("查询分类失败：", e)
        return []
    finally:
        if con: dbUtil.closeCon(con)


def getTopCommentUser(platform=None, basin=None):
    """
    获取TOP前50评论用户名（可按平台 / 流域过滤）
    【核心修复】：将 '评论者昵称' 改为爬虫实际入库的 '昵称'
    """
    c = _cmt_ctx(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            # ⚠️ 爬虫入库字段叫 `昵称`
            sql = ("SELECT `%s`, COUNT(`%s`) AS unCount FROM `%s` WHERE `%s`=%%s "
                   "GROUP BY `%s` ORDER BY unCount DESC LIMIT 0,50") % (
                c['nick'], c['nick'], c['tbl'], c['bcol'], c['nick'])
            cursor.execute(sql, (basin,))
        else:
            sql = ("SELECT `%s`, COUNT(`%s`) AS unCount FROM `%s` "
                   "GROUP BY `%s` ORDER BY unCount DESC LIMIT 0,50") % (
                c['nick'], c['nick'], c['tbl'], c['nick'])
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print("查询评论用户失败：", e)
        return []
    finally:
        if con: dbUtil.closeCon(con)


# ===================== 流域热点事件（供对话按专题取数） =====================
_BASIN_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'dashboard_gen', 'basin_data.json')


def getBasinHotEvents(basin=None, limit=10):
    """读取指定流域的热点事件簇、热词与代表性内容。
    数据源：dashboard_gen/basin_data.json（构建期已按流域聚合）。basin 为空时返回两流域概览。"""
    try:
        if not os.path.exists(_BASIN_JSON):
            return {'error': '流域数据文件不存在'}
        with open(_BASIN_JSON, 'r', encoding='utf-8') as f:
            d = json.load(f)
        basins = d.get('basins') or {}
        targets = [basin] if basin else list(basins.keys())
        out = {}
        for b in targets:
            v = basins.get(b)
            if not v:
                out[b] = {'error': '无此流域数据'}
                continue
            tops = []
            for t in (v.get('topArticles') or [])[:limit]:
                if isinstance(t, dict):
                    tops.append({'内容摘要': (t.get('text') or '')[:80],
                                 '作者': t.get('author'), '议题': t.get('topic'),
                                 '省份': t.get('prov'), '时间': t.get('time'),
                                 '点赞': t.get('like')})
            out[b] = {
                '事件簇': (v.get('clusterNames') or [])[:limit],
                '热词Top': [w for w, _ in (v.get('hotwords') or [])[:limit]],
                '议题分布': [{'议题': k, '条数': n} for k, n in (v.get('topicDist') or [])],
                '情感分布': [{'情感': k, '条数': n} for k, n in (v.get('sent') or [])],
                '代表内容': tops,
            }
        return out if not basin else out.get(basin, {})
    except Exception as e:
        print("读取流域热点失败：", e)
        return {'error': str(e)}


# ===== LITE 海外模式：数据库不可用时，从 lite_data.json 读取静态数据 =====
import os as _lite_os

if _lite_os.getenv('LITE_MODE') == '1':
    import json as _lite_json
    _lite_path = _lite_os.path.join(
        _lite_os.path.dirname(_lite_os.path.dirname(_lite_os.path.abspath(__file__))),
        'lite_data.json')
    _lite_data = {}
    try:
        with open(_lite_path, 'r', encoding='utf-8') as _f:
            _lite_data = _lite_json.load(_f)
    except Exception:
        _lite_data = {}

    def _lite_get(key):
        def _inner(*a, **kw):
            return _lite_data.get(key, [])
        return _inner

    getTotalArticle = _lite_get('getTotalArticle')
    getTopAuthor = _lite_get('getTopAuthor')
    getTopRegion = _lite_get('getTopRegion')
    getArticleTopZan = _lite_get('getArticleTopZan')
    get7DayArticle = _lite_get('get7DayArticle')
    getArticleTypeAmount = _lite_get('getArticleTypeAmount')
    getTopCommentUser = _lite_get('getTopCommentUser')
    getAllArticle = lambda: _lite_data.get('articles', [])[:100]
