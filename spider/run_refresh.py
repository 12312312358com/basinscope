# -*- coding: utf-8 -*-
"""动态采集编排入口（数据动态化 · 含义 B）。
=============================================================================
把「手动跑爬虫 → 手动跑构建链」两步合成一条命令，爬虫与构建链代码零改动：

    采集（现有爬虫，增量 upsert 进库）
      → 库内条数对比（新增 = 0 则跳过重建，防登录态过期空跑）
      → 失效 dashboard_gen 产物（mtime 置 0，让 SWR 判定为过期）
      → 重算生成链（复用 service/dashboard.py 的增量流水线，只重算过期环节）
      → 状态落盘 spider/_state/refresh_state.json

为什么爬虫不进 service/dashboard.py 的 _PIPELINE：
    那条流水线的每一步都是"纯计算"（秒~分钟级、失败可重试、绝无账号风险）；
    爬虫是"联网 + 慢 + 可能失败 + 有账号风险"，混进去会让页面刷新卡在爬虫上。
    所以这里做成**独立编排层**：采集成功才允许它踢生成链。

用法：
    python run_refresh.py --dry-run      # 只打印将执行的计划，不联网不写库
    python run_refresh.py --self-test    # 离线自检（配置/计划/锁/状态/爬虫词表矩阵）
    python run_refresh.py                # 按 crawl_config.json 采集 → 重建（默认 quick 档）
    python run_refresh.py --profile full # 全量档（小时级，慎用）
    python run_refresh.py --pages 1 --no-chain
    python run_refresh.py --platform weibo     # 只跑微博（覆盖配置里的 enabled）

⚠️ 依赖登录态的平台（xhs_zhihu）无人值守会静默采 0 条 —— 状态文件里
   『新增 = 0』就是报警信号，先手动开 Edge 登录再跑。
=============================================================================
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))          # spider/
PRJ = os.path.dirname(BASE)                                # 项目根
GEN = os.path.join(PRJ, 'dashboard_gen')
STATE_DIR = os.path.join(BASE, '_state')
LOCK_PATH = os.path.join(STATE_DIR, 'crawl.lock')
STATE_PATH = os.path.join(STATE_DIR, 'refresh_state.json')
CONFIG_PATH = os.path.join(BASE, 'crawl_config.json')

# 让 run_refresh.py 能 import 项目根的 service/dashboard.py（生成链编排）
sys.path.insert(0, PRJ)


# ================================================================ 配置
def load_config():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        cfg = json.load(f)
    for key in ('platforms', 'chain_refresh', 'timeout_minutes', 'lock_stale_minutes'):
        if key not in cfg:
            raise SystemExit('[配置缺失] crawl_config.json 缺少字段：%s' % key)
    return cfg


def compose_args(arg_map):
    """{"--pages":1, "--no-comments":true, "--basin":["黄河","长江"]}
       -> ["--pages","1","--no-comments","--basin","黄河","--basin","长江"]"""
    out = []
    for k, v in (arg_map or {}).items():
        if v is True:
            out.append(k)
        elif v is False or v is None:
            continue
        elif isinstance(v, list):
            for item in v:
                out += [k, str(item)]
        else:
            out += [k, str(v)]
    return out


def filter_by_schedule(plan, cfg, prev_state, only_platforms=None):
    """按 schedule 频率过滤：某平台距上次成功采集不足其间隔就跳过。

    ## 为什么需要
    两个平台的代价差一个数量级 —— 微博 quick 档实测 353s 且无登录态依赖，
    小红书+知乎 ~60 分钟且依赖 cookie。共用一个频率只有两种结果：要么按微博的
    节奏把小红书按在地上（一天 16 次 Edge 被强杀，绝大多数轮次新增 0 条），
    要么按小红书的节奏让微博数据老到失去意义。

    ## 判据用「上一轮 started_at」而不是 mtime
    产物 mtime 会被 refresh_chain() 改写，不能当采集时间；锁文件时间戳会在
    进程退出后消失。refresh_state.json 的 started_at 是唯一可靠来源。

    ## 安全兜底
    prev_state 为空（首跑/状态丢失）或该平台没有记录 → **不跳过**。宁可多跑
    一轮，也不能因为状态文件损坏就永远不采 —— 那正是本项目最典型的静默失效。
    """
    sched = cfg.get('schedule') or {}
    if not sched:
        return plan, {}
    prev_plats = ((prev_state or {}).get('platforms') or {})
    kept, skipped = [], {}
    now = time.time()
    for job in plan:
        key = job['key']
        interval = sched.get(key)
        if not interval:
            kept.append(job)                    # 没配频率 = 每轮都跑
            continue
        rec = prev_plats.get(key)
        if not rec or not rec.get('at'):
            kept.append(job)                    # 无历史 → 照跑（安全兜底）
            continue
        try:
            last = datetime.fromisoformat(rec['at']).timestamp()
        except Exception:
            kept.append(job)
            continue
        age_min = (now - last) / 60.0
        if age_min < interval:
            skipped[key] = {'age_min': round(age_min), 'interval': interval}
        else:
            kept.append(job)
    return kept, skipped


# 认识 `--spider-arg` 透传参数的爬虫（目前只有小红书/知乎那个）。
# river_basin_spider.py 的参数表里没有 --platform，传给它会直接报错退出，
# 所以按白名单放行，不做就等着炸。
SPIDER_ARG_AWARE = {'xhs_zhihu_spider.py'}


def resolve_plan(cfg, only_platforms=None, cli_pages=None, cli_no_comments=None,
                 profile='quick', spider_args=None):
    """把配置解析成可执行的作业列表。不做任何 IO，--dry-run 与正式跑共用。"""
    jobs = []
    for key, p in cfg['platforms'].items():
        if only_platforms and key not in only_platforms:
            continue
        if not p.get('enabled'):
            continue
        prof = p.get('profiles', {}).get(profile, {}).get('args', {})
        args = compose_args(prof)
        if cli_pages is not None:                       # 命令行覆盖，去掉配置里已有的 --pages
            if '--pages' in args:
                i = args.index('--pages')
                del args[i:i + 2]
            args += ['--pages', str(cli_pages)]
        if cli_no_comments and '--no-comments' not in args:
            args.append('--no-comments')
        # 透传参数。只给「确实认识它的那个爬虫」，否则 river_basin_spider.py
        # 会因不认识的 --platform 直接报错（它的参数表没有这一项）。
        if spider_args:
            if os.path.basename(p['spider']) in SPIDER_ARG_AWARE:
                args += list(spider_args)
            else:
                print('   [透传] %s 不支持附加参数，已忽略：%s'
                      % (p['spider'], ' '.join(spider_args)))
        jobs.append({'key': key, 'spider': p['spider'], 'tables': p.get('tables', []),
                     'args': args, 'note': p.get('note', '')})
    return jobs


# ================================================================ 库内计数
def count_rows(tables):
    """采集前后各数一次，差值 = 本次新增。upsert 同时会更新老行的互动量，
    但那不体现为行数变化 —— 所以状态文件里叫『新增条数』而非『变更条数』。"""
    import pymysql
    conn = pymysql.connect(host=os.getenv('DB_HOST', 'localhost'), user=os.getenv('DB_USER', 'root'), password=os.getenv('DB_PASSWORD', ''),
                           database=os.getenv('DB_NAME', 'db_weibo_basin'), charset='utf8mb4')
    try:
        with conn.cursor() as cur:
            out = {}
            for t in tables:
                cur.execute("SELECT COUNT(*) FROM `%s`" % t)
                out[t] = int(cur.fetchone()[0])
            return out
    finally:
        conn.close()


# ================================================================ 文件锁
def acquire_lock(stale_minutes):
    """O_EXCL 抢锁；残留锁（进程被强杀）超过 stale_minutes 自动清除。
    只互斥本编排层 —— 与 Flask 进程内 service.dashboard 的线程锁是两套，
    两边同时重建的概率低、后果轻（同名产物后写者胜），此处不做跨进程共享锁。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(LOCK_PATH):
        age_min = (time.time() - os.path.getmtime(LOCK_PATH)) / 60.0
        if age_min > stale_minutes:
            print('[WARN] 发现残留锁（%.0f 分钟前），视为上次进程异常退出，清除' % age_min)
            os.remove(LOCK_PATH)
        else:
            raise SystemExit('已有采集在跑（%s，%.0f 分钟前启动）。'
                             '确认没有其它终端在跑就删掉 %s' % (LOCK_PATH, age_min, LOCK_PATH))
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'pid': os.getpid(), 'started': datetime.now().isoformat(timespec='seconds')},
                           ensure_ascii=False))


