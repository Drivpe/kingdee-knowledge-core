#!/usr/bin/env python3
"""kd._impl._manifest —— 多路清单执行链(唯一检索路径)。

**排序契约(2026-09-18 定案,不得重开)**:本内核**不产生任何排序分**。

理由:每一次上游检索都由**官方综合排序**排好了,本内核拿到的每一路都是有序的。
多路的价值是"用不同关键词命中不同文档",不是"给文档打分"。故内核只做两件事:

  1. **去重**——同一条文档被多路命中时只留一条;
  2. **保持稳定顺序**——按(首次出现的路序号, 该路内的上游名次)。

两者的输入都不是算出来的:路序**逐字等于调用方给词的顺序**(ADR-0016 决策 2),
路内名次直接是上游返回的下标。**没有加权、没有分数、没有时间衰减、没有 views 权重**,
也没有"命中路数排序"——那同样是算法评分。

`hitRoutes` / `routes[]` 仍然返回,但**降级为纯信息字段**:它们告诉调用方(LLM)
"这条被哪几路搜到了",供它自己判断该读哪篇,**不参与排序**。

⚠️ **v6.6 删除面**(ADR-0016,2026-09-28):
  * `_resolve()` 字符串查表 —— 网络出口改为**模块级可替换的单一入口**
    (`_upstream._search_upstream`),不再需要为猴补丁包属性而设的间接层;
  * `type_` 过滤与跨页扫描(`_MAX_SCAN_PAGES` 的 while 循环)—— `--type` 删除后
    该循环永不执行(实测:不带 `--type` 时第一页就返回 10 条 = 目标条数);
  * 预算机制(`budget` / `_Budget` / `_BudgetExhausted`)—— 每路恒 1 次请求,
    预算永不可触发,`budget_exhausted` 顶层键随之消失;
  * `max_routes` 形参 —— 上限只在声明里有一个值(`limits.maxKeywords`);
  * 顶层 `text` 键 —— 位置参数删除后,"整句"不再有特殊地位,回显只留 `keywords[]`。
"""
from . import _net, _upstream
from ._config import (apply_link_policy, contract_loaded, log, max_keywords,
                      result_keys, top_keys)
from ._concurrent import run_ordered
from ._errors import UpstreamError
from ._links import compose_url
from ._net import clamp_query
# ⚠️ 链接构造走 `_links.compose_url`(唯一归属地,2026-10-01 K1)——原先是
# `from ._upstream import _question_url`,即"回答号怎么选"在清单侧另推导一遍。

# 每路上游固定取 10 条。清单是"每路 10 条去重归并"的产物,总长最坏只有 路数×10。
# ⚠️ 原 `_MAX_SCAN_PAGES`(跨页扫描上限)已随 `type_` 过滤一并删除:它是"为 type_
# 补齐服务的"旋钮,删除后该循环永不执行(决策 5)。
_PER_ROUTE_WANT = 10


def _plan_routes(keywords, product_id):
    """调用方给的词 → route 列表:**逐字、逐序**,不删改、不重排、不补充。

    唯一清洗是首尾 strip 与跳空串(空白不是词的一部分)。去重在 `_dedupe_routes`;
    内核不生成检索词(ADR-0016 决策 1),路序即调用方给词顺序。产品线直通。
    """
    routes = []
    for k in (keywords or []):
        term = str(k).strip()
        if not term:
            continue
        routes.append({"kind": "explicit", "terms": clamp_query(term)})
    if product_id and int(product_id) != 0:
        # 显式 0/None = 不过滤:**完全不写** productIds(上游把 0 当真值过滤)。
        for r in routes:
            r["productIds"] = int(product_id)
    return routes


def _dedupe_routes(route_list):
    """丢弃检索词完全相同的重复路:同一 query 不发两次请求。

    去重与截断是两件事:丢词由 `keywordsDropped` 通报,重复词不再通报
    (用户裁定「重复的就不要提示了」)。
    """
    out, seen = [], set()
    for r in route_list:
        t = str(r.get("terms") or "")
        if t in seen:
            continue
        seen.add(t)
        out.append(r)
    return out


