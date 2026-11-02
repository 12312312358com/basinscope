"""
微博评论信息 数据访问对象 (已修复图表时间轴排序问题)
"""
from util import dbUtil

# ===================== 平台 / 流域 路由（参赛改造：对话按专题隔离） =====================
_CMT_TABLES = {
    '微博':   {'tbl': 't_basin_comment',  'txt': '评论内容', 'like': '点赞数', 'nick': '昵称'},
    '小红书': {'tbl': 't_xhs_comment',    'txt': '评论内容', 'like': '点赞数', 'nick': '昵称'},
    '知乎':   {'tbl': 't_zhihu_comment',  'txt': '评论内容', 'like': '点赞数', 'nick': '昵称'},
    '抖音':   {'tbl': 't_douyin_comment', 'txt': '评论内容', 'like': '点赞数', 'nick': '昵称'},
}
_DEFAULT_PLATFORM = '微博'


def _cmt(platform=None, basin=None):
    """评论表上下文：微博 + 无流域 → t_comment（旧行为）；否则走流域/平台评论表。"""
    platform = platform or _DEFAULT_PLATFORM
    if platform == '微博' and not basin:
        return {'tbl': 't_comment', 'txt': '评论内容', 'like': '点赞数',
                'nick': '昵称', 'bcol': None}
    cfg = dict(_CMT_TABLES.get(platform, _CMT_TABLES[_DEFAULT_PLATFORM]))
    cfg['bcol'] = '流域'
    return cfg


