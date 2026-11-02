# -*- coding: utf-8 -*-
import pandas as pd
import hashlib
import re
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import sys

sys.stdout.reconfigure(encoding='utf-8')

# ================= 1. 数据库连接配置 =================
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = "db_weibo_basin"
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}?charset=utf8mb4"

engine = create_engine(DATABASE_URL, poolclass=QueuePool, pool_pre_ping=True)


# ================= 2. 脱敏核心函数 =================
def hash_user_id(uid):
    if not uid or pd.isna(uid) or str(uid).strip() in ['', '未知', 'None']: return 'Unknown'
    return "UID_" + hashlib.sha256(str(uid).encode('utf-8')).hexdigest()[:8].upper()


def mask_nickname(name):
    if not name or pd.isna(name) or str(name).strip() in ['', '未知', 'None']: return '匿名网民'
    name = str(name)
    if len(name) <= 1: return name + "*"
    if len(name) == 2: return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def desensitize_text_content(text):
    if not isinstance(text, str) or pd.isna(text): return str(text) if text else ''
    text = re.sub(r'(?<!\d)(1[3-9]\d{9})(?!\d)', lambda m: m.group(1)[:3] + '****' + m.group(1)[7:], text)
    text = re.sub(r'(?<!\d)(\d{17}[\dXx])(?!\d)', lambda m: m.group(1)[:4] + '**********' + m.group(1)[-4:], text)
    text = re.sub(r'(?:V|v|微|信|wx|WX)\s*[:：]?\s*(1[3-9]\d{9})', '微信号: ****', text)
    return text


def desensitize_user_profile(url):
    if not url or pd.isna(url) or 'Unknown' in str(url): return '已脱敏'
    return '已脱敏(原链接已隐藏)'


# ================= 3. 核心执行逻辑 (★ 影子表安全模式) =================
def process_table_safely(original_table, safe_table, id_col, nick_col, content_col, profile_col):
    print(f"\n[START] 开始安全处理表: {original_table} ...")

    # 1. 读取原表数据 (原表毫发无损)
    try:
        df = pd.read_sql(f"SELECT * FROM {original_table}", engine)
        print(f"   [OK] 已读取 {len(df)} 条原始数据。(原表 {original_table} 未做任何修改)")
    except Exception as e:
        print(f"   [ERR] 读取失败: {e}")
        return

    if df.empty:
        print("   [WARN] 表为空，跳过。")
        return

    # 2. 在内存中执行脱敏转换
    print("   [WAIT] 正在内存中执行脱敏算法...")
    if id_col in df.columns: df[id_col] = df[id_col].astype(str).apply(hash_user_id)
    if nick_col in df.columns: df[nick_col] = df[nick_col].astype(str).apply(mask_nickname)
    if content_col in df.columns: df[content_col] = df[content_col].astype(str).apply(desensitize_text_content)
    if profile_col in df.columns: df[profile_col] = df[profile_col].astype(str).apply(desensitize_user_profile)

    # 3. 将脱敏后的数据写入【全新的安全影子表】
    print(f"   [SAFE] 正在将脱敏数据写入安全影子表: {safe_table} ...")
    with engine.connect() as conn:
        # 如果影子表已存在，先删除重建
        conn.execute(text(f"DROP TABLE IF EXISTS {safe_table}"))
        conn.commit()

        # 写入新表 (如果这里报错，原表依然安全！)
        df.to_sql(safe_table, con=conn, if_exists='append', index=False, chunksize=1000)

    print(f"   [DONE] 脱敏数据已安全写入 {safe_table}！")
    print(f"   [GO] 请打开 Navicat/数据库工具，检查 {safe_table} 表的数据是否符合预期。")


# ================= 4. 启动任务 =================
if __name__ == "__main__":
    print("=" * 60)
    print(" [SAFE] 微博历史数据库【绝对安全版】脱敏工具 (影子表模式)")
    print(" [WARN] 本脚本绝不会删除或清空您的原始数据表！")
    print("=" * 60)

    # 处理文章表 -> 生成 t_article_safe
    process_table_safely(
        original_table="t_article", safe_table="t_article_safe",
        id_col="作者ID", nick_col="作者昵称",
        content_col="微博内容", profile_col="作者主页"
    )

    # 处理评论表 -> 生成 t_comment_safe
    process_table_safely(
        original_table="t_comment", safe_table="t_comment_safe",
        id_col="用户ID", nick_col="昵称",
        content_col="评论内容", profile_col="用户主页"
    )

    print("\n" + "=" * 60)
    print(" [OK] 第一阶段完成！脱敏数据已存入 _safe 后缀的新表中。")
    print(" [PIN] 您的原表 (t_article, t_comment) 依然完好无损！")
    print(" [PIN] 请去数据库核对 _safe 表，确认无误后，再运行下方的【一键替换】代码。")
    print("=" * 60)
