# -*- coding: utf-8 -*-
"""舆眼 · 分平台采集入口（薄封装，每个平台一个）

## 为什么要这一层
`run_refresh.py` 的 `--platform` 只在**调度层**筛选（决定跑哪几个配置项），
**不会**透传给底层爬虫。而小红书/知乎共用一个爬虫 `xhs_zhihu_spider.py`
（键 `xhs_zhihu`），要只跑其中一个，必须给它自己的 `--platform 小红书`
（中文键名，见 xhs_zhihu_spider.PLATFORM_ADAPTERS）。这个「两层 platform
键名不同」的坑不值得让每次手工敲命令的人去记，所以各包一层。

    python crawl_weibo.py          # 只爬微博
    python crawl_xhs.py            # 只爬小红书
    python crawl_zhihu.py          # 只爬知乎
    python crawl_all.py            # 三个都爬（= 总入口）

## 每个脚本都做同一件事
    调 run_refresh.py，透传 --profile / --pages / --no-chain 等，
    并保证 --platform 一定带上（避免误跑成全量）。

⚠️ 采集会 `taskkill` 所有 Edge 窗口（take_over_real_edge 的既定行为），
   跑之前先存好手头的页面。
"""
import argparse
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(BASE)
RUNNER = os.path.join(BASE, 'run_refresh.py')
PYTHON = sys.executable          # 用当前解释器，别硬编码 .venv 路径


def crawl(platform_key, extra_spider_arg=None, argv=None):
    """platform_key是 run_refresh.py 的配置键；extra_spider_arg 是给底层爬虫的附加参数。"""
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description='舆眼 %s 采集 + 同步' % (platform_key or '全部平台'))
    ap.add_argument('--profile', choices=['quick', 'full'], default='quick',
                    help='quick=小规模增量(默认)；full=全量，小时级')
    ap.add_argument('--pages', type=int, help='覆盖每关键词抓几页')
    ap.add_argument('--no-chain', action='store_true',
                    help='只采集入库，不失效产物/不重算作品页')
    ap.add_argument('--dry-run', action='store_true', help='只打印计划，不联网不写库')
    ap.add_argument('--force', action='store_true', help='忽略分频间隔，强制采集')
    a = ap.parse_args(argv)

    cmd = [PYTHON, RUNNER, '--profile', a.profile]
    # platform_key 为 None =总入口：交给配置里的 enabled 决定跑哪些，
    # **不能**拼 '--platform None'（那样 run_refresh 匹配不到任何配置项，
    # 会直接SystemExit「没有启用的平台」）。
    if platform_key:
        cmd += ['--platform', platform_key]
    if a.pages is not None:
        cmd += ['--pages', str(a.pages)]
    if a.no_chain:
        cmd += ['--no-chain']
    if a.dry_run:
        cmd += ['--dry-run']
    if a.force:
        cmd += ['--force']
    if extra_spider_arg:
        # 必须包成 --spider-arg X --spider-arg Y 的成对形式：run_refresh.py 用
        # 严格的 parse_args()，裸--platform 会被当成未知参数直接报错退出。
        # 必须用 --spider-arg=值 的等号连写形式：值本身以 '-' 开头
        # （如「--platform 小红书」里的 --platform），空格分隔会被 argparse
        # 当成新选项并报 'expected one argument'。
        cmd += ['--spider-arg=%s' % a_ for a_ in extra_spider_arg]

    print('>> %s 采集（profile=%s）' % (platform_key or '全部平台', a.profile), flush=True)
    return subprocess.call(cmd, cwd=BASE)


if __name__ == '__main__':
    sys.exit(crawl(sys.argv[1] if len(sys.argv) > 1 else 'weibo'))