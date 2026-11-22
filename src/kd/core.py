#!/usr/bin/env python3
"""kd.core —— 检索内核(可 import 的库,无 HTTP 层)。

零账号/零 cookie/零点数/零外部依赖。

公开面(仅此两个高阶函数 + 三个异常类):
  search(keywords=None, product_id=<声明默认>, global_=False, sorts_type=1, rate=None,
         include_other=False) -> dict
                      唯一检索入口:多路关键词检索,**只出帖级标题清单**(不返回正文)
  read(kind, oid, rate=None) -> dict
                      按类型读全文
  QueryTooLong / UpstreamError / InternalError            可分类的调用错误

**三步解耦(本内核的设计主轴)**:清单 → 挑选 → 全读。
  1. `search` 用多路关键词检索,只列出标题级信息;
  2. 调用方(agent)按标题匹配度挑出要读哪几篇;
  3. `read` 取全文,由调用方合成回答(ADR-0008:合成权在调用方)。
内核**不替调用方决定读哪篇**,也不产生任何排序评分——每一路都是上游综合排序的产物,
本内核只做去重(2026-09-18 定案,见 ADR-0013)。

**清单粒度 = 帖子**(2026-09-27,ADR-0014):同一帖的多条回答在上游是多个条目,
清单里**合并为一条**;条目的 `id` 就是帖子号,`read` 直接用它。问答档的对外类型名是
`question`(上游协议里叫 `answer`,映射只在实现体内的 `_norm_item` 一处)。

⚠️ **内核不生成任何检索词**(ADR-0016,2026-09-28,v6.6 破坏性变更):
`search` 的 `keywords` 是唯一输入,内核把收到的词**原样、按原顺序**发往上游。
拆词(以及"哪个词更该排前面")需要语义,规则做不到——三处实测负结果在案
(拉丁词前置把金标从第 2 挤到第 12;泛词拆分掉出前 30;双截断实现并存)。
拆词是**调用层**的职责,规范由调用方维护,本内核不附带也不读取它。`queries[]` 与调用方给的词逐字、逐序相同。
随之删除的还有:位置参数、`--type`、`--max-routes`、`--budget`(预算机制整套)、
`--chunk`,以及原句路(ADR-0009 整体废止)。**清单字段集按类型分份**(决策 6 + 2026-09-29
新增 `other` 档):
类型不适用的键**直接不出现**,而不是填 `null`。

**内部件的封闭方式(工单 #26——前导下划线不足)**:
实现体(全部内部函数、常量、类、以及被 import 进来的 json/re/urllib 等名字)
放在私有实现包里(`kd._impl`,按职责拆成若干子模块)。之所以必须不在本文件:模块级
定义若写在本文件,import 时就会注册进 `kd.core` 的命名空间,`kd.core._rrf_fuse`
仍可属性访问——`__all__` 只约束 `import *`,约束不了属性访问。搬进私有包后,
本模块的命名空间里**只有**上面 5 个公开名,其余一律不存在:
    kd.core.ask        -> AttributeError
    kd.core.RRF_K      -> AttributeError
    kd.core.json       -> AttributeError
这不是"前导下划线"式的君子协定,而是命名空间级隔离;后续重构内部件不再构成
对外破坏性变更。校验见 `tests/kd_regression.py` 的离线组(原
`scripts/check_core_surface.py` 已于 2026-09-27 整体删除,其中三条真防静默失效的
判据并入离线回归)。

**观测口已废止**(2026-11-22,票 07,ADR-0013 增补记):原 `kd.core._impl()` 曾返回
承载实现的包对象供测试/自检读取内部件;health 删除后它只剩测试消费者,且把 67 个
再导出变成隐性 interface。CLI 只读公开包版本与随包声明;测试 fake adapter 仅使用
已确认的网络 seam,不再经 kd.core 暴露任何内部路径。

上游接口(匿名,零 cookie):
  检索    GET https://vip.kingdee.com/api/search?text=&page=&pageSize=&global=&sortsType=&productIds[0]=
  知识全文 GET https://vip.kingdee.com/knowledgeapi/knowledge/{id}
  问题详情 GET https://vip.kingdee.com/api/questions/{id}、回答 GET .../api/answers/{id}
  文章     GET https://vip.kingdee.com/api/articles/{id}

上游纪律:匿名链路,交互短突发 2-3 请求/秒 + 抖动(默认档)。
上游 text 有 100 原始字符硬闸——超限返回 HTTP 200 + errorCode:409 空壳,
实现体用 clamp_query() 压回并在压回时 raise QueryTooLong(不静默截断成"无匹配")。
每路**恒 1 次请求**(跨页扫描已删除):7 个词 = 7 次请求 = 3.33 秒。
"""
# 公开面:`kd.core` 顶层**只允许**出现这 5 个名字(工单 #26 验收标准)。
__all__ = ["search", "read", "QueryTooLong", "UpstreamError", "InternalError"]

# 实现载体。import 的副作用(定义全部内部件)发生在 kd._impl 的命名空间内,
# 不在本模块留下任何内部名。装配别名用后立即 del(见文件末尾),
# 故 vars(kd.core) 恒等于 5 个公开名 + 双下划线元数据,无任何内部属性面。
import importlib as _importlib

# 公开异常类:直接复用实现体里的类对象,身份一致——
# 实现体内部 raise 的实例,调用方 `except kd.core.QueryTooLong` 照常命中。
_IMPL = _importlib.import_module("kd._impl")

QueryTooLong = _IMPL.QueryTooLong
UpstreamError = _IMPL.UpstreamError
InternalError = _IMPL.InternalError

# 公开两个高阶函数:直接绑定实现体里的函数对象(不是包装层)。
# 签名、默认值、docstring、`__globals__`、返回结构全部原样,行为逐字段不变。
search = _IMPL.search
read = _IMPL.read

# 装配别名在绑定完成后立即清除:`_IMPL` / `_importlib` 不得留在 __dict__ 里。
# 故 vars(kd.core) 恒等于 5 个公开名 + 双下划线元数据;无任何 __getattr__ 观测口。
del _IMPL, _importlib
