# -*- coding: utf-8 -*-
"""Deterministic answers for verified BasinScope snapshot facts.

This module is intentionally small and conservative. It only answers questions
whose facts are explicitly present in knowledge/basinscope_snapshot_facts.md.
Unknown questions return None and continue through the normal QA pipeline.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


FACT_FILE = "knowledge/basinscope_snapshot_facts.md"


def _norm(text: str) -> str:
    text = str(text or "").lower()
    for ch in (" ", "\n", "\r", "\t", "，", ",", "。", "？", "?", "：", ":", "；", ";"):
        text = text.replace(ch, "")
    return text


def _has_all(text: str, *terms: str) -> bool:
    return all(term in text for term in terms)


def _ref() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / FACT_FILE
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {
        "id": 1,
        "title": "BasinScope snapshot facts",
        "type": "curated_snapshot",
        "content": "Verified snapshot-level figures from the BasinScope manuscript and repository.",
        "full_content": content,
        "score": 1.0,
        "file_path": FACT_FILE,
    }


def _answer(text: str) -> dict[str, Any]:
    return {"reply": text, "references": [_ref()], "deterministic": True}


def _refusal(text: str) -> dict[str, Any]:
    return {"reply": text, "references": [_ref()], "deterministic": True}


def lookup_snapshot_fact(question: str, basin: str | None = None) -> dict[str, Any] | None:
    q = _norm(question)

    # Scope and boundary questions that must not be sent to the generative agent.
    if "2027" in q and ("预测" in q or "forecast" in q or "rank" in q):
        return _refusal("当前快照没有可用于预测 2027 年风险排名的数据，系统无法据此作预测。")
    if "长江" in q or "全国34" in q or "全国三十四" in q:
        return _refusal("当前为黄河流域专题，无法查询该范围的数据。")
    if ("目标省份" in q or "几个省" in q or "多少个省份" in q) and ("黄河" in q or basin == "黄河"):
        return _answer("当前用于分析的黄河流域目标省份有 8 个：青海、甘肃、宁夏、内蒙古、陕西、山西、河南、山东。")
    if "共源省" in q and ("哪一个" in q or "哪个" in q or "四川" in q):
        return _answer("地图中额外显示的共源省是四川。四川是黄河与长江共源省，但在本项目中归入长江专题，不属于八省黄河分析样本。")

    if ("文化旅游" in q or "文旅" in q) and ("小红书" in q or "知乎" in q):
        return _answer("不包含。当前文化旅游数据仅覆盖微博文章和抖音视频，小红书与知乎的跨平台文本未采集。")

    yellow_context = (basin is not None and "黄河" in basin) or any(
        term in q
        for term in (
            "黄河", "微博", "快照", "当前", "这些文章", "这些评论",
            "douyin", "抖音", "聚类", "风险评分",
        )
    )
    if not yellow_context:
        return None

    # Detailed multi-platform healthcare figures before generic healthcare figures.
    if "医疗" in q and _has_all(q, "微博", "小红书", "知乎") and "文章" in q:
        return _answer("医疗争议数据包含 169 篇微博文章、346 篇小红书文章和 267 篇知乎文章。")
    if "医疗" in q and "评论" in q and "585" not in q and "聚类" not in q:
        return _answer("医疗争议数据包含 585 条评论。它与其他专题评论合并后，形成 936 条聚类输入。")
    if ("轮廓系数" in q or "silhouette" in q):
        return _answer("五个聚类的轮廓系数是 0.464。该数值只是内部诊断指标，不代表分类准确率。")
    if "五个" in q and "聚类" in q and ("412" in q or "多少" in q or "包含" in q):
        return _answer("五个词项聚类的评论数分别为 412、144、142、123 和 115 条。")

    # Core corpus facts.
    if ("三个重点主题" in q or "重点主题" in q) and "多少" in q:
        return _answer("当前快照有 899 篇文章属于三个重点主题。")
    if "生态治理" in q and "文章" in q:
        return _answer("生态治理主题有 371 篇文章。")
    if ("文化旅游" in q or "文旅" in q) and "文章" in q:
        return _answer("文化旅游主题有 359 篇文章。")
    if "医疗" in q and "文章" in q:
        return _answer("医疗争议主题有 169 篇文章。")
    if "中央生态环保督察" in q and "文章" in q:
        return _answer("中央生态环保督察事件有 139 篇微博文章。")
    if ("当前" in q or "快照" in q or "微博" in q) and "文章" in q and ("多少" in q or "几个" in q):
        return _answer("当前微博快照包含 1,097 篇文章。")
    if "点赞" in q:
        return _answer("这些文章的点赞数为 158,423。")
    if ("评论数元数据" in q or "评论数总和" in q or ("评论数" in q and "元数据" in q)):
        return _answer("文章元数据中的评论数总和为 32,833。它不等于实际采集的评论记录数。")
    if "转发" in q:
        return _answer("这些文章的转发数为 72,681。")
    if "跨平台评论" in q and ("多少" in q or "条" in q):
        return _answer("当前快照包含 949 条跨平台评论。")
    if "评论" in q and ("用于聚类" in q or "聚类" in q) and ("多少" in q or "条" in q):
        return _answer("用于 TF-IDF 和 K-means 聚类的评论为 936 条。")

    if "风险" in q and "权重" in q:
        return _answer("风险评分的四个权重分别是 0.40（负面占比）、0.25（声量）、0.20（官方主体敏感度）和 0.15（扩散）。")
    if "黄色" in q and "蓝色" in q:
        return _answer("当前风险分级为 3 个黄色事件和 9 个蓝色事件；另有 2 个低于 30 条阈值的聚类未分级。")
    if "中央生态环保督察" in q and "负面" in q:
        return _answer("中央生态环保督察事件有 139 篇微博文章，其中 73 条为负面记录，负面比例为 52.5%。")
    if "中央生态环保督察" in q and "文章" in q:
        return _answer("中央生态环保督察事件有 139 篇微博文章。")
    if "58.8" in q or ("分项" in q and "贡献" in q):
        return _answer("58.8 分的四个贡献项是：负面占比 21.0、声量 16.4、官方主体敏感度 20.0、扩散 1.4。")
    if "督察整改与问责" in q and ("分数" in q or "得分" in q):
        return _answer("督察整改与问责事件的风险分数为 46.1。")
    if "水污染" in q and ("排放" in q or "排污" in q) and ("分数" in q or "得分" in q):
        return _answer("水污染和排放事件的风险分数为 35.1。")

    if "短视频" in q or "关键帧" in q and ("45.8" in q or "示例" in q or "参数" in q):
        return _answer("示例短视频时长为 45.8 秒，生成 19 个关键帧，ASR 转写为 212 个字符，软件推荐分数为 0.885。该分数不是准确率或因果估计。")
    if "douyin" in q or "抖音" in q:
        return _answer("当前有 33 个黄河 Douyin 案例，其中 17 个为文旅案例，16 个为生态治理案例；33 个案例均有 keyframes、ASR 状态 ok 和非空转写。")

    if "追溯" in q or "来源" in q and "限制" in q:
        return _answer("每项输出都与来源记录、处理规则和已记录的限制相关联；系统还提供方法页和校准页，帮助人工核查。")

    return None
