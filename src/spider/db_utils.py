from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

# 完全匹配你的数据库配置
engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:3306/{os.getenv('DB_NAME')}?charset=utf8mb4"
)


def save_articles_to_db(article_list):
    """增量保存微博数据到t_article表"""
    if not article_list:
        return 0

    conn = engine.connect()
    count = 0

    for row in article_list:
        sql = text("""
        INSERT INTO t_article 
        (id, text, reposts_count, comments_count, attitudes, region_name, created_at, 
         articleType, articleUrl, authorId, authorName, authorHomeUrl)
        VALUES (:id, :text, :reposts_count, :comments_count, :attitudes, :region_name, :created_at,
                :articleType, :articleUrl, :authorId, :authorName, :authorHomeUrl)
        ON DUPLICATE KEY UPDATE
        reposts_count=VALUES(reposts_count),
        comments_count=VALUES(comments_count),
        attitudes=VALUES(attitudes),
        region_name=VALUES(region_name)
        """)

        try:
            conn.execute(sql, row)
            count += 1
        except Exception as e:
            continue

    conn.commit()
    conn.close()
    return count


def save_comments_to_db(comment_list):
    """增量保存评论数据到t_comment表"""
    if not comment_list:
        return 0

    conn = engine.connect()
    count = 0

    for row in comment_list:
        sql = text("""
        INSERT INTO t_comment 
        (id, text, created_at, source, like_counts, articleId, userId, userName, userHomeUrl)
        VALUES (:id, :text, :created_at, :source, :like_counts, :articleId, :userId, :userName, :userHomeUrl)
        ON DUPLICATE KEY UPDATE
        like_counts=VALUES(like_counts)
        """)

        try:
            conn.execute(sql, row)
            count += 1
        except Exception as e:
            continue

    conn.commit()
    conn.close()
    return count