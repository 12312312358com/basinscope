import time, json, re, os, sys, sqlite3, threading, logging, mimetypes, base64
import socket, ssl, hashlib, httpx, asyncio, io, uuid, math, random
try:
    import numpy as np
except ImportError:
    np = None
from typing import List, Dict, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

# 第三方库（按需导入，缺失时降级）
try:
    import requests
except ImportError:
    requests = None
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from fastembed import TextEmbedding
    _has_fastembed = True
except ImportError:
    _has_fastembed = False
try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    _has_langchain = True
except ImportError:
    _has_langchain = False

# ===== LITE 海外模式：langchain 缺失时使用轻量消息类（仅用于会话历史记录）=====
if not _has_langchain:

    class HumanMessage:
        def __init__(self, content=""):
            self.content = content

    class AIMessage:
        def __init__(self, content=""):
            self.content = content

    class SystemMessage:
        def __init__(self, content=""):
            self.content = content
from dotenv import load_dotenv
from openai import OpenAI

# ===================== 🌟 轻量级 OCR 依赖 =====================
try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("[WARN] 缺少 rapidocr_onnxruntime，图片分析功能将不可用。请运行: pip install rapidocr_onnxruntime")

# ===================== 从本包子模块导入 =====================
from .config import logger, root_dir, RERANK_SOURCE_SCORE_FLOOR
from .imports import (getTotalArticle, getTopAuthor, getTopRegion, getArticleTopZan,
                      get7DayArticle, getArticleTypeAmount, getTopCommentUser, getBasinHotEvents,
                      getAllComment, getCommentAmount, getCommentTotal, getCommentHotWordAmount,
                      getCommentByHotWord,
                      get_knowledge, get_knowledge_with_refs, rag_db, academic_validator)

# ===================== 舆情报告数据组装函数（真实数据版） =====================
def _assemble_basin_data(basin):
    """按流域组装报告数据。数据源：dashboard_gen/basin_data.json（构建期已按流域聚合）。"""
    import json as _json
    b = {}
    try:
        p = os.path.join(root_dir, 'dashboard_gen', 'basin_data.json')
        with open(p, encoding='utf-8') as f:
            _d = _json.load(f)
        b = (_d.get('basins') or {}).get(basin) or {}
    except Exception as e:
        logger.warning(f"读取流域数据失败：{e}")

    # 1. 概览
    # ⚠ 口径统一（2026-10-11）：流域报告的「入库总数」改用数据库表（t_basin_article，全议题），
    #   与对话工具 getTotalArticle(basin=...) 对齐 —— basin_data.json 的 articles 是
    #   「聚焦样本（生态治理 + 文旅 + 医患矛盾）」，两者相差数百条，会让同一作品出现两个总数。
    months = b.get('months') or []
    _dates = [str(m[0]) for m in months if isinstance(m, (list, tuple)) and m]
    try:
        _total_articles = int(getTotalArticle(basin=basin) or 0)
    except Exception as _e:
        logger.warning(f"取流域文章总数失败，回退 basin_data：{_e}")
        _total_articles = int(b.get('articles') or 0)
    overview_stats = {
        "total_articles": _total_articles,
        "total_comments": int(b.get('comments') or 0),
        "real_earliest_date": min(_dates) if _dates else "未知",
        "real_latest_date": max(_dates) if _dates else "未知",
    }
    # 2. 趋势（流域聚合为**月粒度**，key 形如 '2026-10'；标记粒度供报告端正确命名与取轴）
    daily_trend = [{"date": str(m[0]), "count": int(m[1])} for m in months
                   if isinstance(m, (list, tuple)) and len(m) >= 2]
    # ⚠ 只保留最近 24 个「有数据的月份」：流域样本年份严重偏向 2026（早期月份常仅 1~2 条），
    #   全区间（2011~2026，长江 89 点 / 黄河 95 点）画出来又密又长，会被误读成"声量趋势"。
    _TREND_KEEP = 24
    _truncated = len(daily_trend) > _TREND_KEEP
    if _truncated:
        daily_trend = daily_trend[-_TREND_KEEP:]
    # 3. 情感
    smap = {}
    for it in (b.get('sent') or []):
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            smap[str(it[0])] = int(it[1])
    pos, neu, neg = smap.get('正面', 0), smap.get('中性', 0), smap.get('负面', 0)
    stotal = pos + neu + neg
    sentiment_trend = {"positive": pos, "neutral": neu, "negative": neg, "total": stotal,
                       "pos_ratio": f"{pos/stotal*100:.1f}%" if stotal else "0%",
                       "neu_ratio": f"{neu/stotal*100:.1f}%" if stotal else "0%",
                       "neg_ratio": f"{neg/stotal*100:.1f}%" if stotal else "0%"}
    # 4. 热词
    hot_topics = [{"keyword": str(w), "heat": int(h), "sentiment": "中性"}
                  for w, h in (b.get('hotwords') or [])[:15]]
    # 5. 评论
    user_comments = []
    for c in (b.get('topComments') or [])[:50]:
        if isinstance(c, dict):
            user_comments.append({"content": c.get('text') or c.get('content') or '',
                                  "likes": c.get('like') or c.get('likes') or 0})
        elif isinstance(c, (list, tuple)) and len(c) >= 2:
            user_comments.append({"content": str(c[0]), "likes": c[1]})

    return {
        "overview_stats": overview_stats,
        "daily_trend": daily_trend,
        "sentiment_trend": sentiment_trend,
        "hot_topics": hot_topics,
        "user_comments": user_comments,
        "basin": basin,
        "trend_grain": "month",
        "trend_note": (f"趋势图为最近 {len(daily_trend)} 个有数据月份"
                       + ("（已截取，早期月份样本极少）" if _truncated else "（覆盖数据全区间）")),
    }


def assemble_use_data(basin=None):
    """
    从数据库和本地 CSV 中提取数据，组装成 report.generate_full_report() 需要的字典结构。
    情感数据：来自 fenci/comment_sent_final.csv
    热词数据：来自 fenci/comment_fre.csv + fenci/hot_sent_final.csv
    basin 非空时改走流域数据（basin_data.json），产出该流域专属报告。
    """
    if basin:
        return _assemble_basin_data(basin)

    import pandas as pd

    use_data = {}

    # 1. 概览统计
    try:
        total_articles = getTotalArticle()
        # ⚠ 评论总数用 getCommentTotal（COUNT(*)）；不能对 getCommentAmount 取 len()
        #   —— 后者返回「近 7 天每日条数」列表，len() 得到的是"天数"（≤7），
        #   旧实现因此让全量报告显示"评论 7 条"。
        total_comments = getCommentTotal()
        real_earliest_date = "未知"
        real_latest_date = "未知"
        try:
            trend = get7DayArticle()
            if isinstance(trend, (list, tuple)) and trend:
                dates = [str(x[0]) for x in trend
                         if isinstance(x, (list, tuple)) and len(x) >= 2]
                if dates:
                    real_earliest_date = min(dates)
                    real_latest_date = max(dates)
        except Exception as e:
            logger.warning(f"获取日期范围失败: {e}")
    except Exception as e:
        logger.warning(f"获取概览统计失败: {e}")
        total_articles = 0
        total_comments = 0
        real_earliest_date = "未知"
        real_latest_date = "未知"

    use_data["overview_stats"] = {
        "total_articles": total_articles,
        "total_comments": total_comments,
        "real_earliest_date": real_earliest_date,
        "real_latest_date": real_latest_date
    }

    # 2. 每日发文趋势
    daily_trend = []
    try:
        raw_trend = get7DayArticle()
        if raw_trend and not isinstance(raw_trend, str):
            if isinstance(raw_trend, (list, tuple)):
                for item in raw_trend:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        daily_trend.append({"date": str(item[0]), "count": int(item[1])})
                    elif isinstance(item, dict):
                        daily_trend.append(item)
    except Exception as e:
        logger.warning(f"获取每日趋势失败: {e}")
    use_data["daily_trend"] = daily_trend

    # 3. 情感分布
    sentiment_trend = {"positive": 0, "neutral": 0, "negative": 0, "total": 0,
                       "pos_ratio": "0%", "neu_ratio": "0%", "neg_ratio": "0%"}
    try:
        sent_path = os.path.join(root_dir, "fenci", "comment_sent_final.csv")
        if os.path.exists(sent_path):
            df = pd.read_csv(sent_path)
            sentiments = df['sentiment'].dropna().astype(str)
            pos = (sentiments == "正面").sum()
            neu = (sentiments == "中性").sum()
            neg = (sentiments == "负面").sum()
            total = pos + neu + neg
            if total > 0:
                sentiment_trend = {
                    "positive": int(pos), "neutral": int(neu), "negative": int(neg),
                    "total": int(total),
                    "pos_ratio": f"{pos/total*100:.1f}%",
                    "neu_ratio": f"{neu/total*100:.1f}%",
                    "neg_ratio": f"{neg/total*100:.1f}%"
                }
    except Exception as e:
        logger.warning(f"读取情感数据失败: {e}")
    use_data["sentiment_trend"] = sentiment_trend

    # 4. 热词排行
    hot_topics = []
    try:
        fre_path = os.path.join(root_dir, "fenci", "comment_fre.csv")
        sent_path = os.path.join(root_dir, "fenci", "hot_sent_final.csv")
        if os.path.exists(fre_path):
            df_fre = pd.read_csv(fre_path, nrows=15)
            word_list = df_fre.iloc[:, 0].astype(str).tolist()
            heat_list = pd.to_numeric(df_fre.iloc[:, 1], errors='coerce').fillna(0).astype(int).tolist()
            word_sent = {}
            if os.path.exists(sent_path):
                df_sent = pd.read_csv(sent_path)
                if 'word' in df_sent.columns and 'sentiment' in df_sent.columns:
                    word_sent = dict(zip(df_sent['word'].astype(str), df_sent['sentiment'].fillna("中性")))
            for w, h in zip(word_list, heat_list):
                hot_topics.append({
                    "keyword": w,
                    "heat": h,
                    "sentiment": word_sent.get(w, "中性")
                })
    except Exception as e:
        logger.warning(f"读取热词数据失败: {e}")
    use_data["hot_topics"] = hot_topics

    # 5. 评论数据
    user_comments = []
    try:
        raw_comments = getAllComment()
        if raw_comments and not isinstance(raw_comments, str):
            for c in raw_comments[:50]:
                if isinstance(c, dict):
                    user_comments.append({
                        "content": c.get("content", ""),
                        "likes": c.get("likes", 0)
                    })
                elif isinstance(c, (list, tuple)):
                    # getAllComment 返回 pymysql 行元组：评论ID|评论内容|评论时间|来源|点赞数|…
                    # （原实现仅判 dict，行元组永远不命中 → user_comments 恒为空，此处修正）
                    user_comments.append({
                        "content": str(c[1]) if len(c) > 1 else '',
                        "likes": c[4] if len(c) > 4 else 0
                    })
    except Exception as e:
        logger.warning(f"获取评论数据失败: {e}")
    use_data["user_comments"] = user_comments

    return use_data


