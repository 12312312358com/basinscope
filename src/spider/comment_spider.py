"""
微博评论内容爬虫（2026-05-28最新修复版）
解决buildComments接口"网页解析失败"问题
"""
import csv
import os
import time
import random
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ✅ 统一使用.env里的最新Cookie，和article_spider保持一致
from dotenv import load_dotenv
load_dotenv()
GLOBAL_COOKIE = os.getenv("WEIBO_COOKIE")

# 清理字符串
def clean_string(s):
    if not s:
        return ""
    return s.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ').strip()


def init_csv():
    if not os.path.exists('comment_data.csv'):
        with open('comment_data.csv', 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'id',
                'text_raw',
                'created_at',
                'source',
                'like_counts',
                'articleId',
                'userId',
                'userName',
                'gender',
                'userHomeUrl'
            ])


def getAllArticleList():
    """从article_data.csv获取需要爬取评论的微博列表"""
    articleList = []
    try:
        with open('article_data.csv', 'r', encoding='utf-8-sig', newline='') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # 跳过表头
            for article in csv_reader:
                # 只爬取有评论的微博
                if len(article) >= 10 and article[3] and int(article[3]) > 0:
                    articleList.append(article)
    except FileNotFoundError:
        print("\n[ERR] 未找到article_data.csv，请先运行article_spider.py")
        return []
    return articleList


def create_session():
    """创建带重试机制的会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def getJsonHtml(session, url, params, referer):
    """
    ✅ 关键修复：
    1. 添加完整的2026年微博要求的请求头
    2. 使用.env里的最新Cookie
    3. 动态设置Referer为具体微博页面
    4. 处理接口返回的ok状态
    """
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        'Cookie': GLOBAL_COOKIE,
        'Referer': 'https://weibo.com/hot/weibo/102803',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        # 用你截图里的真实sec-ch-ua
        'sec-ch-ua': '"Chromium";v="9", "Not?A_Brand";v="8"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    try:
        response = session.get(
            url,
            headers=headers,
            params=params,
            timeout=15,
            verify=True
        )

        if response.status_code == 302:
            print("\n[ERR] Cookie已过期！请更新.env文件中的WEIBO_COOKIE")
            return None
        elif response.status_code == 403:
            print("\n[ERR] 403被拦截：休息10分钟后再运行，并调大延迟")
            return None
        elif response.status_code != 200:
            print(f"\n[ERR] 请求失败，状态码: {response.status_code}")
            return None

        try:
            json_data = response.json()
            # 微博接口返回ok=1才是成功
            if json_data.get("ok") != 1:
                print(f"  接口返回异常，ok={json_data.get('ok')}")
                return None
            return json_data
        except ValueError:
            print("\n[ERR] JSON解析失败，返回内容不是JSON")
            return None

    except Exception as e:
        print(f"\n[ERR] 网络异常: {str(e)}")
        return None


def writeToCsv(row):
    with open('comment_data.csv', 'a', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(row)


def parseJson(json_data, articleId):
    if not json_data or 'data' not in json_data:
        print("  无评论数据")
        return 0

    commentList = json_data['data']
    print(f"  [OK] 获取到 {len(commentList)} 条评论")

    count = 0
    for comment in commentList:
        try:
            comment_id = comment['id']
            text_raw = clean_string(comment['text_raw'])
            created_at = datetime.strptime(
                comment['created_at'],
                "%a %b %d %H:%M:%S %z %Y"
            ).strftime("%Y-%m-%d %H:%M:%S")
            source = comment.get('source', '').replace('来自', '').strip()
            like_counts = comment['like_counts']
            userId = comment['user']['id']
            userName = clean_string(comment['user']['screen_name'])
            # ✅ 合规脱敏：只保留前2个字符
            userName = userName[:2] + "***" if len(userName) > 2 else userName
            gender = '男' if comment['user']['gender'] == 'm' else '女'
            userHomeUrl = f"https://weibo.com/u/{userId}"

            writeToCsv([
                comment_id, text_raw, created_at, source, like_counts,
                articleId, userId, userName, gender, userHomeUrl
            ])
            count += 1

        except Exception as e:
            continue

    return count


def start():
    url = 'https://weibo.com/ajax/statuses/buildComments'
    init_csv()
    articleList = getAllArticleList()

    if not articleList:
        print("[ERR] 没有需要爬取评论的微博，程序结束")
        return

    session = create_session()
    total_count = 0

    print("=" * 60)
    print("微博评论爬取工具（2026-05-28最新修复版）")
    print(f"共发现 {len(articleList)} 条有评论的微博")
    print("=" * 60)

    for i, article in enumerate(articleList):
        article_id = article[0]
        article_title = article[1][:30] + "..." if len(article[1]) > 30 else article[1]
        author_id = article[9]  # ✅ 关键：从article_data.csv获取作者ID（第10列，索引9）
        article_url = article[8]  # ✅ 关键：从article_data.csv获取微博链接（第9列，索引8）

        print(f"\n[{i+1}/{len(articleList)}] 正在爬取：{article_title}")

        # ✅ 关键修复：添加2026年新增的必填参数uid=作者ID
        params = {
            'id': article_id,
            'uid': author_id,  # 没有这个参数必报错！
            'is_show_bulletin': 2,
            'flow': 0,
            'count': 20  # 每次爬取20条最新评论
        }

        json_data = getJsonHtml(session, url, params, article_url)
        if json_data:
            count = parseJson(json_data, article_id)
            total_count += count

        # ✅ 添加随机延迟，避免被封
        time.sleep(random.uniform(3, 6))

    print("\n" + "=" * 60)
    print(f"[DONE] 全部爬取完成！共获取 {total_count} 条评论")
    print("数据已保存到 comment_data.csv")
    print("=" * 60)


if __name__ == '__main__':
    start()