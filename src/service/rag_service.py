import charset_normalizer
import os
import shutil
import time
import threading
import logging
import warnings
from typing import List, Tuple, Dict, Any, Optional

# ================= 环境变量配置 (必须在导入 AI 库之前) =================
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ["TOKENIZERS_PARALLELISM"] = "false"

warnings.filterwarnings("ignore", category=UserWarning)

try:
    import torch
except ImportError:
    torch = None
from tqdm import tqdm
try:
    from langchain_core.documents import Document
except ImportError:
    Document = None
try:
    from langchain_community.vectorstores import Chroma
except ImportError:
    Chroma = None
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    except ImportError:
        HuggingFaceEmbeddings = None

try:
    from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
except ImportError:
    MarkdownHeaderTextSplitter = RecursiveCharacterTextSplitter = None

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    try:
        from langchain.retrievers.ensemble import EnsembleRetriever
    except ImportError:
        try:
            from langchain_classic.retrievers import EnsembleRetriever
        except ImportError:
            EnsembleRetriever = None

try:
    from langchain_community.retrievers import BM25Retriever
except ImportError:
    BM25Retriever = None
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

# 🌟 新增：文件监控依赖
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("[WARN] watchdog 库未安装，文件监控功能将不可用。请运行: pip install watchdog")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)

KNOWLEDGE_DIR = os.path.join(root_dir, "knowledge")
CHROMA_DIR = os.path.join(root_dir, "chroma_db")

COLLECTION_NAME = "weibo_knowledge_base"

# RAG 阈值（与 xinghuo_llm/config.py 保持一致）
RERANK_THRESHOLD = -3.0            # 重排后保留的最低分数
RERANK_SOURCE_SCORE_FLOOR = -6.0   # 低于此分视为"无相关知识"
RERANK_LIMIT = int(os.getenv("RAG_RERANK_LIMIT", "8"))  # CPU 端重排对数上限，避免卡顿

SUPPORTED_EXTENSIONS = (".txt", ".md")

_LOCAL_EMB = os.path.join(root_dir, "models", "bge-large-zh-v1.5")
_LOCAL_RERANK = os.path.join(root_dir, "models", "bge-reranker-v2-m3")


def _resolve_hf_model_to_local_path(hf_model_id: str) -> str:
    """
    🌟 核心修复：将 HuggingFace 模型 ID 解析为本地缓存的实际目录路径。
    彻底避免 CrossEncoder 在离线模式下强制联网检查 modules.json 的问题。
    """
    # 1. 如果已经是本地目录，直接返回
    if os.path.isdir(hf_model_id) and os.path.exists(os.path.join(hf_model_id, "config.json")):
        return hf_model_id

    # 2. 通过 huggingface_hub 缓存扫描，获取本地快照路径（纯本地操作，不联网）
    try:
        from huggingface_hub import scan_cache_dir
        cache_info = scan_cache_dir()
        for repo_info in cache_info.repos:
            if repo_info.repo_id == hf_model_id and repo_info.repo_type == "model":
                for revision in repo_info.revisions:
                    snapshot_path = str(revision.snapshot_path)
                    if os.path.isdir(snapshot_path):
                        logger.info(f"[LINK] 解析本地缓存路径: {hf_model_id} → {snapshot_path}")
                        return snapshot_path
    except Exception as e:
        logger.warning(f"scan_cache_dir 失败: {e}")

    # 3. 手动查找标准缓存目录
    try:
        cache_home = os.environ.get('HF_HOME',
                                    os.path.join(os.path.expanduser('~'), '.cache', 'huggingface'))
        hub_dir = os.path.join(cache_home, 'hub')
        repo_dir_name = "models--" + hf_model_id.replace("/", "--")
        repo_dir = os.path.join(hub_dir, repo_dir_name, "snapshots")
        if os.path.isdir(repo_dir):
            for revision_hash in os.listdir(repo_dir):
                snapshot_path = os.path.join(repo_dir, revision_hash)
                if os.path.isdir(snapshot_path) and os.path.exists(
                        os.path.join(snapshot_path, "config.json")):
                    logger.info(f"[LINK] 手动解析缓存路径: {hf_model_id} → {snapshot_path}")
                    return snapshot_path
    except Exception as e:
        logger.warning(f"手动缓存查找失败: {e}")

    # 4. 兜底：返回原始 ID
    logger.warning(f"[WARN] 无法解析本地路径，将使用原始 ID: {hf_model_id}（可能触发联网）")
    return hf_model_id