def _route_search_once(text, product_id, rate, global_=False, sorts_type=1,
                       page_size=_PER_ROUTE_WANT):
    """单路检索:**只发 1 次请求**(`page_size` 默认 `_PER_ROUTE_WANT`,当前 10),
    不做任何跨页补齐。

    返回 `items`(归一化后的上游条目列表)。上游错误原样上传,由编排层分档处理
    (单路失败不拖垮整轮)。

    ⚠️ **v6.9**:上游响应里的 `totalElements` 本函数**不再读取**。它此前唯一的消费者
    是顶层 `total`,而那个字段已删除(理由见 `_config.VERSION` 的 6.9 条目)——留着读取
    就是"生产者无消费者",与本仓「不留死机制」的纪律冲突。上游照旧返回它:那是**上游
    响应形状**,不是我们的契约,故**不要**把读取加回来。

    ⚠️ **跨页扫描已删除**(ADR-0016 决策 5):原 `while pg <= max_scan_pages` 循环是
    "为 `--type` 补齐服务的"——把混排结果里的目标类型抽出来需要多翻几页。`--type`
    删除后该循环**永不执行**(实测:不带 `--type` 时第一页就返回 10 条 = 目标条数),
    留着是死机制,且它会让"每次请求数不可预测"。现在每路恒 1 次请求:
    7 个词 = 7 次请求 = 3.33 秒(实测)。
    要更深由调用方自己换词或换参数,而不是内核自行扩充取数深度(禁止清单)。

    ⚠️ **本函数经 `_upstream._search_upstream` 调用网络出口**(模块级可替换的单一
    入口):测试把它换成假实现即可从 `core.search` 真跑完整链路而不触网。
    不写成 `from ._upstream import _search_upstream` 的局部绑定——那是 import 期快照,
    替换模块属性对它无效。

    global_ 必须由调用方透传:它是"跨全部产品"的开关,**不是**路由策略。
    """
    items = []
    dd = _upstream._search_upstream(text, product_id, 1, page_size, global_,
                                    sorts_type, rate)
    for x in dd.get("content") or []:
        n = _upstream._norm_item(x, x.get("entity-type") or "")
        if n:
            items.append(n)
    return items


def _manifest_key(n):
    """多路清单的去重键:`f"{type}:{id}"` —— **清单的单位是帖子**(ADR-0014)。

    ⚠️ **`other` 档必须并入 `upstreamType`**(2026-09-29 修正,code review C1):
    `f"{type}:{id}"` 的前提是"同一个 type 下 id 唯一"。前三个已知类型成立
    (knowledge / question / article 各有自己的 id 空间),但 **`other` 是一个
    跨类型的收容桶** —— 它把 `LearningCourse` / `LearningPath` /
    `KnowledgeSpecial` / `LearningBroadcast` **压成同一个 `type="other"`**,
    而它们的 id 空间**互不相干、形状相同**(实测课程与学习路径都用雪花串,
    课程还有 `6898` 这种小整数)。

    后果(实测复现):4 条不同实体 → 去重键只剩 2 个 → 上游缓存 4 条而 `results: 2`,
    `routeErrors: []`、无任何提示 —— **与本轮要治的原始缺陷一字不差的形态**
    (「把'我们没读懂'伪装成'上游没有'」)。即若不处理,就是**用一处静默换另一处静默**。

    现行口径:同一帖的多条回答**合并为一条**,`id` 就是帖子号(见 `_norm_item`),
    故本键天然按帖子归并。已知取舍:同帖的多条回答不再能分开筛;回答数由
    `answersCount` 原生信号承担,"这帖里有采纳答案"由 `adopted` 承担。
    """
    kind = n.get("type") or "?"
    if kind == "other":
        # 跨类型收容桶:类型名必须进键,否则不同实体会互相吃掉。
        ut = str(n.get("upstreamType") or "")
        oid = str(n.get("id") or "")
        if not oid:
            oid = str(n.get("xId") or "")
        return "other:%s:%s" % (ut, oid)
    return "%s:%s" % (kind, n.get("id") or "")


