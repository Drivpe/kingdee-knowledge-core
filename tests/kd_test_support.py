#!/usr/bin/env python3
"""kd 回归用例的 fake 上游共享口径（票 05）。

两条路径（进程内 suite / CLI 子进程）都经本模块的 resolve_payload 识别
"假 200 + errorCode" 并递增上游计数，避免同一逻辑抄两份。
"""
import contextlib as _contextlib
import json
import os
import sys


def _core_and_config():
    """经公开观测口 core._impl() 拿到实现包，再从**实际解析到的模块对象**
    取 config —— 不硬编码私有文件名，故 _config.py 改名不影响测试。"""
    from kd import core
    impl = core._impl()
    # 生产代码里 _net 模块持有 config 的同一对象；经它取，跟着生产走。
    import kd._impl._net as net
    config = net._config
    return core, config


def resolve_payload(payload):
    """生产 _get_json 的同口径后置处理：计数 + errorCode → UpstreamError。"""
    core, config = _core_and_config()
    config._up_inc()
    if isinstance(payload, dict) and payload.get("errorCode"):
        raise core.UpstreamError(int(payload["errorCode"]),
                                 str(payload.get("message") or "")[:200])
    return payload


def install_fake(payload):
    """在 CLI 子进程里把唯一网络出口 `_net._get_json` 换成假实现。

    payload 是 {url子串: response} 映射；未命中一律抛错，绝不静默兜底。
    """
    import kd._impl._net as net

    def fake(url, rate=None):
        for key, response in payload.items():
            if key in url:
                return resolve_payload(response)
        raise RuntimeError("CLI fake 上游未登记该 URL：" + url)

    net._get_json = fake
    return fake


# ---- 生产内部配置的“单一测试注入口” ----
# 回归套件**不直接 import kd._impl._config**：声明覆盖、上游计数复位都经这里，
# 这样私有模块改名不会把测试变成事实 interface（票 05 验收 2/3）。

def contract_copy():
    """取当前生产声明的深拷贝（供用例构造“删一键”的注入变体）。"""
    import copy
    _, config = _core_and_config()
    return copy.deepcopy(config._CONTRACT)


@_contextlib.contextmanager
def contract_override(variant):
    """在 context 内把生产声明替换为 variant，退出必恢复。"""
    _, config = _core_and_config()
    real = config._CONTRACT
    config._CONTRACT = variant
    try:
        yield
    finally:
        config._CONTRACT = real


def reset_upstream_counter():
    """把生产上游调用计数归零（stats.upstreamCalls 的可比基线）。"""
    _, config = _core_and_config()
    config._UP_N = 0