def _ensure_local_model(hf_id: str, local_path: str) -> str:
    if os.environ.get('HF_HUB_OFFLINE') == '1' or os.environ.get('TRANSFORMERS_OFFLINE') == '1':
        if os.path.isdir(local_path) and os.path.exists(os.path.join(local_path, "config.json")):
            logger.info(f"[OK] 检测到本地模型，将离线加载：{local_path}")
            return local_path
        logger.info(f"[LOCK] 离线模式：跳过下载，将从本地缓存加载 {hf_id}")
        return hf_id

    if os.path.isdir(local_path) and os.path.exists(os.path.join(local_path, "config.json")):
        logger.info(f"[OK] 检测到本地模型，将离线加载：{local_path}")
        return local_path
    try:
        from huggingface_hub import snapshot_download
        logger.info(f"[WAIT] 本地无模型，开始下载到 {local_path}（首次需联网，支持断点续传）...")
        snapshot_download(repo_id=hf_id, local_dir=local_path)
        logger.info(f"[OK] 下载完成：{local_path}")
        return local_path
    except Exception as e:
        logger.warning(f"[WARN] 下载失败（{e}），回退联网加载：{hf_id}")
        return hf_id


EMBEDDING_MODEL_NAME = _ensure_local_model("BAAI/bge-large-zh-v1.5", _LOCAL_EMB)
RERANKER_MODEL_NAME = _ensure_local_model("BAAI/bge-reranker-v2-m3", _LOCAL_RERANK)

DEVICE = 'cuda' if torch is not None and torch.cuda.is_available() else 'cpu'
# Reranker 独立设备配置：默认跟随 GPU（fp16 约 1.2G，速度远快于 CPU）。
# 8GB 显存机型上，本地微调 Qwen(f16~3G) + Embedding(~1.3G) + Reranker(f16~1.2G) 约 5.5G，
# 配合各阶段 torch.cuda.empty_cache() 可正常运行；若仍 OOM 会自动降级到 CPU 重试。
# 如需强制 CPU（慢但省显存），设环境变量 RERANKER_DEVICE=cpu。
RERANKER_DEVICE = (os.getenv("RERANKER_DEVICE", "") or DEVICE).lower()
if RERANKER_DEVICE == "cuda" and DEVICE != "cuda":
    RERANKER_DEVICE = "cpu"
logger.info(f"当前使用计算设备：{DEVICE} | Reranker 设备：{RERANKER_DEVICE}")


def load_text_safely(file_path: str) -> str:
    try:
        if file_path.endswith('.md'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read().replace('\x00', '').strip()
            except UnicodeDecodeError:
                pass

        with open(file_path, 'rb') as f:
            raw_data = f.read()

        result = charset_normalizer.from_bytes(raw_data).best()
        if result is None:
            return ""

        text = str(result)
        text = text.replace('\x00', '').strip()
        return text
    except Exception as e:
        logger.error(f"读取失败 {file_path}: {e}")
        return ""


def _split_documents(documents):
    """按文档类型选择切块策略：Markdown 按标题层级切，纯文本按语义切"""
    md_headers = [("##", "h2"), ("###", "h3"), ("####", "h4")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=md_headers,
                                             strip_headers=False)
    txt_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=100,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""])
    result = []
    for d in documents:
        page = d.page_content
        meta = d.metadata
        if page.lstrip().startswith("#") or str(meta.get("source", "")).endswith(".md"):
            try:
                chunks = md_splitter.split_text(page)
                for ch in chunks:
                    content = ch.page_content
                    title_path = " > ".join(str(v) for v in ch.metadata.values() if v)
                    if title_path:
                        content = f"【{title_path}】\n{content}"
                    result.append(Document(page_content=content, metadata=dict(meta)))
                continue
            except Exception:
                pass
        result.extend(txt_splitter.split_documents([d]))
    return result