def _manifest_merge(ns):
    """同帖多条目 → 一条**帖级**条目(ADR-0014,决策 D4)。

    上游搜索端点按**回答**返回:一个帖子下 3 条回答就是 3 个条目,各带自己的回答 id
    与同一个帖子号。清单的单位改成帖子后,这几条必须合并成一条——与人类搜社区时
    看到的形态一致。

    合并规则(逐项,**不引入任何排序分**——排序键仍是 (首次路序, 路内名次)):
      * `type`/`id`/`title`/`questionBody` —— 同帖取值本就相同,**取首个非空**;
      * `snippet` —— 各条回答的命中片段不同,**取上游给的第一条非空**(不拼接:
        拼接会把不相邻的回答片段伪装成一段连续文本);
      * `products` —— 取首个非空列表;
      * `url` —— **采纳优先**(见下),这是唯一一处"合并会改变值"的字段;
      * `adopted` —— **任一侧有值即为该值,两值取或**;两侧都无值则保持缺失。
        ⚠️ **D1 修复(v6.6)**:原写法 `bool(out.get("adopted")) or bool(n.get("adopted"))`
        把缺失键的 `None` 折成 `False` —— 于是一条**没有该字段**的 article 被合成了
        假的 `adopted: false`(上游从没说过它未被采纳,是我们替它说的)。
        实测影响:`tests` 那条"非问答条目 adopted 应为 None"的在线断言在真实数据上
        会红,只因合成数据的 id 互异而从未触发合并。
      * `answersCount` / `comments` / `supports` —— **取最大值**。上游各条各自复述
        同一帖的计数(正常同值),取 max 保证不因某条缺字段而丢掉真值。

    ⚠️ **`url` 的帖级取舍(2026-09-29,问答链接改判)**:问答条目现在是
    `/questions/<帖子号>/answers/<回答号>` 的**长形式**,故一个帖子下有几条回答
    就有几个**不同的** url —— 帖级合并必须选一个。规则:

      1. **采纳回答优先**(`isAdopt` 为真的那条)—— 链接应当指向"解"本身;
      2. 无采纳时回落**上游给的第一条** —— 上游本身按综合排序返回,首条即最好的
         默认落点,内核不引入任何自己的判断(零算法排序契约不变)。

    这与 `adopted` 的"取或"是两件事:`adopted` 说的是"这帖里有采纳答案",
    `url` 说的是"点开该落在哪条回答上"。
    """
    out = dict(ns[0]) if ns else {}
    for n in ns[1:]:
        for k in ("type", "id", "title", "url", "questionBody"):
            if not out.get(k) and n.get(k):
                out[k] = n[k]
        if not out.get("snippet") and n.get("snippet"):
            out["snippet"] = n["snippet"]
        if not out.get("products") and n.get("products"):
            out["products"] = n["products"]
        # 帖级布尔:任一侧**有值**时取或。两侧都无值 → 保持缺失(不得合成 False,D1)。
        vals = [v for v in (out.get("adopted"), n.get("adopted")) if v is not None]
        out["adopted"] = any(bool(v) for v in vals) if vals else None
        for k in ("answersCount", "comments", "supports"):
            a, b = out.get(k), n.get(k)
            if isinstance(a, int) and isinstance(b, int):
                out[k] = max(a, b)
            elif b is not None and a is None:
                out[k] = b
    # 问答帖的 url 单独定:采纳回答优先,无则回落到上游首条(见 docstring)。
    # ⚠️ **2026-10-01(K1)**:这条回落链**不再在这里实现** —— 它由
    # `_links._pick_answer_id`(零算法契约)承载,`compose_url` 统一选回答号。
    # 原先 read 侧另走 `bestAnswer[0]` 单点取法,两侧对同一帖给出不同 url(已复现)。
    # ⚠️ 候选集按 `ns` 的**上游返回顺序**给(采纳优先的判定在 `_pick_answer_id` 里)。
    # ⚠️⚠️ **相对 HEAD 的唯一行为放宽(如实声明,不得再自称"逐字相同")**:
    # `_pick_answer_id` 先对每个候选做 `_s()` 归一(等价于原 `_question_url` 的
    # `str(...).strip()`),**再**丢弃空段 —— 于是"空白段"被视为**该段缺失**而跳过,
    # 落到下一个非空候选。HEAD 的回落链用真值过滤(`.get("url")` 那行),`"   "` 为真
    # ⇒ **不跳过**,行为是"给不出链接"。实测两版对照:
    #   * `ns=[(空白,未采纳),(11,未采纳)]` → HEAD `url=None`,现版 `…/answers/11`;
    #   * `ns=[(空白,未采纳)]`            → 两版同为 `None`;
    #   * `ns=[(11,未采纳),(12,未采纳)]`   → 两版同为 `…/answers/11`。
    # **生产不可达**(上游 id 恒为无空白的数字串),故这不是线上故障,而是
    # 契约/实现不符;口径由用户在 2026-10-03 裁定为"承认放宽"。
    # 之所以保留放宽:语义上"跨过缺段找一个可用回答号"优于"整帖给不出链接"
    # (后者让读者损失一次跳转),且方向与 `compose_url` 的必需段规则一致。
    # 守护用例:`t_pick_answer_id_multi_candidate_blank_skip`(多候选构造)。
    if out.get("type") == "question":
        out["url"] = compose_url(
            "question", out.get("id"),
            [(n["_answerId"], n.get("adopted"))
             for n in ns if n.get("_answerId")])
    return out


