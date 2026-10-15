# -*- coding: utf-8 -*-
"""短视频分析 · L1 文本+封面层（不下视频）

包结构（插件式，加维度 = 加一个 analyzers/*.py，数据层/调度层零改动）：
    db.py            作品库引擎获取
    registry.py      分析器注册表
    store.py         JSONL 开放 schema 特征库
    base.py          分析器基类
    analyzers/       三个 L1 分析器
    l1_runner.py     编排器 + CLI

三条红线（写死在本层）：
    1. 默认不保存原始视频文件（封面只取图、不取视频流）
    2. 人脸/声纹特征默认不提取
    3. 抽样结论必须标注"基于 N 条样本"，不得外推成全量
"""
