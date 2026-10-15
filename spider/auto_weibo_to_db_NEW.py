# -*- coding: utf-8 -*-
import time
import os
import re
import getpass
import random
import json
import subprocess
import urllib.parse
import logging
import hashlib  # 新增：用于ID哈希脱敏
from datetime import datetime, timedelta
from DrissionPage import ChromiumPage, ChromiumOptions
import pandas as pd
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
import sys
import openpyxl  # 用于读取Excel配置

sys.stdout.reconfigure(encoding='utf-8')  # 重要！强制控制台用UTF-8编码


# ================= 1. 自动化任务配置区 =================
def load_config():
    """
    所有爬虫控制参数均在此处直接硬编码。
    如需调整爬取数量，请直接修改下方字典中的数字。
    """
    return {
        'article_pages': 6,  # 每个热搜词爬取的文章页数 (建议 2~5)
        'comment_limit': 5,  # 方案3核心：按评论数排序后，选出前 N 条爆款微博
        'comment_pages': 5  # 对选出的每条爆款微博，抓取前 N 页评论
    }


# ================= 2. 数据库与日志配置  =================
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = "db_weibo_basin"

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}?charset=utf8mb4"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_pre_ping=True,
    pool_recycle=1800
)


@event.listens_for(engine, "connect")
def set_charset(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET NAMES utf8mb4")
    cursor.close()


logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_spider.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


# ================= 3. 核心：智能接管 Edge =================
def take_over_real_edge():
    # ============ 修改点：固定 Edge 路径 ============
    edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    if not os.path.exists(edge_path):
        logging.error(f"找不到 Edge 浏览器: {edge_path}")
        return None
    # =====================================================

    username = getpass.getuser()
    # ============ 修改点：改用「独立调试 profile」 ============
    # 原写法用 Edge 默认 User Data 目录，有两个致命问题：
    #   1) 不设 user_data_path 时，DrissionPage 会去 TEMP 下建临时 userData 目录。
    #      本机 TEMP/TMP 被指到 C:\Windows\TEMP 且当前账号无写权限，
    #      会抛 [WinError 5] 拒绝访问，导致接管失败。
    #   2) Edge 136+ 在「默认 User Data 目录」下会直接忽略 --remote-debugging-port，
    #      9222 端口根本不会监听（本机 Edge 153，必然踩中）。
    # 换成独立目录后两个问题同时消失，且不影响你自己日常使用的 Edge。
    user_data_dir = fr"C:\Users\{username}\AppData\Local\DrissionEdgeProfile"
    os.makedirs(user_data_dir, exist_ok=True)
    # ==========================================================
    debug_port = 9222
    co = ChromiumOptions()
    co.set_local_port(debug_port)
    co.set_browser_path(edge_path)
    co.set_user_data_path(user_data_dir)  # 关键：钉死可写的 profile 目录

    try:
        page = ChromiumPage(co)
        logging.info("Edge 调试实例已就绪（独立 profile），接管成功！")
        return page
    except Exception:
        pass

    logging.info("正在自动启动 Edge 浏览器...")
    try:
        subprocess.run('taskkill /F /IM msedge.exe >nul 2>&1', shell=True)
        time.sleep(1.5)
    except:
        pass

    start_cmd = f'"{edge_path}" --remote-debugging-port={debug_port} --user-data-dir="{user_data_dir}"'
    subprocess.Popen(start_cmd, shell=True)
    time.sleep(4)

    try:
        page = ChromiumPage(co)
        logging.info("成功接管 Edge 浏览器！")
        return page
    except Exception as e:
        logging.error(f"接管失败: {e}")
        return None


# ================= 4. 浏览器硬解热搜榜 =================
def get_hot_search_keywords(page, top_n=35):
    """
    获取微博实时热搜榜。
    核心策略：直接用真实浏览器打开“热搜榜H5页面”，
    利用 DrissionPage 的 DOM 解析能力，直接把页面上的热搜词“抠”下来！
    """
    print("\n" + "=" * 50)
    print(" 正在获取微博实时热搜榜...")
    print("=" * 50)

    hot_url = "https://s.weibo.com/top/summary"

    try:
        page.get(hot_url)
        page.wait.doc_loaded(timeout=10)
        time.sleep(1.5)

        if "login" in page.url or "passport" in page.url:
            raise ValueError("检测到未登录！请在 Edge 浏览器中手动登录微博后重试。")

        elements = page.eles('css:td.td-02 a')

        keywords = []
        for el in elements:
            word = el.text.strip()
            if word and word not in keywords:
                keywords.append(word)
            if len(keywords) >= top_n:
                break

        if not keywords:
            print(" 主选择器未匹配到数据，尝试备用 JS 提取...")
            js_code = """
            var words = [];
            document.querySelectorAll('.td-02 a, .hot-list a, .list-a a').forEach(el => {
                if(el.innerText.trim()) words.push(el.innerText.trim());
            });
            return words;
            """
            keywords = page.run_js(js_code)[:top_n]

        if not keywords:
            raise ValueError("页面已打开，但未找到任何热搜词元素。")

        print(f"\n  成功获取微博热搜 Top {len(keywords)}：")
        print("-" * 50)
        for i, kw in enumerate(keywords, 1):
            print(f"  {i:>2}. {kw}")
        print("-" * 50)

        logging.info(f"浏览器硬解模式成功获取热搜关键词 {len(keywords)} 个")
        return keywords

    except Exception as e:
        logging.error(f"获取热搜完全失败: {e}")
        print(f" 获取热搜失败: {e}")
        print(" 提示：请确保你的 Edge 浏览器已经登录了微博账号！")
        return []


# ================= 5. 时间与数据清洗函数 =================
def format_article_time(created_at):
    if not created_at:
        return ""
    now = datetime.now()
    try:
        if created_at == "刚刚":
            return now.strftime("%Y-%m-%d %H:%M:%S")
        if "分钟前" in created_at:
            return (now - timedelta(minutes=int(re.search(r'\d+', created_at).group()))).strftime("%Y-%m-%d %H:%M:%S")
        if "小时前" in created_at:
            return (now - timedelta(hours=int(re.search(r'\d+', created_at).group()))).strftime("%Y-%m-%d %H:%M:%S")
        if created_at.startswith("今天"):
            return now.replace(hour=int(created_at[3:5]), minute=int(created_at[6:8]), second=0).strftime(
                "%Y-%m-%d %H:%M:%S")
        if created_at.startswith("昨天"):
            return (now - timedelta(days=1)).replace(hour=int(created_at[3:5]), minute=int(created_at[6:8]),
                                                     second=0).strftime("%Y-%m-%d %H:%M:%S")
        if re.match(r'^\d{2}-\d{2}$', created_at):
            return f"{now.year}-{created_at} 00:00:00"
        if re.match(r'^\d{4}-\d{2}-\d{2}$', created_at):
            return f"{created_at} 00:00:00"
        if "+" in created_at and len(created_at) > 20:
            return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d %H:%M:%S")
    except:
        pass
    return created_at


def format_comment_time(created_at):
    if not created_at:
        return ""
    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return created_at


def clean_text(text):
    if not isinstance(text, str):
        return str(text) if text is not None else ''
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    try:
        text.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError:
        text = text.encode('utf-8', 'ignore').decode('utf-8')
    return text


def safe_int(value):
    if value is None or value == '':
        return 0
    try:
        return int(str(value).replace(',', ''))
    except:
        return 0


# ================= 6. 数据脱敏模块 (PIPL合规) =================
SALT = "weibo_spider_2026_secret_salt"  # 保证同一用户哈希结果一致


def hash_id(user_id):
    """对用户ID进行加盐SHA256哈希（不可逆，但能保持同一用户ID的一致性）"""
    if not user_id or str(user_id).strip() == '':
        return 'unknown'
    raw = f"{SALT}_{str(user_id)}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]  # 取前16位足够区分


def mask_nickname(nickname):
    """昵称掩码：保留首尾，中间用*代替"""
    if not nickname or len(nickname) <= 1:
        return "匿名用户"
    if len(nickname) == 2:
        return nickname[0] + "*"
    return nickname[0] + "*" * (len(nickname) - 2) + nickname[-1]


def mask_region(region):
    """地区模糊化：只保留省份，去除具体城市（如 '广东 广州' -> '广东'）

    修复记录（2026-09-21）：
      微博接口返回的 region_name 形如「发布于 广东」。原实现直接 split() 取
      parts[0]，拿到的是前缀「发布于」而不是省份，省份被整段丢弃。
      实测某一轮入库的 2001 条中，1640 条因此被写成「发布于」、361 条「未知」，
      真实省份 0 条 —— 这也是 IP 地图上多省显示为 0 的上游原因。
      现在先剔除「发布于」前缀，再取首段。
    """
    if not region:
        return '未知'
    s = str(region).replace('发布于', '').strip()
    if not s or s == '未知':
        return '未知'
    parts = s.split()
    if not parts:
        return '未知'
    prov = parts[0].strip()
    # 兜底：拿到的不是省份（如 'chinadaily' 之类的来源串）
    if not prov or len(prov) > 6:
        return '未知'
    return prov


def mask_pii_text(text):
    """文本脱敏：正则过滤手机号、身份证号、邮箱、微信号"""
    if not isinstance(text, str):
        return str(text) if text else ''

    # 1. 过滤手机号 (13x, 14x, 15x, 17x, 18x, 19x)
    text = re.sub(r'1[3-9]\d{9}', '[手机号已过滤]', text)
    # 2. 过滤身份证号 (18位)
    text = re.sub(r'\b\d{17}[\dXx]\b', '[身份证已过滤]', text)
    # 3. 过滤邮箱
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[邮箱已过滤]', text)
    # 4. 过滤常见微信号/QQ号 (如 v: 12345, qq 12345)
    text = re.sub(r'(?:v|vx|wechat|qq|扣扣)\s*[:：]?\s*\d{5,11}', '[社交账号已过滤]', text, flags=re.IGNORECASE)

    return text


# ====================================================================


# ================= 7. 入库逻辑 (批量+临时表合并) =================
def save_to_db(articles, comments):
    print("\n" + "=" * 50)
    print("开始数据持久化到数据库 ")
    print("=" * 50)
    art_count, com_count = 0, 0

    current_dir = os.path.dirname(os.path.abspath(__file__))
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    if articles:
        try:
            clean_arts = []
            for a in articles:
                clean_arts.append({
                    '微博ID': clean_text(a['微博ID']),
                    '微博内容': clean_text(a['微博内容']),
                    '转发数': safe_int(a['转发数']),
                    '评论数': safe_int(a['评论数']),
                    '点赞数': safe_int(a['点赞数']),
                    '发布地区': clean_text(a['发布地区']),
                    '发布时间': clean_text(a['发布时间']),
                    '分类': clean_text(a['分类']),
                    '微博链接': clean_text(a['微博链接']),
                    '作者ID': clean_text(a['作者ID']),
                    '作者昵称': clean_text(a['作者昵称']),
                    '作者主页': clean_text(a['作者主页'])
                })
            df_art = pd.DataFrame(clean_arts)
            df_art['微博ID'] = df_art['微博ID'].astype(str)
            df_art['作者ID'] = df_art['作者ID'].astype(str)

            csv_art_path = os.path.join(current_dir, f'articles_{time_str}.csv')
            df_art.to_csv(csv_art_path, index=False, encoding='utf-8-sig')
            print(f" 文章数据已保存至 CSV: {csv_art_path}")
            fixed_art_path = os.path.join(current_dir, 'article_data.csv')
            df_art.to_csv(fixed_art_path, index=False, encoding='utf-8-sig')

            with engine.connect() as conn:
                df_art.to_sql('t_article_temp', con=conn, if_exists='replace', index=False, chunksize=1000)
                sql_art = text("""
                    INSERT INTO t_article (`微博ID`, `微博内容`, `转发数`, `评论数`, `点赞数`, `发布地区`, `发布时间`, `分类`, `微博链接`, `作者ID`, `作者昵称`, `作者主页`)
                    SELECT `微博ID`, `微博内容`, `转发数`, `评论数`, `点赞数`, `发布地区`, `发布时间`, `分类`, `微博链接`, `作者ID`, `作者昵称`, `作者主页`
                    FROM t_article_temp
                    ON DUPLICATE KEY UPDATE
                        `转发数`=VALUES(`转发数`),
                        `评论数`=VALUES(`评论数`),
                        `点赞数`=VALUES(`点赞数`)
                """)
                result = conn.execute(sql_art)
                conn.commit()
                conn.execute(text("DROP TABLE IF EXISTS t_article_temp"))
                art_count = len(df_art)
                print(f" 微博数据入库完成：处理了 {art_count} 条文章")
        except Exception as e:
            logging.error(f" 文章批量入库失败: {e}")
            print(f" 文章批量入库失败: {e}")

    if comments:
        try:
            clean_coms = []
            for c in comments:
                clean_coms.append({
                    '评论ID': clean_text(c['评论ID']),
                    '评论内容': clean_text(c['评论内容']),
                    '评论时间': clean_text(c['评论时间']),
                    '来源': clean_text(c['来源']),
                    '点赞数': safe_int(c['点赞数']),
                    '微博ID': clean_text(c['微博ID']),
                    '用户ID': clean_text(c['用户ID']),
                    '昵称': clean_text(c['昵称']),
                    '性别': clean_text(c['性别']),
                    '用户主页': clean_text(c['用户主页'])
                })
            df_com = pd.DataFrame(clean_coms)
            df_com['评论ID'] = df_com['评论ID'].astype(str)
            df_com['微博ID'] = df_com['微博ID'].astype(str)
            df_com['用户ID'] = df_com['用户ID'].astype(str)

            csv_com_path = os.path.join(current_dir, f'comments_{time_str}.csv')
            df_com.to_csv(csv_com_path, index=False, encoding='utf-8-sig')
            print(f" 评论数据已保存至 CSV: {csv_com_path}")
            fixed_com_path = os.path.join(current_dir, 'comment_data.csv')
            df_com.to_csv(fixed_com_path, index=False, encoding='utf-8-sig')

            with engine.connect() as conn:
                df_com.to_sql('t_comment_temp', con=conn, if_exists='replace', index=False, chunksize=1000)
                sql_com = text("""
                    INSERT INTO t_comment (`评论ID`, `评论内容`, `评论时间`, `来源`, `点赞数`, `微博ID`, `用户ID`, `昵称`, `性别`, `用户主页`)
                    SELECT `评论ID`, `评论内容`, `评论时间`, `来源`, `点赞数`, `微博ID`, `用户ID`, `昵称`, `性别`, `用户主页`
                    FROM t_comment_temp
                    ON DUPLICATE KEY UPDATE
                        `点赞数`=VALUES(`点赞数`)
                """)
                result = conn.execute(sql_com)
                conn.commit()
                conn.execute(text("DROP TABLE IF EXISTS t_comment_temp"))
                com_count = len(df_com)
                print(f" 评论数据入库完成：处理了 {com_count} 条评论")
        except Exception as e:
            logging.error(f" 评论批量入库失败: {e}")
            print(f" 评论批量入库失败: {e}")

    print(f"\n 数据持久化完成！共处理 {art_count} 条微博，{com_count} 条评论")


# ================= 8. 主执行流程（ 改为热搜驱动） =================
def main_job():
    # ---------- 读取配置 ----------
    config = load_config()

    pages = config.get('article_pages', 3)  # 每个关键词爬几页文章
    comment_limit = config.get('comment_limit', 5)  # 对前几条文章抓评论
    comment_pages = config.get('comment_pages', 2)  # 每篇文章抓几页评论

    # ---------- ★ 核心改动：热搜关键词数量，默认35 ----------
    hot_search_top_n = config.get('hot_search_top_n', 35)  # 可在配置文件里覆盖

    # ---------- 启动浏览器 ----------
    page = take_over_real_edge()
    if not page:
        print(" 浏览器启动/接管失败，程序退出。")
        return

    # ----------  获取微博热搜前 N 作为关键词 ----------
    keywords = get_hot_search_keywords(page, top_n=hot_search_top_n)

    if not keywords:
        print(" 未能获取到热搜关键词，程序退出。")
        subprocess.run('taskkill /F /IM msedge.exe >nul 2>&1', shell=True)
        return

    print("\n" + "=" * 50)
    print(f" 本次将从热搜 Top {len(keywords)} 中爬取文章和评论")
    print(f"   每个关键词爬 {pages} 页文章")
    print(f"   对前 {comment_limit} 篇文章各抓 {comment_pages} 页评论")
    print("=" * 50 + "\n")

    logging.info(f" 热搜任务启动，本次将爬取 {len(keywords)} 个热搜关键词...")

    # 先访问移动端微博，为后续 API 请求做准备
    page.get("https://m.weibo.cn")
    time.sleep(2)

    all_articles = []
    all_comments = []

    # ================= 1. 爬取文章 =================
    for idx, keyword in enumerate(keywords, 1):
        logging.info(f" [{idx}/{len(keywords)}] 正在自动爬取热搜关键词：【{keyword}】")
        print(f"\n [{idx}/{len(keywords)}] 正在爬取热搜：【{keyword}】")

        sleep_time = random.uniform(3, 8)
        print(f"   随机休眠 {sleep_time:.2f} 秒以避免触发反爬...")
        time.sleep(sleep_time)

        for p in range(1, pages + 1):
            containerid = f"100103type=1&q={keyword}"
            api_url = f"https://m.weibo.cn/api/container/getIndex?containerid={urllib.parse.quote(containerid)}&page_type=searchall&page={p}"
            page.get(api_url)
            time.sleep(2)
            try:
                html_body = page.run_js("return document.body.innerText")
                if "滑动" in html_body or "验证" in html_body or "为了你的账号安全" in html_body:
                    print(f" 检测到滑动验证码！程序已暂停。请手动去浏览器完成验证，然后按回车键继续...")
                    input()
                    page.get(api_url)
                    time.sleep(3)
                data = json.loads(page.run_js("return document.body.innerText"))
                if data.get('ok') != 1:
                    print(f"    关键词【{keyword}】第{p}页无数据(ok={data.get('ok')})，跳过")
                    break
                page_count = 0
                for card in data.get('data', {}).get('cards', []):
                    mblogs = [card.get('mblog')] if card.get('card_type') == 9 else [sub.get('mblog') for sub in
                                                                                     card.get('card_group', []) if
                                                                                     sub.get('card_type') == 9]
                    for mblog in mblogs:
                        if not mblog:
                            continue
                        user = mblog.get('user', {})

                        # ▼▼▼ 修改这里：应用脱敏函数 ▼▼▼
                        all_articles.append({
                            '微博ID': str(mblog.get('id', '')),
                            '微博内容': mask_pii_text(
                                re.sub(r'<[^>]+>', '', mblog.get('text', '')).strip().replace('\n', ' ')),
                            '转发数': str(mblog.get('reposts_count', 0)),
                            '评论数': str(mblog.get('comments_count', 0)),
                            '点赞数': str(mblog.get('attitudes_count', 0)),
                            '发布地区': mask_region(mblog.get('region_name', '未知')),  # 地区模糊化
                            '发布时间': format_article_time(mblog.get('created_at', '')),
                            '分类': mblog.get('source', '未知'),
                            '微博链接': f"https://weibo.com/status/{mblog.get('id', '')}",
                            '作者ID': hash_id(user.get('id', '')),  # ID 哈希化
                            '作者昵称': mask_nickname(user.get('screen_name', '未知')),  # 昵称掩码
                            '作者主页': '已脱敏'  # 切断主页链接
                        })
                        page_count += 1
                print(f"   第{p}页获取到 {page_count} 条微博")
            except Exception as e:
                logging.error(f"文章 关键词【{keyword}】第{p}页解析失败: {e}")
                print(f"    第{p}页解析失败: {e}")

    print(f"\n 文章爬取完毕，共获取 {len(all_articles)} 条微博")

    # ================= 2. 爬取评论  =================
    print("\n 正在对爬取到的微博按【评论数】进行智能排序...")

    # 按评论数降序排序，优先抓取互动量最高、最热门的微博
    all_articles.sort(key=lambda x: safe_int(x['评论数']), reverse=True)

    # 选出排序后前 comment_limit 条高互动微博
    top_articles = all_articles[:comment_limit]
    weibo_ids = [a['微博ID'] for a in top_articles]

    # 在控制台直观展示选中的评论数较多的微博
    print(f" 已智能选出评论数最高的 {len(weibo_ids)} 条微博进行评论抓取：")
    print("-" * 60)
    for i, art in enumerate(top_articles, 1):
        # 截取前30个字符展示，避免控制台刷屏
        content_preview = art['微博内容'][:30].replace('\n', ' ') + ('...' if len(art['微博内容']) > 30 else '')
        print(f"   {i}. [评论数:{art['评论数']:<6}] {content_preview}")
        print(f"      链接: {art['微博链接']}")
    print("-" * 60)

    for weibo_id in weibo_ids:
        detail_url = f"https://weibo.com/detail/{weibo_id}"
        max_id = 0

        for p in range(1, comment_pages + 1):
            print(f"  正在爬取微博 {weibo_id} 的第 {p} 页评论...")
            try:
                if p == 1:
                    page.listen.start('buildComments')
                    page.get(detail_url)
                    packet = page.listen.wait(timeout=15)
                    page.listen.stop()
                    data = packet.response.body if packet else None

                    if isinstance(data, str):
                        data = json.loads(data)
                else:
                    api_url = f"https://weibo.com/ajax/statuses/buildComments?id={weibo_id}&count=20&max_id={str(max_id)}"

                    js_code = f"""
                    return fetch('{api_url}', {{
                        method: 'GET',
                        credentials: 'include',
                        headers: {{
                            'Accept': 'application/json, text/plain, */*',
                            'X-Requested-With': 'XMLHttpRequest',
                            'Referer': 'https://weibo.com/detail/{weibo_id}',
                            'User-Agent': navigator.userAgent
                        }}
                    }}).then(r => r.text()).catch(e => '');
                    """
                    json_str = page.run_js(js_code)

                    if not json_str or not json_str.strip().startswith('{'):
                        print(f"  第{p}页请求被微博拦截(返回空或非JSON)，停止当前微博翻页: {weibo_id}")
                        logging.warning(f" 第{p}页请求被微博拦截，停止当前微博翻页: {weibo_id}")
                        break

                    data = json.loads(json_str)

                if not data or not data.get('data'):
                    break

                max_id = data.get('max_id') or data.get('max_id_str') or 0

                for comment in data['data']:
                    user_info = comment.get('user', {}) or {}

                    all_comments.append({
                        '评论ID': str(comment.get('id', '')),
                        '评论内容': mask_pii_text(comment.get('text_raw', '').replace('\n', ' ').strip()),
                        '评论时间': format_comment_time(comment.get('created_at', '')),
                        '来源': comment.get('source', ''),
                        '点赞数': str(comment.get('like_counts', 0)),
                        '微博ID': weibo_id,
                        '用户ID': hash_id(user_info.get('id', '')),  # ID 哈希化
                        '昵称': mask_nickname(user_info.get('screen_name', '')),  # 昵称掩码
                        '性别': user_info.get('gender', ''),
                        '用户主页': '已脱敏'  # 切断主页链接
                    })

                if max_id == 0:
                    break
                time.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                print(f"  评论爬取异常 (微博:{weibo_id} 第{p}页): {e}")
                logging.error(f"评论爬取异常 (微博:{weibo_id} 第{p}页): {e}")
                break

    print(f" 评论爬取完毕，共获取 {len(all_comments)} 条评论")

    # ================= 3. 数据入库 =================
    save_to_db(all_articles, all_comments)

    # 关闭浏览器
    subprocess.run('taskkill /F /IM msedge.exe >nul 2>&1', shell=True)
    logging.info(" 所有热搜关键词爬取完毕，浏览器已关闭。\n")
    print("\n 全部任务完成！")


if __name__ == "__main__":
    main_job()