def _manifest_fuse(route_lists):
    """多路结果 → 去重后的清单条目(带 hitRoutes / routes)。

    route_lists 是 [(路序号, [规范化条目, …]), …],顺序即路的执行顺序。
    返回 (keys, route_hits, by_key):
      keys       按 (首次路序号, 路内名次) 排列的清单键
      route_hits {去重键: {路序号,…}} —— 纯信息,不参与排序
      by_key     {去重键: 帖级条目} —— 同帖多条目已由 `_manifest_merge` 合并

    ⚠️ 合并(`_manifest_merge`)在这里发生,**排序键不受其影响**:排序仍只看
    "首次出现的路序号 + 该路内上游名次",取的是该帖最早被哪一路第几名召回。
    合并只改变条目的**字段内容**(帖级聚合),不改变任何顺序——零算法排序是硬契约
    (ADR-0013),把清单粒度从回答级改成帖子级(ADR-0014)**不得**顺带引入排序分。
    """
    route_hits, order, groups = {}, [], {}
    for route_no, items in route_lists:
        for pos, n in enumerate(items, 1):
            if not n:
                continue
            k = _manifest_key(n)
            if k not in route_hits:
                route_hits[k] = set()
                order.append(k)
                groups[k] = []
            route_hits[k].add(route_no)
            groups[k].append(n)
    # ⚠️ **直接保序,不排序**:内核不产生排序分(ADR-0013),路序来自调用方给词顺序。
    #
    # 顺序契约就在 `order` 的构造上:它只在 `k not in route_hits` 的首次命中分支里
    # append 一次,而 route_lists 已按 (路序号, 路内名次) 遍历 —— 故 `order` 的次序
    # 逐字等于"首次路序 + 路内名次"。这就是"清单顺序 = 调用方给词的顺序,
    # 该路内上游名次"的载体(ADR-0016 决策 2 的硬契约)。
    # 保序由公开结果本身 + fake 上游用例验证,不再靠任何影子载体。
    keys = list(order)
    by_key = {k: _manifest_merge(groups[k]) for k in keys}
    return keys, route_hits, by_key


