import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# ===================== 日志配置（控制台 + 文件） =====================
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("XinghuoLLM")

try:
    _file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "xinghuo_llm.log"),
        maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_file_handler)
except Exception as e:
    logger.warning(f"日志文件写入不可用: {e}")

# ==================== 全局常量 ====================
DB_PATH = "data.db"
VECTOR_DB_PATH = "vector_db.json"
FILE_UPLOAD_FOLDER = "uploads"
os.makedirs(FILE_UPLOAD_FOLDER, exist_ok=True)

# HuggingFace 国内镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# ===================== RAG 参数（与 rag_service 保持一致） =====================
RERANK_THRESHOLD = -3.0            # bge-reranker-v2-m3 重排后保留的最低分数
RERANK_SOURCE_SCORE_FLOOR = -6.0   # 低于此分视为"无相关知识"

# ===================== 配置与日志初始化 =====================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
env_path = os.path.join(root_dir, ".env")

logger.info(f"正在尝试加载 .env 文件，路径：{env_path}")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
    logger.info(".env 文件加载成功！")
else:
    logger.warning("未找到 .env 文件！请检查路径！")