# -*- coding: utf-8 -*-
"""作品库（db_weibo_basin）引擎获取。

优先复用项目现有引擎（spider/auto_weibo_to_db_NEW.py），
避免重复硬编码；回退时按项目默认值自建。连接参数可被环境变量覆盖。
"""
import os
import sys


def get_engine():
    """返回 sqlalchemy engine（指向 db_weibo_basin）。"""
    # 1) 优先复用项目现有引擎
    try:
        _spider = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'spider')
        if os.path.isdir(_spider):
            sys.path.insert(0, _spider)
            from auto_weibo_to_db_NEW import engine  # noqa: F401
            return engine
    except Exception:
        pass
    # 2) 回退：按项目默认值自建（与 auto_weibo_to_db_NEW.py 一致）
    from sqlalchemy import create_engine
    host = os.getenv('DB_HOST', 'localhost')
    user = os.getenv('DB_USER', 'root')
    pwd = os.getenv('DB_PASSWORD', '')
    name = os.getenv('DB_NAME', 'db_weibo_basin')
    url = f'mysql+pymysql://{user}:{pwd}@{host}:3306/{name}?charset=utf8mb4'
    return create_engine(url)

