import charset_normalizer
from flask import Blueprint, render_template, jsonify, request, current_app, send_file, session
from dao import articleDao, commentDao
from util.category_taxonomy import domain_distribution
import json
import os
import re
import sys
from urllib.parse import quote

# 项目根目录（LITE 海外版读取 CSV 用绝对路径，避免依赖工作目录）
APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _read_csv(path, nrows=None, encoding='utf-8'):
    """轻量 CSV 读取（标准库 csv，替代 pandas，供海外 LITE 版使用）
    返回 (headers, rows)，rows 为 list[list]，自动跳过空行。"""
    import csv as _csv
    try:
        with open(path, 'r', encoding=encoding, errors='replace') as f:
            all_rows = list(_csv.reader(f))
    except Exception:
        return [], []
    if not all_rows:
        return [], []
    headers = all_rows[0]
    rows = [r for r in all_rows[1:] if r and any(str(c).strip() for c in r)]
    if nrows:
        rows = rows[:nrows]
    return headers, rows

# ================= 海外 LITE 精简环境重依赖保护 =================
# 缺失时对应功能优雅降级，不影响系统启动
try:
    from util import wordcloudUtil
except Exception as _e:
    print(f"[LITE 警告] 词云模块加载失败，词云功能将跳过。原因: {_e}")
    wordcloudUtil = None

# 已改用标准库 csv 轻量读取（_read_csv），不再依赖 pandas
try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from snownlp import SnowNLP
except ImportError:
    SnowNLP = None

# 🌟 核心修复：不再创建新的 XinghuoLLMService 实例，使用 xinghuo_llm.py 中的全局实例
from service.xinghuo_llm import xinghuo_llm, assemble_use_data
from service.snapshot_facts import lookup_snapshot_fact
try:
    from service.report_service import generate_full_report
except Exception as _e:
    print(f"[LITE 警告] 报告模块加载失败，报告生成功能将降级。原因: {_e}")
    generate_full_report = None
import shutil
import time

# ================= 导入 RAG 检索函数和全局数据库实例 =================
try:
    from service.rag_service import get_knowledge_with_refs, rag_db
except Exception as e:
    print(f"[WARN] RAG 模块加载失败，内容可追溯功能将降级处理。原因: {e}")
    rag_db = None
    get_knowledge_with_refs = None

pb = Blueprint('page', __name__, url_prefix='/page', template_folder='templates')


@pb.route('/home')
def home():
    articleData = articleDao.get7DayArticle() or []
    xAxis7ArticleData = []
    yAxis7ArticleData = []
    for article in articleData:
        xAxis7ArticleData.append(article[0])
        yAxis7ArticleData.append(article[1])

    # 【修复】原实现是「按 `分类` 原始拼接串 GROUP BY → 降序 → 取前 10 → 其余归『其他』」。
    #   但 `分类` 是微博账号标签的自由拼接串（领域 + 认证 + 设备混排，如
    #   "娱乐博主 iPhone客户端"、"数码博主 微博原创视频博主"），全表 5,116 个互异取值，
    #   90.5% 的取值样本数 ≤5 → Top10 只覆盖 18.72%，81.28% 的样本被倒进「其他」，
    #   表现为"分类结果几乎全部落到其他"。
    #   现改为受控词表归类（util/category_taxonomy.py）：先切标签，再按领域/认证/设备
    #   三维度归类，最后聚合；「其他」不再是吸收池，未标注样本以覆盖率形式显式呈现。
    articleTypeAmountList = list(articleDao.getArticleTypeAmount() or [])
    arcTypeData = domain_distribution(articleTypeAmountList, max_slices=10)['items']

    try:
        top50CommentUserList = commentDao.getTopCommentUser() or []
        top50CommentUserNameList = [cu[0] for cu in top50CommentUserList]

        if not top50CommentUserNameList:
            comment_str = "暂无评论"
        else:
            comment_str = ' '.join(top50CommentUserNameList)

        wordcloudUtil.genWordCloudPic(comment_str, "comment_user_cloud.jpg")
        print("词云生成成功！")
    except Exception as e:
        print("词云生成失败：", e)

    commentData = []
    commentAmountList = commentDao.getCommentAmount() or []
    for comment in commentAmountList:
        commentData.append({'value': comment[1], 'name': comment[0]})

    return render_template('index.html',
                           xAxis7ArticleData=xAxis7ArticleData,
                           yAxis7ArticleData=yAxis7ArticleData,
                           arcTypeData=arcTypeData,
                           commentData=commentData)


