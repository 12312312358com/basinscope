# -*- coding: utf-8 -*-
"""短视频分析长跑看门狗：持续监督，发现停滞/异常立即记录并给出恢复建议。

判据（实测单条 ≈27 秒）：
  - 心跳 = dashboard_gen/video_insight.json 的 mtime + meta.n
  - 停滞：连续 STALL_SEC（默认 240 秒）内 n 与 mtime 均无变化
  - 异常中断：进程消失但 n < 总数

用法：
    python service/video/insight/watch_insight.py                # 默认每 30s 采样
    python service/video/insight/watch_insight.py --total 110
输出同时写 stdout 与 video_features/_insight_watch.log（便于事后追溯）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_PRJ = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
TARGET = os.path.join(_PRJ, 'dashboard_gen', 'video_insight.json')
LOG = os.path.join(_PRJ, 'video_features', '_insight_watch.log')


def _state(target, kind='json'):
    """返回 (n, mtime, ok)。json 读 meta.n；jsonl 数非空行。"""
    try:
        mt = os.path.getmtime(target)
        if kind == 'jsonl':
            with io.open(target, encoding='utf-8') as f:
                return sum(1 for l in f if l.strip()), mt, True
        with io.open(target, encoding='utf-8') as f:
            d = json.load(f)
        return d.get('meta', {}).get('n', 0), mt, True
    except Exception:
        try:
            return -1, os.path.getmtime(target), False
        except OSError:
            return -1, 0.0, False


def _alive(marker='build_insight'):
    """目标进程是否还在（wmic 查命令行里含 marker 的 python）。查不到返回 None。"""
    try:
        out = subprocess.run(['wmic', 'process', 'where', "name='python.exe'",
                              'get', 'CommandLine', '/format:list'],
                             capture_output=True, text=True, timeout=20).stdout
        return marker in out
    except Exception:
        return None          # 查不到就不作为判据


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--total', type=int, default=110, help='预期总条数')
    ap.add_argument('--target', default=TARGET, help='要监督的产物文件')
    ap.add_argument('--kind', default='json', choices=['json', 'jsonl'], help='产物类型')
    ap.add_argument('--marker', default='build_insight', help='进程命令行特征串')
    ap.add_argument('--interval', type=int, default=30, help='采样间隔（秒）')
    ap.add_argument('--stall', type=int, default=240, help='停滞判定阈值（秒）')
    ap.add_argument('--max-minutes', type=int, default=240, help='最长监督时长（分钟）')
    ap.add_argument('--grace', type=int, default=120,
                    help='启动后宽限秒数：这段时间内不判定"全部完成"'
                         '（防重跑时采样到上一次的旧产物而误判完成）')
    a = ap.parse_args()

    t_start = time.time()
    last_n, last_mt = -2, 0.0
    last_change = time.time()
    stall_reported = False
    base_n, base_t = None, None      # 速率基线：取"首个有效采样点"，避免首采样算出荒谬速率
    log = io.open(LOG, 'a', encoding='utf-8')

    def say(msg):
        line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
        print(line, flush=True)
        log.write(line + '\n')
        log.flush()

    say('看门狗启动：目标 %d 条，每 %ds 采样，停滞阈值 %ds' % (a.total, a.interval, a.stall))
    while True:
        n, mt, ok = _state(a.target, a.kind)
        now = time.time()
        el = now - t_start
        moved = (n != last_n) or (mt != last_mt)
        if moved:
            last_change = now
            stall_reported = False
            if base_n is None and n >= 0:
                base_n, base_t = n, now
            dt = (now - base_t) if base_t else 0
            rate = ((n - (base_n or 0)) / dt * 60) if dt >= 5 else 0
            eta = ((a.total - n) / rate) if rate > 0 and n < a.total else None
            say('进度 %d/%d%s%s'
                % (n, a.total,
                   ('（%.1f 条/分）' % rate) if rate > 0 else '',
                   ('，剩约 %.0f 分钟' % eta) if eta else ''))
        else:
            idle = now - last_change
            if idle > a.stall and not stall_reported:
                stall_reported = True
                alive = _alive(a.marker)
                say('⚠️ 疑似停滞：已 %.0f 秒无进展（当前 %d/%d）。进程存活=%s'
                    % (idle, n, a.total, alive))
                if alive is False:
                    say('   → 判定为异常中断（进程已不在）。恢复建议：'
                        '直接重跑 build_insight.py --limit 0（断点续跑会跳过已完成的 %d 条）' % max(n, 0))
                else:
                    say('   → 进程仍在：可能正卡在单条长视频/网络重试。建议再等 3 分钟；'
                        '仍不动则停掉后重跑 build_insight.py --limit 0（自动续跑）')
        if n >= a.total:
            if el < a.grace:
                # 宽限期内命中上限：极可能是上一次的旧产物（重跑场景）→ 不判定完成
                if moved:
                    say('宽限期内读到 %d/%d（多半是上一次的旧产物，继续观察）' % (n, a.total))
            else:
                say('✅ 全部完成：%d/%d，总耗时 %.0f 分钟' % (n, a.total, el / 60))
                break
        alive = _alive(a.marker)
        if alive is False and n < a.total:
            say('❌ 异常中断：进程已退出但仅完成 %d/%d。恢复建议：'
                '重跑 build_insight.py --limit 0（跳过已完成，继续补齐）' % (max(n, 0), a.total))
            break
        if el > a.max_minutes * 60:
            say('⏹ 达到最长监督时长（%d 分钟），退出监督。当前 %d/%d'
                % (a.max_minutes, n, a.total))
            break
        last_n, last_mt = n, mt
        time.sleep(a.interval)
    log.close()


if __name__ == '__main__':
    main()