# ===================== 核心大模型服务类 =====================
class XinghuoLLMService:
    def __init__(self):
        self.api_password = os.getenv("XINGHUO_API_PASSWORD")
        self.base_url = os.getenv("XINGHUO_BASE_URL", "https://spark-api-open.xf-yun.com/v1")
        self.model_name = os.getenv("XINGHUO_MODEL", "lite")

        self.client = None
        self.chat_histories = defaultdict(list)
        # 🌟 新增：用户画像字典（与 session_id 独立）
        self.user_profiles = defaultdict(lambda: {
            "weak_theories": [],
            "strong_theories": [],
            "total_interactions": 0
        })
        # 🌟 用户画像持久化（重启不丢失）
        self.user_profiles_path = os.path.join(root_dir, "user_profiles.json")
        self._load_user_profiles()
        self.DEBUG = True
        self._route_emb_cache = {}   # 语义路由 embedding 缓存（LRU 简化版）

        # ================= 🌟 双模型混合路由（hybrid / local / api）=================
        # hybrid：学科知识问答 → 本地微调模型（+RAG 证据）；复杂任务 → 星火 API；互为兜底
        # local ：全部走本地微调模型（旧 USE_FINETUNED_MODEL=true 行为）
        # api   ：全部走星火 API（旧默认行为）
        _routing = os.getenv("MODEL_ROUTING", "").strip().lower()
        if _routing not in ("hybrid", "local", "api"):
            _routing = "local" if os.getenv("USE_FINETUNED_MODEL", "false").lower() == "true" else "api"
        self.routing_mode = _routing
        self.use_finetuned = self.routing_mode in ("hybrid", "local")  # 本地模型是否参与
        # PRIMARY_BACKEND：hybrid 模式下学科问答的主/备顺序（默认星火为主，本地微调为辅）
        #   api   = 星火优先（云端生成，响应快；本地微调作兜底，断网/限流时自动切换）
        #   local = 本地微调优先（可离线 + RAG 教材溯源演示，但需在 GPU 上生成长文本，较慢）
        self.primary_backend = os.getenv("PRIMARY_BACKEND", "api").strip().lower()
        if self.primary_backend not in ("api", "local"):
            self.primary_backend = "api"
        logger.info(f" 学科问答主用后端（PRIMARY_BACKEND）：{self.primary_backend}")
        self.finetuned_model = None
        self._local_model_loaded = False  # 懒加载标记
        self._last_backend = "api"  # 记录最近一次 _call_llm 实际使用的后端
        # 星火为主（PRIMARY_BACKEND=api）：【不】在启动时预加载本地模型，
        # 避免 3GB 微调模型 + 嵌入 + 重排序同时占满物理内存/页面文件导致
        # Windows os error 1455（页面文件太小）进而进程崩溃（exit 139）。
        # 仅在星火 API 调用失败、需要本地兜底时才按需懒加载。
        self._eager_load_local = self.use_finetuned and self.primary_backend == "local"
        if self._eager_load_local:
            try:
                from finetuned_model import FineTunedModel
                self.finetuned_model = FineTunedModel()
                self._local_model_loaded = True
                logger.info(f" 双模型路由模式【{self.routing_mode} | 本地为主】：本地微调模型加载成功")
            except Exception as e:
                logger.error(f"加载本地模型失败: {e}")
                self.finetuned_model = None

        # ================= 🔧 语义路由引擎（SentenceTransformer）=================
        self.router_model = None
        if os.getenv("LITE_MODE") == "1":
            logger.info("LITE 模式：跳过语义路由本地模型，使用关键词路由")
        else:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(" 正在加载语义路由 Embedding 模型 (bge-large-zh)...")
                self.router_model = SentenceTransformer(
                    "BAAI/bge-large-zh-v1.5",
                    device="cpu"
                )
                _ = self.router_model.encode("test", normalize_embeddings=True)
                logger.info(" 语义路由 Embedding 模型初始化成功！")
            except Exception as e:
                logger.error(f" 语义路由嵌入模型加载失败: {e}，将降级使用关键词匹配。")
                # 修复：本行原先掉在 except 之外，导致无条件把 router_model 置空。
                # 后果是模型即使加载成功也会被立刻丢弃，第 266 行的 `if self.router_model:`
                # 永远为假 -> semantic_routes / route_embeddings / route_indices 从未创建
                # -> _route_intent 永远走关键词分支，语义路由是死代码。
                self.router_model = None

        if self.router_model:
            self.semantic_routes = {
                "LITERATURE_GENERATION": [
                    "生成关于沉默螺旋的文献", "帮我写一篇文献综述", "关于议程设置的文献",
                    "生成文献综述", "写一份研究综述", "帮我整理相关文献",
                    "关于信息茧房的学术综述", "生成开题报告", "论文文献框架",
                    "帮我生成关于舆论极化的文献", "写一份关于沉默螺旋的文献综述",
                    "整理关于使用与满足的文献", "关于框架理论的学术综述",
                    "帮我查找相关文献", "有哪些关于这个主题的论文",
                    "生成关于群体极化的研究综述", "关于网络舆情的文献"
                ],
                "DATA_ANALYSIS_REPORT": [
                    "帮我分析一下最近的舆情数据", "生成一份完整的舆情报告",
                    "结合数据看看沉默的螺旋现象", "最近大家都不说话了，分析一下趋势",
                    "本次舆情的态势感知", "近7天的热词趋势是什么", "网络舆论极化分析",
                    "分析一下舆情态势", "生成分析报告", "分析近期舆情走势",
                    "统计一下发帖量", "看看数据报告", "舆情态势分析", "生成数据分析报告"
                ],
                "GENERAL_QA": [
                    "今天天气怎么样", "你好", "什么是新闻传播学", "推荐几本书",
                    "随便聊聊", "你是谁", "讲个笑话", "系统使用说明"
                ]
            }

            self.route_names = list(self.semantic_routes.keys())
            all_examples = [item for sublist in self.semantic_routes.values() for item in sublist]
            self.route_embeddings = self.router_model.encode(
                all_examples,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            self.route_indices = []
            start_idx = 0
            for name in self.route_names:
                count = len(self.semantic_routes[name])
                self.route_indices.append((start_idx, start_idx + count))
                start_idx += count
        else:
            self.semantic_routes = None
            self.route_embeddings = None
            self.route_indices = None

        # ================= 🌟 轻量级视觉预处理引擎 (RapidOCR) =================
        self.ocr_engine = None
        if HAS_OCR:
            try:
                logger.info(" 正在初始化 RapidOCR 视觉预处理引擎...")
                self.ocr_engine = RapidOCR()
                logger.info(" RapidOCR 初始化成功！图片分析已切换为 OCR+LLM 模式，内存占用极低。")
            except Exception as e:
                logger.error(f" RapidOCR 初始化失败: {e}")
                logger.warning("[WARN] 图片分析功能将不可用，请检查 rapidocr_onnxruntime 是否正确安装。")
        else:
            logger.warning("[WARN] RapidOCR 未安装，图片分析功能不可用。")

        # 🌟 学科理论白名单（已扩展至15个理论）
        self.TEACHING_THEORY_WHITELIST = """【新闻传播学核心理论索引（唯一允许引用源）】
[1] 议程设置理论 (Agenda-Setting)：McCombs & Shaw (1972)，媒体通过报道频次影响公众对议题重要性的认知排序。
[2] 沉默的螺旋 (Spiral of Silence)：Noelle-Neumann (1974)，个体因害怕孤立而倾向于表达主流意见，导致少数意见沉默。
[3] 使用与满足 (Uses and Gratifications)：Katz et al. (1973)，受众主动选择媒介以满足特定需求（认知、情感、社交等）。
[4] 框架理论 (Framing)：Goffman (1974)，媒体通过选择、强调、排除等方式建构现实，影响受众解读。
[5] 群体极化 (Group Polarization)：Sunstein (2002)，同质化群体讨论后观点趋向极端化。
[6] 培养理论 (Cultivation Theory)：Gerbner (1976)，长期媒介接触塑造受众对现实世界的认知。
[7] 创新扩散理论 (Diffusion of Innovations)：Rogers (1962)，新事物通过社会系统传播的过程与采纳者分类。
[8] 知沟理论 (Knowledge Gap)：Tichenor et al. (1970)，社会经济地位较高者比低者更快获取大众媒介信息，导致知识差距扩大。
[9] 数字鸿沟 (Digital Divide)：NTIA (1999)，不同群体在信息通信技术获取、使用和素养上的差距。
[10] 第三人效果 (Third-Person Effect)：Davison (1983)，人们倾向于认为媒介信息对他人的影响大于对自己的影响。
[11] 媒介依赖理论 (Media Dependency Theory)：Ball-Rokeach & DeFleur (1976)，社会越复杂，个人越依赖媒介来获取信息。
[12] 把关人理论 (Gatekeeping)：White (1950)，媒介组织通过对信息筛选、过滤来设置公众议程。
[13] 两级传播 (Two-Step Flow)：Lazarsfeld et al. (1944)，信息从大众媒介经由意见领袖再流向普通受众。
[14] 涵化分析 (Cultivation Analysis) 补充说明：Gerbner 的涵化理论，长期观看电视导致人们对社会现实的认知趋于一致。
[15] 选择性接触 (Selective Exposure)：Hyman & Sheatsley (1947)，个体倾向于接触与自身观点一致的信息，避免对立信息。
⚠️ 铁律：仅允许引用上述 [1]-[15]，严禁自行补充其他理论、学者或案例！超出范围请回复"该理论暂未纳入当前教学理论库，建议查阅《传播学教程》（郭庆光著）或相关核心教材。" """

        # 🌟 理论关键词 → 白名单编号映射（供按需注入，压缩 prompt 长度）
        self._THEORY_KEYWORDS = [
            ("1", ["议程设置"]), ("2", ["沉默的螺旋", "沉默螺旋"]),
            ("3", ["使用与满足"]), ("4", ["框架理论", "框架"]),
            ("5", ["群体极化"]), ("6", ["培养理论"]),
            ("7", ["创新扩散"]), ("8", ["知沟"]),
            ("9", ["数字鸿沟"]), ("10", ["第三人效果", "第三人"]),
            ("11", ["媒介依赖"]), ("12", ["把关人", "把关"]),
            ("13", ["两级传播", "意见领袖"]), ("14", ["涵化分析", "涵化"]),
            ("15", ["选择性接触", "选择性"]),
        ]

        # 流域作用域：由服务端按当前专题强制注入；模型不传、也无法绕过（见 _execute_single_tool）
        self._basin_scope = {}

        # 平台枚举参数（流域不交给模型选择）
        _PLAT = {"type": "string", "enum": ["微博", "小红书", "知乎", "抖音"],
                 "description": "要查询的平台；不填默认微博"}

        # 工具定义
        self.tools = [
            {"type": "function",
             "function": {"name": "getTotalArticle",
                          "description": "【必备工具】获取本地实时数据库中帖子/文章的总数量。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getTopAuthor",
                          "description": "【必备工具】获取数据库中点赞数最高、影响力最大的作者/博主信息。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getTopRegion",
                          "description": "【必备工具】获取数据库中发帖数量最多（声量最高）的省份/地区。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getArticleTopZan",
                          "description": "【必备工具】获取数据库中点赞数最高、传播最广的高赞帖子列表。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "get7DayArticle",
                          "description": "【核心趋势工具】获取本地数据库中近 7 天的最新发帖数量趋势。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getArticleTypeAmount",
                          "description": "【必备工具】获取数据库中帖子的分类或类型统计。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getTopCommentUser",
                          "description": "【必备工具】获取数据库中评论次数最多的高频评论用户。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getAllComment",
                          "description": "【必备工具】获取数据库中最新的评论列表。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getCommentAmount",
                          "description": "【趋势工具】获取最近 7 天每天的评论条数（用来看评论趋势；不是评论总量）。",
                          "parameters": {"type": "object", "properties": {"platform": _PLAT}, "required": []}}},
            {"type": "function",
             "function": {"name": "getCommentHotWordAmount",
                          "description": "【核心趋势工具】获取特定关键词在近7天内的评论数量趋势。",
                          "parameters": {"type": "object", "properties": {
                              "word": {"type": "string", "description": "要查询的关键词"},
                              "platform": _PLAT},
                                         "required": ["word"]}}},
            {"type": "function",
             "function": {"name": "getCommentByHotWord",
                          "description": "【必备工具】获取包含特定关键词的具体最新评论原文。",
                          "parameters": {"type": "object", "properties": {
                              "word": {"type": "string", "description": "要查询的关键词"},
                              "platform": _PLAT},
                                         "required": ["word"]}}},
            {"type": "function",
             "function": {"name": "getBasinHotEvents",
                          "description": "【必备工具】获取当前流域的热点事件簇、热词与代表性内容。"
                                         "当用户询问「本流域有哪些热点事件/话题/事件类型」时使用"
                                         "（流域由系统按当前专题自动限定，无需传参）。",
                          "parameters": {"type": "object", "properties": {}, "required": []}}},
        ]

        self.tool_map = {
            "getTotalArticle": lambda p: {"帖子总数": getTotalArticle(p.get('platform', '微博'), p.get('basin'))},
            "getTopAuthor": lambda p: {"最高点赞作者": getTopAuthor(p.get('platform', '微博'), p.get('basin'))},
            "getTopRegion": lambda p: {"最高声量省份": getTopRegion(p.get('platform', '微博'), p.get('basin'))},
            "getArticleTopZan": lambda p: {"高赞帖子": getArticleTopZan(p.get('platform', '微博'), p.get('basin'))},
            "get7DayArticle": lambda p: {"近 7 天发帖量": get7DayArticle(p.get('platform', '微博'), p.get('basin'))},
            "getArticleTypeAmount": lambda p: {"帖子分类统计": getArticleTypeAmount(p.get('platform', '微博'), p.get('basin'))},
            "getTopCommentUser": lambda p: {"高频评论用户": getTopCommentUser(p.get('platform', '微博'), p.get('basin'))},
            "getAllComment": lambda p: {"最新评论": getAllComment(200, p.get('platform', '微博'), p.get('basin'))},
            "getCommentAmount": lambda p: {"近 7 天评论量": getCommentAmount(p.get('platform', '微博'), p.get('basin'))},
            "getCommentHotWordAmount": lambda p: {
                f"热词 [{p.get('word', '')}]7 天趋势": getCommentHotWordAmount(
                    p.get('word', ''), p.get('platform', '微博'), p.get('basin'))},
            "getCommentByHotWord": lambda p: {
                f"包含 [{p.get('word', '')}] 的评论": getCommentByHotWord(
                    p.get('word', ''), p.get('platform', '微博'), p.get('basin'))},
            "getBasinHotEvents": lambda p: {"流域热点事件": getBasinHotEvents(p.get('basin'))},
        }

        if not self.api_password:
            logger.warning("[WARN] 未在 .env 中找到 XINGHUO_API_PASSWORD，大模型服务将处于离线状态！")
        else:
            try:
                self.client = OpenAI(api_key=self.api_password, base_url=self.base_url)
                logger.info(f" 星火大模型 HTTP 服务初始化成功！(模型：{self.model_name})")
            except Exception as e:
                logger.error(f" 星火大模型客户端初始化失败：{e}")

        _test_rule = self._get_required_elements("麦克卢汉 信息茧房")
        if "forbidden_theories" in _test_rule:
            logger.info(" [v20241025-FINAL] 新版规则引擎校验通过！禁用理论检测 + 强制路由已激活。")
        else:
            logger.error(" [vOLD] 警告：当前运行的仍是旧版代码！请检查部署路径或重启服务。")

    def _release_rag_gpu(self):
        """本地模型生成前，把 RAG 侧的 Embedding/Reranker 临时挪到 CPU 腾显存。"""
        try:
            if rag_db is not None and hasattr(rag_db, "release_gpu"):
                rag_db.release_gpu()
        except Exception as e:
            logger.warning(f"[WARN] 释放检索模型显存失败（忽略，继续生成）: {e}")

    def _release_local_gpu(self):
        """本地生成结束后回收显存，并把检索模型还原到 GPU。"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        try:
            if rag_db is not None and hasattr(rag_db, "resume_gpu"):
                rag_db.resume_gpu()
        except Exception as e:
            logger.warning(f"[WARN] 还原检索模型到 GPU 失败（下次检索会自动重建）: {e}")

    def _get_matched_theory_whitelist(self, text: str) -> str:
        """🌟 按需注入理论白名单（prompt 瘦身）：仅保留问题命中的理论条目。
        一条都未命中时才回退全量白名单，保证理论引用规范不受影响。"""
        ids = [tid for tid, kws in self._THEORY_KEYWORDS
               if any(k in text for k in kws)]
        if not ids:
            return self.TEACHING_THEORY_WHITELIST
        lines = self.TEACHING_THEORY_WHITELIST.splitlines()
        picked = [lines[0]]
        for ln in lines[1:]:
            if any(ln.startswith(f"[{tid}]") for tid in ids):
                picked.append(ln)
        picked.append("⚠️ 铁律：仅允许引用上述列出的理论条目，严禁自行补充其他理论、学者或案例！"
                      "超出范围请回复「该理论暂未纳入当前教学理论库，建议查阅《传播学教程》（郭庆光著）或相关核心教材。」")
        return "\n".join(picked)

    def _ensure_local_model(self):
        """🌟 按需懒加载本地微调模型（仅星火为主且 API 兜底时才触发）。
        星火为主模式不在启动时预加载，避免 3GB 模型 + 嵌入 + 重排序同时占满
        页面文件导致 Windows os error 1455（页面文件太小）乃至进程崩溃（exit 139）。"""
        if self.finetuned_model is not None or not self.use_finetuned:
            return self.finetuned_model
        if self._local_model_loaded:
            return self.finetuned_model
        try:
            from finetuned_model import FineTunedModel
            self.finetuned_model = FineTunedModel()
            self._local_model_loaded = True
            logger.info("[STAR] 本地微调模型按需加载成功（星火兜底已就绪）")
        except Exception as e:
            logger.error(f"按需加载本地模型失败，仅使用星火 API: {e}")
            self.finetuned_model = None
        return self.finetuned_model

    def _call_llm(self, messages, temperature=0.7, max_tokens=4096, prefer="api", **kwargs):
        """统一LLM调用：双模型混合路由（带指数退避重试 + 双向兜底）
        prefer="local"：优先本地微调模型（学科知识问答场景）
        prefer="api"  ：优先星火 API（Agent 工具调用 / 报告等复杂任务）
        hybrid 模式下一方失败自动降级另一方，保证服务可用性。"""
        # 路由模式修正：api/local 模式不分流
        if self.routing_mode == "local":
            prefer = "local"
        elif self.routing_mode == "api":
            prefer = "api"
        if prefer == "local" and not self.finetuned_model:
            # 星火为主模式：本地模型未预加载，尝试按需懒加载；失败则降级 API
            if self.use_finetuned:
                self._ensure_local_model()
            if not self.finetuned_model:
                prefer = "api"

        # 构造后端尝试顺序（hybrid 互为兜底）
        order = [prefer]
        if self.routing_mode == "hybrid":
            order.append("api" if prefer == "local" else "local")

        last_err = None
        for backend in order:
            if backend == "local":
                if not self.finetuned_model and self.use_finetuned:
                    self._ensure_local_model()
                if not self.finetuned_model:
                    continue
                try:
                    # 生成前把 Embedding/Reranker 临时挪到 CPU：8GB 卡上三个模型同时驻留
                    # 会溢出，生成耗时从 6 秒劣化到 80+ 秒甚至卡死
                    self._release_rag_gpu()
                    ans = self.finetuned_model.generate(
                        messages, max_tokens=min(max_tokens, 512), temperature=temperature)
                    self._last_backend = "local"
                    return ans
                except Exception as e:
                    last_err = e
                    logger.warning(f"本地微调模型调用失败，尝试降级: {e}")
                finally:
                    # 无论成功失败都回收显存并还原检索模型，保证下一轮检索不受影响
                    self._release_local_gpu()
            else:
                if not self.client:
                    continue
                last_err = None
                for attempt in range(3):
                    try:
                        resp = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                        self._last_backend = "api"
                        return resp.choices[0].message.content or ""
                    except Exception as e:
                        last_err = e
                        err_str = str(e)
                        # 审核/鉴权/参数类错误不重试
                        if any(code in err_str for code in ["SuspectedResult", "10013", "10014", "10019", "400", "401", "402"]):
                            break
                        if attempt < 2:
                            time.sleep(1.5 * (attempt + 1))
        if last_err:
            raise last_err
        raise RuntimeError("无可用大模型后端（本地微调模型与星火 API 均未就绪）")

    @staticmethod
    def _detect_prompt_injection(message: str) -> bool:
        """检测提示词注入：忽略指令 / 扮演系统 / 越狱等模式"""
        patterns = [
            r"忽略(上面|以上|之前|所有).{0,10}(指令|要求|规则|提示|内容)",
            r"无视(上面|以上|之前|所有).{0,10}(指令|要求|规则|提示|内容)",
            r"不(要|必)遵守(上面|以上|之前).{0,10}(指令|要求|规则)",
            r"(扮演|假装|模拟|你现在是).{0,10}(系统|管理员|admin|assistant)",
            r"system prompt|jailbreak|越狱|绕过.{0,6}(限制|审查|审核)",
            r"泄露.{0,6}(系统提示|system prompt|你的指令)",
            r"重复(上面|以上).{0,10}(内容|指令|话)",
        ]
        for pat in patterns:
            if re.search(pat, message, re.IGNORECASE):
                return True
        return False

    def _rewrite_query(self, message: str) -> list:
        """查询改写：仅对复杂问题生成 1 个子查询，避免普通问题引入额外延迟"""
        complex_kws = ["分析", "论述", "综合", "机制", "影响", "如何", "为什么",
                       "结合", "比较", "区别", "联系", "阐述", "探讨", "综述"]
        if not self.client or len(message) < 10 or not any(k in message for k in complex_kws):
            return []
        prompt = f"""你是检索专家。请把下面的用户问题改写为 1 个更适合知识库检索的查询（更具体、包含学科术语），只输出这一行查询：
问题：{message}"""
        try:
            resp = self._call_llm([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=120)
            line = resp.strip().lstrip(" -0123456789.、").strip()
            return [line] if 2 <= len(line) <= 100 else []
        except Exception as e:
            logger.warning(f"查询改写失败: {e}")
            return []

    def _sanitize_text(self, text: str, deep_mode: bool = False) -> str:
        if not text:
            return text

        sanitize_map = {
            r"舆论控制": "议程引导", r"洗脑": "共识建构", r"翻墙": "跨境信息获取",
            r"网军": "协同传播节点", r"水军": "协同传播节点", r"删帖": "内容合规治理",
            r"封号": "内容合规治理",
            r"AIGC造假": "生成式内容失真", r"AI造假": "生成式内容失真", r"深度伪造": "合成媒体技术",
            r"造谣": "未经证实信息传播",
            r"暴乱": "社会秩序事件", r"敏感事件": "特定公共事件",
            r"抗议": "群体表达", r"示威": "集体表达",
            r"性": "性别",
        }

        if deep_mode:
            sanitize_map.update({
                r"群体性事件": "突发公共事件",
                r"舆情危机": "传播现象",
                r"导火索": "触发因素",
            })

        for pattern, repl in sanitize_map.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

        # PII 脱敏：手机号 / 身份证 / 邮箱
        text = re.sub(r'1[3-9]\d{9}', '[手机号已脱敏]', text)
        text = re.sub(r'\d{17}[\dXx]', '[身份证已脱敏]', text)
        text = re.sub(r'[\w.+-]+@[\w-]+\.[\w.]+', '[邮箱已脱敏]', text)

        text = re.sub(
            r'[^\u4e00-\u9fa5a-zA-Z0-9\s.,;:!?\'"()\-_\[\]#*|`~{}=+《》【】（），。？！；：""''、\n\r]',
            '', text
        )

        if deep_mode:
            logger.info(" 深度脱敏模式已激活，文本已进行学术安全处理。")
        return text

    def _route_intent(self, user_message: str) -> str:
        theory_names = [
            "议程设置", "沉默的螺旋", "使用与满足", "框架理论", "群体极化",
            "培养理论", "创新扩散", "知沟", "数字鸿沟", "第三人效果",
            "媒介依赖", "把关人", "两级传播", "涵化", "选择性接触",
            "沉默螺旋", "议程设置理论", "涵化分析", "信息茧房", "拟态环境",
            "意见领袖", "回音室效应", "过滤气泡"
        ]
        if any(t in user_message for t in theory_names):
            return "GENERAL_QA"
        REPORT_KEYWORDS = [
            "生成舆情报告", "写舆情报告", "生成报告", "生成分析报告",
            "舆情报告", "舆情简报", "舆情总结"
        ]
        if any(kw in user_message for kw in REPORT_KEYWORDS):
            logger.info(" 强匹配报告关键词，直接路由到 DATA_ANALYSIS_REPORT")
            return "DATA_ANALYSIS_REPORT"

        if not self.router_model:
            literature_keywords = ["文献综述", "文献", "研究综述", "学术综述",
                                   "开题报告", "论文框架", "查找相关论文", "整理文献"]
            if any(kw in user_message for kw in literature_keywords):
                return "LITERATURE_GENERATION"

            data_analysis_keywords = ["舆情报告", "数据分析", "生成报告", "态势感知",
                                      "统计", "发帖量", "评论量", "趋势分析",
                                      "舆情数据", "分析报告", "完整报告", "舆情态势",
                                      "舆情走势", "数据报告"]
            if any(kw in user_message for kw in data_analysis_keywords):
                return "DATA_ANALYSIS_REPORT"

            return "GENERAL_QA"

        try:
            user_emb = self._route_emb_cache.get(user_message)
            if user_emb is None:
                user_emb = self.router_model.encode(
                    [user_message],
                    normalize_embeddings=True
                )[0]
                if len(self._route_emb_cache) > 512:
                    self._route_emb_cache.clear()
                self._route_emb_cache[user_message] = user_emb
            route_scores = {}
            for i, (start, end) in enumerate(self.route_indices):
                route_name = self.route_names[i]
                examples_emb = self.route_embeddings[start:end]
                if np is not None:
                    scores = [np.dot(user_emb, ex) for ex in examples_emb]
                else:
                    scores = [sum(a * b for a, b in zip(user_emb, ex)) for ex in examples_emb]
                route_scores[route_name] = max(scores)

            sorted_routes = sorted(route_scores.items(), key=lambda x: x[1], reverse=True)
            top_route, top_score = sorted_routes[0]
            second_route, second_score = sorted_routes[1] if len(sorted_routes) > 1 else ("NONE", 0.0)
            if re.search(
                    r'^(你好|嗨|hi|hello|你是谁|你叫什么|你是什么|你是什么模型|你是什么AI|你是什么大模型|你是AI|你是机器人|介绍一下自己|帮我介绍一下|what is your name|谁是你|讲个笑话|随便聊聊)',
                    user_message, re.IGNORECASE):
                logger.info(" 检测到问候/自我介绍，直接返回 GENERAL_QA")
                return "GENERAL_QA"
            if top_route == "GENERAL_QA":
                data_keywords = ["数据", "报告", "趋势", "统计", "舆情", "分析", "发帖量", "评论量", "热词"]
                if not any(kw in user_message for kw in data_keywords):
                    logger.info(f" 向量初筛 GENERAL_QA，且无数据分析关键词，直接返回")
                    return "GENERAL_QA"

            CONFUSION_THRESHOLD = 0.60
            MARGIN_THRESHOLD = 0.05
            is_confused = (top_score < CONFUSION_THRESHOLD) or (top_score - second_score < MARGIN_THRESHOLD)

            if is_confused and top_route != "GENERAL_QA":
                candidates = [r[0] for r in sorted_routes[:2] if r[0] != "GENERAL_QA"]
                if not candidates:
                    candidates = [top_route]
                logger.info(f"[WARN] 进入混淆区，启动 LLM 仲裁！")
                final_intent = self._llm_intent_arbitrator(user_message, candidates)
                return final_intent

            if top_score < 0.45:
                # 【可观测性】此处是最大的一处"短路到兜底类"：低相似度一律判 GENERAL_QA。
                # 阈值本身未改动（改它会直接改变路由行为，需先用数据说话），
                # 但补上 WARNING 级日志，使「GENERAL_QA 占比」可被 grep 统计：
                #     grep "低分降级" <日志文件> | wc -l
                # 若该占比过高，说明 GENERAL_QA 变成了万能「其他」桶，
                # 应先扩 route 示例语料或重训 router，而不是调阈值。
                logger.warning(f"低分降级 GENERAL_QA: top={top_route} score={top_score:.3f} "
                               f"input={user_message[:30]!r}")
                return "GENERAL_QA"
            logger.info(f" 向量初筛直接命中: 【{top_route}】 (得分: {top_score:.3f})")
            return top_route
        except Exception as e:
            logger.warning(f"语义路由计算出错: {e}，降级为 GENERAL_QA")
            return "GENERAL_QA"

    def _llm_intent_arbitrator(self, user_message: str, candidates: list) -> str:
        if not self.client:
            return candidates[0]
        intent_descriptions = {
            "LITERATURE_GENERATION": "文献综述/学术综述生成",
            "DATA_ANALYSIS_REPORT": "舆情数据分析",
            "GENERAL_QA": "通用问答"
        }
        candidate_desc = "\n".join([f"{i+1}. {c}: {intent_descriptions.get(c, '其他')}" for i, c in enumerate(candidates)])
        prompt = f"""你是一个意图分类器。请根据用户的输入，从以下候选意图中选出最匹配的一个。
只允许回复意图的英文代码（如 DATA_ANALYSIS_REPORT），不要有任何其他废话。

候选意图：
{candidate_desc}

用户输入："{user_message}"

最匹配的意图代码是："""
        try:
            response = self._call_llm([{"role": "system", "content": "你是一个精准的意图分类器，只输出英文代码。"},
                          {"role": "user", "content": prompt}], temperature=0.0, max_tokens=20)
            # 【修复】原实现只做 strip() 与去掉 "。"、"."，模型若返回
            #   " DATA_ANALYSIS_REPORT"、"DATA_ANALYSIS_REPORT\n"、加粗或带解释的整句，
            #   都不在 candidates 里，会**静默降级到 candidates[0]**——
            #   即"分类结果被短路到默认类"的典型成因。
            #   现改为：先做宽松归一化（去空白/换行/中英文标点/引号/括号）精确比对；
            #   若模型回了整句话，则退化为"候选代码在串中出现且唯一"的容错解析；
            #   两者都失败才降级，并打 WARNING 日志（降级率可 grep 统计）。
            norm = re.sub(r'[\s\u3000。，,、.：:；;"\'`【】\[\]（）()*#]+', '', response or '').upper()
            for c in candidates:
                if norm == c.upper():
                    return c
            hits = [c for c in candidates if c.upper() in norm]
            if len(hits) == 1:
                logger.info(f"LLM 仲裁返回非规范串，已容错解析为 【{hits[0]}】: {response!r}")
                return hits[0]
            logger.warning(f"LLM 仲裁无法映射到候选：候选={candidates} 原始返回={response!r}，"
                           f"降级返回第一候选 {candidates[0]}")
            return candidates[0]
        except Exception as e:
            logger.error(f"LLM 仲裁失败: {e}，降级返回第一候选 {candidates[0]}")
            return candidates[0]

    def _execute_single_tool(self, func_name, args, basin=None):
        """执行工具调用。basin 为服务端按当前专题强制注入的流域，
        会**覆盖**模型可能传入的任何流域参数，确保数据不跨专题泄露。"""
        if func_name in self.tool_map:
            try:
                call_args = dict(args) if isinstance(args, dict) else {}
                if basin:
                    call_args['basin'] = basin        # 强制覆盖，模型绕不过
                else:
                    call_args.pop('basin', None)      # 非专题场景不允许模型自选流域
                res = self.tool_map[func_name](call_args)
                return json.dumps(res, ensure_ascii=False, default=str)
            except Exception as e:
                logger.error(f"工具 {func_name} 执行出错：{e}")
                return json.dumps({"error": f"工具执行失败：{str(e)}"}, ensure_ascii=False)
        else:
            logger.warning(f"未知工具调用：{func_name}")
            return json.dumps({"error": f"未知工具：{func_name}"}, ensure_ascii=False)

    def _retrieve_few_shot_examples(self, user_message: str, top_k: int = 3) -> str:
        examples_path = os.path.join(root_dir, "knowledge", "few_shot_examples.json")
        try:
            with open(examples_path, 'r', encoding='utf-8') as f:
                examples = json.load(f)
        except Exception:
            logger.warning("[WARN] Few-shot 示例库未找到或格式错误，将跳过 Few-shot 注入")
            return ""

        scored = []
        for ex in examples:
            keywords = ex.get("keywords", [])
            score = sum(1 for kw in keywords if kw in user_message)
            scored.append((score, ex))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_examples = [ex for s, ex in scored[:top_k] if s > 0]

        if not top_examples:
            return ""

        few_shot_prompt = "【专业回答范例】\n"
        for i, ex in enumerate(top_examples):
            few_shot_prompt += f"示例{i+1}：\n问：{ex['question']}\n答：{ex['answer']}\n\n"
        few_shot_prompt += "请参照上述示例的专业性和引用格式，回答以下问题：\n\n"

        return few_shot_prompt

    def _is_complex_query(self, user_message: str) -> bool:
        complex_keywords = [
            "分析", "论述", "比较", "机制", "原因", "影响", "综合",
            "如何", "为什么", "谈谈", "阐述", "揭示", "探讨",
            "结合", "基于", "关系", "区别", "联系"
        ]
        return any(kw in user_message for kw in complex_keywords)

    def _is_discipline_qa(self, user_message: str, intent: str = "GENERAL_QA") -> bool:
        """学科知识问答判定：适合交给本地微调模型（叠加 RAG 证据）回答的场景。
        判定标准：涉及学科理论关键词 + 问答式提问 + 非复杂多步任务。"""
        if intent in ("DATA_ANALYSIS_REPORT", "LITERATURE_GENERATION"):
            return False
        theory_kw = [
            "议程设置", "沉默的螺旋", "使用与满足", "框架理论", "群体极化",
            "培养理论", "创新扩散", "知沟", "数字鸿沟", "第三人效果",
            "媒介依赖", "把关人", "两级传播", "涵化", "选择性接触",
            "拟态环境", "信息茧房", "意见领袖", "麦克卢汉", "李普曼",
            "媒介即讯息", "舆论", "传播学"
        ]
        qa_kw = ["是什么", "什么是", "谁提出", "提出者", "提出", "解释", "含义", "概念",
                 "定义", "内涵", "指什么", "简述", "介绍", "说说", "是什么意思"]
        has_theory = any(t in user_message for t in theory_kw)
        has_qa = any(k in user_message for k in qa_kw) or user_message.rstrip().endswith(("？", "?"))
        return (has_theory and has_qa
                and len(user_message) <= 80
                and not self._is_complex_query(user_message))

    def _format_agent_observation(self, tool_name: str, observation_str: str) -> str:
        try:
            data = json.loads(observation_str)
        except Exception:
            return observation_str

        if isinstance(data, list):
            return observation_str

        if isinstance(data, dict):
            if len(data) == 1:
                key, value = next(iter(data.items()))
                if isinstance(value, (list, int, float, str)):
                    return json.dumps(value, ensure_ascii=False)
            simplified = {}
            for k, v in data.items():
                if isinstance(v, (list, tuple)) and len(v) > 10:
                    simplified[k] = f"共{len(v)}条记录，前5条: {v[:5]}"
                else:
                    simplified[k] = v
            return json.dumps(simplified, ensure_ascii=False)

        return observation_str

    def _solve_complex_query_agent(self, user_message: str, session_id: str) -> dict:
        tool_descriptions = []
        for t in self.tools:
            fn = t.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            tool_descriptions.append(f"- {name}: {desc}")
        tools_str = "\n".join(tool_descriptions)

        system_prompt = f"""你是一个能够使用工具解决问题的智能助手。你必须严格遵循以下格式，不能添加任何额外解释。

【可用工具】
{tools_str}

【格式】
Question: 用户问题
Thought: 分析需要做什么
Action: 工具名称（只写名称，不要加额外文字）
Action Input: JSON 参数，如果不需要参数则写 {{}}

（此时你必须停止，等待系统返回 Observation）

Observation: 工具执行结果

（你可以继续输出 Thought/Action，或输出最终答案）

Final Answer: 必须包含从 Observation 中获取的具体数值，并用它们进行详细分析。不得说“没有数据”。

【示例】
Question: 最近一周发帖趋势如何？
Thought: 我需要获取近7天的发帖数据。
Action: get7DayArticle
Action Input: {{}}
Observation: [["2026-07-22", 120], ["2026-07-23", 135], ["2026-07-24", 150], ["2026-07-25", 145], ["2026-07-26", 160], ["2026-07-27", 155], ["2026-07-28", 140]]
Thought: 根据数据，发帖量从120增长到140左右，呈上升趋势。
Final Answer: 近一周（7月22日至28日）发帖量总体上升，从120条增至140条，期间有小幅波动。

【重要指导】
1. 你必须从多个角度分析问题，尽可能调用多个相关工具（如 getCommentAmount, getArticleTypeAmount, getCommentHotWordAmount 等）获取多维度数据。
2. 在 Final Answer 中，必须包含：
   - **数据总结**：列出关键数字和趋势；
   - **理论联系**：如果问题涉及传播学理论（如沉默螺旋、议程设置等），请明确引用并解释数据如何支持或反驳该理论；
   - **深入分析**：探讨数据背后的可能原因、影响、局限性；
   - **结论与建议**：基于数据给出明确判断和下一步建议。
3. 回答长度应不少于 300 字，条理清晰，使用 Markdown 分段。
4. 当用户问题涉及“沉默螺旋”、“舆论极化”、“回音室”等概念时，你不仅应获取发帖趋势，还应调用 getCommentAmount、getCommentByHotWord（如“负面”、“反对”、“沉默”）等工具，以获取情感倾向和具体评论。

【示例2】
Question: 结合近7天发帖数据，分析沉默的螺旋现象是否可能存在。
Thought: 我需要获取近7天的发帖趋势，同时查看评论情感分布，以便从多个角度分析沉默螺旋。
Action: get7DayArticle
Action Input: {{}}
Observation: [["2026-07-22", 120], ["2026-07-23", 135], ["2026-07-24", 150], ["2026-07-25", 145], ["2026-07-26", 160], ["2026-07-27", 155], ["2026-07-28", 140]]
Thought: 发帖量上升但增速放缓。为了进一步判断是否存在沉默螺旋，我需要了解评论情感倾向。
Action: getCommentAmount
Action Input: {{}}
Observation: {{"近 7 天评论量": 1890}}
Thought: 评论总量较大，但还需查看是否有负面关键词被压制。
Action: getCommentHotWordAmount
Action Input: {{"word": "反对"}}
Observation: {{"热词 [反对]7 天趋势": [2, 1, 0, 1, 0, 0, 0]}}
Thought: 反对关键词出现频率极低，结合发帖量上升，可推断主流意见占主导，少数意见沉默，符合沉默的螺旋理论[2]。
Final Answer: 近一周（7月22日至28日）发帖量从120条逐步增至140条，总体上升但幅度平稳；评论总量达到1890条，互动较为活跃。然而，反对性关键词“反对”在7天内仅出现4次，且逐日减少。这一数据组合表明：主流意见主导的讨论环境下，少数异见者倾向于保持沉默，即沉默的螺旋理论[2]所描述的“个体因害怕孤立而放弃表达”的现象正在显现。平台算法可能进一步强化了主流声音的可见性，导致少数观点被边缘化。未来需要结合更详细的情绪分析来验证这一趋势。该现象也提示我们，在社交媒体舆情监测中，不能仅看发帖量，还需要关注意见多样性。若持续缺乏异见，则可能造成群体极化[5]，需要采取引导措施促进多元表达。

现在开始！
Question: {user_message}
Thought:"""

        messages = [{"role": "system", "content": system_prompt}]
        max_iterations = 5
        iteration = 0
        final_answer = ""
        references = []
        last_observation = ""

        while iteration < max_iterations:
            iteration += 1
            try:
                full_output = self._call_llm(messages, temperature=0.1, max_tokens=4096)
            except Exception as e:
                logger.error(f"智能体调用 LLM 失败: {e}")
                break

            logger.info(f"[BOT] 模型输出: {full_output[:300]}...")
            messages.append({"role": "assistant", "content": full_output})

            final_answer_match = re.search(r'Final Answer:\s*(.*)', full_output, re.DOTALL)
            if final_answer_match:
                final_answer = final_answer_match.group(1).strip()
                break

            action_match = re.search(r'Action:\s*(.*?)(?=\n|$)', full_output)
            action_input_match = re.search(r'Action Input:\s*(.*?)(?=\n|$)', full_output)

            if action_match and action_input_match:
                raw_action = action_match.group(1).strip()
                possible_tools = [t["function"]["name"] for t in self.tools]
                tool_name = None
                if raw_action in possible_tools:
                    tool_name = raw_action
                else:
                    for t in possible_tools:
                        if t in raw_action:
                            tool_name = t
                            break
                if not tool_name:
                    logger.warning(f"[WARN] 无法从 Action 中提取有效工具名: {raw_action}")
                    messages.append({"role": "user",
                                     "content": f"Observation: 无法识别工具 '{raw_action}'，请只输出工具名称。"})
                    continue
                try:
                    tool_args = json.loads(action_input_match.group(1).strip())
                except Exception:
                    tool_args = {}
                logger.info(f" 准备调用工具: {tool_name}, 参数: {tool_args}")
                observation = self._execute_single_tool(tool_name, tool_args)
                observation_str_raw = json.dumps(observation, ensure_ascii=False)
                observation_str = self._format_agent_observation(tool_name, observation_str_raw)
                last_observation = observation_str
                logger.info(f" 工具返回(格式化后): {observation_str[:200]}...")

                truncated_output = full_output.split("Observation:")[0].strip()
                messages[-1] = {"role": "assistant", "content": truncated_output}
                messages.append({"role": "user", "content": f"Observation: {observation_str}"})
            else:
                logger.warning(f"[WARN] 未解析到有效 Action，模型输出: {full_output[:200]}")
                messages.append({"role": "user",
                                 "content": "Observation: 输出格式错误，请严格按照 Thought/Action/Action Input 或 Final Answer 格式输出。"})

        if not final_answer:
            messages.append({"role": "user", "content": "请根据以上分析，给出最终答案。"})
            try:
                final_answer = self._call_llm(messages, temperature=0.3, max_tokens=4096)
            except Exception as e:
                final_answer = "经过多步分析，但最终答案生成失败。"

        if not re.search(r'\d', final_answer) and last_observation:
            logger.info("[WARN] 最终答案未包含数据，触发强制数据重试...")
            force_prompt = f"""你的上一个回答没有包含从 Observation 中获取的具体数据。请重新回答，必须将以下 Observation 中的数值直接写出来，并结合它们进行分析。

Observation: {last_observation}

原始问题: {user_message}

最终答案（必须包含具体数字）："""
            try:
                final_answer = self._call_llm([{"role": "user", "content": force_prompt}], temperature=0.1, max_tokens=4096)
            except Exception as e:
                logger.error(f"强制重试失败: {e}")

        deep_analysis_keywords = ["分析", "机制", "影响", "原因", "关系", "演变", "趋势"]
        if any(kw in user_message for kw in deep_analysis_keywords):
            try:
                followup_prompt = f"""你是一位新闻传播学教授。根据下面的原始问题和回答，请提出 2 个值得进一步探讨的延伸问题，并对每个问题给出详细的分析和参考答案（每个答案不少于 150 字）。

原始问题：{user_message}
回答：{final_answer[:800]}

请按以下格式输出：
### 💡 延伸思考
**Q1: 问题内容**
**参考答案:** 详细解答（不少于 150 字）

**Q2: 问题内容**
**参考答案:** 详细解答（不少于 150 字）

最多输出 2 个问题，答案要结合传播学理论进行分析，可以引用新媒体案例。"""

                followup_text = self._call_llm([{"role": "system", "content": "你是一位严谨的新闻传播学教授，擅长深入浅出地分析问题。"},
                                          {"role": "user", "content": followup_prompt}], temperature=0.5, max_tokens=1024)
                followup_text = followup_text.strip()
                if followup_text and "延伸思考" in followup_text:
                    final_answer += "\n\n" + followup_text
            except Exception as e:
                logger.warning(f"生成延伸思考失败: {e}")

        return {"answer": final_answer, "references": references}

    def _analyze_image(self, image_path: str) -> str:
        """多模态图片理解：优先调用星火视觉模型（配置后启用），否则回退 OCR"""
        if not os.path.exists(image_path):
            return "⚠️ 图片路径无效"

        # 1) 真·视觉理解（若配置了视觉模型）
        vision = self._vision_analyze(image_path)
        if vision:
            return vision

        # 2) OCR 兜底
        if not self.ocr_engine:
            return "⚠️ OCR 引擎未就绪（且未配置视觉模型）"
        try:
            logger.info(f" 开始 OCR 识别: {os.path.basename(image_path)}")
            result, elapse = self.ocr_engine(image_path)
            if not result:
                return "⚠️ 图片中未识别到有效文字"
            lines = []
            for line in result:
                bbox, text, confidence = line
                try:
                    conf_display = f"{float(confidence):.0%}"
                except Exception:
                    conf_display = str(confidence)
                lines.append(f"[置信度{conf_display}] {text}")
            logger.info(f" OCR 识别完成，提取行数: {len(lines)}")
            return "【图片 OCR 提取内容】\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"OCR 出错: {e}")
            return f"⚠️ 图片解析失败: {str(e)}"

    def _vision_analyze(self, image_path: str):
        """调用视觉模型理解图片（通用：支持通义 qwen-vl 或星火视觉，通过环境变量配置）
        .env 配置（任选一组）：
          通义：VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
                VISION_API_KEY=你的DASHSCOPE_KEY   VISION_MODEL=qwen-vl-plus
          星火：XINGHUO_VISION_MODEL=你的视觉模型名
        """
        vision_model = os.getenv("VISION_MODEL", "") or os.getenv("XINGHUO_VISION_MODEL", "")
        vision_base = os.getenv("VISION_BASE_URL", self.base_url)
        vision_key = os.getenv("VISION_API_KEY", self.api_password)
        if not vision_model or not vision_key:
            return None
        try:
            import base64
            from openai import OpenAI as _VisionOpenAI
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            mime = mimetypes.guess_type(image_path)[0] or "image/png"
            data_url = f"data:{mime};base64,{b64}"
            vclient = _VisionOpenAI(api_key=vision_key, base_url=vision_base)
            resp = vclient.chat.completions.create(
                model=vision_model,
                messages=[{"role": "user", "content": [
                    {"type": "text",
                     "text": "请描述这张图片的内容：识别其中的文字、图表、公式或场景，并给出专业的新闻传播学视角解读。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]}],
                temperature=0.2, max_tokens=1024,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                logger.info(f"[OK] 视觉模型理解成功: {vision_model} @ {vision_base}")
                return "【图片视觉理解】\n" + content
        except Exception as e:
            logger.warning(f"视觉模型调用失败，回退 OCR: {e}")
        return None

    def _safe_parse_int(self, value) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        logger.debug(f"_safe_parse_int 收到非预期类型 {type(value)}，返回 0")
        return 0

    # ---------- 核心聊天方法 ----------
    def chat(self, user_message: str, session_id: str = "default", is_report_request: bool = False,
             image_path: str = None, user_id: str = None, mode: str = "strict", file_path: str = None,
             basin: str = None):
        t_chat_start = time.time()  # 🌟 阶段打点起点
        # 🌟 专题流域作用域：本会话锁定流域；工具取数时由服务端强制只取该流域
        if basin:
            self._basin_scope[session_id] = basin
        else:
            self._basin_scope.pop(session_id, None)

        # 🌟 专题隔离「硬闸」：提问中出现**另一条**流域名 → 直接拒答，不调 LLM。
        #   软提示（system_prompt）不可靠 —— 实测模型会拿本流域数据去顶替对方流域的问题
        #   （问"长江声量最高省份"却答"本流域为山东"），必须由服务端兜住。
        _b_now = self._basin_scope.get(session_id)
        if _b_now and user_message:
            _other = '长江' if _b_now == '黄河' else '黄河'
            if _other in user_message:
                return {"answer": (f"当前为{_b_now}流域专题，无法查询{_other}流域的数据；"
                                   f"跨流域对比请见首页「两流域核心指标对照」。"),
                        "references": []}

        if not self.client and not self.use_finetuned:
            return {"answer": "⚠️ 大模型服务未启动", "references": []}

        # 提示词注入检测
        if self._detect_prompt_injection(user_message):
            logger.warning("[WARN] 检测到疑似提示词注入，已拦截")
            return {"answer": "检测到可能存在提示词注入的请求，为保障系统安全已拦截。请以正常学术问题提问。",
                    "references": []}

        visual_context = ""
        if image_path:
            visual_desc = self._analyze_image(image_path)
            visual_context = f"\n【用户上传的图片内容分析】：\n{visual_desc}\n"

        # 处理上传的文档文件（PDF、Word、Excel等）
        file_context = ""
        if file_path and os.path.exists(file_path):
            try:
                from .file_parser import parse_file_to_text
                file_text = parse_file_to_text(file_path)
                file_name = os.path.basename(file_path)
                file_context = f"\n【用户上传的文件内容（{file_name}）】：\n{file_text[:8000]}\n"
            except Exception as e:
                logger.error(f"文件处理失败: {e}")
                file_context = f"\n文件处理失败：{e}\n"

        intent = self._route_intent(user_message)
        t_after_route = time.time()  # 🌟 打点：意图路由完成
        # 历史兼容位，恒定不激活
        is_teaching_request = False
        is_data_analysis_intent = (intent == "DATA_ANALYSIS_REPORT")
        is_literature_intent = (intent == "LITERATURE_GENERATION")

        # ---------- 🌟 双模型混合路由：本条请求优先使用的后端 ----------
        # 学科知识问答（简短理论概念/归属问题）→ 本地微调模型 + RAG 教材证据
        # 复杂任务（Agent 工具调用 / 报告 / 识图 / 文件）→ 星火 API
        prefer_local = (
            self.routing_mode == "hybrid"
            and self.finetuned_model is not None
            and self.primary_backend == "local"   # 仅配置 local 时学科问答才优先本地微调模型
            and not visual_context and not file_context
            and not is_report_request
            and not is_teaching_request
            and not is_data_analysis_intent
            and not is_literature_intent
            and self._is_discipline_qa(user_message, intent)
        )
        if prefer_local:
            logger.info(" 双模型路由：学科知识问答 → 本地微调模型（RAG 证据已注入知识库段落）")
        elif self._is_discipline_qa(user_message, intent) and self.routing_mode == "hybrid":
            logger.info(" 双模型路由：学科知识问答 → 星火 API 优先（RAG 证据已注入，本地微调作兜底）")

        # ---------- 文献综述生成 ----------
        if is_literature_intent:
            logger.info(" 文献综述生成意图")
            topic = re.sub(r"(生成|关于|的|文献|综述|一份|一篇|写|帮我|请|查找|整理|相关|学术)", "", user_message).strip()
            if not topic or len(topic) < 2:
                topic = user_message

            references = []
            rag_knowledge = ""
            try:
                rag_knowledge, rag_refs = get_knowledge_with_refs(f"{topic} 传播学", rag_db, top_k=10)
                rag_refs = rag_refs or []
                if rag_refs and rag_refs[0].get('score', -999) < RERANK_SOURCE_SCORE_FLOOR:
                    rag_knowledge = ""
                    rag_refs = []
                if rag_knowledge and len(rag_knowledge.strip()) > 15:
                    rag_knowledge = self._sanitize_text(rag_knowledge, deep_mode=False)
                references = rag_refs
            except Exception as e:
                logger.warning(f"RAG 检索异常: {e}")

            knowledge_section = ""
            if rag_knowledge and len(rag_knowledge.strip()) > 15:
                knowledge_section = f"【知识库资料】：\n{rag_knowledge[:3000]}"
            else:
                knowledge_section = "【知识库提示】：专题文献较少，请基于专业知识生成。"

            lit_prompt = f"""你是新闻传播学教授。用户要求生成关于「{topic}」的学术文献综述，并指定使用议程设置理论[1]和/或沉默的螺旋理论[2]。这些理论在核心理论白名单内，请放心使用，不得以任何理由回复“该理论暂未纳入当前教学理论库”。

{self.TEACHING_THEORY_WHITELIST}

{knowledge_section}

【输出结构要求】：
###  一、研究背景与问题提出
###  二、理论基础与核心概念（必须引用[1]和/或[2]）
###  三、已有研究成果综述
###  四、研究空白与未来展望
###  五、核心参考文献

【铁律】：
1. 必须引用理论[1]和/或[2]，正常生成完整综述。
2. 仅引用理论白名单 [1]-[15] 中的理论，不得编造理论名称。
3. 引用知识库中的真实文献时使用角标标注。
4. Markdown 格式，学术严谨，宁可简短也不虚构。"""

            messages = [{"role": "system", "content": "严谨的学术教授，不编造文献。"},
                        {"role": "user", "content": lit_prompt}]
            try:
                answer = self._call_llm(messages, temperature=0.3, max_tokens=4096)
                if not rag_knowledge or len(rag_knowledge.strip()) < 15:
                    answer += "\n\n> ⚠️ 当前知识库专题文献较少，建议补充原著及论文。"
                answer += "\n\n*⚠️ [AI生成标识] 仅供教学科研参考。*"
                self.chat_histories[session_id].append(HumanMessage(content=user_message))
                self.chat_histories[session_id].append(AIMessage(content=answer))
                if user_id:
                    self.user_profiles[user_id]["total_interactions"] += 1
                    self._save_user_profiles()
                return {"answer": answer, "references": references}
            except Exception as e:
                logger.error(f"文献综述生成失败: {e}")
                return {"answer": f" 生成失败：{str(e)}", "references": []}

        # ---------- 数据分析报告 ----------
        EXPLICIT_REPORT_KEYWORDS = ["生成报告", "写报告", "舆情报告", "分析报告", "舆情简报", "舆情总结"]
        if is_data_analysis_intent and not any(kw in user_message for kw in EXPLICIT_REPORT_KEYWORDS):
            logger.info(" 数据分析意图，但无明确报告关键词，转为复杂问题智能体处理")
            is_data_analysis_intent = False
        if is_data_analysis_intent:
            logger.info(" 检测到舆情报告生成请求，调用完整报告引擎...")
            try:
                from service.report_service import generate_full_report
            except ImportError as e:
                logger.error(f" 导入报告生成模块失败: {e}")
                return {"answer": "⚠️ 报告生成模块未就绪，请联系管理员。", "references": []}

            report_data = assemble_use_data()
            if not report_data or (not report_data.get("daily_trend") and not report_data.get("hot_topics")):
                logger.warning("[WARN] 舆情数据不完整，生成的报告可能缺乏部分内容")

            try:
                filepath = generate_full_report(report_data)
                report_filename = os.path.basename(filepath)
                answer = f" 完整舆情分析报告已生成！\n[REPORT_PATH:{report_filename}]"
                self.chat_histories[session_id].append(HumanMessage(content=user_message))
                self.chat_histories[session_id].append(AIMessage(content=answer))
                if user_id:
                    self.user_profiles[user_id]["total_interactions"] += 1
                    self._save_user_profiles()
                return {"answer": answer, "references": []}
            except Exception as e:
                logger.error(f" 生成报告失败: {e}")
                return {"answer": f" 报告生成失败：{str(e)}", "references": []}

        # ---------- 通用问答与理论场景 ----------
        if not is_report_request:
            is_report_request = any(kw in user_message for kw in ["生成报告", "舆情报告", "分析报告", "完整报告"])

        if not is_teaching_request and not is_data_analysis_intent and not is_literature_intent and not visual_context and not file_context and self._is_complex_query(user_message):
            logger.info(" 检测到复杂问题，启动多步推理智能体...")
            agent_result = self._solve_complex_query_agent(user_message, session_id)
            if agent_result is not None:
                answer = agent_result.get("answer", "")
                refs = agent_result.get("references", [])
                if len(answer) < 200:
                    refine_prompt = f"""你是一个传播学专家。用户的问题是：{user_message}
已有的初步分析如下：
{answer}

请将上述分析扩展为一篇内容充实、逻辑严谨的学术分析（不少于500字）。要求：
- 包含数据细节；
- 引用相关传播学理论（如沉默的螺旋、议程设置等），并使用角标[1]~[15]；
- 分析现象原因与影响；
- 给出明确的结论。
扩展后："""
                    try:
                        answer = self._call_llm([{"role": "user", "content": refine_prompt}], temperature=0.3, max_tokens=4096)
                    except Exception:
                        pass
                self.chat_histories[session_id].append(HumanMessage(content=user_message))
                self.chat_histories[session_id].append(AIMessage(content=answer))
                if user_id:
                    self.user_profiles[user_id]["total_interactions"] += 1
                    self._save_user_profiles()
                return {"answer": answer, "references": refs}

        safe_user_message = user_message
        references = []

        if is_teaching_request:
            safe_user_message = self._sanitize_text(user_message, deep_mode=True)
            if visual_context:
                visual_context = self._sanitize_text(visual_context, deep_mode=True)
            logger.info(" 理论场景：注入理论白名单 + RAG")
            knowledge = self._get_matched_theory_whitelist(user_message)
            if visual_context or file_context:
                # 多模态/文件场景：跳过 RAG 检索（图片内容即主要上下文），避免 CPU Reranker 卡顿
                references = []
            else:
                # 纯文字短请求（无检索意图）跳过 RAG：避免 CPU Reranker 卡顿，如"帮我总结内容"
                _short_skip = (len(user_message) < 15 and not any(kw in user_message for kw in
                  ["检索", "查找", "资料", "论文", "文献", "理论", "研究", "知识库", "根据"]))
                if _short_skip:
                    references = []
                else:
                    try:
                        theory_names = ["议程设置", "沉默的螺旋", "使用与满足", "框架理论", "群体极化",
                                        "培养理论", "创新扩散", "知沟", "数字鸿沟", "第三人效果",
                                        "媒介依赖", "把关人", "两级传播", "涵化", "选择性接触",
                                        "信息茧房", "拟态环境", "意见领袖"]
                        query = user_message
                        for t in theory_names:
                            if t in user_message:
                                query = f"{t} 理论 新媒体 传播机制"
                                break
                        rag_knowledge, rag_refs = get_knowledge_with_refs(query, rag_db, top_k=5)
                        rag_refs = rag_refs or []
                        if rag_refs and rag_refs[0].get('score', -999) < RERANK_SOURCE_SCORE_FLOOR:
                            rag_knowledge = ""
                            rag_refs = []
                        if rag_knowledge and len(rag_knowledge.strip()) > 15:
                            rag_knowledge = self._sanitize_text(rag_knowledge, deep_mode=True)
                            knowledge += "\n\n【学术知识库补充】：\n" + rag_knowledge
                        references = rag_refs
                    except Exception as e:
                        logger.warning(f"教学 RAG 异常: {e}")
        elif intent == "GENERAL_QA":
            # 🌟 自我介绍类问题 → 强制以新闻传播学垂直领域身份回答（绕过星火默认身份）
            if re.search(
                r'^(你是什么|你叫什么|你是谁|你是AI|你是机器人|你是什么模型|你是什么AI|你是什么大模型|介绍一下|帮我介绍|who are you|what are you)',
                user_message, re.IGNORECASE
            ):
                answer = (
                    "我是「新闻传播学垂直领域AI助手」，核心能力集中在新闻传播学（传播理论、新闻业务、新媒体、舆情分析）方向的知识问答、理论解释与学术引导。\n\n"
                    "底层由两个引擎协作：\n"
                    "• **星火大模型**（科大讯飞云端 API）：负责通用对话、报告生成等复杂任务；\n"
                    "• **本地微调模型**（Qwen2.5-1.5B + 新闻传播学 LoRA 适配器）：负责学科垂直问答，并结合 RAG 教材证据库降低幻觉。\n\n"
                    "如果你在问“我是不是星火”，答案是：星火是我的通用底座之一；但我的专业定位是新闻传播学，回答时会优先调用学科知识库与本地微调模型，而不是通用大模型的默认身份。"
                )
                self.chat_histories[session_id].append(HumanMessage(content=user_message))
                self.chat_histories[session_id].append(AIMessage(content=answer))
                if user_id:
                    self.user_profiles[user_id]["total_interactions"] = self.user_profiles[user_id].get("total_interactions", 0) + 1
                    self._save_user_profiles()
                logger.info(" 自我介绍类问题 → 强制以新闻传播学垂直领域身份回答（不走 LLM）")
                return {"answer": answer, "references": []}

            # 学科知识问答（理论概念/归属/定义问题）→ 检索 RAG 教材证据，
            # 供本地微调模型做证据增强，避免幻觉（如"信息茧房"归属错误）
            if self._is_discipline_qa(user_message, intent):
                try:
                    # 学科短问答用小预算：本地 1.5B 模型 prompt 越长推理越慢
                    # （实测注入 1.4 万字证据时，生成从 8s 劣化到 90s+ 并触发显存溢出）
                    knowledge, rag_refs = get_knowledge_with_refs(
                        user_message, rag_db, top_k=5, per_doc_chars=500, max_ctx_chars=1600)
                    rag_refs = rag_refs or []
                    if rag_refs and rag_refs[0].get('score', -999) < RERANK_SOURCE_SCORE_FLOOR:
                        knowledge = "暂无相关学术资料。"
                        rag_refs = []
                    if not knowledge or len(knowledge.strip()) < 15:
                        knowledge = "暂无相关学术资料。"
                    else:
                        knowledge = self._sanitize_text(knowledge, deep_mode=True)
                    references = rag_refs
                    logger.info(f" 学科问答 RAG 证据：{len(references)} 条引用 | 上下文 {len(knowledge)} 字")
                except Exception as e:
                    logger.warning(f"学科问答 RAG 异常: {e}")
                    knowledge = "暂无相关学术资料。"
                    references = []
            else:
                knowledge = "暂无相关学术资料。"
                references = []
        elif visual_context or file_context:
            # 多模态/文件场景：跳过 RAG 检索，避免 CPU 端 Reranker 超长延迟（实测 200s+），图片/文件内容即主要上下文
            knowledge = "未检索到相关文献。"
            rag_refs = []
            references = []
        else:
            # 纯文字短请求（无检索意图）跳过 RAG：避免 CPU Reranker 卡顿，如"帮我总结内容"
            # 豁免：学科理论问答（含理论关键词的短问句）必须检索教材证据
            _short_skip = (len(user_message) < 15
                           and not any(kw in user_message for kw in
                          ["检索", "查找", "资料", "论文", "文献", "理论", "研究", "知识库", "根据"])
                           and not self._is_discipline_qa(user_message, intent))
            if _short_skip:
                knowledge = "未检索到相关文献。"
                rag_refs = []
                references = []
            else:
                rag_query = f"{user_message} 网络舆情 传播机制 数据分析" if is_report_request else user_message
                try:
                    knowledge, rag_refs = get_knowledge_with_refs(rag_query, rag_db, top_k=5)
                    rag_refs = rag_refs or []
                    if rag_refs and rag_refs[0].get('score', -999) < RERANK_SOURCE_SCORE_FLOOR:
                        knowledge = "未检索到相关文献。"
                        rag_refs = []
                    if not knowledge or len(knowledge.strip()) < 15:
                        knowledge = "未检索到相关文献。"
                    else:
                        knowledge = self._sanitize_text(knowledge, deep_mode=True)
                    references = rag_refs
                except Exception as e:
                    logger.warning(f"RAG 异常: {e}")
                    knowledge = get_knowledge(rag_query, rag_db, top_k=5) or "未检索到相关文献。"

        SENSITIVE_PATTERNS = [
            r'习近平', r'李克强', r'中国共产党', r'中共中央',
            r'全国代表大会', r'国务院', r'国家主席', r'中央军委',
        ]
        for pattern in SENSITIVE_PATTERNS:
            knowledge = re.sub(pattern, '[已过滤]', knowledge)

        # ---------- 个性化画像注入 ----------
        if user_id:
            profile = self.user_profiles.get(user_id, {})
            weak = ', '.join(profile.get('weak_theories', [])) or '暂无'
            strong = ', '.join(profile.get('strong_theories', [])) or '暂无'
            interactions = profile.get('total_interactions', 0)
            weak_count = len(profile.get('weak_theories', []))

            profile_text = (
                f"【当前用户画像】\n"
                f"- 薄弱理论: {weak}\n"
                f"- 掌握较好的理论: {strong}\n"
                f"- 历史交互次数: {interactions}\n"
            )

            if interactions < 3:
                style_instruction = (
                    "该用户是初学者，请使用通俗易懂的语言，多用生活案例和比喻来解释概念，"
                    "避免过多专业术语。\n"
                )
            elif weak_count >= 3:
                style_instruction = (
                    "该用户有一定基础但薄弱理论较多，请侧重理论之间的逻辑关联，"
                    "每个薄弱理论提供至少一个新媒体案例辅助理解。\n"
                )
            else:
                style_instruction = (
                    "该用户基础扎实，可适当提供前沿研究视角或批判性讨论，"
                    "激发深度思考。\n"
                )

            personalized_instruction = (
                style_instruction +
                "对薄弱理论要多举例、用通俗语言解释；"
                "对已掌握的理论可适当简略。\n"
            )

            knowledge = profile_text + personalized_instruction + "\n" + knowledge

        # 🌟 根据模式选择系统提示词（创意模式）
        if mode == "creative" and not is_teaching_request:
            system_prompt = f"""你是新闻传播学领域的专业AI助手，同时也是一位具有批判性思维的学术向导。你接受过该学科的深度训练，能够提供多角度、启发式的分析。

【回答原则】
1. 鼓励你运用新闻传播学的经典理论和前沿研究来解释问题，但不局限于特定的理论列表。你可以引用任何你认为合适的学者、理论和案例。
2. 回答应尽量包含多元视角，例如不同学派的观点、正反两面的论据，以及当前学术界的争议点。
3. 在提供结论的同时，也要引导用户进一步思考，激发他们的好奇心和探索欲。
4. 回答风格可以更灵活，适当使用例子、比喻或故事来增强理解，但核心观点仍需保持学术逻辑。
5. 如果你引用了特定的理论或学者，请尽量在文中注明出处，以确保知识的可追溯性。

【学术知识库】：
{knowledge}
"""
        else:
            system_prompt = f"""你是新闻传播学领域的专业AI助手。你接受过该学科的深度训练，具有以下能力：

【核心要求】
1. 仅允许引用以下15个核心理论（使用半角方括号标注编号）：
[1] 议程设置 (McCombs & Shaw, 1972)
[2] 沉默的螺旋 (Noelle-Neumann, 1974)
[3] 使用与满足 (Katz et al., 1973)
[4] 框架理论 (Goffman, 1974)
[5] 群体极化 (Sunstein, 2002)
[6] 培养理论 (Gerbner, 1976)
[7] 创新扩散 (Rogers, 1962)
[8] 知沟理论 (Tichenor et al., 1970)
[9] 数字鸿沟 (NTIA, 1999)
[10] 第三人效果 (Davison, 1983)
[11] 媒介依赖 (Ball-Rokeach & DeFleur, 1976)
[12] 把关人理论 (White, 1950)
[13] 两级传播 (Lazarsfeld et al., 1944)
[14] 涵化分析 (Gerbner, 1976)
[15] 选择性接触 (Hyman & Sheatsley, 1947)

2. 引用规范：
   - 每个理论引用时必须在句末标注编号，例如：…这体现了议程设置理论[1]。
   - 引用多个理论时按编号排序，如 [1][4][12]。
   - 严禁引用列表之外的任何理论名称或学者。

3. 回答风格：
   - 使用学术化语言，避免口语化。
   - 尽量采用“理论定义 → 机制解释 → 新媒体环境下的应用分析”三段式结构。
   - 引用数据或事实时，给出明确的来源说明。

4. 自检要求：
   - 在回答末尾检查是否引用了未授权的理论，若有则立即修正。
   - 如果回答中涉及新闻传播学理论，必须使用[1]~[15]的编号进行标注。如果没有引用任何理论，请明确说明。
   - 在回答最后，请列出所有引用的理论编号，例如“参考理论：[1][2]”。

【学术知识库】：
{knowledge}
"""

        # 🌟 专题流域限定：告知模型当前只掌握该流域数据，跨流域必须拒答（最高优先级）
        _b = self._basin_scope.get(session_id)
        if _b:
            system_prompt += (
                f"\n\n【当前专题限定（最高优先级）】本次对话处于「{_b}流域」专题。\n"
                f"1. 凡涉及数据的问题（数量、排名、省份、事件、趋势、情感），"
                f"**必须先调用相应工具获取{_b}流域的真实数据再作答**；"
                f"不得只复述工具的用途说明而不实际调用，更不得凭记忆编造数字。\n"
                f"2. 数据工具已由系统锁定为「{_b}流域」，返回的即为{_b}流域数据，"
                f"你无需也无法切换流域，请直接使用工具结果回答。\n"
                f"3. 若用户提问中出现另一条流域名或要求两流域对比，只回复这一句"
                f"「当前为{_b}流域专题，无法查询其他流域的数据；跨流域对比请见首页『两流域核心指标对照』」，"
                f"**不得用本流域的数据顶替对方流域的问题，也不得追加任何追问、建议或"
                f"「可协助调取 / 请补充需求」之类的内容**。"
            )
            # 🌟 服务端预取本流域核心数据并注入：不依赖模型是否主动调工具（lite 模型常不调），
            #    保证「声量最高省份 / 总数 / 事件簇 / 热词」这类高频问题一定有真实数据可依。
            try:
                _facts = [f"- 本流域入库帖子总数：{getTotalArticle(basin=_b)} 条",
                          f"- 本流域声量（发帖量）最高的省份：{getTopRegion(basin=_b)}"]
                _ev = getBasinHotEvents(_b, limit=8) or {}
                _clus = _ev.get('事件簇') or []
                _hws = _ev.get('热词Top') or []
                if _clus:
                    _facts.append("- 本流域事件簇：" + '、'.join(map(str, _clus)))
                if _hws:
                    _facts.append("- 本流域高频热词：" + '、'.join(map(str, _hws)))
                system_prompt += ("\n\n【系统已实时查询到的本流域数据】\n" + "\n".join(_facts) +
                                  "\n（以上为服务端按当前专题锁定的真实数据，可直接作为事实依据；"
                                  "若需其它维度可继续调用工具，工具同样只会返回本流域数据。）")
            except Exception as _e:
                logger.warning(f"预取流域数据失败：{_e}")

        few_shot_text = self._retrieve_few_shot_examples(user_message, top_k=3)
        if few_shot_text:
            system_prompt += "\n\n" + few_shot_text

        messages = [{"role": "system", "content": system_prompt}]

        history = self.chat_histories[session_id]
        for msg in history[-6:]:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            messages.append({"role": role, "content": msg.content or ""})

        # 组装上下文（图片+文件）
        context_parts = []
        if visual_context:
            context_parts.append(visual_context)
        if file_context:
            context_parts.append(file_context)
        context_str = "\n".join(context_parts)
        final_input = f"{context_str}\n\n用户问题：{safe_user_message}" if context_str else safe_user_message
        messages.append({"role": "user", "content": final_input})

        tool_result_cache = {}
        t_ctx_ready = time.time()
        # 🌟 max_tokens 分级：普通问答 1024 / 多模态 2048，
        # 避免一律 4096 导致 lite 模型长时间逐字生成（报告场景在其他分支仍用 4096）
        answer_budget = 2048 if (is_teaching_request or visual_context or file_context) else 1024
        try:
            if prefer_local or visual_context or file_context or not self.client:
                # 本地微调模型 / 多模态 / 文件 / 无API场景：禁用工具调用，直接基于注入的上下文生成，
                # 避免星火模型 tools 循环导致的超长延迟（实测 240s+ -> <60s）
                response_text = self._call_llm(messages, temperature=0.1, max_tokens=answer_budget,
                                               prefer="local" if prefer_local else "api")
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name, messages=messages, tools=self.tools, tool_choice="auto",
                    temperature=0.1, max_tokens=answer_budget
                )
                message = response.choices[0].message
                if message.tool_calls:
                    messages.append(message)
                    for tool_call in message.tool_calls:
                        fn = tool_call.function.name
                        args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                        res_str = self._execute_single_tool(fn, args, self._basin_scope.get(session_id))
                        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": res_str})
                        try:
                            parsed = json.loads(res_str)
                            if "result" in parsed:
                                tool_result_cache[fn] = parsed["result"]
                        except:
                            pass
                    response_text = self._call_llm(messages, temperature=0.1, max_tokens=answer_budget, prefer="api")
                else:
                    response_text = message.content or ""
        except Exception as e:
            error_str = str(e)
            logger.error(f"大模型调用失败：{e}")
            if any(code in error_str for code in ["SuspectedResult", "500", "10019", "10014", "10013"]):
                return {"answer": "系统正进行学术合规校验，请尝试使用'模拟数据'等表述，或生成学术报告。", "references": references}
            return {"answer": f"❌ 服务异常：{error_str}", "references": references}

        response_text = re.sub(r'<thought>.*?</thought>', '', response_text, flags=re.DOTALL).strip()

        # 🌟 阶段打点汇总：定位慢在 路由/检索/LLM 哪一段
        t_llm_done = time.time()
        logger.info(f"[TIME] chat 耗时拆解: 路由 {t_after_route - t_chat_start:.1f}s | "
                    f"上下文/RAG {t_ctx_ready - t_after_route:.1f}s | "
                    f"LLM {t_llm_done - t_ctx_ready:.1f}s | "
                    f"累计 {t_llm_done - t_chat_start:.1f}s")

        # ---------- 🌟 双模型来源标注：本地微调模型生成的回答显式标注（演示可追溯） ----------
        if prefer_local and self._last_backend == "local":
            response_text += ("\n\n*—— 本回答由本地微调学科模型（Qwen2.5-1.5B + LoRA）"
                              "结合知识库检索生成，观点可溯源至下方参考资料*")

        if is_teaching_request:
            response_text = re.sub(r'\[(?!(?:[1-9]|1[0-5])\])[^\]]*\]', '', response_text)

        # ========== 🌟 内容可追溯强制检查 ==========
        if is_teaching_request or "理论" in user_message or "传播" in user_message:
            if not re.search(r'\[([1-9]|1[0-5])\]', response_text):
                response_text += "\n\n> ⚠️ 本回答涉及学科理论，但未自动标注理论编号。建议参阅下方知识库来源，或重新提问以便获取更规范的学术回复。"

        if user_id and not is_teaching_request and len(response_text) > 100:
            try:
                weak_theories = self.user_profiles[user_id].get("weak_theories", [])
                if weak_theories:
                    rec_query = f"{' '.join(weak_theories[:2])} 传播学"
                    if get_knowledge_with_refs and rag_db:
                        rec_knowledge, rec_refs = get_knowledge_with_refs(rec_query, rag_db, top_k=2)
                        if rec_refs:
                            rec_lines = "\n### 📚 推荐阅读（基于你的学习情况）\n"
                            for i, ref in enumerate(rec_refs[:2]):
                                title = ref.get('source', '未知资料')
                                rec_lines += f"- {title}\n"
                            response_text += rec_lines
            except Exception as e:
                logger.warning(f"个性化推荐失败: {e}")

        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=response_text))
        logger.info(f"[DOC] 最终返回 {len(references)} 条 RAG 引用")
        if user_id:
            self.user_profiles[user_id]["total_interactions"] += 1
            self._save_user_profiles()
        return {"answer": response_text, "references": references}

    def _get_required_elements(self, question: str) -> dict:
        safe_q = self._sanitize_text(question, deep_mode=True).lower()
        if ("麦克卢汉" in safe_q or "媒介即讯息" in safe_q) and ("信息茧房" in safe_q or "算法推荐" in safe_q):
            return {"theories": ["1", "2"], "forbidden_theories": ["6"], "logic_keywords": ["窄化", "显著性", "自我审查", "同质化"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        if ("拉斯韦尔" in safe_q or "5w" in safe_q) and ("认知失调" in safe_q or "引导权丧失" in safe_q):
            return {"theories": ["1", "3"], "forbidden_theories": ["7"], "logic_keywords": ["算法过滤", "主动选择", "认知固化", "信息环境失衡"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        if ("后真相" in safe_q or "数字生产" in safe_q) and ("特点" in safe_q or "影响" in safe_q):
            return {"theories": ["4", "5"], "logic_keywords": ["情绪化框架", "事实让位于情感", "回音室", "观点极端化"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        if "信息茧房" in safe_q or "算法推荐" in safe_q or "认知窄化" in safe_q:
            return {"theories": ["1", "2", "3"], "logic_keywords": ["窄化", "强化", "压制", "固化", "循环", "反馈", "机制", "导致"], "causal_chain_required": True, "min_theory_count": 3, "demo_template": "..."}
        elif "舆论极化" in safe_q or "撕裂" in safe_q or "回音室" in safe_q:
            return {"theories": ["2", "5"], "logic_keywords": ["同质化", "讨论", "极端", "回声室", "放大", "强化"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        elif "舆论" in safe_q or "热搜" in safe_q or "议题" in safe_q or "议程设置" in safe_q:
            return {"theories": ["1", "4"], "logic_keywords": ["显著性", "建构", "解读", "框架", "排序"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        elif "沉默" in safe_q or "螺旋" in safe_q:
            return {"theories": ["2", "4"], "logic_keywords": ["孤立恐惧", "意见气候", "自我审查", "主流意见", "沉默", "螺旋"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        elif "知沟" in safe_q or "知识沟" in safe_q or "数字鸿沟" in safe_q:
            return {"theories": ["8", "9"], "logic_keywords": ["差距", "获取", "素养", "社会经济"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        elif "第三人效果" in safe_q or "第三人" in safe_q:
            return {"theories": ["10"], "logic_keywords": ["高估", "影响", "自我", "他人"], "causal_chain_required": True, "min_theory_count": 1, "demo_template": "..."}
        elif "媒介依赖" in safe_q or "依赖理论" in safe_q:
            return {"theories": ["11"], "logic_keywords": ["复杂", "依赖", "信息获取"], "causal_chain_required": True, "min_theory_count": 1, "demo_template": "..."}
        elif "把关人" in safe_q or "把关" in safe_q:
            return {"theories": ["12"], "logic_keywords": ["筛选", "过滤", "议程"], "causal_chain_required": True, "min_theory_count": 1, "demo_template": "..."}
        elif "两级传播" in safe_q or "意见领袖" in safe_q:
            return {"theories": ["13"], "logic_keywords": ["意见领袖", "流向", "大众媒介"], "causal_chain_required": True, "min_theory_count": 1, "demo_template": "..."}
        elif "涵化" in safe_q or "培养" in safe_q:
            return {"theories": ["6", "14"], "logic_keywords": ["长期", "认知", "主流化"], "causal_chain_required": True, "min_theory_count": 2, "demo_template": "..."}
        elif "选择性接触" in safe_q or "选择性" in safe_q:
            return {"theories": ["15"], "logic_keywords": ["一致", "避免", "对立"], "causal_chain_required": True, "min_theory_count": 1, "demo_template": "..."}
        else:
            return {"theories": ["1"], "logic_keywords": ["影响", "导致", "因为", "所以", "机制"], "causal_chain_required": False, "min_theory_count": 1, "demo_template": "..."}

    def _extract_theories_from_answer(self, text: str) -> list:
        explicit = re.findall(r'\[([1-9]|1[0-5])\]', text)
        if explicit:
            return list(set(explicit))
        theory_keywords = {
            "议程设置": "1", "agenda setting": "1",
            "沉默的螺旋": "2", "spiral of silence": "2",
            "使用与满足": "3", "uses and gratifications": "3",
            "框架": "4", "framing": "4",
            "群体极化": "5", "group polarization": "5",
            "培养": "6", "cultivation": "6",
            "创新扩散": "7", "diffusion of innovations": "7",
            "知沟": "8", "knowledge gap": "8",
            "数字鸿沟": "9", "digital divide": "9",
            "第三人效果": "10", "third person effect": "10",
            "媒介依赖": "11", "media dependency": "11",
            "把关人": "12", "gatekeeping": "12",
            "两级传播": "13", "two-step flow": "13",
            "涵化": "14", "cultivation analysis": "14",
            "选择性接触": "15", "selective exposure": "15"
        }
        found = []
        for kw, tid in theory_keywords.items():
            if kw.lower() in text.lower() and tid not in found:
                found.append(tid)
        return found

    def _score_by_structure(self, student_text: str, req: dict) -> tuple:
        hit_theories = self._extract_theories_from_answer(student_text)
        hit_set = set(hit_theories)
        req_set = set(req["theories"])
        forbidden = req.get("forbidden_theories", [])
        if any(t in hit_set for t in forbidden):
            return 0, {"theory_score": 0, "logic_score": 0, "citation_bonus": 0, "penalty": 0, "hit_count": 0, "req_count": len(req_set), "has_logic": False, "missing_count": len(req_set)}
        theory_ratio = len(hit_set & req_set) / len(req_set) if req_set else 0
        theory_points = theory_ratio * 60
        has_logic = req["causal_chain_required"] and any(kw in student_text for kw in req["logic_keywords"])
        logic_points = 40 if has_logic else (25 if req["causal_chain_required"] else 35)
        has_citations = bool(re.findall(r'\[([1-9]|1[0-5])\]', student_text))
        citation_bonus = 5 if has_citations else 0
        missing_count = len(req_set - hit_set)
        penalty_points = missing_count * 10 + len(hit_set - req_set) * 5
        penalty_points = min(penalty_points, 95)
        raw_score = theory_points + logic_points + citation_bonus - penalty_points
        score = max(0, min(100, int(raw_score)))
        details = {"theory_score": int(theory_points), "logic_score": int(logic_points), "citation_bonus": citation_bonus, "penalty": int(penalty_points), "hit_count": len(hit_set & req_set), "req_count": len(req_set), "has_logic": has_logic, "missing_count": missing_count}
        return score, details

    def _call_llm_directly(self, prompt: str) -> str:
        # 复杂工具调用需要强指令跟随能力：优先星火 API，
        # hybrid 模式下 API 不可用时自动降级本地微调模型（_call_llm 内置兜底）
        try:
            return self._call_llm([{"role": "user", "content": prompt}],
                                  temperature=0.1, max_tokens=4096, prefer="api")
        except Exception as e:
            logger.error(f"直接调用失败: {e}")
            return f"❌ 生成失败：{str(e)}"


    def _load_user_profiles(self):
        try:
            if os.path.exists(self.user_profiles_path):
                with open(self.user_profiles_path, encoding="utf-8") as f:
                    data = json.load(f)
                for uid, profile in data.items():
                    self.user_profiles[uid] = profile
                logger.info(f"[DIR] 已加载 {len(data)} 个用户画像")
        except Exception as e:
            logger.warning(f"加载用户画像失败: {e}")

    def _save_user_profiles(self):
        try:
            with open(self.user_profiles_path, "w", encoding="utf-8") as f:
                json.dump(dict(self.user_profiles), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存用户画像失败: {e}")
    def clear_history(self, session_id: str = "default"):
        self.chat_histories[session_id] = []
        return "清空历史"

    def generate_learning_report(self, user_id: str) -> str:
        """学情报告：基于用户画像生成学习现状分析与建议"""
        profile = self.user_profiles.get(user_id, {})
        weak = profile.get("weak_theories", []) or []
        strong = profile.get("strong_theories", []) or []
        interactions = profile.get("total_interactions", 0)
        if not self.client:
            return "大模型服务未启动，无法生成学情报告。"
        prompt = f"""请根据以下学情数据，生成一份简明学情诊断报告：
- 薄弱理论：{', '.join(weak) if weak else '暂无明确薄弱点'}
- 掌握较好的理论：{', '.join(strong) if strong else '暂无记录'}
- 历史交互次数：{interactions}
输出要求：1) 学习现状分析（2-3 句）；2) 3 条针对性改进建议；3) 下一步学习重点。"""
        try:
            resp = self._call_llm([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=1024)
            return resp.strip()
        except Exception as e:
            logger.error(f"学情报告生成失败: {e}")
            return "学情报告生成失败，请稍后重试。"