class KnowledgeFileHandler(FileSystemEventHandler):
    """监控知识库目录的文件变化，并调用 AdvancedRAG 的增量索引方法"""
    def __init__(self, rag_instance):
        self.rag = rag_instance

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(SUPPORTED_EXTENSIONS):
            logger.info(f"[NEW] 检测到新文件: {event.src_path}")
            self.rag.index_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(SUPPORTED_EXTENSIONS):
            logger.info(f"[SYNC] 检测到文件修改: {event.src_path}")
            self.rag.remove_file_from_index(event.src_path)
            self.rag.index_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(SUPPORTED_EXTENSIONS):
            logger.info(f"[DEL] 检测到文件删除: {event.src_path}")
            self.rag.remove_file_from_index(event.src_path)


class AdvancedRAG:
    def __init__(self):
        self.embeddings = None
        self.vectorstore = None
        self.reranker = None
        self.splits = []          # 保留全量文档块，供 BM25 重建
        self.ensemble_retriever = None
        self.file_to_ids = {}     # 映射：file_path -> [doc_id1, doc_id2, ...]
        self.lock = threading.Lock()  # 线程安全锁
        self._gpu_released = False    # 检索模型是否已被临时挪到 CPU
        if os.getenv("LITE_MODE") == "1":
            logger.info("LITE 模式：跳过本地模型与向量库加载（RAG 降级）")
        else:
            self._init_models()
            self._init_rag()

    def _init_models(self):
        """初始化 Embedding 和 Reranker 模型"""
        logger.info("正在加载 Embedding 模型 (bge-large-zh)...")

        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={
                'device': DEVICE,
                'local_files_only': True
            },
            encode_kwargs={'normalize_embeddings': True, 'batch_size': 32}
        )

        logger.info("正在加载 Reranker 重排序模型 (bge-reranker-v2-m3)...")

        reranker_local_path = _resolve_hf_model_to_local_path(RERANKER_MODEL_NAME)
        logger.info(f"[DIR] Reranker 实际加载路径: {reranker_local_path}")

        self.reranker = CrossEncoder(
            model_name_or_path=reranker_local_path,
            device=RERANKER_DEVICE,
        )
        # GPU 上改用 fp16：显存占用减半（2.3G → 1.2G），为本地微调模型腾出空间
        if RERANKER_DEVICE == "cuda":
            try:
                self.reranker.model.half()
                logger.info("[OK] Reranker 已切换 fp16（显存占用减半）")
            except Exception as e:
                logger.warning(f"[WARN] Reranker fp16 转换失败，保持 fp32: {e}")
        logger.info("[OK] 所有模型加载完毕！")

    def _rerank_predict(self, pairs):
        """带显存回收 + OOM 自动降级的 Rerank 推理。

        8GB 显卡上本地微调模型与 Reranker 共用显存，容易在连续提问时 OOM：
        1) 推理前先 empty_cache 回收碎片；
        2) 首次 OOM 后把 Reranker 降级到 CPU 重试一次，保证服务不中断。
        """
        try:
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
            return self.reranker.predict(pairs, convert_to_numpy=True)
        except RuntimeError as e:
            if "out of memory" not in str(e).lower():
                raise
            logger.warning("[WARN] Rerank 显存不足，回收显存后降级到 CPU 重试")
            try:
                if torch is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                self.reranker.model.to("cpu")
                scores = self.reranker.predict(pairs, convert_to_numpy=True)
                if torch is not None and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                return scores
            except Exception as e2:
                logger.error(f"[ERR] Rerank CPU 降级仍失败: {e2}")
                raise

    def release_gpu(self):
        """本地微调模型生成前，把检索侧模型临时挪到 CPU 腾显存。

        8GB 显卡（RTX 4060 Laptop）上，微调模型 fp16 ~3G + Embedding ~1.3G
        + Reranker fp16 ~1.2G 同时驻留会溢出到内存，导致生成从 6 秒劣化到 80+ 秒
        甚至卡死。生成前先释放，生成后由 resume_gpu() 还原。
        """
        if torch is None or not torch.cuda.is_available():
            return
        if self._gpu_released:
            torch.cuda.empty_cache()
            return
        moved = []
        try:
            client = getattr(self.embeddings, "client", None)
            if client is not None:
                client.to("cpu")
                moved.append("Embedding")
        except Exception as e:
            logger.warning(f"[WARN] Embedding 释放显存失败: {e}")
        try:
            if self.reranker is not None:
                self.reranker.model.to("cpu")
                moved.append("Reranker")
        except Exception as e:
            logger.warning(f"[WARN] Reranker 释放显存失败: {e}")
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        self._gpu_released = True
        if moved:
            logger.info(f"[CLEAN] 已释放检索模型显存（{'/'.join(moved)} → CPU），供本地模型生成")

    def resume_gpu(self):
        """生成结束后把检索侧模型还原到 GPU（幂等，未释放时直接返回）。"""
        if torch is None or not torch.cuda.is_available():
            return
        if not self._gpu_released:
            return
        moved = []
        try:
            if self.embeddings is not None and DEVICE == "cuda":
                client = getattr(self.embeddings, "client", None)
                if client is not None:
                    client.to(DEVICE)
                    moved.append("Embedding")
        except Exception as e:
            logger.warning(f"[WARN] Embedding 还原 GPU 失败: {e}")
        try:
            if self.reranker is not None and RERANKER_DEVICE == "cuda":
                self.reranker.model.to(RERANKER_DEVICE)
                try:
                    self.reranker.model.half()
                except Exception:
                    pass
                moved.append("Reranker")
        except Exception as e:
            logger.warning(f"[WARN] Reranker 还原 GPU 失败: {e}")
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        self._gpu_released = False
        if moved:
            logger.info(f"[RECYCLE] 检索模型已还原 GPU（{'/'.join(moved)}）")

    def _init_rag(self):
        """初始化 RAG 知识库：全量加载并启动文件监控"""
        documents = []
        total_chars = 0
        self.file_to_ids = {}

        if not os.path.exists(KNOWLEDGE_DIR):
            raise ValueError(f"知识库文件夹不存在！请检查路径：{KNOWLEDGE_DIR}")

        logger.info(f"开始深度扫描双轨知识库：{KNOWLEDGE_DIR}")
        for root, dirs, files in os.walk(KNOWLEDGE_DIR):
            for filename in files:
                if filename.endswith(SUPPORTED_EXTENSIONS):
                    file_path = os.path.join(root, filename)
                    text = load_text_safely(file_path)

                    if text and len(text) > 10:
                        source_type = "summary" if "历史笔记" in root else "full_text"
                        doc = Document(
                            page_content=text,
                            metadata={
                                "title": os.path.splitext(filename)[0],
                                "source": filename,
                                "source_type": source_type,
                                "file_path": file_path
                            }
                        )
                        documents.append(doc)
                        total_chars += len(text)
                        tag = "摘要" if source_type == "summary" else "正文"
                        logger.info(f"[{tag}] 加载成功：{filename} (字数：{len(text)})")

        if not documents:
            raise ValueError(f"知识库为空！请确保 {KNOWLEDGE_DIR} 目录下有 .txt 或 .md 文件。")

        self.splits = _split_documents(documents)
        logger.info(f"切分为 {len(self.splits)} 个高质量文本块 (总字数：{total_chars})")

        # 构建 file_to_ids 映射（每个文件内从 0 计数，避免跨文件索引错乱）
        file_counts = {}
        for d in self.splits:
            file_path = d.metadata.get("file_path", "")
            cnt = file_counts.get(file_path, 0)
            file_counts[file_path] = cnt + 1
            doc_id = f"{file_path}_chunk_{cnt}"
            self.file_to_ids.setdefault(file_path, []).append(doc_id)

        self.vectorstore = None
        need_rebuild = False

        if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
            logger.info("[FIND] 发现本地向量库目录，正在智能识别集合...")
            try:
                import chromadb
                client = chromadb.PersistentClient(path=CHROMA_DIR)
                existing_collections = client.list_collections()

                target_collection = None
                for c in existing_collections:
                    if c.name == COLLECTION_NAME:
                        target_collection = COLLECTION_NAME
                        break

                if target_collection is None and existing_collections:
                    target_collection = existing_collections[0].name
                    logger.warning(
                        f"⚠️ 未找到指定集合 [{COLLECTION_NAME}]，自动兼容加载历史集合：[{target_collection}]")

                if target_collection:
                    test_vectorstore = Chroma(
                        persist_directory=CHROMA_DIR,
                        embedding_function=self.embeddings,
                        collection_name=target_collection
                    )

                    doc_count = test_vectorstore._collection.count()
                    if doc_count > 0:
                        test_vectorstore.similarity_search("test", k=1)
                        logger.info(f"[OK] 加载成功！使用集合：[{target_collection}]（含 {doc_count} 个文档块）")
                        self.vectorstore = test_vectorstore
                    else:
                        logger.warning(f"[WARN] 集合 [{target_collection}] 为空，需要重建...")
                        need_rebuild = True
                else:
                    logger.warning("[WARN] 数据库目录存在但无任何集合，需要重建...")
                    need_rebuild = True

            except Exception as e:
                logger.error(f"[ERR] 集合识别失败：{str(e)}")
                logger.info("[WARN] 将尝试强制重建向量库...")
                need_rebuild = True
        else:
            logger.info("[FOLDER] 未发现本地向量库，将创建新库...")
            need_rebuild = True

        if need_rebuild or self.vectorstore is None:
            logger.info(f"[START] 开始构建向量库 (共 {len(self.splits)} 个文本块)...")

            if os.path.exists(CHROMA_DIR):
                shutil.rmtree(CHROMA_DIR, ignore_errors=True)
            os.makedirs(CHROMA_DIR, exist_ok=True)

            self.vectorstore = Chroma(
                embedding_function=self.embeddings,
                persist_directory=CHROMA_DIR,
                collection_name=COLLECTION_NAME
            )

            batch_size = 100
            total_batches = (len(self.splits) + batch_size - 1) // batch_size

            for i in tqdm(range(0, len(self.splits), batch_size),
                          total=total_batches,
                          desc="⏳ 向量化进度"):
                batch = self.splits[i:i + batch_size]
                # 使用游标按文件顺序消费 ID，避免跨文件索引越界
                consumed = {}
                ids = []
                for d in batch:
                    fp = d.metadata["file_path"]
                    idx = consumed.get(fp, 0)
                    consumed[fp] = idx + 1
                    ids.append(self.file_to_ids[fp][idx])
                self.vectorstore.add_documents(batch, ids=ids)

            logger.info(f"[SAVE] 向量库构建完成！集合名：[{COLLECTION_NAME}]")

        logger.info("正在构建 BM25 + 向量 混合检索链路...")
        bm25_retriever = BM25Retriever.from_documents(self.splits)
        bm25_retriever.k = 10

        vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 10})

        if EnsembleRetriever:
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, vector_retriever],
                weights=[0.4, 0.6]
            )
        logger.info(f"[OK] RAG 知识库初始化完成！")

        # 启动文件监控
        self._start_watcher()

    def _start_watcher(self):
        """启动文件监控守护线程"""
        if not WATCHDOG_AVAILABLE:
            logger.warning("[WARN] watchdog 未安装，无法启用文件监控动态更新功能。")
            return
        try:
            event_handler = KnowledgeFileHandler(self)
            self.observer = Observer()
            self.observer.schedule(event_handler, path=KNOWLEDGE_DIR, recursive=True)
            self.observer.start()
            logger.info("[LOOK] 文件监控已启动，将自动增量更新知识库...")
        except Exception as e:
            logger.error(f"启动文件监控失败: {e}")

    def index_file(self, file_path: str):
        """索引单个文件并加入向量库（线程安全）"""
        text = load_text_safely(file_path)
        if not text or len(text) <= 10:
            return

        with self.lock:
            # 1. 切分
            source_type = "summary" if "历史笔记" in file_path else "full_text"
            doc = Document(page_content=text, metadata={
                "title": os.path.splitext(os.path.basename(file_path))[0],
                "source": os.path.basename(file_path),
                "source_type": source_type,
                "file_path": file_path
            })
            chunks = _split_documents([doc])

            # 2. 生成 ID 并添加到向量库
            ids = [f"{file_path}_chunk_{i}" for i in range(len(chunks))]
            try:
                self.vectorstore.add_documents(chunks, ids=ids)
                self.file_to_ids[file_path] = ids
                logger.info(f"[OK] 已索引文件: {file_path}，添加 {len(chunks)} 个块")
            except Exception as e:
                logger.error(f"[ERR] 索引文件失败 {file_path}: {e}")
                return

            # 3. 同步 splits（供 BM25 使用）并重建混合检索器
            self.splits = [d for d in self.splits
                           if d.metadata.get("file_path") != file_path]
            self.splits.extend(chunks)
            self._rebuild_bm25()

    def remove_file_from_index(self, file_path: str):
        """从向量库中删除指定文件的所有文档块（线程安全）"""
        with self.lock:
            ids = self.file_to_ids.pop(file_path, [])
            if ids:
                try:
                    self.vectorstore._collection.delete(ids=ids)
                    logger.info(f"[DEL] 已移除文件索引: {file_path}，删除 {len(ids)} 个块")
                except Exception as e:
                    logger.error(f"[ERR] 删除索引失败 {file_path}: {e}")
                    return

            # 同步移除 splits 并重建 BM25
            self.splits = [d for d in self.splits
                           if d.metadata.get("file_path") != file_path]
            self._rebuild_bm25()

    def _rebuild_bm25(self):
        """重建 BM25 检索器（基于当前所有 splits，供增量更新后使用）"""
        if not self.splits:
            self.ensemble_retriever = None
            return
        bm25_retriever = BM25Retriever.from_documents(self.splits)
        bm25_retriever.k = 10
        if EnsembleRetriever and self.vectorstore is not None:
            vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 10})
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, vector_retriever],
                weights=[0.4, 0.6])

    def _single_query_docs(self, query: str, k: int, source_filter: Optional[str] = None):
        """单查询检索（BM25+向量 混合或向量检索），供 RRF 融合复用"""
        if source_filter in ["summary", "full_text"]:
            retriever = self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={
                    "k": k,
                    "fetch_k": 20,
                    "lambda_mult": 0.4,
                    "filter": {"source_type": source_filter}
                }
            )
            return retriever.invoke(query)
        if self.ensemble_retriever:
            return self.ensemble_retriever.invoke(query)
        return self.vectorstore.similarity_search(query, k=k)

    def _rrf_search(self, queries: List[str], top_k: int, source_filter: Optional[str],
                    score_threshold: float, k: int = 60) -> List[Tuple[Document, float]]:
        """多查询 RRF（Reciprocal Rank Fusion）融合检索 + 重排 + 阈值过滤"""
        seen = {}
        for q in queries:
            try:
                docs = self._single_query_docs(q, top_k * 3, source_filter)
            except Exception as e:
                logger.warning(f"RRF 子查询失败: {q[:30]} -> {e}")
                continue
            for rank, doc in enumerate(docs, 1):
                key = doc.page_content[:200]
                if key not in seen:
                    seen[key] = {"doc": doc, "rrf": 0.0}
                seen[key]["rrf"] += 1.0 / (k + rank)

        ranked = sorted(seen.values(), key=lambda x: x["rrf"], reverse=True)[:top_k * 3]
        if not ranked:
            return []

        # 用主查询做重排精排（限制对数，避免 CPU 端过慢）
        try:
            rerank_candidates = ranked[:RERANK_LIMIT]
            pairs = [[queries[0], d["doc"].page_content[:400]] for d in rerank_candidates]  # 同 hybrid_search：截断重排输入
            scores = self._rerank_predict(pairs)
            ranked = [d for _, d in sorted(zip(scores, ranked), key=lambda x: x[0], reverse=True)]
        except Exception as e:
            logger.warning(f"RRF 重排失败，使用 RRF 分数排序: {e}")

        return [(d["doc"], float(d["rrf"])) for d in ranked[:top_k]]

    def hybrid_search(self, query: str, top_k: int = 3, source_filter: Optional[str] = None,
                      score_threshold: float = RERANK_THRESHOLD,
                      extra_queries: Optional[List[str]] = None) -> List[Tuple[Document, float]]:
        """
        🌟 核心检索逻辑：双路召回 + Reranker 精排 + 置信度阈值过滤
        :param score_threshold: bge-reranker-v2-m3 分数阈值，低于此值的结果将被丢弃
        """
        if self.vectorstore is None or self.vectorstore._collection.count() == 0:
            logger.error("[ERR] 向量库无效！")
            return []

        if extra_queries:
            return self._rrf_search([query] + list(extra_queries), top_k, source_filter, score_threshold)

        docs = self._single_query_docs(query, top_k * 3, source_filter)

        if not docs:
            return []

        docs = docs[:RERANK_LIMIT]  # 限制重排对数，避免 CPU 端过慢（实测 15 个候选可达 200s+）
        # 🌟 重排输入截断：cross-encoder 耗时随文本长度平方增长，CPU 上 800+ 字文档
        # 每对需 10~20s；取前 400 字足够判断相关性，重排耗时可降一个数量级。
        # 注意：仅截断重排打分输入，返回给 LLM 的完整证据内容不受影响。
        pairs = [[query, doc.page_content[:400]] for doc in docs]
        scores = self._rerank_predict(pairs)

        sorted_results = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)

        # 🌟 核心修复：增加置信度过滤，只保留真正相关的文档
        filtered_results = [(doc, float(score)) for score, doc in sorted_results
                            if score >= score_threshold][:top_k]

        # 打印日志便于调试阈值
        if sorted_results:
            max_score = sorted_results[0][0]
            logger.info(f"[FIND] Rerank 最高分: {max_score:.4f} | 阈值: {score_threshold} | "
                        f"召回: {len(docs)}篇 → 过滤后: {len(filtered_results)}篇")

        if not filtered_results and sorted_results:
            logger.warning(f"[WARN] 所有 {len(sorted_results)} 篇文档均低于阈值 {score_threshold}，"
                           f"最高分仅 {sorted_results[0][0]:.4f}，判定为无相关知识")

        return filtered_results