@pb.route('/homePageData')
def getHomePageData():
    totalArticle = articleDao.getTotalArticle()
    topAuthor = articleDao.getTopAuthor()
    topRegion = articleDao.getTopRegion()
    topArticles = articleDao.getArticleTopZan()
    return jsonify(
        totalArticle=totalArticle,
        topAuthor=topAuthor,
        topRegion=topRegion,
        topArticles=topArticles
    )


@pb.route('/hotWord')
def hotWord():
    hotwordList = []
    df = None
    try:
        _h, _rows = _read_csv(os.path.join(APP_ROOT, 'fenci', 'comment_fre.csv'), nrows=100)
        for value in _rows:
            hotwordList.append(str(value[0]).strip())
    except Exception as e:
        print("读取 comment_fre.csv 失败:", e)
        hotwordList = ["暂无热词"]

    defaultHotWord = request.args.get('word', default=hotwordList[0] if hotwordList else "暂无热词")

    hotwordNum = 0
    if _rows:
        for value in _rows:
            if defaultHotWord == str(value[0]).strip():
                hotwordNum = int(value[1]) if str(value[1]).strip() not in ('', 'nan') else 0

    sentiments = '中性'
    try:
        _h2, _rows2 = _read_csv(os.path.join(APP_ROOT, 'fenci', 'hot_sent_final.csv'))
        hot_sent_map = {}
        if 'word' in _h2 and 'sentiment' in _h2:
            _wi = _h2.index('word')
            _si = _h2.index('sentiment')
            for _r in _rows2:
                if len(_r) > max(_wi, _si):
                    _w = str(_r[_wi]).strip()
                    _sv = str(_r[_si]).strip()
                    if _w:
                        hot_sent_map[_w] = _sv or '中性'
        if defaultHotWord in hot_sent_map:
            sentiments = hot_sent_map[defaultHotWord]
        else:
            stc = SnowNLP(defaultHotWord).sentiments
            if stc > 0.6:
                sentiments = '正面'
            elif stc < 0.2:
                sentiments = '负面'
    except:
        try:
            stc = SnowNLP(defaultHotWord).sentiments
            if stc > 0.6:
                sentiments = '正面'
            elif stc < 0.2:
                sentiments = '负面'
        except:
            pass

    commentHotWordData = commentDao.getCommentHotWordAmount(defaultHotWord)

    xAxisHotWordData = []
    yAxisHotWordData = []

    if commentHotWordData:
        for comment in commentHotWordData:
            try:
                date_val = str(comment[0]) if comment[0] is not None else "未知日期"
                count_val = int(comment[1]) if comment[1] is not None else 0
                xAxisHotWordData.append(date_val)
                yAxisHotWordData.append(count_val)
            except Exception as e:
                continue
    else:
        print("[WARN] DAO层返回了空数据！")

    commentList = commentDao.getCommentByHotWord(defaultHotWord) or []

    return render_template('hotWord.html',
                           hotwordList=hotwordList,
                           defaultHotWord=defaultHotWord,
                           hotwordNum=hotwordNum,
                           sentiments=sentiments,
                           xAxisHotWordData=xAxisHotWordData,
                           yAxisHotWordData=yAxisHotWordData,
                           commentList=commentList)


@pb.route('/articleData')
def articleData():
    articleOldList = articleDao.getAllArticle()[:8000]
    articleNewList = []

    sentiment_map = {}
    try:
        _h3, _rows3 = _read_csv(os.path.join(APP_ROOT, 'fenci', 'article_sentiment_fixed.csv'))
        sentiment_map = {}
        if 'article_id' in _h3 and 'sentiment' in _h3:
            _ai = _h3.index('article_id')
            _si3 = _h3.index('sentiment')
            for _r in _rows3:
                if len(_r) > max(_ai, _si3):
                    _aid = str(_r[_ai]).strip()
                    _sv3 = str(_r[_si3]).strip()
                    if _aid:
                        sentiment_map[_aid] = _sv3 or '中性'
    except:
        pass

    for article in articleOldList:
        try:
            article = list(article)
            article_id = str(article[0])

            if article_id in sentiment_map:
                sentiments = sentiment_map[article_id]
            else:
                stc = SnowNLP(article[1]).sentiments
                if stc > 0.6:
                    sentiments = '正面'
                elif stc < 0.2:
                    sentiments = '负面'
                else:
                    sentiments = '中性'

            article.append(sentiments)
            articleNewList.append(article)
        except:
            continue

    return render_template('articleData.html', articleList=articleNewList)


