# -*- coding: utf-8 -*-
"""分析器注册表：加维度 = 加一个 analyzers/*.py 并在模块内 @register。

数据层与调度层均通过 name 引用，不关心具体实现，故新增分析器无需改表、无需改 runner。
"""


_REGISTRY = {}


def register(analyzer_cls):
    """装饰器：把分析器类登记进注册表（以 cls.name 为键）。"""
    if not getattr(analyzer_cls, 'name', ''):
        raise ValueError('分析器必须定义类属性 name')
    _REGISTRY[analyzer_cls.name] = analyzer_cls
    return analyzer_cls


def get(name):
    return _REGISTRY.get(name)


def all_analyzers():
    return list(_REGISTRY.values())


def names():
    return list(_REGISTRY.keys())
