#!/usr/bin/env python3
"""kd._impl._errors —— 可分类的对外错误。

三个异常类的**类对象**被 kd.core 直接复用(不是包装),故实现体内部 raise 的实例,
调用方 `except kd.core.QueryTooLong` 照常命中。身份一致性由公开面守卫判据 6 钉住,
本模块是这三个类唯一的定义地——不得在别处再造一份同名类。

内部件 `_raise_min`(最小键重抛)已于票 08 收进 `_concurrent`,与保序/失败收集
同一实现;本模块只定义三个对外异常类,不再承载并发执行机制。
"""


class UpstreamError(Exception):
    """上游业务错误(HTTP 200 但 body 带 errorCode)。

    上游的"假 200"形态:HTTP 层成功,业务层失败。不识别就会把"查询被拒绝"
    静默降级成"无匹配结果"——本套件多处注释记着这条教训。
    """

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__("upstream %s: %s" % (code, message))


class QueryTooLong(ValueError):
    """检索词超过上游 100 原始字符硬闸。

    压回上限内确实能跑通,但静默截断会把"查询被上游拒绝"伪装成"官方没这类文档"
    ——故显式报错,由调用方决定是否用 `clamped` 字段里的压回值重试。
    """

    def __init__(self, original, clamped, limit):
        self.original = original
        self.clamped = clamped
        self.limit = limit
        super().__init__("query too long: %d > %d upstream chars" % (len(original), limit))


class InternalError(Exception):
    """参数/内部使用错误(CLI 默认映射为用法错误退出码 2,**按 `code` 分档**)。

    ⚠️ **可选分类标识 `code`**(2026-09-29 收口,"错误码的分类不依赖文案"):

    本类原先只有自由文本 message,于是"到底是哪一种内部错"只能由**消费方对文案做
    子串匹配**来区分 —— `cli._guard` 曾写 `if "没有它的全文端点" in str(e): ...` 来
    判定 `other` 档的能力边界。那种写法的后果不是"丑",而是**改一个措辞就会让分类
    静默漂移**:`unsupported_kind`(exit 1)会无声退回 `usage`(exit 2),把调用方
    引向"去改参数",而它其实没传错;且当时**没有任何回归用例**覆盖这一档
    (`grep unsupported_kind tests/` 零命中),漂移不会有信号。

    现在**抛出处**用 `code=` 显式声明分类,文案与分类彻底解耦:

        raise InternalError("…文案随便怎么写…", code="unsupported_kind")
        # 消费者只读 `e.code`,永不读 message

    约定:
      * `code=None`(默认,**含全部既有单参调用**)= 未分类 → CLI 按**用法错误**
        (exit 2)兜底 —— 与改动前的行为逐字相同,故单参调用完全兼容;
      * 已知分类见 `_detail._detail`(当前**唯一的分类值**是 `unsupported_kind`)。
        ⚠️ **不在这里预置枚举清单**:没有消费者的档位就是死机制("声明必须有消费者"),
        新增分类时在**抛出处**声明,并在 `cli._guard` 里给它一条映射。
    """

    def __init__(self, message, code=None):
        self.code = code
        super().__init__(message)