@pb.route('/articleDataAnalysis')
def articleDataAnalysis():
    arcTypeList = []
    try:
        _h4, _rows4 = _read_csv(os.path.join(APP_ROOT, 'spider', 'arcType_data.csv'))
        for value in _rows4:
            if value:
                arcTypeList.append(value[0])
    except:
        arcTypeList = ["全部"]

    defaultArcType = request.args.get('arcType', default=arcTypeList[0] if len(arcTypeList) > 0 else "全部")
    articleList = articleDao.getArticleByArcType(defaultArcType) or []

    xDzData = []
    xPlData = []
    xZfData = []
    rangeNum = 1000
    rangeNum2 = 100

    for item in range(0, 10):
        xDzData.append(str(rangeNum * item) + '-' + str(rangeNum * (item + 1)))
        xPlData.append(str(rangeNum * item) + '-' + str(rangeNum * (item + 1)))

    for item in range(0, 20):
        xZfData.append(str(rangeNum2 * item) + '-' + str(rangeNum2 * (item + 1)))

    xDzData.append('1万+')
    xPlData.append('1万+')
    xZfData.append('2千+')

    yDzData = [0] * len(xDzData)
    yPlData = [0] * len(xPlData)
    yZfData = [0] * len(xZfData)

    for article in articleList:
        try:
            dz = int(article[4]) if article[4] is not None else 0
            for item in range(len(xDzData)):
                if dz < rangeNum * (item + 1):
                    yDzData[item] += 1
                    break
                elif dz >= 10000:
                    yDzData[-1] += 1
                    break
        except:
            pass

        try:
            pl = int(article[3]) if article[3] is not None else 0
            for item in range(len(xPlData)):
                if pl < rangeNum * (item + 1):
                    yPlData[item] += 1
                    break
                elif pl >= 10000:
                    yPlData[-1] += 1
                    break
        except:
            pass

    for article in articleList:
        try:
            zf = int(article[2]) if article[2] is not None else 0
            for item in range(len(xZfData)):
                if zf < rangeNum2 * (item + 1):
                    yZfData[item] += 1
                    break
                elif zf >= 2000:
                    yZfData[-1] += 1
                    break
        except:
            pass

    return render_template('articleDataAnalysis.html',
                           arcTypeList=arcTypeList,
                           defaultArcType=defaultArcType,
                           xDzData=xDzData,
                           yDzData=yDzData,
                           xPlData=xPlData,
                           yPlData=yPlData,
                           xZfData=xZfData,
                           yZfData=yZfData)


@pb.route('/commentDataAnalysis')
def commentDataAnalysis():
    commentList = commentDao.getAllComment()
    xDzData = []
    rangeNum = 5
    for item in range(0, 20):
        xDzData.append(str(rangeNum * item) + '-' + str(rangeNum * (item + 1)))
    xDzData.append('1百+')
    yDzData = [0 for x in range(len(xDzData))]
    genderDic = {'男': 0, '女': 0}

    for comment in commentList:
        try:
            for item in range(len(xDzData)):
                if int(comment[4]) < rangeNum * (item + 1):
                    yDzData[item] += 1
                    break
                elif int(comment[4]) > 100:
                    yDzData[len(xDzData) - 1] += 1
                    break
        except:
            pass

        try:
            if comment[8] in genderDic:
                genderDic[comment[8]] += 1
        except:
            pass

    genderData = [{'name': x[0], 'value': x[1]} for x in genderDic.items()]

    try:
        _h5, _rows5 = _read_csv(os.path.join(APP_ROOT, 'fenci', 'comment_fre.csv'), nrows=50)
        hotCommentwordList = [str(x[0]) for x in _rows5]
        str2 = ' '.join(hotCommentwordList)
        wordcloudUtil.genWordCloudPic(str2, 'comment_cloud.jpg')
    except Exception as e:
        print("词云生成失败：", e)

    return render_template('commentDataAnalysis.html',
                           xDzData=xDzData,
                           yDzData=yDzData,
                           genderData=genderData)


