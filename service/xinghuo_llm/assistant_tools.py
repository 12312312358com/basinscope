import json, re, os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .knowledge_base import SubjectKnowledgeBase
from .config import logger, root_dir


class ResearchAssistant:
    # 类属性，由 main.py 注入
    llm = None
    rag_db = None

    @staticmethod
    def literature_review(topic: str, theories: List[str] = None) -> str:
        rag_knowledge = ""
        if ResearchAssistant.rag_db is not None:
            try:
                from .imports import get_knowledge_with_refs
                rag_knowledge, _ = get_knowledge_with_refs(
                    f"{topic} 传播学 文献", ResearchAssistant.rag_db, top_k=10)
            except Exception:
                pass
        if not theories:
            theories = ["议程设置理论", "沉默的螺旋理论", "使用与满足理论"]
        theory_section = ""
        for th in theories:
            info = SubjectKnowledgeBase.search_theory(th)
            if info:
                theory_section += (f"- **{info[0]['zh_name']}**（{info[0]['author']}, "
                                   f"{info[0]['year']}）：{info[0]['desc']}\n")
            else:
                theory_section += f"- {th}：待补充\n"
        if ResearchAssistant.llm and ResearchAssistant.llm.client:
            prompt = f"""请为用户生成一篇关于「{topic}」的新闻传播学文献综述。
【可引用的理论框架】：
{theory_section}
【知识库中的相关资料】：
{rag_knowledge[:2000] if rag_knowledge else "暂无相关资料"}
【输出结构】：
## 文献综述：{topic}
### 1. 研究背景
### 2. 理论基础
### 3. 已有研究成果
### 4. 研究空白与展望
### 5. 参考文献
⚠️ 铁律：不得编造学者姓名、期刊名或年份。资料不足时明确告知用户。"""
            try:
                response = ResearchAssistant.llm.client.chat.completions.create(
                    model=ResearchAssistant.llm.model_name,
                    messages=[{"role": "system", "content": "你是严谨的新闻传播学教授，绝不编造文献信息。"},
                              {"role": "user", "content": prompt}],
                    temperature=0.3, max_tokens=4096)
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"LLM 文献综述生成失败: {e}")
        review = f"""## 文献综述框架：{topic}
### 1. 研究背景
{topic}是当前新闻传播学领域的重要议题，尤其在数字媒体环境下呈现出新特点。
### 2. 理论基础
{theory_section}
### 3. 已有研究成果
> ⚠️ 当前知识库中关于该主题的文献资料有限，建议查阅 CNKI、Web of Science 等学术数据库获取相关论文。
### 4. 研究空白与展望
- 缺乏跨文化比较视角
- 针对本土语境的实证研究不足
- 新媒体环境下的理论适用性有待验证
### 5. 建议查阅的核心文献
- 郭庆光.《传播学教程》. 中国人民大学出版社.
- McCombs, M. & Shaw, D. (1972). The Agenda-Setting Function of Mass Media. *Public Opinion Quarterly*.
- Noelle-Neumann, E. (1974). The Spiral of Silence. *Journal of Communication*.
"""
        return review

    @staticmethod
    def research_design(topic: str, method: str = "混合方法", hypotheses: List[str] = None) -> str:
        if hypotheses:
            hyp_text = chr(10).join(hypotheses)
        else:
            hyp_text = "H1: 变量A与变量B呈正相关\nH2: 变量C对{}具有调节作用".format(topic)
        return f"""## 研究设计：{topic}
### 研究问题
1. {topic}的现状与特征是什么？
2. 影响{topic}的关键因素有哪些？
3. 如何应对{topic}带来的挑战？
### 研究假设
{hyp_text}
### 研究方法
- **主方法**：{method}
- **数据收集**：问卷调查（n≥300）+ 深度访谈（n≥20）
- **数据分析**：SPSS/AMOS回归分析 + NVivo主题编码
### 技术路线
文献梳理 → 理论建模 → 问卷/访谈设计 → 数据采集 → 统计分析 → 结论与建议
"""

    @staticmethod
    def paper_framework(topic: str, style: str = "实证论文") -> str:
        sections = {
            "实证论文": ["引言（背景与问题）", "文献综述与理论假设", "研究设计", "实证分析", "结论与讨论", "参考文献"],
            "综述论文": ["引言", "研究脉络", "核心议题与争论", "方法与评述", "未来展望", "参考文献"],
            "案例研究": ["导论", "案例背景", "理论框架", "案例分析", "发现与启示", "结论"]
        }
        secs = sections.get(style, sections["实证论文"])
        return f"""## 论文框架：{topic}
**论文类型：** {style}
### 建议结构
{' -> '.join(secs)}
### 写作规范
- 摘要：200-300字（目的-方法-结果-结论）
- 关键词：3-5个
- 正文：8000-15000字
- 参考文献：≥20篇，近5年≥60%
- 学术规范：严格遵循APA第7版格式
"""

    @staticmethod
    def polish_academic(text: str, style: str = "规范学术") -> str:
        """学术润色：优先调用大模型，失败时降级为通用建议"""
        llm = ResearchAssistant.llm
        if llm and llm.client:
            prompt = f"""请对以下学术文本进行润色（风格：{style}），要求：
1. 保持原意，提升学术表达；
2. 修正语法、用词与逻辑衔接；
3. 输出润色后的完整文本，并在末尾列出 3 条主要修改说明。

原文：
{text[:3000]}"""
            try:
                resp = llm.client.chat.completions.create(
                    model=llm.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3, max_tokens=2048)
                content = resp.choices[0].message.content or ""
                if content.strip():
                    return content.strip()
            except Exception as e:
                logger.error(f"学术润色 LLM 调用失败: {e}")
        return (f"【学术润色建议】（大模型未就绪，仅提供通用建议）\n原文：{text[:200]}...\n"
                f"1) 使用更正式学术词汇；2) 增加过渡句；3) 明确研究主体；4) 检查被动语态使用。")


