"""
    数据库连接工具（配置外部化：从 .env 读取，未配置时回退本地默认值）
"""
import os
try:
    from pymysql import Connection
except ImportError:
    Connection = None

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "db_weibo_basin")


def getCon():
    """获取数据连接（带连接/读写超时，避免卡死）"""
    con = Connection(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )
    return con


def closeCon(con: Connection):
    if con:
        con.close()
