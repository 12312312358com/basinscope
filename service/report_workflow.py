# service/report_workflow.py
"""工作流驱动的舆情报告生成
用 WorkflowEngine 编排：数据组装 → 事实清单 → 图表 → 章节并行生成 → 排版保存
章节并行（ThreadPoolExecutor）+ 单章失败自动重试（max_retries）
"""
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor

# ===== 海外 LITE 精简环境：python-docx 缺失时优雅降级 =====
try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    _DOC_AVAILABLE = True
except Exception as _docx_err:
    Document = None
    Pt = RGBColor = Inches = Cm = None
    WD_ALIGN_PARAGRAPH = None
    qn = None
    _DOC_AVAILABLE = False
    print(f"[LITE] python-docx 不可用（{_docx_err}），Word 报告生成将降级")

from service.xinghuo_llm.workflow import WorkflowEngine
from service.report_service import (extract_fact_sheet, format_data_for_llm,
                                    generate_charts, clean_llm_output,
                                    deep_sanitize, _set_run_font)
from service.rag_service import get_knowledge, rag_db
from service.xinghuo_llm import xinghuo_llm

CHAPTERS = [
    {"title": "一、舆情整体态势与生命周期研判", "data_keys": ["overview_stats", "daily_trend"],
     "rag_query": "网络舆情生命周期理论 发酵期 爆发期", "chart": "trend"},
    {"title": "二、热门议题聚焦与传播层级分析", "data_keys": ["hot_topics", "keywords"],
     "rag_query": "议程设置理论 框架理论 社交媒体话题演化", "chart": "top10_bar"},
    {"title": "三、核心议题与情感倾向交叉分析", "data_keys": ["hot_topics", "sentiment_trend"],
     "rag_query": "情感传播机制 舆论极化 负面情绪动员", "chart": "hotword_sentiment"},
    {"title": "四、关键节点用户互动与意见领袖识别", "data_keys": ["user_comments", "overview_stats"],
     "rag_query": "意见领袖 两级传播 网络群体极化现象", "chart": "comment_scatter"},
    {"title": "五、舆论情感演化规律与风险预警", "data_keys": ["sentiment_trend", "daily_trend"],
     "rag_query": "网络舆情情感演化规律 沉默螺旋 风险感知", "chart": "sentiment"},
    {"title": "六、用户评论语言特征分析", "data_keys": ["user_comments", "keywords"],
     "rag_query": "网络语言特征 受众心理 使用与满足 社交媒体评论", "chart": None},
    {"title": "七、舆情综合研判与治理优化建议", "data_keys": ["overview_stats", "sentiment_trend", "hot_topics"],
     "rag_query": "企业舆情应对策略 危机公关 媒介化治理", "chart": None},
]


def _gen_one(chapter, fact_sheet, safe_data):
    """生成单章正文（带 3 次重试）"""
    context_text = "暂无相关理论补充"
    if rag_db:
        try:
            context_text = deep_sanitize(get_knowledge(chapter["rag_query"], rag_db, top_k=5))
        except Exception:
            pass

    chapter_data_list = []
    for key in chapter.get("data_keys", []):
        if key in safe_data:
            chapter_data_list.append(f"【{key}数据】:\n{safe_data[key]}")
    chapter_data = "\n\n".join(chapter_data_list) if chapter_data_list else "暂无数据"

    final_prompt = f"""你是一位顶尖高校的【新闻传播学教授】兼【资深舆情分析专家】。
请根据【事实清单】、【参考数据】和【理论知识】，撰写报告章节：《{chapter['title']}》。

=== 【事实清单 - 数据基准】 ===
以下为系统已核实的数据；标注为"未知/无数据"的维度，请在正文中如实说明，严禁编造任何数值：
{json.dumps(fact_sheet, ensure_ascii=False, indent=2)}

=== 【理论知识】 ===
{context_text}

=== 【参考数据明细】 ===
{chapter_data}

=== 【严格写作要求】 ===
1. 纯段落叙述，禁止列表、编号、分点。
2. 数据为0或未知时用"该维度暂无显著特征/暂无完整数据"一笔带过。
3. 三段式论证：引用已核实数值 + 传播学理论解释 + 明确判断。
4. 时间锚点用 real_earliest_date/real_latest_date；若为"未知"用"本期数据"，禁止编造日期。
5. 关键论断后括号标注理论来源；任何数据必须来自事实清单，没有的一律不写。
6. 字数 600-900 字，直接输出纯文本正文，不要标题。"""
    final_prompt = deep_sanitize(final_prompt)

    last_err = None
    for attempt in range(3):
        try:
            resp = xinghuo_llm.client.chat.completions.create(
                model=xinghuo_llm.model_name,
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0.3, max_tokens=2048)
            content = (resp.choices[0].message.content or "").strip()
            if content:
                cleaned = clean_llm_output(content, chapter_title=chapter["title"])
                return cleaned or "（该章节生成失败）"
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    return f"（该章节生成失败：{last_err}）"


