"""
文件解析：把用户上传的文档转成纯文本，供大模型消费。

⚠️ 为什么不用 unstructured 的 partition/auto：
    本项目所在的 venv（base = E:\\pythonTest，Python 3.13.7）里，
    `unstructured.partition.image` 会在 ctypes 加载动态库时触发
    0xC0000409（栈缓冲区溢出）、`unstructured.partition.json` 触发
    0xC0000005（访问违例），两者都会直接把解释器打成段错误；
    另外 `.md` 缺 markdown、`.xlsx` 缺 msoffcrypto 依赖。
    而 `unstructured.partition.auto` 会把上述模块全部拉进来，
    导致「用户一上传文档、Flask 进程就崩」。
    因 llm_service 里是函数内惰性导入，启动时不会暴露，只有真上传才炸。

    所以这里改为「按扩展名精确分派」到轻量库：
        .pdf          → PyMuPDF(fitz)，失败回退 pdfminer.six
        .docx         → python-docx（段落 + 表格，保持文档顺序）
        .xlsx / .xlsm → openpyxl（只读模式）
        .pptx         → python-pptx
        .html / .htm  → BeautifulSoup
        .txt/.md/.csv/.tsv/.json → 直接读（保留原有行为，并加了编码回退）
    以上库均已在本环境安装且导入正常，全链路不再触碰 unstructured。
"""
import os
from typing import Iterator, List

from .config import logger

# —— 纯文本：直接读取，不走任何解析器 ——
_PLAIN_EXTS = {'.txt', '.md', '.markdown', '.csv', '.tsv', '.json'}

# —— 旧版二进制格式：无可靠纯 Python 解析器，明确提示而不是崩溃 ——
_LEGACY_HINT = {
    '.doc': '暂不支持旧版 .doc 格式，请用 Word 另存为 .docx 后重新上传',
    '.xls': '暂不支持旧版 .xls 格式，请用 Excel 另存为 .xlsx 后重新上传',
}


# ============================ 纯文本 ============================
def _read_plain_text(file_path: str) -> str:
    """按 utf-8-sig → utf-8 → gbk 顺序尝试解码，全失败则用替换字符兜底。"""
    for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb18030'):
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"读取纯文本文件失败: {file_path} - {e}")
            return f"文件读取错误：{e}"
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


# ============================ PDF ============================
def _parse_pdf(file_path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        fitz = None

    if fitz is not None:
        parts: List[str] = []
        with fitz.open(file_path) as doc:
            for page in doc:
                txt = page.get_text()
                if txt and txt.strip():
                    parts.append(txt.strip())
        text = "\n\n".join(parts).strip()
        if text:
            return text
        logger.warning(f"PDF 未提取到文字（疑为扫描件/图片型）: {file_path}")
        return "（该 PDF 未提取到文字，可能是扫描件或图片型 PDF，请改用图片上传走 OCR）"

    from pdfminer.high_level import extract_text
    return extract_text(file_path) or ""


# ============================ DOCX ============================
def _iter_docx_blocks(doc) -> Iterator[object]:
    """按文档正文的真实顺序产出段落与表格（python-docx 的 paragraphs/tables 会各丢顺序）。"""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in doc.element.body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, doc)
        elif child.tag == qn('w:tbl'):
            yield Table(child, doc)


def _parse_docx(file_path: str) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(file_path)
    blocks: List[str] = []
    table_seq = 0

    for block in _iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                blocks.append(t)
        elif isinstance(block, Table):
            table_seq += 1
            rows = []
            for row in block.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append(f"【表格{table_seq}】")
                blocks.extend(rows)

    return "\n".join(blocks)


# ============================ XLSX ============================
def _parse_xlsx(file_path: str) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(file_path, read_only=True, data_only=True)
    try:
        out: List[str] = []
        for ws in wb.worksheets:
            out.append(f"【工作表：{ws.title}】")
            for row in ws.iter_rows(values_only=True):
                cells = ["" if v is None else str(v).strip() for v in row]
                if any(cells):
                    out.append(" | ".join(cells))
        return "\n".join(out)
    finally:
        wb.close()


# ============================ PPTX ============================
def _parse_pptx(file_path: str) -> str:
    from pptx import Presentation

    prs = Presentation(file_path)
    out: List[str] = []
    for idx, slide in enumerate(prs.slides, 1):
        out.append(f"【第{idx}页】")
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = "".join(run.text for run in para.runs).strip()
                    if t:
                        out.append(t)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        out.append(" | ".join(cells))
    return "\n".join(out)


# ============================ HTML ============================
def _parse_html(file_path: str) -> str:
    from bs4 import BeautifulSoup

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    for tag in soup(['script', 'style']):
        tag.decompose()
    return soup.get_text('\n', strip=True)


_DISPATCH = {
    '.pdf': _parse_pdf,
    '.docx': _parse_docx,
    '.xlsx': _parse_xlsx,
    '.xlsm': _parse_xlsx,
    '.pptx': _parse_pptx,
    '.html': _parse_html,
    '.htm': _parse_html,
}


def parse_file_to_text(file_path: str) -> str:
    """
    把文件解析为纯文本（PDF / DOCX / XLSX / PPTX / HTML / TXT / MD / CSV）。

    注意：绝不 import unstructured —— 该库在本环境会打崩解释器，详见模块开头说明。
    """
    if not file_path or not os.path.exists(file_path):
        return f"文件不存在：{file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    # 纯文本直接读取，效率最高
    if ext in _PLAIN_EXTS:
        return _read_plain_text(file_path)

    if ext in _LEGACY_HINT:
        logger.warning(f"不支持的旧版格式 {ext}: {file_path}")
        return _LEGACY_HINT[ext]

    handler = _DISPATCH.get(ext)
    if handler is None:
        logger.warning(f"不支持的文件类型 {ext or '（无扩展名）'}: {file_path}")
        return f"不支持的文件类型：{ext or '（无扩展名）'}"

    try:
        text = handler(file_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"解析文件失败: {file_path} - {e}")
        return f"文件解析失败：{e}"

    if not text or not text.strip():
        return "（文件解析完成，但未提取到文字内容）"
    return text
