# -*- coding: utf-8 -*-
"""JSONL 开放 schema 特征库（L1 落库方式）。

方案 §十 要求"加维度 = 加一个分析器文件，数据层零改动"。本层用 JSONL 而非固定列表，
天然满足开放 schema：每条特征是一行 JSON，含 analyzer / version / kv / status，
同一视频可并存多个版本的特征，便于回溯与增量重算。

后续若需并入关系型表（t_video_feature），只需换一个 store 实现，analyzer 与 runner 不动。
"""
import json
import os
from datetime import datetime


class FeatureStore:
    def __init__(self, path):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)

    def write(self, record):
        """追加一行 JSONL。record 形如：
        {content_id, platform, basin, topic, features:{name:{version,kv,status}},
         coverage:{n_analyzed,n_total}, generated_at}
        """
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def reset(self):
        if os.path.exists(self.path):
            os.remove(self.path)


def now_iso():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