class ComplexQuerySolver:
    @staticmethod
    def decompose(query: str) -> List[str]:
        """规则分解 + 关键词增强"""
        sub_questions = []
        if "分析" in query and "影响" in query:
            sub_questions.append(f"{query}的原因")
            sub_questions.append(f"{query}的机制")
            sub_questions.append(f"{query}的对策")
        elif "对比" in query:
            sub_questions.append("对比双方的异同")
        elif "如何" in query or "怎么" in query:
            sub_questions.append(f"{query}：现状与问题")
            sub_questions.append(f"{query}：成因分析")
            sub_questions.append(f"{query}：对策建议")
        else:
            sub_questions.append(query)
        return sub_questions

    @classmethod
    def solve(cls, query: str, llm_func) -> str:
        subs = cls.decompose(query)
        answers = []
        for sub in subs:
            ans = llm_func(sub)
            if isinstance(ans, dict):
                ans = ans.get("answer", "")
            answers.append(ans)
        return "\n\n".join([f"【子问题{i + 1}】{subs[i]}\n{answers[i][:300]}..." for i in range(len(subs))])
    @classmethod
    def decompose_with_llm(cls, query: str) -> List[str]:
        """LLM 任务分解：把复杂问题拆成 2-4 个可独立回答的子问题"""
        llm = ResearchAssistant.llm
        if llm and llm.client:
            prompt = f"""请把以下复杂学术问题拆解为 2-4 个可独立回答的子问题。
只输出子问题，每行一个，不要编号外的任何文字：
问题：{query}"""
            try:
                resp = llm.client.chat.completions.create(
                    model=llm.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0, max_tokens=500)
                subs = [l.strip(" -0123456789.、").strip()
                        for l in resp.choices[0].message.content.splitlines() if l.strip()]
                subs = [s for s in subs if len(s) >= 4]
                if len(subs) >= 2:
                    return subs[:4]
            except Exception as e:
                logger.error(f"LLM 分解失败，回退规则分解: {e}")
        return cls.decompose(query)

    @classmethod
    def solve_smart(cls, query: str, llm_func) -> str:
        """LLM 分解 + 子答案聚合（比纯规则分解更贴合复杂问题）"""
        subs = cls.decompose_with_llm(query)
        answers = []
        for sub in subs:
            ans = llm_func(sub)
            if isinstance(ans, dict):
                ans = ans.get("answer", "")
            answers.append(ans)
        return "\n\n".join([f"【子问题{i + 1}】{subs[i]}\n{answers[i][:300]}..." for i in range(len(subs))])


class AdaptiveLearningPath:
    @staticmethod
    def generate(current_level: str, goal: str, weak_points: List[str] = None,
                 available_hours: int = 10, exam_date: str = "2026-12-31") -> str:
        if not weak_points:
            weak_points = ["传播理论", "研究方法", "网络舆情"]
        days_left = (datetime.strptime(exam_date, "%Y-%m-%d") - datetime.now()).days
        days_left = max(days_left, 7)
        plan = f"""## 自适应学习计划（{days_left}天备考）
**当前水平：** {current_level}
**目标：** {goal}
**每周可用时间：** {available_hours}小时
### 薄弱点强化
"""
        for wp in weak_points:
            plan += f"- **{wp}**：每日30分钟知识点梳理 + 20分钟真题训练\n"
        plan += f"""
### 阶段安排（每7天为一周期）
- **基础补弱期**（第1-{min(7, days_left)}天）：集中攻克薄弱点
- **综合提升期**（第{min(7, days_left) + 1}-{min(14, days_left)}天）：论述题+理论应用训练
- **冲刺模拟期**（第{min(14, days_left) + 1}-{days_left}天）：全真模拟+错题回顾
### 每日推荐
- 早上：背诵理论要点
- 下午：刷真题+分析
- 晚上：总结笔记+预习
"""
        return plan


class LessonEnricher:
    @classmethod
    def enrich(cls, topic: str, existing_lesson: str = "") -> str:
        rich = existing_lesson
        theories = SubjectKnowledgeBase.search_theory(topic)
        if theories:
            rich += "\n\n**📚 可引用的核心理论：**\n"
            for t in theories[:3]:
                rich += f"- {t['zh_name']}（{t['author']}, {t['year']}）：{t['desc'][:80]}...\n"
        for case_key, case_val in SubjectKnowledgeBase.CASES.items():
            if case_key in topic:
                rich += f"\n**📌 相关案例：** {case_val}\n"
                break
        return rich