def release_lock():
    if os.path.exists(LOCK_PATH):
        os.remove(LOCK_PATH)


# ================================================================ 产物失效
def invalidate_products():
    """把生成链的全部 JSON 产物 mtime 置 0。
    service/dashboard 的 _is_fresh 只看产物 mtime 与 TTL，感知不到『库里多了几行』——
    不失效的话，新数据要等 TTL（最长 12 小时）自然过期才会被算进来。"""
    try:
        from service.dashboard import _PIPELINE
        products = [s.product for s in _PIPELINE if s.product.endswith('.json')]
    except Exception as e:
        print('[WARN] 读不到生成链定义（%s），退回静态清单' % e)
        products = ['hotword_preview_data.json', 'sentiment_preview_data.json',
                    'ip_map_data.json', 'feature_detail_data.json', 'unified_data.json',
                    'basin_data.json', 'video_data.json', 'video_topic_data.json',
                    'jinan_map_data.json']
    done = []
    for name in products:
        path = os.path.join(GEN, name)
        if os.path.exists(path):
            os.utime(path, (0, 0))
            done.append(name)
    return done


def refresh_chain():
    """重算生成链（增量：只重算被失效的环节 + 其下游）。"""
    from service.dashboard import refresh
    return refresh(force=False)


# ================================================================ 心跳哨兵
# 依赖登录态的平台（xhs_zhihu）无人值守会**静默采0 条**：爬虫rc=0、不报错，
# 但库里没新东西。于是 `skip_chain_if_no_new` 会「跳过重建」，页面看起来一切
# 正常 —— 数据却已经停更。这是本项目反复出现的静默失效模式。
#
# 心跳要做的事：**把「停更」和「正常无新内容」区分开**。
# 判据不是单轮的新增数（单轮 0 条很正常，词表可能有近几天的都没命中），
# 而是**连续 N 轮同一个 enabled 平台都是 0** —— 那就不是「没新内容」，
# 是「采不动了」，最常见原因是 cookie 过期。
#
# 纯函数 + 只读历史状态，便于离线自测（见 self_test 的心跳项）。
HEARTBEAT_HISTORY = 5      # 最多回看最近几轮
HEARTBEAT_STREAK = 3       # 连续几轮 0 条就告警


