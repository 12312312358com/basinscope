# -*- coding: utf-8 -*-
from .config import logger
from .imports import rag_db
from .knowledge_base import SubjectKnowledgeBase
from .assistant_tools import ResearchAssistant
from .llm_service import XinghuoLLMService, assemble_use_data

# ===================== 全局实例化 =====================
try:
    xinghuo_llm = XinghuoLLMService()
    spark_llm = xinghuo_llm
    logger.info("[OK] XinghuoLLMService 初始化成功！")
except Exception as e:
    logger.error(f"[ERR] 星火大模型服务初始化失败：{str(e)}")
    xinghuo_llm = None
    spark_llm = None

# ===================== 依赖注入 =====================
ResearchAssistant.llm = xinghuo_llm
ResearchAssistant.rag_db = rag_db

# ===================== 附加引用（供其他模块访问） =====================
if xinghuo_llm:
    xinghuo_llm.knowledge_base = SubjectKnowledgeBase
    xinghuo_llm.research_assistant = ResearchAssistant
    logger.info("[OK] 增强模块已附加到 xinghuo_llm")