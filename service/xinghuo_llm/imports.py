from .config import logger

# ===================== 安全导入 DAO、RAG 和验证器模块 =====================
def _fallback_data(*args, **kwargs):
    return "数据暂缺"

try:
    if __import__('os').getenv('LITE_MODE') == '1':
        raise ImportError('LITE 模式：跳过 MySQL，使用静态数据')
    from dao.articleDao import (
        getTotalArticle, getTopAuthor, getTopRegion, getArticleTopZan,
        get7DayArticle, getArticleTypeAmount, getTopCommentUser, getBasinHotEvents
    )
    from dao.commentDao import (
        getAllComment, getCommentAmount, getCommentTotal, getCommentHotWordAmount, getCommentByHotWord
    )
    logger.info("[OK] 数据库 DAO 模块加载成功！")
except Exception as e:
    logger.warning(f'DAO 模块导入失败 ({e})，尝试加载 LITE 静态数据...')
    # ===== LITE 海外模式：数据库不可用时，从 lite_data.json 读取静态统计 =====
    _lite_data = {}
    try:
        import os as _os, json as _json
        _lite_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
            'lite_data.json')
        if _os.path.exists(_lite_path):
            with open(_lite_path, 'r', encoding='utf-8') as _f:
                _lite_data = _json.load(_f)
            logger.info('LITE 静态数据加载成功')
    except Exception as _le:
        logger.warning(f'LITE 静态数据加载失败: {_le}')

    def _lite(key):
        def _inner(*a, **kw):
            return _lite_data.get(key) or _fallback_data()
        return _inner

    def _lite_comments():
        return _lite_data.get('comments') or []

    def _lite_comment_by_hotword(hotword):
        if not hotword:
            return []
        hw = str(hotword)
        return [c for c in _lite_data.get('comments', []) if isinstance(c, list) and len(c) > 1 and hw in str(c[1])]

    def _lite_comment_hotword_amount(hotword):
        matched = _lite_comment_by_hotword(hotword)
        date_map = {}
        for c in matched:
            d2 = str(c[2])[:10] if len(c) > 2 and c[2] else '未知'
            date_map[d2] = date_map.get(d2, 0) + 1
        items = sorted(date_map.items())
        return [[dd, nn] for dd, nn in items[-7:]]

    getTotalArticle = _lite('getTotalArticle')
    getTopAuthor = _lite('getTopAuthor')
    getTopRegion = _lite('getTopRegion')
    getArticleTopZan = _lite('getArticleTopZan')
    get7DayArticle = _lite('get7DayArticle')
    getArticleTypeAmount = _lite('getArticleTypeAmount')
    getTopCommentUser = _lite('getTopCommentUser')
    getBasinHotEvents = _lite('getBasinHotEvents')
    getAllComment = _lite_comments
    getCommentAmount = _lite('getCommentAmount')
    getCommentTotal = _lite('getCommentTotal')
    getCommentHotWordAmount = _lite_comment_hotword_amount
    getCommentByHotWord = _lite_comment_by_hotword

try:
    from service.rag_service import get_knowledge, get_knowledge_with_refs, rag_db
    logger.info("[OK] RAG 知识库模块加载成功！")
except Exception as e:
    logger.warning(f"RAG 模块导入失败 ({e})，学术知识检索将不可用。")
    get_knowledge = lambda query, db=None, top_k=5, source_filter=None: "知识库不可用"
    get_knowledge_with_refs = lambda query, db=None, top_k=5, source_filter=None: ("知识库不可用", [])
    rag_db = None

try:
    from service.academic_validator import academic_validator
    logger.info("[SAFE] 学术合规验证器 (AcademicValidator) 加载成功！")
except Exception as e:
    logger.warning(f" 学术合规验证器导入失败 ({e})，将降级使用基础正则兜底。")
    academic_validator = None