def _manifest_project(n, route_nos):
    """清单条目的对外形态:只给标题级信息,不返回 contentText。

    调用方要全文走 `read(id, kind=type)`——"筛选"与"深读"两步解耦、各自可重试。
    没有 contentText 就不存在"替调用方决定读哪篇"这件事。

    **字段集 = 该条目 `type` 的键集(公共 + 类型专属),从 contract.json 声明取**
    (决策 D13 单一来源 + ADR-0016 决策 6 分三份)。声明里列了哪些键,本函数就产出
    哪些键 —— 故"多出字段/少了字段"两种情况都能被声明侧抓住。

    ⚠️ **取值规则(ADR-0016 决策 6,别改)**:
      * **类型不适用的键直接不出现在该条目上** —— 例如 article 不会有 `adopted`。
        这不是"填 null 也可以",而是一个语义区分:
          - **结构性不适用**(知识文档永远没有回答数)= 键**不出现**;
          - **上游没给值**(这条问答帖上游没给 comment 数)= 值为 `null`。
        混成同一种表示会让调用方分不清"这个字段对本类型无意义"与"这次没取到"。
      * 故本函数**不再**用 `{k: n.get(k) for k in result_keys()}` 统一填 `None`
        (那是旧形态,它让三类条目长着同一套键)。

    除标题级信息外,透传上游的**原生信号**(采纳标记/回答数/评论数/问题正文):
    它们是上游直接给的,不是本内核算的,正是调用方按标题匹配度挑选时需要的旁证。

    ⚠️ 条目已是**帖级**(`_manifest_merge` 合并过同帖多条回答),故这些信号的语义
    都是帖级的:`adopted` = "这帖里有采纳答案"。
    """
    # ⚠️ 不用 `{...} | {...}`(PEP 584 的 dict 合并运算符,Python 3.9+):
    # pyproject.toml 声明 `requires-python = ">=3.8"`,README 也写「Python 3.8+」。
    # 在 3.8 上这会直接 SyntaxError —— 而本套件号称"纯标准库、零依赖、装了就能跑",
    # 声明与实现不一致会让 3.8 用户拿到一个连 import 都过不去的包。
    kind = n.get("type")
    out = {k: n.get(k) for k in result_keys(kind)}
    # ⚠️ **这两个键不是"声明之外的额外键"**(2026-10-01 更正,原注释称"不在声明里当
    # 条目字段"与事实不符):`contract.json` 的 `resultKeysCommon` **恰好列着**
    # `hitRoutes` / `routes`。上面那行 `result_keys(kind)` 已经把这两个键**拼进**
    # `out`(值为上游条目的同名键,通常 None);下面两行做的是**覆盖其值** ——
    # 它们是**内核算出**的命中信息(不来自上游条目),而声明管的只是"有哪些键"。
    out["hitRoutes"] = len(route_nos)
    out["routes"] = sorted(route_nos)
    # ⚠️ **链接政策的生效点**(2026-09-28;口径 2026-09-29 改判):三档都给链接,
    # 而 `other` 档给不出(实测无可点网页形式)。**这里是政策唯一的运行期闸门** ——
    # `apply_link_policy` 是它的消费者,声明不落到生产路径就等于没修
    # (CONTEXT.md:「声明必须有消费者,否则'单一来源'是假的」)。
    # (键恒在:它是公共键,政策改的是**值**而不是"这个字段对本类型是否有意义"。)
    out["url"] = apply_link_policy(kind, out.get("url"))
    return out


