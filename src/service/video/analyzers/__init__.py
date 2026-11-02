# -*- coding: utf-8 -*-
"""导入即注册三个 L1 分析器（依赖 service/video 在 sys.path 上）。"""
from .meta_profile import MetaProfileAnalyzer  # noqa: F401
from .cover_visual import CoverVisualAnalyzer  # noqa: F401
from .comment_insight import CommentInsightAnalyzer  # noqa: F401