try:
    _rag_instance = AdvancedRAG()
except Exception as e:
    logger.error(f"RAG 初始化失败：{str(e)}")
    _rag_instance = None

rag_db = _rag_instance


def get_knowledge(query, db=None, top_k=4, source_filter=None, extra_queries=None):
    """用于普通的 AI 对话问答"""
    if db is None:
        db = _rag_instance
    if db is None:
        return "知识库未初始化，请检查日志。"

    doc_score_pairs = db.hybrid_search(query, top_k=top_k, source_filter=source_filter, extra_queries=extra_queries)

    res = ""
    for d, score in doc_score_pairs:
        source_type = d.metadata.get('source_type', 'unknown')
        tag = "核心摘要" if source_type == "summary" else "全量正文"
        res += f"### 来源文献 [{tag}]：《{d.metadata['source']}》(相关度:{score:.2f})\n{d.page_content}\n\n"

    return res


def get_knowledge_with_refs(query, db=None, top_k=3, source_filter=None, extra_queries=None,
                             per_doc_chars=1200, max_ctx_chars=4000):
    """
    🌟 增强版：面向长文引用的知识检索
    - 返回带 file_path 的完整引用
    - 大模型上下文使用【完整原文】，避免截断导致幻觉
      ⚠️ 但需受预算约束：单个长文本块可达 3000+ 字，5 段拼接后 prompt 近万 token，
         本地 1.5B 模型推理会因此从 8s 劣化到 90s+（显存溢出到内存）。
         故新增 per_doc_chars / max_ctx_chars 两级上限：
         * 综述等长文场景用默认宽松预算（1200/4000）
         * 学科短问答传更小预算（500/1600），既保留关键证据又保证秒级响应
    - 前端展示使用【300字摘要】，保证界面美观
    - 附带 Rerank 置信度分数，供业务层做二次兜底
    """
    if db is None:
        db = _rag_instance
    if db is None:
        return "", []

    doc_score_pairs = db.hybrid_search(query, top_k=top_k, source_filter=source_filter, extra_queries=extra_queries)

    context_text = ""
    references = []
    ctx_budget_exhausted = False

    for idx, (doc, score) in enumerate(doc_score_pairs):
        ref_id = idx + 1
        source_name = doc.metadata.get('source', '未知文献')
        source_type = doc.metadata.get('source_type', 'full_text')
        full_content = doc.page_content

        # 🌟 给大模型的上下文：在预算内尽量完整，避免无截断导致 prompt 过长
        # 上下文预算用尽后，仍继续登记引用条目（保证前端引用卡片完整），只是不再拼接正文
        if not ctx_budget_exhausted:
            ctx_body = full_content if not per_doc_chars else full_content[:per_doc_chars]
            if per_doc_chars and len(full_content) > per_doc_chars:
                ctx_body += "…（后续内容已折叠，完整原文见引用卡片）"
            context_text += f"[{ref_id}] 来源：《{source_name}》(相关度:{score:.2f})\n{ctx_body}\n\n"
            if max_ctx_chars and len(context_text) >= max_ctx_chars:
                context_text += "…（其余证据已达上下文预算上限，详情见引用卡片）\n"
                ctx_budget_exhausted = True

        # 🌟 给前端的展示内容才进行截断
        display_content = full_content[:300] + ("..." if len(full_content) > 300 else "")

        references.append({
            "id": ref_id,
            "title": source_name,
            "type": "核心摘要" if source_type == "summary" else "论文正文",
            "content": display_content,
            "full_content": full_content,
            "score": round(score, 4),
            "file_path": doc.metadata.get('file_path', '')
        })

    return context_text.strip(), references


def reset_vector_db():
    """安全重置向量库（用于调试或强制重建）"""
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)
        logger.info(f"[OK] 已安全删除向量库目录：{CHROMA_DIR}")
    else:
        logger.info(f"[INFO] 向量库目录不存在：{CHROMA_DIR}")
    logger.info("[TIP] 提示：重新启动服务将自动重建向量库")


def force_reload_knowledge():
    """手动强制重载知识库（调用此函数会清空索引并重新全量加载）"""
    global _rag_instance
    if _rag_instance:
        _rag_instance.observer.stop()
        _rag_instance.observer.join()
    reset_vector_db()
    _rag_instance = AdvancedRAG()
    return "知识库已强制重新加载"