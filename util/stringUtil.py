"""
字符串工具类
"""
import re


def remove_all_tags(html_text):
    """
    去除文本中的所有 HTML 标签

    参数:
        html_text: 包含 HTML 标签的文本

    返回:
        纯文本内容（保留标签间的文本）
    """
    # 匹配所有 HTML 标签（包括自闭合标签）
    return re.sub(r'<[^>]+>', '', html_text)


def remove_urls_clean(text):
    """
    删除URL并清理多余空格
    """
    # 删除URL
    no_urls = re.sub(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.\-?=%&:#@$,;+!]*', '', text)
    # 清理连续空格和空行
    return re.sub(r'\s+', ' ', no_urls).strip()


def clean_string(text):
    text = remove_urls_clean(text)
    text = remove_all_tags(text)
    # 匹配所有中文字符（含扩展区）、数字、大小写字母
    pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6dfa-zA-Z0-9]')
    return ''.join(pattern.findall(text))