@pb.route('/articleCloud')
def articleCloud():
    img_path = os.path.join(current_app.static_folder, 'article_cloud.jpg')
    csv_path = './fenci/article_fre2.csv'

    try:
        if not os.path.exists(img_path) or (
                os.path.exists(csv_path) and os.path.getmtime(csv_path) > os.path.getmtime(img_path)):
            _h6, _rows6 = _read_csv(csv_path, nrows=50)
            hotArticleWordList = [str(x[0]) for x in _rows6]
            str2 = ' '.join(hotArticleWordList)
            wordcloudUtil.genWordCloudPic(str2, 'article_cloud.jpg')
            print("文章词云重新生成成功！")
        else:
            print("[FAST] 文章词云已存在，直接读取缓存！")
    except Exception as e:
        print("词云失败：", e)

    return render_template('articleCloud.html')


@pb.route('/commentCloud')
def commentCloud():
    img_path = os.path.join(current_app.static_folder, 'comment_cloud.jpg')
    csv_path = './fenci/comment_fre2.csv'

    try:
        if not os.path.exists(img_path) or (
                os.path.exists(csv_path) and os.path.getmtime(csv_path) > os.path.getmtime(img_path)):
            _h7, _rows7 = _read_csv(csv_path, nrows=50)
            hotCommentWordList = [str(x[0]) for x in _rows7]
            result_str = ' '.join(hotCommentWordList)
            wordcloudUtil.genWordCloudPic(result_str, 'comment_cloud.jpg')
            print("评论词云重新生成成功！")
        else:
            print("[FAST] 评论词云已存在，直接读取缓存！")
    except Exception as e:
        print("评论词云失败：", e)

    return render_template('commentCloud.html')


@pb.route('/commentUserCloud')
def commentUserCloud():
    img_path = os.path.join(current_app.static_folder, 'comment_user_cloud.jpg')
    csv_path = './fenci/comment_user_fre2.csv'

    try:
        if not os.path.exists(img_path) or (
                os.path.exists(csv_path) and os.path.getmtime(csv_path) > os.path.getmtime(img_path)):
            _h8, _rows8 = _read_csv(csv_path, nrows=50)
            hotCommentUserWordList = [str(x[0]) for x in _rows8]
            result_str = ' '.join(hotCommentUserWordList)
            wordcloudUtil.genWordCloudPic(result_str, 'comment_user_cloud.jpg')
            print("评论用户词云重新生成成功！")
        else:
            print("[FAST] 评论用户词云已存在，直接读取缓存！")
    except Exception as e:
        print("评论用户词云失败：", e)

    return render_template('commentUserCloud.html')


@pb.route('/ipDataAnalysis')
def ipDataAnalysis():
    from util import mapUtil
    cityList = mapUtil.cityList
    articleList = articleDao.getAllArticle() or []
    commentList = commentDao.getAllComment(limit=None) or []   # 统计类页面必须取全量，不能吃默认的 LIMIT 200

    cityDic = {}
    for article in articleList:
        try:
            ip_info = str(article[5])
            if ip_info and "发布于" in ip_info:
                province = ip_info.split("发布于")[-1].strip()
                for city in cityList:
                    if city['province'] in province:
                        cityDic[city['province']] = cityDic.get(city['province'], 0) + 1
        except Exception as e:
            continue

    cityDic2 = {}
    for comment in commentList:
        try:
            ip_info = str(comment[3])
            if ip_info:
                for city in cityList:
                    if city['province'] in ip_info:
                        cityDic2[city['province']] = cityDic2.get(city['province'], 0) + 1
        except Exception as e:
            continue

    articleCityDicList = [{'name': k, 'value': v} for k, v in cityDic.items()]
    commentCityDicList = [{'name': k, 'value': v} for k, v in cityDic2.items()]

    return render_template('ipDataAnalysis.html',
                           articleCityDicList=articleCityDicList,
                           commentCityDicList=commentCityDicList)


