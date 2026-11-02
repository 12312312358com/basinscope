# service/academic_validator.py
import re
import logging

logger = logging.getLogger("AcademicValidator")


class AcademicValidator:
    """学术内容可追溯性验证器（引用必须来自真实 RAG 文档，绝不伪造角标）"""

    @staticmethod
    def validate_citations(content: str, references: list) -> dict:
        """
        校验回答中的 [n] 角标：
        - 无角标 → 不通过，但只提示、不自动注入（防止伪造引用）
        - 角标指向不存在的文献 → 不通过
        """
        result = {
            "valid": False,
            "citation_count": 0,
            "missing_refs": [],
            "fixed_content": content
        }
        citations = re.findall(r'\[(\d+)\]', content)
        result["citation_count"] = len(citations)

        if not citations:
            logger.warning("[WARN] 未检测到角标引用，将如实提示用户（不自动注入）")
            return result

        cited_ids = set(map(int, citations))
        ref_ids = set(range(1, len(references) + 1))
        result["missing_refs"] = list(cited_ids - ref_ids)
        result["valid"] = (len(result["missing_refs"]) == 0)
        return result

    @staticmethod
    def validate_ai_disclosure(content: str) -> bool:
        """验证 AI 生成标识（比赛合规性要求）"""
        disclosure_keywords = ["AI生成", "人工智能辅助", "大模型生成", "由系统自动生成"]
        return any(kw in content for kw in disclosure_keywords)


# 全局实例
academic_validator = AcademicValidator()