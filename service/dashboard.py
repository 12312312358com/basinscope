# -*- coding: utf-8 -*-
"""单页仪表盘数据服务（stale-while-revalidate 缓存 + 产物级增量重算）。

生成链（有依赖，须按序执行）：
  build_hotword_data.py    -> hotword_preview_data.json    jieba 全量分词（约 20s，最贵）
  build_sentiment_data.py  -> sentiment_preview_data.json  依赖 hotword
  build_ip_data.py         -> ip_map_data.json             SQL 统计
  build_feature_data.py    -> feature_detail_data.json     依赖 ip
  build_unified_data.py    -> unified_data.json            依赖上述 4 个 json + 实时查 db_weibo_basin
  build_basin_data.py      -> basin_data.json              直查 t_basin_article / t_basin_comment（流域专题）
  build_unified_page.py    -> BasinScope-黄河流域舆情.html        依赖 unified_data.json + basin_data.json

数据来源：全部来自 db_weibo_basin 实时查询 / 项目 fenci CSV / 知识库与微调文件，非静态快照。

缓存策略（stale-while-revalidate）：
  1) 缓存新鲜  -> 直接返回（毫秒级）
  2) 缓存陈旧  -> 立即返回旧内容（用户零等待），后台线程增量重算
  3) 无缓存    -> 同步生成；应用启动时后台预热，正常不会撞上

增量规则：每个脚本声明「产物 + 依赖 + 新鲜期」，产物仍新鲜且上游本轮未重算则跳过，
从而避免每次刷新都重跑 20 秒的分词。上游重算过则下游强制跟随，保证数据一致。
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_GEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard_gen')
_PRJ = os.path.dirname(_GEN_DIR)
_HTML_NAME = 'BasinScope-黄河流域舆情.html'
_HTML_PATH = os.path.join(_GEN_DIR, _HTML_NAME)

# 优先用项目虚拟环境；缺失时回退到当前解释器（例如精简副本不带 .venv）
_PYTHON = os.path.join(_PRJ, '.venv', 'Scripts', 'python.exe')
if not os.path.isfile(_PYTHON):
    _PYTHON = sys.executable

_MINUTE = 60
_HOUR = 3600

_HTML_TTL = 10 * _MINUTE      # 页面缓存新鲜期
_STEP_TIMEOUT = 900           # 单个脚本超时（秒）
_MIN_HTML_SIZE = 50 * 1024    # 有效 HTML 的最小体积（防空文件 / 半截写入）


@dataclass(frozen=True)
class _Step:
    """生成链上的一个环节。"""
    script: str                 # 脚本文件名
    product: str                # 产物文件名（相对 dashboard_gen/）
    deps: tuple = ()            # 依赖的产物文件名
    ttl: float = 0.0            # 产物新鲜期（秒）；0 表示只要进入刷新就重跑


_PIPELINE = (
    # jieba 全量分词最贵（约 20s），而微博语料变化很慢 -> 给最长的新鲜期
    _Step('build_hotword_data.py', 'hotword_preview_data.json', (), 12 * _HOUR),
    _Step('build_sentiment_data.py', 'sentiment_preview_data.json',
          ('hotword_preview_data.json',), 12 * _HOUR),
    # 纯 SQL 统计，秒级完成 -> 新鲜期适中，兼顾实时性
    _Step('build_ip_data.py', 'ip_map_data.json', (), 30 * _MINUTE),
    _Step('build_feature_data.py', 'feature_detail_data.json', ('ip_map_data.json',), 30 * _MINUTE),
    # 汇总层：读上面 4 个 json + 实时查库（约 8s）
    _Step('build_unified_data.py', 'unified_data.json',
          ('hotword_preview_data.json', 'sentiment_preview_data.json',
           'ip_map_data.json', 'feature_detail_data.json'), 10 * _MINUTE),
    # 流域专题（长江 / 黄河）：直查 t_basin_* + jieba 分词 + SnowNLP 判定（约 15s）。
    # 它是 build_unified_page 的硬依赖 —— 少了这一步，流域页会永远停在上次手动
    # 生成的快照上，新采的微博 / 抖音数据进不来。
    _Step('build_basin_data.py', 'basin_data.json', (), 10 * _MINUTE),
    # 视频分析（舆情短视频三层特征）：读 video_features/*.jsonl，独立于微博/流域链路
    # → video_data.json（聚合）+ video_analysis.html（自包含总览页）。
    _Step('build_video_data.py', 'video_data.json', (), 30 * _MINUTE),
    _Step('build_video_page.py', 'video_analysis.html', ('video_data.json',), 0),
    # 短视频智能分析：把模型产出（video_insight.json，由 service/video/insight 预生成、
    # 不在本流水线内，属"预计算产物"）与 L2 原始证据按 cid 合并 → 前端可消费的切片。
    # 纯 Python、秒级、零模型调用。
    _Step('build_video_topic_data.py', 'video_topic_data.json',
          ('video_insight.json',), 30 * _MINUTE),
    # 首页总览 · 济南区位地图数据（纯 SQL 统计：省级 IP 属地 + 地市/区县正文提及，
    # 约 30 次 LIKE 全表扫描，秒级）。供 build_unified_page 的「济南区位」卡片消费。
    _Step('build_jinan_map.py', 'jinan_map_data.json', (), 30 * _MINUTE),
    # 最终组装（约 1s）：只要上游动过就必须跟着重出
    _Step('build_unified_page.py', _HTML_NAME,
          ('unified_data.json', 'basin_data.json', 'video_topic_data.json',
           'jinan_map_data.json'), 0),
)

_refresh_lock = threading.Lock()   # 串行化刷新，兼作「是否正在刷新」的信号
_bg_thread = None


# ---------------------------------------------------------------- 产物校验
def _product_ok(name):
    """产物是否存在且完好（json 需可解析，防止半截写入被当成有效缓存）。"""
    path = os.path.join(_GEN_DIR, name)
    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False
    except OSError:
        return False
    if name.endswith('.json'):
        try:
            with open(path, encoding='utf-8') as f:
                json.load(f)
        except Exception:
            logger.warning('[dashboard] 产物损坏，将重算：%s', name)
            return False
    return True


def _is_fresh(step):
    if step.ttl <= 0:
        return False
    if not _product_ok(step.product):
        return False
    try:
        return (time.time() - os.path.getmtime(os.path.join(_GEN_DIR, step.product))) < step.ttl
    except OSError:
        return False


# ---------------------------------------------------------------- 执行
def _run_step(step):
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'      # Windows 下避免子进程中文输出乱码
    result = subprocess.run(
        [_PYTHON, os.path.join(_GEN_DIR, step.script)],
        cwd=_GEN_DIR,
        capture_output=True, text=True,
        encoding='utf-8', errors='replace',
        timeout=_STEP_TIMEOUT,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            '%s 退出码 %s\n%s\n--- stderr ---\n%s'
            % (step.script, result.returncode, result.stdout[-1200:], result.stderr[-1200:])
        )


def _refresh_unlocked(force=False):
    """执行生成链（调用方必须已持有 _refresh_lock）。

    force=False 时按产物新鲜期跳过不必重算的环节；上游重算过则下游强制跟随。
    返回 (ok, msg)。
    """
    if not os.path.isdir(_GEN_DIR):
        return False, 'dashboard_gen 目录不存在'

    rebuilt = set()
    started = time.time()
    for step in _PIPELINE:
        if not force and _is_fresh(step) and not (rebuilt & set(step.deps)):
            continue
        step_start = time.time()
        try:
            _run_step(step)
        except subprocess.TimeoutExpired:
            return False, '%s 执行超时（>%ds）' % (step.script, _STEP_TIMEOUT)
        except Exception as e:
            return False, str(e)
        rebuilt.add(step.product)
        logger.info('[dashboard] %s -> %s  耗时 %.1fs', step.script, step.product, time.time() - step_start)

    msg = 'OK（重算 %d/%d 步，耗时 %.1fs）' % (len(rebuilt), len(_PIPELINE), time.time() - started)
    logger.info('[dashboard] 刷新完成：%s', msg)
    return True, msg


def refresh(force=False):
    """阻塞式刷新生成链，返回 (ok, msg)。

    force=True 忽略产物新鲜期全量重跑；否则只重算过期环节。
    """
    with _refresh_lock:
        return _refresh_unlocked(force=force)


# ---------------------------------------------------------------- 读取缓存
def _read_html():
    """读取缓存 HTML，返回 (html, fresh)。html 为 None 表示无可用缓存。"""
    try:
        if not os.path.isfile(_HTML_PATH) or os.path.getsize(_HTML_PATH) < _MIN_HTML_SIZE:
            return None, False
        age = time.time() - os.path.getmtime(_HTML_PATH)
        with open(_HTML_PATH, encoding='utf-8') as f:
            html = f.read()
    except OSError as e:
        logger.warning('[dashboard] 读取缓存失败：%s', e)
        return None, False
    if not html or not html.strip():
        return None, False
    return html, age < _HTML_TTL


# ---------------------------------------------------------------- 后台刷新
def _background_refresh():
    if not _refresh_lock.acquire(blocking=False):
        return          # 已有刷新在跑，不重复触发
    try:
        _refresh_unlocked()
    except Exception:
        logger.exception('[dashboard] 后台刷新异常')
    finally:
        _refresh_lock.release()


def _kick_background_refresh():
    """触发一次后台增量刷新；已在刷新中则跳过。"""
    global _bg_thread
    if _bg_thread is not None and _bg_thread.is_alive():
        return
    _bg_thread = threading.Thread(target=_background_refresh, name='dashboard-refresh', daemon=True)
    _bg_thread.start()


def warmup_async():
    """应用启动时后台预热：缓存缺失或陈旧就提前重算，避免首个请求撞上冷启动。

    非阻塞、异常静默（仅写日志），绝不影响应用启动。
    """
    threading.Thread(target=_warmup, name='dashboard-warmup', daemon=True).start()


def _warmup():
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        html, fresh = _read_html()
        if html is not None and fresh:
            return
        logger.info('[dashboard] 启动预热：开始生成/更新缓存')
        ok, msg = _refresh_unlocked()
        logger.info('[dashboard] 启动预热：%s', '完成' if ok else '失败 -> %s' % msg)
    except Exception:
        logger.exception('[dashboard] 预热异常')
    finally:
        _refresh_lock.release()


# ---------------------------------------------------------------- 对外主入口
def get_html(force=False):
    """获取仪表盘 HTML，返回 (html, error)。

    - 缓存新鲜：直接返回（毫秒级）
    - 缓存陈旧：立即返回旧内容（用户零等待）并后台增量重算
    - 无缓存  ：同步生成（仅冷启动；启动时预热已尽量消除该场景）
    """
    html, fresh = _read_html()

    if force:
        ok, msg = refresh(force=True)
        if not ok:
            # 刷新失败但有旧内容时，宁可返回旧内容也不要开天窗
            return (html, msg) if html is not None else (None, msg)
        html, _ = _read_html()
        return (html, None) if html is not None else (None, '生成完成后未找到有效 HTML 产物')

    if html is not None and fresh:
        return html, None

    if html is not None:
        # stale-while-revalidate：先把旧内容给用户，后台悄悄更新
        _kick_background_refresh()
        return html, None

    ok, msg = refresh()
    if not ok:
        return None, msg
    html, _ = _read_html()
    return (html, None) if html is not None else (None, '生成完成后未找到有效 HTML 产物')