@pb.route('/sentimentAnalysis')
def sentimentAnalysis():
    import time

    start = time.time()
    base_dir = current_app.root_path
    fenci_dir = os.path.join(base_dir, 'fenci')

    # 1. 热词情感统计
    xHotBarData = ['正面', '中性', '负面']
    yHotBarData = [0, 0, 0]
    try:
        csv_path = os.path.join(fenci_dir, 'hot_sent_final.csv')
        _h9, _rows9 = _read_csv(csv_path)
        sentiments = []
        if 'sentiment' in _h9:
            _si9 = _h9.index('sentiment')
            for _r in _rows9:
                if len(_r) > _si9:
                    _sv9 = str(_r[_si9]).strip()
                    if _sv9 and _sv9.lower() != 'nan':
                        sentiments.append(_sv9)
        for s in sentiments:
            if s == "正面":
                yHotBarData[0] += 1
            elif s == "负面":
                yHotBarData[2] += 1
            else:
                yHotBarData[1] += 1
    except Exception as e:
        print(f"[WARN] 热词情感数据加载失败: {str(e)}")
        yHotBarData = [0, 0, 0]

    hotTreeMapData = [
        {"name": "正面", "value": yHotBarData[0]},
        {"name": "中性", "value": yHotBarData[1]},
        {"name": "负面", "value": yHotBarData[2]}
    ]

    # 2. 评论情感统计
    contentPieData1 = [
        {"name": "正面", "value": 0},
        {"name": "中性", "value": 0},
        {"name": "负面", "value": 0}
    ]
    try:
        csv_path = os.path.join(fenci_dir, 'comment_sent_final.csv')
        _h10, _rows10 = _read_csv(csv_path)
        sentiments = []
        if 'sentiment' in _h10:
            _si10 = _h10.index('sentiment')
            for _r in _rows10:
                if len(_r) > _si10:
                    _sv10 = str(_r[_si10]).strip()
                    if _sv10 and _sv10.lower() != 'nan':
                        sentiments.append(_sv10)
        for s in sentiments:
            if s == "正面":
                contentPieData1[0]['value'] += 1
            elif s == "负面":
                contentPieData1[2]['value'] += 1
            else:
                contentPieData1[1]['value'] += 1
    except Exception as e:
        print(f"[WARN] 评论情感数据加载失败: {str(e)}")
        contentPieData1 = [
            {"name": "正面", "value": 0},
            {"name": "中性", "value": 0},
            {"name": "负面", "value": 0}
        ]

    # 3. 帖子情感统计
    contentPieData2 = [
        {"name": "正面", "value": 0},
        {"name": "中性", "value": 0},
        {"name": "负面", "value": 0}
    ]
    try:
        csv_path = os.path.join(fenci_dir, 'article_sent_final.csv')
        _h11, _rows11 = _read_csv(csv_path)
        sentiments = []
        if 'sentiment' in _h11:
            _si11 = _h11.index('sentiment')
            for _r in _rows11:
                if len(_r) > _si11:
                    _sv11 = str(_r[_si11]).strip()
                    if _sv11 and _sv11.lower() != 'nan':
                        sentiments.append(_sv11)
        for s in sentiments:
            if s == "正面":
                contentPieData2[0]['value'] += 1
            elif s == "负面":
                contentPieData2[2]['value'] += 1
            else:
                contentPieData2[1]['value'] += 1
    except Exception as e:
        print(f"[WARN] 帖子情感数据加载失败: {str(e)}")
        contentPieData2 = [
            {"name": "正面", "value": 0},
            {"name": "中性", "value": 0},
            {"name": "负面", "value": 0}
        ]

    # 4. 热词排行
    xhotData15 = []
    yhotData15 = []
    try:
        csv_path = os.path.join(fenci_dir, 'comment_fre.csv')
        _h12, _rows12 = _read_csv(csv_path, nrows=15)
        xhotData15 = [str(x[0]).strip() for x in _rows12 if x and str(x[0]).strip() not in ('', 'nan')][::-1]
        yhotData15 = [int(x[1]) for x in _rows12 if len(x) > 1 and str(x[1]).strip() not in ('', 'nan')][::-1]
    except Exception as e:
        print(f"[WARN] 热词排行数据加载失败: {str(e)}")
        xhotData15 = []
        yhotData15 = []

    print(f"[OK] 情感分析页面加载完成，耗时：{time.time() - start:.2f}s")
    return render_template('sentimentAnalysis.html',
                           xHotBarData=xHotBarData,
                           yHotBarData=yHotBarData,
                           hotTreeMapData=hotTreeMapData,
                           contentPieData1=contentPieData1,
                           contentPieData2=contentPieData2,
                           xhotData15=xhotData15,
                           yhotData15=yhotData15)


