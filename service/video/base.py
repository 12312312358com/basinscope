# -*- coding: utf-8 -*-
"""分析器基类：只约束形状，不约束内容（方案 §十 10.2）。

ctx 由 runner 注入，统一字段：
    ctx['record']   : 一条内容记录（dict，列名即 t_bettafish_article 的列）
    ctx['comments'] : 该内容关联的评论文本列表（list[str]）
    ctx['cover_url']: 封面图地址（str 或 None）
analyze() 返回 {key: value, ...} 的 KV 字典；异常由 runner 兜底为 status='error'。
"""
from registry import register  # noqa: F401  (供子类用 @register)


class BaseAnalyzer:
    name = ''           # 唯一标识，写入 feature.analyzer
    version = '0.1'     # 版本，便于重算与回溯
    needs = ()          # 声明依赖：metadata / cover_url / comments

    def analyze(self, ctx):
        raise NotImplementedError
