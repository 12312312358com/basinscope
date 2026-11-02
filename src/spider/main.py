"""
爬数据，持久化到数据库 主函数（最终版，自动建表）
"""
import os
import pandas as pd
from sqlalchemy import create_engine

# 数据库连接
engine = create_engine('mysql+pymysql://%s:%s@%s:%s/%s?charset=utf8mb4' % (os.getenv('DB_USER', 'root'), os.getenv('DB_PASSWORD', ''), os.getenv('DB_HOST', 'localhost'), os.getenv('DB_PORT', '3306'), os.getenv('DB_NAME', 'db_weibo_basin')))

def saveToDb():
    try:
        # 1. 导入 article_data.csv → t_article 表
        article_df = pd.read_csv('article_data.csv')
        article_df.to_sql('t_article', con=engine, if_exists='replace', index=False)
        print(f" 已成功导入 {len(article_df)} 条微博数据到 t_article")

        # 2. 导入 comment_data.csv → t_comment 表
        comment_df = pd.read_csv('comment_data.csv')
        comment_df.to_sql('t_comment', con=engine, if_exists='replace', index=False)
        print(f" 已成功导入 {len(comment_df)} 条评论数据到 t_comment")

        print("\n 所有数据已成功保存到数据库！")

    except Exception as e:
        print(f" 入库失败：{e}")

if __name__ == '__main__':
    print("数据持久化到数据库开始...")
    saveToDb()
    print("数据持久化到数据库结束！")