def _gen_chapters_parallel(fact_sheet, safe_data):
    """7 章并行生成（工作流步骤）"""
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_gen_one, ch, fact_sheet, safe_data): ch["title"] for ch in CHAPTERS}
        out = {}
        for fut in futures:
            out[futures[fut]] = fut.result()
    return out


def _build_docx(chapters, charts, report_dir="reports"):
    """排版并保存 Word（工作流步骤）"""
    if Document is None:
        print("[LITE] python-docx 不可用，跳过 Word 报告生成")
        return None
    os.makedirs(report_dir, exist_ok=True)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    style.paragraph_format.line_spacing = 1.5
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), "SimSun")

    title = doc.add_heading("网络舆情分析综合报告", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if title.runs:
        _set_run_font(title.runs[0], cn_font="SimHei", size=Pt(22), color=RGBColor(0, 0, 0))

    p_ai = doc.add_paragraph()
    p_ai.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_ai = p_ai.add_run(
        "⚠️ [AI生成标识] 本报告由新闻传播学垂类大模型结合本地数据库与学科知识库(RAG)自动生成，仅供教学科研参考，不构成任何决策建议。")
    _set_run_font(run_ai, size=Pt(10), color=RGBColor(0x80, 0x80, 0x80))

    for idx, ch in enumerate(CHAPTERS):
        heading = doc.add_heading(ch["title"], level=1)
        if heading.runs:
            _set_run_font(heading.runs[0], cn_font="SimHei", size=Pt(16), color=RGBColor(0, 0, 0))
        content = chapters.get(ch["title"], "")
        for para_text in [p.strip() for p in str(content).split("\n") if p.strip()]:
            p = doc.add_paragraph(para_text)
            p.paragraph_format.first_line_indent = Cm(0.74)
        chart_key = ch.get("chart")
        if chart_key and chart_key in charts:
            try:
                img_para = doc.add_paragraph()
                img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run_img = img_para.add_run()
                run_img.add_picture(charts[chart_key], width=Inches(5.5))
            except Exception:
                pass

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{report_dir}/舆情分析报告_{timestamp}.docx"
    doc.save(filename)
    return filename


def generate_report_workflow(use_data, report_dir="reports"):
    """WorkflowEngine 编排主链路：数据→事实→图表→并行章节→保存"""
    engine = WorkflowEngine()
    engine.add_step("fact_sheet", lambda **kw: extract_fact_sheet(use_data))
    engine.add_step("safe_data",
                    lambda **kw: {k: format_data_for_llm(v) for k, v in use_data.items()})
    engine.add_step("charts", lambda **kw: generate_charts(use_data, report_dir))
    engine.add_step("chapters", lambda fact_sheet, safe_data, **kw: _gen_chapters_parallel(fact_sheet, safe_data),
                    max_retries=1)
    engine.add_step("save", lambda chapters, charts, **kw: _build_docx(chapters, charts, report_dir),
                    max_retries=1)
    results = engine.execute()
    save_step = next((r for r in results if r["step"] == "save"), None)
    if save_step and save_step["status"] == "success":
        return save_step["output"]
    raise RuntimeError(f"报告生成失败: {results}")