# ===================== 🌟 核心修复：AI 聊天路由（支持文档、图片、模式） =====================
@pb.route('/chat', methods=['POST'])
def ai_chat():
    """处理 AI 聊天问答，集成 RAG 知识溯源，支持多模态输入和创意模式"""
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get('message', '').strip()
        image_path = data.get('image_path', None)
        file_path = data.get('file_path', None)        # 新增：文档路径
        mode = data.get('mode', 'strict')              # 新增：对话模式（strict/creative）
        basin = (data.get('basin') or '').strip() or None   # 专题流域（长江/黄河）；空=不限

        if not user_message and not image_path and not file_path:
            return jsonify({"reply": "⚠️ 提问内容不能为空", "references": []})

        # 获取当前用户
        user = session.get('user', 'anonymous')
        user_id = user if isinstance(user, str) else (
            user.get('username', 'anonymous') if isinstance(user, dict) else 'anonymous')

        # 会话隔离：按「用户 + 流域」分桶，避免跨专题追问时历史串台
        # Verified snapshot facts take precedence over generative routing.
        if user_message:
            deterministic = lookup_snapshot_fact(user_message, basin=basin)
            if deterministic is not None:
                return jsonify({
                    "reply": deterministic["reply"],
                    "references": deterministic.get("references", []),
                })

        sid = f"{user_id}:{basin}" if basin else user_id

        # 🌟 核心修复：调用 xinghuo_llm.chat()，传入所有参数（含专题流域）
        raw_reply = xinghuo_llm.chat(
            user_message,
            session_id=sid,
            image_path=image_path,
            user_id=user_id,
            mode=mode,
            file_path=file_path,
            basin=basin
        )

        # 🌟 正确解构字典返回值
        if isinstance(raw_reply, dict):
            reply_text = raw_reply.get("answer", "系统返回数据异常")
            references = raw_reply.get("references", [])
        else:
            reply_text = str(raw_reply) if raw_reply else "⚠️ 大模型未返回有效内容，请重试。"
            references = []

        # 🌟 返回 reply + references 给前端
        return jsonify({
            "reply": reply_text,
            "references": references
        })
    except Exception as e:
        print(f"[ERR] /chat 接口报错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"❌ 服务器内部错误: {str(e)}", "references": []}), 500


# ===================== 🌟 修改后的生成学术报告路由 =====================
@pb.route('/generate_report', methods=['POST'])
def generate_report():
    """调用完整报告引擎生成舆情分析报告"""
    try:
        # 专题流域（可选）：前端按所在专题传入，生成对应流域的报告
        _data = request.get_json(silent=True) or {}
        basin = (_data.get('basin') or '').strip() or None
        # 1. 组装报告数据
        use_data = assemble_use_data(basin)
        # 2. 生成完整报告（Word文档）
        filepath = generate_full_report(use_data)  # 返回如 reports/舆情分析报告_2026-07-26_13-47-11.docx
        report_filename = os.path.basename(filepath)

        # 3. 将报告文件复制到 static/reports/ 下，以便下载路由能找到
        save_dir = os.path.join(current_app.static_folder, 'reports')
        os.makedirs(save_dir, exist_ok=True)
        target_path = os.path.join(save_dir, report_filename)
        shutil.copy2(filepath, target_path)

        return jsonify({
            "reply": f"✅ 完整舆情分析报告已生成！\n[REPORT_PATH:{report_filename}]",
            "report_path": report_filename,
            "references": []
        })
    except Exception as e:
        print(f"[ERR] /generate_report 接口报错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"❌ 报告生成失败: {str(e)}", "report_path": "", "references": []}), 500


# ===================== 下载报告 =====================
@pb.route('/download_report', methods=['GET'])
def download_report():
    """处理 Word 报告下载"""
    try:
        filename = request.args.get('path', '').strip()
        if not filename:
            return "未指定文件", 400

        if '..' in filename or '/' in filename or '\\' in filename:
            return "非法文件名", 400

        file_dir = os.path.join(current_app.static_folder, 'reports')
        file_path = os.path.join(file_dir, filename)

        if os.path.exists(file_path):
            ascii_filename = quote(filename.encode('utf-8'))
            try:
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=filename
                )
            except TypeError:
                return send_file(
                    file_path,
                    as_attachment=True,
                    attachment_filename=ascii_filename
                )
        else:
            return "文件不存在或已过期", 404
    except Exception as e:
        print(f"[ERR] /download_report 接口报错: {str(e)}")
        return f"下载失败: {str(e)}", 500


# ===================== 图片上传（多模态视觉分析） =====================
@pb.route('/upload_image', methods=['POST'])
def upload_image():
    """处理前端上传的图片（供多模态视觉分析使用）"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "没有文件"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "文件名为空"}), 400

        upload_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        import uuid
        ext = os.path.splitext(file.filename)[1] or '.png'
        allowed_img = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
        if ext.lower() not in allowed_img:
            return jsonify({"error": f"不支持的图片格式：{ext}（支持 JPG/PNG/WebP/GIF/BMP）"}), 400
        safe_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(upload_dir, safe_name)
        MAX_SIZE = 20 * 1024 * 1024  # 20MB
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_SIZE:
            return jsonify({"error": "文件大小超过 20MB 限制"}), 400

        file.save(save_path)

        return jsonify({"image_path": save_path, "filename": safe_name,
                        "url": '/static/uploads/' + safe_name})
    except Exception as e:
        print(f"[ERR] /upload_image 接口报错: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ===================== 🌟 新增：文档上传路由（PDF、Word、Excel等） =====================
@pb.route('/upload_file', methods=['POST'])
def upload_file():
    """处理文档文件上传（PDF、Word、Excel等）"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "没有文件"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "文件名为空"}), 400

        # 安全限制：只允许常见文档类型
        allowed_ext = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.md', '.csv'}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_ext:
            return jsonify({"error": f"不支持的文件类型：{ext}"}), 400

        upload_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        import uuid
        safe_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(upload_dir, safe_name)
        MAX_SIZE = 20 * 1024 * 1024  # 20MB
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_SIZE:
            return jsonify({"error": "文件大小超过 20MB 限制"}), 400

        file.save(save_path)

        return jsonify({"file_path": save_path, "filename": safe_name,
                        "url": '/static/uploads/' + safe_name})
    except Exception as e:
        print(f"[ERR] /upload_file 接口报错: {str(e)}")
        return jsonify({"error": str(e)}), 500
# ===================== 🌟 知识库手动重载 API =====================
@pb.route('/api/knowledge/reload', methods=['POST'])
def reload_knowledge():
    """手动触发知识库的强制重新加载"""
    try:
        from service.rag_service import force_reload_knowledge
        result = force_reload_knowledge()
        return jsonify({"status": "success", "message": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ===================== 🌟 用户反馈接口（支撑"用户认可度"评分） =====================
@pb.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """记录用户对 AI 回答的反馈，用于效果验证报告"""
    try:
        data = request.get_json(silent=True) or {}
        user = session.get('user', 'anonymous')
        user_id = user if isinstance(user, str) else (
            user.get('username', 'anonymous') if isinstance(user, dict) else 'anonymous')
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "feedback.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, question TEXT, answer TEXT,
            rating INTEGER, comment TEXT, scene TEXT, created_at TEXT)""")
        conn.execute("INSERT INTO feedback(user_id, question, answer, rating, comment, scene, created_at) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (user_id,
                      str(data.get('question', ''))[:500],
                      str(data.get('answer', ''))[:2000],
                      int(data.get('rating', 0)),
                      str(data.get('comment', ''))[:500],
                      str(data.get('scene', ''))[:50],
                      time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@pb.route('/api/feedback/export', methods=['GET'])
def export_feedback():
    """导出反馈记录 CSV，供《06—效果验证报告》使用"""
    try:
        import sqlite3, csv, io as _io
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "feedback.db")
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM feedback ORDER BY id").fetchall()
        conn.close()
        cols = ["id", "user_id", "question", "answer", "rating", "comment", "scene", "created_at"]
        buf = _io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(cols)
        writer.writerows(rows)
        from flask import Response
        return Response(
            "\ufeff" + buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=feedback.csv"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# ===================== 🌟 异步报告生成与任务进度 =====================
@pb.route('/generate_report_async', methods=['POST'])
def generate_report_async():
    """异步生成报告：立即返回 task_id，前端轮询 /api/task/<id> 获取进度"""
    try:
        from service.task_manager import task_manager
        from service.xinghuo_llm import assemble_use_data
        from service.report_service import generate_full_report

        def _run(progress_cb=None):
            if progress_cb:
                progress_cb(10, "正在组装数据...")
            use_data = assemble_use_data()
            if progress_cb:
                progress_cb(40, "正在并行生成报告章节...")
            from service.report_workflow import generate_report_workflow
            result = generate_report_workflow(use_data)
            return result

        task_id = task_manager.submit("舆情报告生成", _run)
        return jsonify({"status": "success", "task_id": task_id})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@pb.route('/api/task/<task_id>', methods=['GET'])
def task_status(task_id):
    """查询异步任务状态：status/progress/message/result/error"""
    try:
        from service.task_manager import task_manager
        task = task_manager.get(task_id)
        if not task:
            return jsonify({"status": "error", "msg": "任务不存在"}), 404
        return jsonify(task)
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ===================== 单页仪表盘（参考站点同款 · 数据实时查 db_weibo_basin） =====================
@pb.route('/dashboard')
def dashboard():
    """单页仪表盘：18 视图深蓝仪表盘，数据实时查 db_weibo_basin。

    缓存采用 stale-while-revalidate：命中新鲜缓存直接返回；缓存过期时先返回
    旧内容（用户零等待）并在后台增量重算；?force=1 才同步全量重算。
    """
    from service.dashboard import get_html
    force = request.args.get('force') == '1'
    html, err = get_html(force=force)
    if html is None:
        from flask import escape
        return "<h3 style='color:#ff6b6b;font-family:monospace'>仪表盘生成失败</h3><pre>%s</pre>" % escape(err or '未知错误'), 500
    return html


@pb.route('/api/dashboard/refresh', methods=['POST'])
def dashboard_refresh():
    """强制刷新仪表盘数据（忽略缓存，重跑完整生成链）"""
    from service.dashboard import refresh
    ok, msg = refresh(force=True)
    return jsonify({"status": "success" if ok else "error", "message": msg})


# ===================== 动态采集（spider/run_refresh.py 编排层的一键入口） =====================
# 环境变量 DATA_REFRESH_ENABLE：本地默认开启；LITE 海外演示默认关闭 —— 评委误点会触发
# 真实爬虫 + 接管 Edge（弹出浏览器窗口），演示现场不可控；确要演示时显式设 DATA_REFRESH_ENABLE=1。
def _data_refresh_enabled():
    lite = os.getenv("LITE_MODE", "0") == "1"
    return os.getenv("DATA_REFRESH_ENABLE", "0" if lite else "1") == "1"


def _crawl_paths():
    """返回 (spider目录, 运行态目录, crawl.lock 路径, refresh_state.json 路径)。
    与 run_refresh.py 的约定保持一致：锁存在 = 正在采集（编排层自己的互斥）。"""
    spider_dir = os.path.join(APP_ROOT, 'spider')
    state_dir = os.path.join(spider_dir, '_state')
    return (spider_dir, state_dir,
            os.path.join(state_dir, 'crawl.lock'),
            os.path.join(state_dir, 'refresh_state.json'))


@pb.route('/api/data/refresh', methods=['POST'])
def data_refresh_start():
    """一键动态采集：后台拉起 spider/run_refresh.py（quick 档，约 3~6 分钟）。

    流程 = 增量采集（现有爬虫，upsert 进库）→ 新增>0 才失效产物并重算生成链。
    本接口立即返回，前端轮询 /page/api/data/refresh/status；
    并发兜底靠编排层自己的 crawl.lock —— 重复触发时子进程拿不到锁会自行退出。
    """
    if not _data_refresh_enabled():
        return jsonify({"status": "disabled"})
    import subprocess as _sp
    spider_dir, state_dir, lock, _statef = _crawl_paths()
    if os.path.exists(lock):
        return jsonify({"status": "running"})
    py = os.path.join(APP_ROOT, '.venv', 'Scripts', 'python.exe')
    if not os.path.isfile(py):
        py = sys.executable          # 精简副本无 .venv 时回退当前解释器
    os.makedirs(state_dir, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    # 子进程输出落盘（spider/_state/last_run.log），采集明细可随时回查
    logf = open(os.path.join(state_dir, 'last_run.log'), 'w', encoding='utf-8')
    try:
        _sp.Popen([py, os.path.join(spider_dir, 'run_refresh.py'), '--profile', 'quick'],
                  cwd=spider_dir, env=env, stdout=logf, stderr=_sp.STDOUT)
    finally:
        logf.close()
    return jsonify({"status": "started"})


@pb.route('/api/data/refresh/status', methods=['GET'])
def data_refresh_status():
    """采集状态：running = crawl.lock 是否存在；last = 最近一次 refresh_state.json。"""
    _spider_dir, _state_dir, lock, statef = _crawl_paths()
    running = os.path.exists(lock)
    started = None
    if running:
        try:
            with open(lock, encoding='utf-8') as f:
                started = json.load(f).get('started')
        except Exception:
            started = None
    last = None
    if os.path.exists(statef):
        try:
            with open(statef, encoding='utf-8') as f:
                last = json.load(f)
        except Exception:
            last = None
    return jsonify({"status": "ok", "enabled": _data_refresh_enabled(),
                    "running": running, "started": started, "last": last})
