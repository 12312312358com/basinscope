import time
import re
from typing import List, Dict, Callable, Optional


class BenchmarkSuite:
    TEST_CASES = [
        # ---------- 助教场景 ----------
        {"id": "T01", "scene": "助教-教案生成",
         "query": "请为新闻传播学《传播学概论》课程生成一份关于'议程设置理论'的教案，含教学目标、重难点、教学过程。",
         "expected": ["议程设置", "教案", "教学目标", "重难点"],
         "min_len": 100},
        {"id": "T02", "scene": "助教-作业批改",
         "query": "题目：论述议程设置理论在新媒体环境下的变化。我的回答：议程设置理论由麦库姆斯和肖提出，强调媒体通过报道频率影响公众对议题重要性的认知。在新媒体环境下，算法推荐成为新的议程设置者，信息茧房加剧了选择性接触。",
         "expected": ["评分", "批改", "理论"],
         "min_len": 50},
        {"id": "T03", "scene": "助教-学情诊断",
         "query": "我的薄弱点是沉默的螺旋理论，请帮我诊断学习情况并给出提升建议。",
         "expected": ["沉默", "薄弱", "建议"],
         "min_len": 80},
        {"id": "T04", "scene": "助教-试题讲解",
         "query": "请讲解'框架理论'的核心概念，并举例说明其在社交媒体中的体现。",
         "expected": ["框架", "戈夫曼"],
         "min_len": 100},
        # ---------- 助学场景 ----------
        {"id": "T05", "scene": "助学-知识问答",
         "query": "什么是知沟理论？请用通俗语言解释，并结合数字鸿沟说明。",
         "expected": ["知沟", "数字鸿沟", "知识差距"],
         "min_len": 100},
        {"id": "T06", "scene": "助学-学习路径",
         "query": "我是一名大二新闻学学生，请帮我制定期末传播学复习计划，薄弱点是批判学派和研究方法。",
         "expected": ["复习", "计划", "薄弱"],
         "min_len": 100},
        {"id": "T07", "scene": "助学-复杂问题",
         "query": "请综合分析算法推荐如何导致信息茧房，并从议程设置、沉默的螺旋、群体极化三个理论角度论述。",
         "expected": ["议程设置", "沉默", "极化", "信息茧房"],
         "min_len": 200},
        {"id": "T08", "scene": "助学-概念辨析",
         "query": "请辨析'培养理论'与'涵化分析'的异同。",
         "expected": ["培养", "涵化", "异同"],
         "min_len": 100},
        # ---------- 助研场景 ----------
        {"id": "T09", "scene": "助研-文献综述",
         "query": "生成关于算法推荐对信息茧房影响的文献综述框架，要求包含议程设置和沉默的螺旋理论。",
         "expected": ["文献综述", "议程设置", "沉默"],
         "min_len": 200},
        {"id": "T10", "scene": "助研-论文框架",
         "query": "帮我搭建一篇关于'网络舆情情感演化'的实证论文框架。",
         "expected": ["框架", "引言", "结论", "参考文献"],
         "min_len": 100},
        {"id": "T11", "scene": "助研-学术润色",
         "query": "请帮我润色这段学术文字：算法推荐让用户看到更多同质化内容，这不好，会影响用户观点。",
         "expected": ["润色", "建议"],
         "min_len": 50},
        {"id": "T12", "scene": "助研-数据分析",
         "query": "请分析近期的舆情数据，说明发帖趋势和主要热词。",
         "expected": ["趋势", "热词", "数据"],
         "min_len": 100},
    ]

    @classmethod
    def run(cls, llm_func: Callable, judge_func: Optional[Callable] = None) -> List[dict]:
        """
        llm_func: query -> dict(含 answer/references)
        judge_func: (query, answer) -> int (1-5)，可选，LLM-as-a-Judge 评分
        """
        results = []
        for case in cls.TEST_CASES:
            start = time.time()
            ok = False
            answer = ""
            refs = []
            hits = 0
            try:
                resp = llm_func(case["query"])
                if isinstance(resp, dict):
                    answer = resp.get("answer", "") or ""
                    refs = resp.get("references", []) or []
                else:
                    answer = str(resp)
                expected = case.get("expected", [])
                min_hits = max(1, (len(expected) + 1) // 2)
                hits = sum(1 for kw in expected if kw in answer)
                ok = (len(answer) >= case.get("min_len", 50) and hits >= min_hits)
            except Exception as e:
                answer = f"异常: {e}"
                ok = False
            elapsed = time.time() - start

            # RAG 引用命中率：回答中的 [n] 是否在引用列表范围内
            cit_ids = [int(x) for x in re.findall(r"\[(\d+)\]", answer)]
            valid_cit = sum(1 for c in cit_ids if 1 <= c <= len(refs))
            cit_hit_ratio = round(valid_cit / max(len(cit_ids), 1), 2) if cit_ids else 0.0

            # LLM-as-a-Judge 评分（可选）
            judge_score = None
            if judge_func is not None:
                try:
                    judge_score = int(judge_func(case["query"], answer) or 0)
                except Exception:
                    judge_score = None

            results.append({
                "id": case["id"],
                "scene": case["scene"],
                "status": "通过" if ok else "失败",
                "response_time_s": round(elapsed, 2),
                "answer_len": len(answer),
                "ref_count": len(refs),
                "cit_hit_ratio": cit_hit_ratio,
                "hit_keywords": f"{hits}/{len(expected)}",
                "judge_score": judge_score,
                "answer_preview": answer[:120],
            })
        return results