def _search_manifest(keywords=None, product_id=None, blank_dropped=0, global_=False,
                     sorts_type=1, rate=None, include_other=False):
    """调用方给的词 → 每路一次上游检索 → 去重归并 → 出**帖级**清单。**唯一检索路径。**

    设计(已定,勿重开):多路 + 只出清单 + 每路 `page_size=_PER_ROUTE_WANT`(当前 10)
    + **零排序分**。

    ⚠️ **内核不生成任何检索词**(ADR-0016 决策 1):`queries[]` 与调用方给的
    `keywords` **逐字、逐序**相同。本函数不再是"拆词入口",而是"发送 + 归并"。

    ⚠️ 原 `text` / `type_` / `max_routes` / `budget` 形参已于 v6.6 删除:
      * `text` —— 位置参数删除后无来源;顶层 `text` 键一并消失(契约不挂恒 null 的坑);
      * `type_` —— 清单不做类型过滤,调用方从条目的 `type` 字段自己筛;
      * `max_routes` —— 上限只在声明里一个值(`limits.maxKeywords`);
      * `budget` —— 预算机制整套删除(每路恒 1 次请求,不可触发)。

    ⚠️ **清单分页已整体删除**(决策 D10,2026-09-27)。取舍:清单总长最坏就是
    "路数×10 去重归并后"的量,不能翻页时只能拿全部;需要更多就换词重搜。

    `include_other` 由 `_public.search` 传入(默认 `False` = **隐藏** `other` 档):
    上游罕见类型(课程/路径/专题/直播)单独收容成一档,默认不混进清单以保护调用方的
    挑选信噪比;隐藏时把跳过的条数写进顶层 `otherSkipped` 与 `scanNote` ——
    **隐藏必须可见**,否则"清单比实际召回少了一截"的差额又会变成无解释的静默。

    `blank_dropped` 由 `_public.search` 传入:调用方给的词里有几条是空串/纯空白
    (调用层已拦掉"全是空白"的输入,这里只处理**部分空**)。它必须进 `scanNote`——
    否则 `["甲","",""]` 只发 1 路而返回体看不出少了词,调用方会把自己的输入错误
    读成"内核只召回了 1 路"。规格 §A4:「违规的不是说不,是**不说**」。
    """
    # ---- 收词与上限:超出按顺序取前 N,并**写明丢了几条**(ADR-0016 决策 4) ----
    limit = max_keywords()
    route_list = _plan_routes(keywords=keywords, product_id=product_id)
    # `routesPlanned` 的口径(沿用 spec 第 3 节冻结的语义):**去重前、受上限截断后**
    # 的计划路数。不要改成去重后的实际路数——那不是这个字段的语义。
    planned = min(len(route_list), limit)
    route_list = _dedupe_routes(route_list)
    # ⚠️ 截断 = **按调用方给的顺序取前 N**(ADR-0016 决策 2),不再有"截断优先级"。
    # 原 `_truncate_routes` / `_TRUNC_PRIORITY` 已删:"按重要性保席位"这个概念整体消失
    # ——路序已逐字等于调用方给的顺序,内核没有做选择。违规的不是"取前 N",是**不说**。
    dropped = max(0, len(route_list) - limit)
    route_list = route_list[:limit]
    # ⚠️ **`routesDegraded` 已整体删除**(2026-09-29,工单 #33,用户裁定)。
    #
    # 用户原话:「**重复的就不要提示了,非重复的超上限的提示**」。
    # 按此口径 `keywordsDropped`(去重后词数 − 上限)**恰好是对的**,保留;
    # 要撤的是**重复词那一支的提示** —— 它原先报得**不一致**:
    #     `A B A`(3 词 1 重复)报「路数塌缩:3→2 路」;
    #     `A…G A`(8 词 1 重复)只字不提。**同一原因时而报时而不报。**
    # 留一个恒 false 的键是"死机制",与本仓"不留占位、不承诺不存在的能力"冲突,
    # 故整套删除(顶层键 + scanNote 句 + CLI stderr 句),不是置 false。
    #
    # ⚠️ **去重本身保留**:不得对同一 query 发两次上游请求。

    # ---- 路由并发:执行机制走 _concurrent,业务政策留本处 ----
    # 并发上界就是路数(maxKeywords 已是声明上限),限速仍只有 _RateLimiter 一处。
    # 上游故障 → routeErrors;程序缺陷 → 按最小路号重抛;中断类立即穿透。
    results, errors = {}, {}
    route_by_no = dict(enumerate(route_list, 1))

    def _route_failure(route_no, e):
        # 业务政策 ①:上游故障只进 routeErrors,不拖垮整轮。
        r = route_by_no[route_no]
        if isinstance(e, UpstreamError):
            log("UPSTREAM_ERR:", "route=%s code=%s msg=%s"
                % (r.get("kind"), e.code, e.message))
            errors[route_no] = {"route": route_no, "kind": r.get("kind"),
                                "terms": r.get("terms"),
                                "error": "upstream_error", "code": e.code,
                                "message": e.message}
        else:
            # 传输层/协议层/解析层故障:同属可重试的上游故障,无业务错误码。
            log("UPSTREAM_ERR:", "route=%s terms=%s %s: %s"
                % (r.get("kind"), str(r.get("terms"))[:40], type(e).__name__,
                   str(e)[:120]))
            errors[route_no] = {"route": route_no, "kind": r.get("kind"),
                                "terms": r.get("terms"),
                                "error": type(e).__name__,
                                "code": None, "message": str(e)[:200]}

    def _route_bug(route_no, e):
        # 业务政策 ②:程序缺陷只留痕,不写进 routeErrors;按最小路号重抛由
        # run_ordered 统一负责。
        r = route_by_no[route_no]
        log("ROUTE_BUG:", "route=%s terms=%s %s: %s(这是内核缺陷,"
            "不是上游故障,故不进 routeErrors)"
            % (r.get("kind"), str(r.get("terms"))[:40], type(e).__name__,
               str(e)[:120]))

    if route_list:
        tasks = {}
        for route_no, route in route_by_no.items():
            # r.get("productIds") 容忍缺键:不过滤(0/None)时刻意不写该键,
            # 显式 0 若透传会被上游当真值过滤(会把 Knowledge 挤出前排)。
            tasks[route_no] = lambda route=route: _route_search_once(
                route["terms"], route.get("productIds"), rate,
                global_=global_, sorts_type=int(sorts_type),
                page_size=_PER_ROUTE_WANT)
        results, _ = run_ordered(
            tasks, max_workers=len(route_list), expected=_net.UPSTREAM_FAILURES,
            on_failure=_route_failure, on_bug=_route_bug)
    # 按路号还原顺序(并发完成顺序**不得**泄漏进清单)。
    route_lists = [(n, results[n]) for n in sorted(results)]
    route_errors = [errors[n] for n in sorted(errors)]
    done = len(results)
    # ⚠️ `done` 在并发前是**循环内累加**的;现在改成"从结果集重算" ——
    # 与串行版逐字等价(每路至多贡献一次 done),但不再依赖任何共享可变状态
    # (那样就必须加锁,而锁会让这段变脆)。
    # ⚠️ v6.9:原在这里重算的顶层 `total`(各路 `totalElements` 的 max)已删除,
    # 故 `results` 的值也从 `(items, total)` 元组收成 `items` 本身。

    # 去重归并:同帖多条回答在此合并为一条(ADR-0014),排序键不受影响。
    keys, route_hits, by_key = _manifest_fuse(route_lists)
    # ---- `other` 档的**默认隐藏 + 通报跳过数**(2026-09-29,工单 #32)----
    # ⚠️ 隐藏是**默认**行为(用户裁定:这些类型质量低,得与前三档区分开),
    # 但**隐藏必须可见** —— 否则就是用一处静默换另一处静默:
    # 调用方看到的结果比实际召回少了一截,却不知道差额是开关造成的。
    # `otherSkipped` 就是那个通报口。
    other_keys = [k for k in keys if (by_key[k].get("type") == "other")]
    other_skipped = 0 if include_other else len(other_keys)
    if not include_other and other_keys:
        keys = [k for k in keys if k not in set(other_keys)]
    manifest = [_manifest_project(by_key[k], route_hits[k]) for k in keys]

    scan_parts = ["多路清单:%d/%d 路完成,每路 pageSize=%d,归并后 %d 条(帖子级)"
                  % (done, planned, _PER_ROUTE_WANT, len(manifest))]
    if dropped:
        # ADR-0016 决策 4:丢词必须在返回体里可见。这是既有纪律("宁可报错也不静默
        # 截断",见 clamp_query)在多路场景的落地。
        scan_parts.append("收词超上限:收到 %d 个词,只发前 %d 个(丢 %d 条,见 keywordsDropped)"
                          % (len(route_list) + dropped, limit, dropped))
    if blank_dropped:
        # ⚠️ 部分空串的丢弃也要说(v6.6 审查补):它不是"超上限",是调用方输入里有
        # 无效词。此前静默跳过 —— 调用方看到路数变少却找不到原因。
        scan_parts.append("丢弃空白词 %d 条(调用方输入里的空串/纯空白,不产生检索路)"
                          % blank_dropped)
    if route_errors:
        scan_parts.append("失败路 %d 条(见 routeErrors)" % len(route_errors))
    if other_skipped:
        # ⚠️ **这条通报是本档的存在理由之一**(工单 #32):没有它,
        # "上游缓存里有 212 条、清单只剩 2 条"的差额就仍然无解释 —— 那正是本缺陷的原始形态。
        scan_parts.append("隐藏 %d 条罕见类型(课程/路径/专题等,见 otherSkipped;"
                          "需显式打开才返回)" % other_skipped)
    if not manifest:
        scan_parts.append("部分路失败,召回不完整" if route_errors else "无匹配")

    # ⚠️ **顶层字段照 `topKeys` 声明拼**(ADR-0016 决策 8 / B4):
    # 此前 `topKeys` 在生产路径**零调用**(实测 `rg` 仅剩定义与导出),与 CONTEXT.md
    # 的纪律直接冲突:**「声明必须有消费者,否则'单一来源'是假的」**。
    # 现在声明是渲染闸门:从声明里删一个键,真实输出就跟着少一个(有回归钉子)。
    payload = {
        "ok": True,
        "keywords": list(keywords) if keywords else None,
        "queries": [r["terms"] for r in route_list],
        "routesPlanned": planned,
        # 本次**实际生效**的产品过滤:整数=产品线 id,0=不过滤。
        # 这是调用方唯一可执行的产品线判据(与 --product 同值域,可直接比对):
        # **恒等于调用方传入的值**(不传即声明默认)——2026-09-27 起内核不再做任何
        # 字面推导(决策 D14),问句里的「苍穹」二字不再改写它。
        # ⚠️ v6.6 起**不再出现 `null`**(决策 3 三态收两态):`None` 与"不传"同义,
        # 都在 `_public.search` 归一到声明默认值;唯一特殊值是显式 `0`(不过滤)。
        "effectiveProductId": product_id,
        "results": manifest,
        # 被隐藏掉的 other 档条数(0 = 没跳过或开关已开)。见上方通报段。
        "otherSkipped": other_skipped,
        "routeErrors": route_errors,
        # ADR-0016 决策 4:丢了几条词。0 表示没丢。
        "keywordsDropped": dropped,
        "scanNote": ";".join(scan_parts),
        # ADR-0016 决策 7:声明(cfg)是否真的读到。false 时链接政策已回落
        # "全部不给链接" → 所有 url 是 null,调用方必须能分辨"没链接"与"没读到声明"。
        "contractCfgLoaded": contract_loaded(),
    }
    # ⚠️ 票 06:完整 payload 原样上送,只在公开 seam(`_public.search` 注入 stats
    # 之后)投影一次。投影前移到这里会让 stats 绕过声明闸门,且同一字段投影两遍。
    return payload


def project_top(payload):
    """按 `topKeys` 声明投影顶层字段(声明的**唯一消费者**,票 06)。

    调用点只有一处:`_public.search` 注入 `stats` 之后。此前 `_search_manifest`
    返回前也投影一次,那是同一字段投两遍,且让 stats 绕过闸门。
    声明里没有的键**一律不出现在最终返回体**——这就是"删声明即删输出"的机制。
    """
    return {k: payload[k] for k in top_keys() if k in payload}