def load_state():
    """读上次的状态；不存在/损坏返回 None。"""
    try:
        with open(STATE_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def heartbeat(prev_states, state, cfg, platforms_ran):
    """算心跳，返回 {平台: {streak, suspect, reason}}。

    prev_states : 由新到旧的历史状态列表（本轮 state 不含在内）
    state       : 本轮 state
    platforms_ran: 本轮真正跑过的平台 key 集合
    """
    n = max(1, int(cfg.get('heartbeat_streak', HEARTBEAT_STREAK)))
    hist = [state] + list(prev_states)          # 本轮在最前
    result = {}

    for key in platforms_ran:
        v = (state.get('platforms') or {}).get(key)
        if not v:
            continue
        added = v.get('added') or {}
        total = sum(x for x in added.values() if isinstance(x, int))
        streak = 0
        if total == 0:
            streak = 1
            for st in hist[1:]:# 回看历史，连续就累加，遇到有新增就停
                hv = (st.get('platforms') or {}).get(key)
                if hv is None:
                    break                        # 该轮没跑这个平台，连续性无法判断
                had = hv.get('added') or {}
                htotal = sum(x for x in had.values() if isinstance(x, int))
                if htotal > 0:
                    break
                streak += 1
                if streak >= HEARTBEAT_STREAK + 1:
                    break
        result[key] = {
            'streak': streak,
            'added_total': total,
            'suspect': streak >= n,
            'reason': ('连续 %d 轮新增 0 条 —— 多半是登录态过期，请手动打开 Edge '
                       '重新登录后重跑' % streak) if streak >= n else '',
        }
    return result


# ================================================================ 状态落盘
def write_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    state['written_at'] = datetime.now().isoformat(timespec='seconds')
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    return STATE_PATH


# ================================================================ 主流程
def run(args):
    cfg = load_config()
    plan = resolve_plan(cfg, only_platforms=args.platform, cli_pages=args.pages,
                        cli_no_comments=args.no_comments if args.no_comments else None,
                        profile=args.profile, spider_args=args.spider_arg)
    if not plan:
        raise SystemExit('没有启用的平台。检查 crawl_config.json 的 enabled，'
                         '或用 --platform 指定（可选：%s）' % '、'.join(cfg['platforms']))

    # ---- 分频：距上次采集不足该平台间隔的，本轮跳过 ----
    prev_for_sched = load_state()
    if args.platform or args.force:
        plan, sched_skipped = plan, {}          # 显式指定平台 = 用户明确要跑，跳过频率限制
    else:
        plan, sched_skipped = filter_by_schedule(plan, cfg, prev_for_sched)
    if sched_skipped:
        for k, v in sched_skipped.items():
            print('== [分频] %s 距上次采集 %d 分钟 < 间隔 %d 分钟，本轮跳过'
                  % (k, v['age_min'], v['interval']))
    if not plan:
        print('== 本轮所有平台都未到采集间隔，无需动作 ==')
        return None

    if args.dry_run:
        print('== 计划（dry-run，未联网未写库）==')
        for j in plan:
            print('  [%s] %s %s' % (j['key'], j['spider'], ' '.join(j['args'])))
            print('         计数表：%s' % ('、'.join(j['tables']) or '无'))
        for k, v in (sched_skipped or {}).items():
            print('  [%s] —— 分频跳过（距上次 %d 分钟 < 间隔 %d 分钟）'
                  % (k, v['age_min'], v['interval']))
        print('  采集完成后：%s' % (
            '失效产物 → 重算生成链' if cfg.get('chain_refresh', True) and not args.no_chain
            else '不重算生成链（--no-chain / 配置关闭）'))
        print('  超时：%d 分钟 / 锁残留判定：%d 分钟 / 状态文件：%s'
              % (cfg['timeout_minutes'], cfg['lock_stale_minutes'], STATE_PATH))
        sched = cfg.get('schedule') or {}
        if sched:
            print('  分频配置：%s'
                  % '  '.join('%s=%d分钟' % (k, v) for k, v in sched.items()))
        return

    acquire_lock(cfg['lock_stale_minutes'])
    started = time.time()
    state = {'started_at': datetime.now().isoformat(timespec='seconds'),
             'profile': args.profile, 'platforms': {}, 'added_total': 0}
    try:
        for j in plan:
            print('\n== [%s] %s %s' % (j['key'], j['spider'], ' '.join(j['args'])))
            before = count_rows(j['tables']) if j['tables'] else {}
            t0 = time.time()
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            try:
                r = subprocess.run(
                    [sys.executable, os.path.join(BASE, j['spider'])] + j['args'],
                    cwd=BASE, capture_output=True, text=True, encoding='utf-8',
                    errors='replace', timeout=cfg['timeout_minutes'] * 60, env=env)
                rc, tail = r.returncode, (r.stdout or '')[-600:]
            except subprocess.TimeoutExpired:
                rc, tail = -9, '超时（>%d 分钟），已抓到的部分此前已 upsert 进库' % cfg['timeout_minutes']
            dur = time.time() - t0
            after = count_rows(j['tables']) if j['tables'] else {}
            added = {t: after.get(t, 0) - before.get(t, 0) for t in j['tables']}
            state['platforms'][j['key']] = {
                'rc': rc, 'duration_s': round(dur, 1), 'added': added,
                # at：本平台「跑过」的时刻，分频下一轮靠它算「距上次多久」。
                # 注意是本轮开始时间而非结束时间 —— 采集耗时可达 60 分钟，用结束时
                # 间会让间隔凭空多出 1 小时。
                'at': state['started_at'],
                'rows_after': after, 'stdout_tail': tail.strip()[-300:]}
            state['added_total'] += sum(added.values())
            print('   退出码 %d · 耗时 %.0fs · 新增 %s' % (
                rc, dur, json.dumps(added, ensure_ascii=False)))

        # ---- 闭环：有新增才重建（防止登录态过期空跑后白重建 60 秒）----
        all_ok = all(v['rc'] == 0 for v in state['platforms'].values())
        if args.no_chain or not cfg.get('chain_refresh', True):
            state['chain'] = {'skipped': True, 'reason': '命令行/配置关闭'}
        elif state['added_total'] == 0 and cfg.get('skip_chain_if_no_new', True):
            state['chain'] = {'skipped': True,
                              'reason': '新增 0 条（若用了需要登录态的平台，先检查 cookie）'}
            print('\n== 新增 0 条，跳过生成链重建（登录态过期？）==')
        elif not all_ok:
            state['chain'] = {'skipped': True, 'reason': '有爬虫非零退出，不重建（保旧页面）'}
            print('\n== 有爬虫异常退出，跳过生成链重建 ==')
        else:
            print('\n== 失效产物 → 重算生成链 ==')
            touched = invalidate_products()
            print('   已失效 %d 个产物：%s' % (len(touched), '、'.join(touched)))
            ok, msg = refresh_chain()
            state['chain'] = {'ok': ok, 'msg': msg}
            print('   生成链：%s' % msg)

        # ---- 心跳：区分「停更」与「正常无新内容」 ----
        # 必须**在 write_state 之前**算，且要读上一轮的状态。当前状态文件只存
        # 一轮，覆盖掉就没法数连续几轮了 —— 所以先备份上一轮，再算，最后写。
        prev = load_state()
        prev_hist = []
        if prev:
            backup = os.path.join(STATE_DIR, 'refresh_state.prev.json')
            try:
                with open(backup, 'w', encoding='utf-8') as f:
                    json.dump(prev, f, ensure_ascii=False, indent=1)
            except Exception:
                pass
            prev_hist.append(prev)
        ran = {j['key'] for j in plan}
        hb = heartbeat(prev_hist, state, cfg, ran)
        state['heartbeat'] = hb
        for key, v in hb.items():
            mark = '[心跳] %s' % key
            if v['suspect']:
                print('\n%s  %s  ⚠ 疑似停更 —— %s' % (mark, '新增 0 条 ×%d 轮' % v['streak'], v['reason']))
            elif v['streak']:
                print('\n%s  新增 0 条（连续 %d 轮，未达告警阈值 %d）'
                      % (mark, v['streak'], cfg.get('heartbeat_streak', HEARTBEAT_STREAK)))

        state['duration_s'] = round(time.time() - started, 1)
        write_state(state)
        print('\n== 完成（%.0fs），状态：%s' % (state['duration_s'], STATE_PATH))
        return state
    finally:
        release_lock()


# ================================================================ 离线自检
def self_test():
    """不联网不写库：配置 → 计划 → 锁 → 状态 → 生成链定义 → 爬虫词表矩阵。"""
    ok = []

    cfg = load_config()
    ok.append(('配置解析', '%d 个平台定义' % len(cfg['platforms'])))

    plan = resolve_plan(cfg)
    enabled = [j['key'] for j in plan]
    # 2026-10-08 启用 xhs_zhihu（原断言 == ['weibo'] 被打破）。
    # 这里不再钉死具体平台 —— 平台集合是配置驱动的，硬编码会让「开一个平台就
    # 自检红」这种无关变更冒充真 bug。改为断言**结构**：都在配置里、都 enabled、
    # 参数已展开。
    assert enabled, '没有任何平台被启用'
    for k in enabled:
        assert k in cfg['platforms'], k
        assert cfg['platforms'][k].get('enabled'), '%s 未 enabled 却进了计划' % k
    if 'douyin' in cfg['platforms']:
        assert not cfg['platforms']['douyin'].get('enabled'), '抖音应保持关闭（库内 0 条、风控最严）'
    assert '--pages' in plan[0]['args'] and '--no-comments' in plan[0]['args']
    ok.append(('计划解析', '启用 %s，quick 档参数已展开' % '、'.join(enabled)))

    full = resolve_plan(cfg, cli_pages=2, cli_no_comments=True)
    i = full[0]['args'].index('--pages')
    assert full[0]['args'][i + 1] == '2' and full[0]['args'].count('--pages') == 1
    ok.append(('CLI 覆盖', '--pages 命令行覆盖生效且不重复'))

    prof_full = resolve_plan(cfg, profile='full')
    assert '--pages' not in prof_full[0]['args'] and '--no-comments' not in prof_full[0]['args']
    ok.append(('档位切换', 'full 档不带 --pages / --no-comments（用爬虫内置默认）'))

    acquire_lock(cfg['lock_stale_minutes'])
    assert os.path.exists(LOCK_PATH)
    try:
        acquire_lock(cfg['lock_stale_minutes'])     # 应立刻失败
        raise AssertionError('锁未生效')
    except SystemExit:
        ok.append(('文件锁', '互斥生效（第二次获取被拒）'))
    release_lock()
    assert not os.path.exists(LOCK_PATH)
    ok.append(('文件锁', '释放干净'))

    # 状态读写 —— 必须用**独立临时文件**。
    # 2026-10-08 修：原写法调 write_state() 再 os.remove()，而 write_state 写的
    # 就是真实的 STATE_PATH（refresh_state.json）—— 于是自检把**生产状态文件**
    # 当临时文件删掉了，连带丢掉「上一轮新增数」，而心跳正是靠它数连续几轮。
    # 自检绝不能碰生产数据，这是本项目的硬规矩（同 _verify_order_ratchet）。
    p = os.path.join(STATE_DIR, '_selftest_state.json')
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'_selftest': True}, f, ensure_ascii=False)
    with open(p, encoding='utf-8') as f:
        assert json.load(f)['_selftest'] is True
    os.remove(p)
    assert not os.path.exists(p)
    # 反向断言：真实状态文件若存在，自检后必须仍可解析（没被自检动过）
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            json.load(f)
    ok.append(('状态读写', 'roundtrip 通过（用独立临时文件，未触碰真实状态）'))

    # ---- 心跳：把「停更」与「正常无新内容」分开 ----
    def st_with(total, key='xhs_zhihu'):
        return {'platforms': {key: {'rc': 0, 'added': {'t': total}}}}

    n0 = cfg.get('heartbeat_streak', HEARTBEAT_STREAK)
    # 1) 本轮 0 条 + 历史 0 条 ×(n0-1) → 连续 n0 轮 → 必须告警
    h = heartbeat([st_with(0)] * (n0 - 1), st_with(0), cfg, {'xhs_zhihu'})
    assert h['xhs_zhihu']['suspect'], h
    assert h['xhs_zhihu']['streak'] == n0, h
    ok.append(('心跳·停更告警', '连续 %d 轮 0 条 → suspect' % n0))

    # 2) 本轮 0 条但历史里有新增 → 连续性被打断，不得告警
    h = heartbeat([st_with(5)], st_with(0), cfg, {'xhs_zhihu'})
    assert not h['xhs_zhihu']['suspect'], h
    ok.append(('心跳·不误报', '历史有新增时连续计数中断，不告警'))

    # 3) 本轮有新增 → 永远不告警
    h = heartbeat([st_with(0)] * (n0 + 2), st_with(7), cfg, {'xhs_zhihu'})
    assert not h['xhs_zhihu']['suspect'] and h['xhs_zhihu']['streak'] == 0, h
    ok.append(('心跳·有新增', 'streak=0，不告警'))

    # 4) 只统计本轮真跑过的平台：单跑微博不该让小红书被判定停更
    h = heartbeat([{'platforms': {'xhs_zhihu': {'rc': 0, 'added': {'t': 0}}}}],
                  {'platforms': {'weibo': {'rc': 0, 'added': {'t': 9}}}},
                  cfg, {'weibo'})
    assert 'xhs_zhihu' not in h, h
    ok.append(('心跳·只算跑过的平台', '--platform 覆盖时不误伤其它平台'))

    # ---- 分频：按平台实测代价差一个数量级，不能共用一个频率 ----
    from datetime import timedelta
    now = datetime.now()
    plan2 = resolve_plan(cfg)
    sched_cfg = dict(cfg, schedule={'weibo': 360, 'xhs_zhihu': 720})

    def state_at(minutes_ago, keys):
        at = (now - timedelta(minutes=minutes_ago)).isoformat(timespec='seconds')
        return {'platforms': {k: {'rc': 0, 'at': at, 'added': {'t': 1}} for k in keys}}

    # 1) 刚跑过 → 两个平台都该跳过
    kept, skip = filter_by_schedule(plan2, sched_cfg, state_at(10, ['weibo', 'xhs_zhihu']))
    assert not kept and set(skip) == {'weibo', 'xhs_zhihu'}, (kept, skip)
    ok.append(('分频·未到间隔跳过', '10 分钟前刚跑过 → 两平台均跳过'))

    # 2) 微博到期、小红书未到 → 只跑微博（这是分频的核心用例）
    kept, skip = filter_by_schedule(plan2, sched_cfg, state_at(400, ['weibo', 'xhs_zhihu']))
    assert [j['key'] for j in kept] == ['weibo'], (kept, skip)
    assert 'xhs_zhihu' in skip
    ok.append(('分频·按平台分别放行', '400 分钟后只放行 weibo(360min)，xhs_zhihu(720min) 继续等待'))

    # 3) 都到期 → 都跑
    kept, skip = filter_by_schedule(plan2, sched_cfg, state_at(800, ['weibo', 'xhs_zhihu']))
    assert len(kept) == len(plan2) and not skip, (kept, skip)
    ok.append(('分频·都到期放行', '800 分钟后两平台均放行'))

    # 4) **安全兜底**：状态文件不存在时必须照跑，不能因为状态丢失就永不采集
    kept, skip = filter_by_schedule(plan2, sched_cfg, None)
    assert len(kept) == len(plan2), (kept, skip)
    ok.append(('分频·状态丢失兜底', '无状态文件时不跳过（防静默失效）'))

    # 5) 某平台缺at 字段（旧状态文件兼容）→ 照跑
    kept, skip = filter_by_schedule(plan2, sched_cfg,
                                    {'platforms': {'weibo': {'rc': 0, 'added': {'t': 3}}}})
    assert len(kept) == len(plan2), (kept, skip)
    ok.append(('分频·旧状态兼容', '缺 at 字段的老状态不导致跳过'))

    # 6) 配置约束：lock_stale 必须 > timeout，否则下一轮会误清仍在跑的锁
    assert cfg['lock_stale_minutes'] > cfg['timeout_minutes'], \
        'lock_stale(%d) 必须 > timeout(%d)，否则下一轮误清活锁' % (
            cfg['lock_stale_minutes'], cfg['timeout_minutes'])
    ok.append(('配置·锁超时自洽', 'lock_stale %d > timeout %d'
               % (cfg['lock_stale_minutes'], cfg['timeout_minutes'])))

    # 7) 无 schedule 配置时不做任何过滤（向后兼容）
    kept, skip = filter_by_schedule(plan2, dict(cfg, schedule={}), state_at(1, ['weibo']))
    assert len(kept) == len(plan2)
    ok.append(('分频·无配置则不过滤', 'schedule 缺失时行为不变'))

    from service.dashboard import _PIPELINE
    prods = [s.product for s in _PIPELINE if s.product.endswith('.json')]
    assert len(prods) >= 8, prods
    missing = [n for n in prods if not os.path.exists(os.path.join(GEN, n))]
    ok.append(('生成链定义', '%d 个 JSON 产物%s'
               % (len(prods), '' if not missing else '（缺失：%s）' % missing)))

    r = subprocess.run([sys.executable, os.path.join(BASE, 'river_basin_spider.py'), '--dry-run'],
                       cwd=BASE, capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert r.returncode == 0, (r.stdout or '')[-400:]
    matrix = [l for l in (r.stdout or '').splitlines() if '词' in l or '矩阵' in l]
    ok.append(('爬虫词表矩阵（--dry-run）', '退出码 0%s' % ('：' + matrix[0].strip()[:60] if matrix else '')))

    print('== 自检 ==')
    for name, msg in ok:
        print('  [OK] %-22s %s' % (name, msg))
    print('全部通过（未联网、未写库、未动任何产物）')


def main():
    ap = argparse.ArgumentParser(
        prog='run_refresh.py',
        description='动态采集编排：按 crawl_config.json 调用现有爬虫（增量 upsert），'
                    '有新增才重算生成链。爬虫与构建链代码零改动。')
    ap.add_argument('--profile', choices=['quick', 'full'], default='quick',
                    help='采集档位：quick=每流域 1 省 1 页不抓评论（分钟级）；full=爬虫内置默认（小时级）')
    ap.add_argument('--platform', action='append',
                    help='只跑指定平台（weibo / xhs_zhihu / douyin），可重复；覆盖配置里的 enabled')
    ap.add_argument('--pages', type=int, help='覆盖每个关键词抓几页')
    ap.add_argument('--no-comments', action='store_true', help='强制跳过评论抓取')
    ap.add_argument('--no-chain', action='store_true', help='只采集，不失效产物、不重算生成链')
    ap.add_argument('--dry-run', action='store_true', help='只打印计划，不联网不写库')
    ap.add_argument('--force', action='store_true',
                    help='忽略 schedule 分频，本轮强制采集所有 enabled 平台')
    # 透传给底层爬虫的附加参数。用于「调度层粒度比爬虫层粗」的情况：
    # 小红书/知乎在配置里同属 xhs_zhihu 一个键（调度层无法再拆），要只跑其中
    # 一个必须给xhs_zhihu_spider.py 自己的 --platform（中文键名）。
    # 不加这个口子的话，crawl_xhs.py / crawl_zhihu.py 传进来的 --platform
    # 会被下面的 parse_args 当成未知参数直接报错退出。
    ap.add_argument('--spider-arg', action='append', default=[],
                    help='透传给底层爬虫的参数，可重复。例：--spider-arg --platform --spider-arg 知乎')
    ap.add_argument('--self-test', action='store_true', help='离线自检，不联网不写库')
    a = ap.parse_args()

    if a.self_test:
        self_test()
    else:
        run(a)


if __name__ == '__main__':
    main()