def getAllComment(limit=200, platform=None, basin=None):
    """
    查询评论信息（默认最多 200 条，供 AI 报告上下文/页面展示用）
    limit=None 表示不限条数，用于统计类页面（如 IP 地图）
    可按平台 / 流域过滤。
    """
    c = _cmt(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = "SELECT * FROM `%s` WHERE `%s`=%%s AND `%s`!='' ORDER BY 评论时间 DESC" % (
                c['tbl'], c['bcol'], c['txt'])
            params = [basin]
        else:
            sql = "SELECT * FROM `%s` WHERE `%s`!='' ORDER BY 评论时间 DESC" % (c['tbl'], c['txt'])
            params = []
        if limit:
            sql += " LIMIT %d" % int(limit)
        if params:
            cursor.execute(sql, tuple(params))
        else:
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print(e)
        return []
    finally:
        dbUtil.closeCon(con)


def getAllArticle():
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        sql = "SELECT * FROM t_article ORDER BY 发布时间 DESC LIMIT 200"
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print(e)
        return []
    finally:
        dbUtil.closeCon(con)


def getTopCommentUser(platform=None, basin=None):
    """高频评论用户 Top50（可按平台 / 流域过滤）"""
    c = _cmt(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = ("SELECT `%s`, COUNT(`%s`) AS unCount FROM `%s` WHERE `%s`=%%s "
                   "GROUP BY `%s` ORDER BY unCount DESC LIMIT 0, 50") % (
                c['nick'], c['nick'], c['tbl'], c['bcol'], c['nick'])
            cursor.execute(sql, (basin,))
        else:
            sql = ("SELECT `%s`, COUNT(`%s`) AS unCount FROM `%s` "
                   "GROUP BY `%s` ORDER BY unCount DESC LIMIT 0, 50") % (
                c['nick'], c['nick'], c['tbl'], c['nick'])
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print(e)
        return []
    finally:
        dbUtil.closeCon(con)


# ================= 核心修复区域 =================

def getCommentAmount(platform=None, basin=None):
    """获取总体评论的日期分布（最近7天，时间升序；可按平台 / 流域过滤）"""
    c = _cmt(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        use_b = bool(basin and c.get('bcol'))
        # 【修复】带参查询时 % 需转义为 %%，否则 pymysql 会把它当占位符
        fmt = '%%Y-%%m-%%d' if use_b else '%Y-%m-%d'
        wf = f"WHERE `{c['bcol']}`=%s" if use_b else ''
        sql = f"""
            SELECT commentDate, commentTotal FROM (
                SELECT DATE_FORMAT(评论时间,'{fmt}') AS commentDate, COUNT(*) AS commentTotal
                FROM `{c['tbl']}` {wf}
                GROUP BY commentDate
                ORDER BY commentDate DESC
                LIMIT 7
            ) AS temp
            ORDER BY commentDate ASC
        """
        if use_b:
            cursor.execute(sql, (basin,))
        else:
            cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print("getCommentAmount 报错:", e)
        return []
    finally:
        dbUtil.closeCon(con)


def getCommentTotal(platform=None, basin=None):
    """评论**总条数**（COUNT(*)）。
    ⚠ 与 getCommentAmount 区分：后者虽名为"数量"，实际返回「近 7 天每日条数」列表；
    需要"评论总数"（概览/报告）时应调用本函数，否则 len() 得到的是"天数"而非"条数"。
    可按平台 / 流域过滤。"""
    c = _cmt(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        if basin and c.get('bcol'):
            sql = "SELECT COUNT(*) FROM `%s` WHERE `%s`=%%s" % (c['tbl'], c['bcol'])
            cursor.execute(sql, (basin,))
        else:
            sql = "SELECT COUNT(*) FROM `%s`" % c['tbl']
            cursor.execute(sql)
        res = cursor.fetchone()
        return int(res[0]) if res else 0
    except Exception as e:
        print("getCommentTotal 报错:", e)
        return 0
    finally:
        dbUtil.closeCon(con)


def getCommentHotWordAmount(hotword, platform=None, basin=None):
    """获取特定热词的日期分布（最近7天，时间升序；可按平台 / 流域过滤）"""
    c = _cmt(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()

        # 🔥 核心修复：% 一律转义为 %%，防止 pymysql 字符串格式化报错！
        conds = f"LOCATE(%s, `{c['txt']}`) > 0"
        params = [hotword]
        if basin and c.get('bcol'):
            conds += f" AND `{c['bcol']}`=%s"
            params.append(basin)
        sql = f"""
            SELECT commentDate, commentTotal FROM (
                SELECT DATE_FORMAT(评论时间,'%%Y-%%m-%%d') AS commentDate, COUNT(*) AS commentTotal
                FROM `{c['tbl']}`
                WHERE {conds}
                GROUP BY commentDate
                ORDER BY commentDate DESC
                LIMIT 7
            ) AS temp
            ORDER BY commentDate ASC
        """

        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    except Exception as e:
        print("🔥 getCommentHotWordAmount 报错:", e)
        return []
    finally:
        dbUtil.closeCon(con)

# ================================================


def getCommentByHotWord(hotword, platform=None, basin=None):
    """获取包含特定关键词的评论原文（可按平台 / 流域过滤）"""
    c = _cmt(platform, basin)
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        sql = f"SELECT * FROM `{c['tbl']}` WHERE LOCATE(%s, `{c['txt']}`) > 0"
        params = [hotword]
        if basin and c.get('bcol'):
            sql += f" AND `{c['bcol']}`=%s"
            params.append(basin)
        sql += " ORDER BY 评论时间 DESC LIMIT 100"
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    except Exception as e:
        print(e)
        return []
    finally:
        dbUtil.closeCon(con)


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

    def _lite_comments(*a, **kw):
        return _lite_data.get('comments', [])

    def _lite_comment_by_hotword(hotword):
        if not hotword:
            return []
        hw = str(hotword)
        return [c for c in _lite_data.get('comments', []) if isinstance(c, list) and len(c) > 1 and hw in str(c[1])]

    def _lite_comment_hotword_amount(hotword):
        matched = _lite_comment_by_hotword(hotword)
        date_map = {}
        for c in matched:
            d2 = str(c[2])[:10] if len(c) > 2 and c[2] else '未知'
            date_map[d2] = date_map.get(d2, 0) + 1
        items = sorted(date_map.items())
        return [[dd, nn] for dd, nn in items[-7:]]

    getAllComment = _lite_comments
    getCommentAmount = _lite_get('getCommentAmount')
    getTopCommentUser = _lite_get('getTopCommentUser')
    getCommentHotWordAmount = _lite_comment_hotword_amount
    getCommentByHotWord = _lite_comment_by_hotword
