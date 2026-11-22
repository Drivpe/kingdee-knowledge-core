#!/usr/bin/env python3
"""kd._impl —— kd.core 的私有实现包(按职责拆分的装配层)。

**为什么是包而不是单文件**:kd.core 的公开面隔离依赖"实现体不在 kd.core 的命名空间里"
这一机制(工单 #26)。此前全部实现挤在一个 1331 行的模块 `kd._core_impl.py` 里,
47 个顶层定义横跨 9 块职责。拆成包后,seam 落在**职责簇**:每个私有子模块自成一个
可独立阅读的单位,而可见性隔离仍由"kd.core 只 import 本包"保证(隔离与文件数量无关)。

**装配层的职责**(票 07 收口后只剩一件):向 `kd.core` 提供 5 个公开名
(2 函数 + 3 异常)。原"把全部内部件汇集到本包命名空间、供 `core._impl()` 观测"
的机制已废止(ADR-0013 增补记):CLI 只读公开包版本与随包声明;
冻结基线与测试 fake adapter 仅经 `kd._impl._net` 这一已确认 seam 取配置和替换网络。
故本文件**不再再导出任何内部名**,私有实现的改名与文件布局不再构成外部契约。

子模块地图:
  _errors    三个对外异常类(类对象身份被 kd.core 复用)
  _config    单一真源常量、契约声明(contract.json)、限速、上游计数
  _net       上游 HTTP 出口(_get_json)、检索词硬闸(clamp_query)
             「什么算上游故障」的单一分类来源(UPSTREAM_FAILURES)
  _text      html2text、标题降级链(_title_of)
  _upstream  上游检索调用与条目规范化(_norm_item)
  _links     条目对外链接的唯一归属地(_URL_OF / compose_url / link_for_item)
  _manifest  多路清单执行链(唯一检索路径)、帖级归并、声明投影
  _detail    按 kind 读全文
  _public    公开面函数 search / read
"""
# ---- kd.core 装配所需的 5 个公开名(唯独这几个会被 kd.core 取走) ----
from ._config import VERSION  # noqa: F401  版本单一真源(kd.__version__)
from ._errors import InternalError, QueryTooLong, UpstreamError  # noqa: F401
from ._public import read, search  # noqa: F401
