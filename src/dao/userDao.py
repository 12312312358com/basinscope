"""
    用户数据访问对象
"""
from entity.UserModel import User
from util import dbUtil


def login(user: User):
    """
    登录判断
    :param user:
    :return:
    """
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        # 只修复SQL注入，方法名/逻辑完全不变
        sql = "SELECT * FROM t_user WHERE username=%s and password=%s"
        cursor.execute(sql, (user.username, user.password))
        return cursor.fetchone()
    except Exception as e:
        print(e)
        con.rollback()
        return None
    finally:
        dbUtil.closeCon(con)


def add(user: User):
    """
    用户注册添加
    :param user:
    :return:
    """
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        # 修复注入 + 增加 commit（必须！）
        sql = "insert into t_user values(null,%s,%s,%s)"
        cursor.execute(sql, (user.username, user.password, user.createtime))
        con.commit()
        return cursor.rowcount
    except Exception as e:
        print(e)
        con.rollback()
        return None
    finally:
        dbUtil.closeCon(con)


def getByUserName(username):
    """
    根据用户名查询用户信息
    :param username:
    :return:
    """
    con = None
    try:
        con = dbUtil.getCon()
        cursor = con.cursor()
        sql = "SELECT * FROM t_user WHERE username=%s"
        cursor.execute(sql, (username,))
        return cursor.fetchall()
    except Exception as e:
        print(e)
        con.rollback()
        return None
    finally:
        dbUtil.closeCon(con)