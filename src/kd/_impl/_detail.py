#!/usr/bin/env python3
"""kd._impl._detail —— 按 kind 读全文(知识 / 问答 / 文章)。

三个 kind 的取数与展开逻辑各自独立,但**分发点只应有一处**(`_detail`),
调用方(read)无需知道分发表存在。

⚠️ 问答这一档的对外 kind 是 **`question`**(决策 D5,2026-09-27),不是上游协议里的
`answer`。上游 `/api/questions/{帖子号}` 按**帖子**返回(问题正文 + 采纳答案 +
全部回答列表),故 kind 名与"帖子级"这一事实对齐;上游原始值 `answer` 只在
`_upstream._norm_item` 一处被翻译,本模块不出现它。
"""
from . import _net
from ._config import (ENTITY_KINDS, VIP, _burst, log,
                      max_detail_knowledge, read_keys, read_truncated_values)
from ._concurrent import _raise_min, run_ordered
# 上游故障只按 _net.UPSTREAM_FAILURES 整类判定,不按具体异常类型分支;
# 不在本模块重导 UpstreamError(分类宽度单一来源在 _net)。
from ._errors import InternalError
# ⚠️ 链接构造与政策闸门**合在一处**走 `link_for_item`(2026-10-01,K1):
# 原先此处写 `apply_link_policy(kind, _URL_OF[kind] % id)` —— 闸门与模板各来一处,
# 且问答的回答号在这里另按 `bestAnswer[0]` 推导(与清单侧分叉)。`_URL_OF` 已不在
# 本模块 import:留着它就是第三处拼 url 的入口。
from ._links import link_for_item
from ._text import _is_true, html2text

# ⚠️ **深读侧的全部网络调用必须经 `_net._get_json` 属性访问**(2026-09-29 出口统一)。
# 原先写 `from ._net import _get_json` 是 import 期快照 —— 替换 `_net._get_json`
# 拦不住本模块的 5 个调用点,于是"离线组真的不联网"这条承诺是**概率性的**:
# 有网就真发、没网就静默吞(实测抓到 1 次真实上游请求而 48/48 仍全绿)。
# 这是本仓"声明必须有消费者,否则'单一来源'是假的"那条纪律的又一例 ——
# `_upstream` 的 docstring 声称自己是"全内核唯一出口",而本模块的调用完全不经过它。


def _knowledge_article(kid, rate=None):
    d = _net._get_json(VIP + "/knowledgeapi/knowledge/" + str(kid), rate)
    return {"ok": True, "id": str(kid), "type": "knowledge", "title": d.get("title"),
            "contentText": html2text(d.get("content")),
            "url": link_for_item("knowledge", kid),
            "products": [p.get("name") for p in (d.get("products") or [])][:3],
            "updatedAt": d.get("updatedAt")}


def _answer_brief(a):
    """单条回答的摘要形态(含追问链)。"""
    disc = []
    for e in (a.get("appendQuestionsAndAnswers") or []):
        if isinstance(e, dict):
            t = html2text(e.get("content") or e.get("plainTextContent") or "")
            if t:
                disc.append({"creator": (e.get("creator") or {}).get("name")
                             if isinstance(e.get("creator"), dict) else None,
                             "contentText": t})
    return {"id": str(a.get("id") or ""),
            "contentText": html2text(a.get("description") or a.get("summary") or a.get("content") or ""),
            "adopted": _is_true(a.get("isAdopt")),
            "usefuls": a.get("usefuls"), "comments": a.get("comments"),
            "creator": (a.get("creator") or {}).get("name"),
            "createdAt": a.get("createdAt"),
            "discussion": disc or None}


def _q_products(d):
    mod = d.get("module") or d.get("domain") or {}
    pn = mod.get("pathName")
    return pn.split("/") if pn else []


def _question_detail(qid, rate=None):
    """问答帖全文:问题正文 + 最佳答案 + 回答列表(可展开详情)。

    入参 `qid` 是**帖子号**——上游 `/api/questions/{id}` 只认帖子号。

    ⚠️ `type` 回填的是对外 kind `question`(决策 D5);上游协议里的 `answer` 不在
    这里的对外字段中出现。清单条目的 `id` 就是帖子号,故 `read(kind="question", id)`
    直接可读,不存在"该传哪个 id"的问题(双 id 空间已随 D6 消失)。

    ⚠️ **`truncated` 为字符串枚举**(ADR-0016 决策 7,v6.6)。原实现是布尔 `true`,
    把两种成因压成同一个值:

      | 值 | 含义 | LLM 该做什么 |
      |---|---|---|
      | `"answer_limit"` | 帖子太长没读完(**逐条详情只展开前 N 条**;翻页已无上限,2026-09-29) | 接受现状,在答案里声明 |
      | `"upstream_error"` | 上游报错 | **重试** |

    为什么必须分开:`truncated` 是召回置信度判定(ADR-0010)的输入之一。把
    "上游坏了"与"资料就这么多"压成同一个值,会让判定**在最该保守的时候给出乐观
    结论**——上游故障时调用方会以为"这帖只有这些答案"。

    ⚠️ 原 `budget` 形参与 `_BudgetExhausted` 分支已删(v6.6):预算机制整套删除。
    同时规格已确认 `page_limit` 与 `budget` 两档**不存在**——清单侧不再截断
    (跨页扫描删除 + 预算删除),截断只可能发生在问答深读的这一处。
    """
    d = _net._get_json(VIP + "/api/questions/" + str(qid), rate)
    # ⚠️ **深度只读声明**(票 06):它来自 `limits.maxDetail` 单一来源,
    # 生产路径固定。测试要构造截断场景靠 fake 响应(给更多回答),
    # 不再靠往私有函数里注入旋钮。
    max_detail = max_detail_knowledge()
    # ⚠️ `truncated` 的**两个枚举值从声明取**(2026-10-01,D12):此前 `"answer_limit"`
    # / `"upstream_error"` 各在下面的分支里写一遍字面量,而枚举的语义表只在 docstring
    # 与 ANSWER-SPEC 里 —— 改枚举值要同时改四处,没人盯得住。现在声明是单一来源,
    # 消费者是本函数(有回归钉子:改声明里的值 → 真实输出的 `truncated` 跟着变)。
    # ⚠️ 必须在**函数开头**取(而不是在那两个分支里就地取):下面 `except` 块也要用它,
    # 就地取会把取值点放进 `try` 内,异常路径取不到。
    tvals = read_truncated_values()
    # ⚠️ **问答的 url 是长形式**(2026-09-29 改判):`/questions/<帖子号>/answers/<回答号>`。
    # 回答号**不再取自 `d["bestAnswer"][0]["id"]` 这个单点**(2026-10-01,K1):
    # 原先无采纳帖时该取法给不出链接,而清单侧同一帖会回落到上游首条 ——
    # 实测复现:同帖两条都未被采纳的回答,`search` 给 `…/answers/A1`、`read` 给 `None`。
    # 现在两侧共用 `_links.compose_url` 的**同一套回落链**(采纳优先 → 上游首条),
    # 候选集在下面 `answers` 建好后一并交给它(见函数末尾的赋值与注释)。
    # ⚠️ `d["answers"]` 是回答**条数**(整数),**不是**数组,不可当数组遍历;
    # 回答列表另有端点(`/api/questions/<qid>/answers`)。
    # ⚠️ 无论如何**不得回落短形式**(`/question/<qid>` 恒死、复数无 aid 段亦死)。
    best = d.get("bestAnswer")
    best_t = best[0] if (isinstance(best, list) and best and isinstance(best[0], dict)) else None
    out = {"ok": True, "id": str(qid), "type": "question", "title": d.get("title"),
           "contentText": html2text(d.get("description")),
           # ⚠️ **占位**:真值在函数末尾赋(那时 `answers` 才建好,才能把回答列表
           # 一起交给 `_links` 选回答号)。保留这行只为**键序不变** —— `url` 必须
           # 仍排在 `contentText` 与 `isSolved` 之间,不许因为"赋值挪后"而漂到末尾。
           "url": None,
           "isSolved": d.get("isSolved"), "answersCount": d.get("answers"),
           "views": d.get("views"), "rewardCoins": d.get("rewardCoins"),
           "products": _q_products(d),
           "createdAt": d.get("createdAt"), "updatedAt": d.get("updatedAt")}
    if best_t is not None:
        out["bestAnswer"] = _answer_brief(best_t)
    # 回答展开(翻页+逐条详情)是深读里最贵的请求。截断**必须显式标记**并给出
    # "已取/总数"两个数字——截断而不标记等于把"资料不完整"伪装成"资料就是这样"。
    # 两类成因分开记(见 docstring 的枚举表)。
    truncated = None
    answers, total_pages = [], None
    # ⚠️ 在 `try` **外**初始化:外层的 `except` 要用它报"失败规模",
    # 而它由翻页块内的页级 catch 填充(作用域必须覆盖两处)。
    failed_pages = {}
    try:
        # ---- 翻页:先取第 1 页,再决定还剩几页(ADR-0017 决策 4) ----
        # ⚠️ 不能"把页号全并发出去":`totalPages` 只有第 1 页的响应里才有。
        # 故顺序是**先决后并**:首页单独取,据此算出页号集合,其余页并发取。
        # ⚠️ **翻页上限已删除**(2026-09-29,工单 #30):原 `max_answer_pages=3`
        # 实测**永不可触发**(10 个问答帖全 `totalPages=1`;25 条帖子回答数中位 2、
        # 90 分位 4、最大 5;要触发需单帖 >60 回答,0 条)。留着是"画上去的旋钮"。
        # 现在**有多少页取多少页**,截断只可能来自 `max_detail`(逐条详情展开)。
        first = _net._get_json(VIP + "/api/questions/%s/answers?page=1&pageSize=20"
                               % qid, rate)
        pages = [_answer_brief(a) for a in (first.get("content") or [])]
        # 不变量：首页与 answers 绑定同一列表对象，成功页就地 extend，
        # 异常路径也能保住已取回的首页（ADR-0020 决策 1）。
        answers = pages
        total_pages = first.get("totalPages") or 1
        if total_pages > 1:
            # 并发上界取声明 burst（与单次最大在飞请求数对齐，不自造第二个限速器）。
            # 口径：只把 _net.UPSTREAM_FAILURES 当局部失败收集；程序缺陷按最小键穿透。
            # 翻页执行走 _concurrent:按页号归位、逐页失败收集、最小页号重抛。
            # 首页已单独取并绑定 answers;这里只并发剩余页,成功页就地 extend。
            workers = max(1, min(total_pages - 1, _burst()))
            tasks = {p: (lambda p=p: _net._get_json(
                VIP + "/api/questions/%s/answers?page=%d&pageSize=20" % (qid, p), rate))
                for p in range(2, total_pages + 1)}
            ordered, failed_pages = run_ordered(
                tasks, max_workers=workers, expected=_net.UPSTREAM_FAILURES)
            # 就地 extend 到 pages(与 answers 同一对象),按页号 sorted 归位,
            # 不让完成先后决定回答顺序。
            for p in sorted(ordered):
                pages.extend([_answer_brief(a) for a in (ordered[p].get("content") or [])])
            if failed_pages:
                log("UPSTREAM_ERR:", "route=question_detail qid=%s failedPages=%s"
                    % (qid, sorted(failed_pages)))
                _raise_min(failed_pages)
        # total_pages 与 answers 的就地绑定是当前不变量;下面不再重新赋值。
        answers.sort(key=lambda a: (not a["adopted"]))
        # 详情补全只覆盖前 N 条,其余仍是列表摘要 —— 这是**唯一**剩下的截断来源。
        if len(answers) > max(max_detail, 0):
            # ⚠️ 枚举值取自声明(2026-10-01,D12),见函数开头的 `tvals`。
            truncated = tvals["answerLimit"]
        # 逐条详情执行走 _concurrent:按下标归位、逐项失败收集、最小下标重抛。
        # 已知边界:truncated 是单值枚举,详情失败时外层会置 upstream_error,
        # 覆盖先前的 answer_limit;这是既有契约,本轮不改。
        targets = answers[:max(max_detail, 0)]
        if targets:
            det_workers = max(1, min(len(targets), _burst()))
            tasks = {i: (lambda a=a: _net._get_json(
                VIP + "/api/answers/" + a["id"], rate)) for i, a in enumerate(targets)}
            dets, det_failed = run_ordered(
                tasks, max_workers=det_workers, expected=_net.UPSTREAM_FAILURES)
            for i in sorted(dets):
                a = targets[i]         # 列表里同一个对象,就地写回
                det = _answer_brief(dets[i])
                if len(det.get("contentText") or "") > len(a.get("contentText") or ""):
                    a["contentText"] = det["contentText"]
                if det.get("discussion"):
                    a["discussion"] = det["discussion"]
            if det_failed:
                _raise_min(det_failed)
    except _net.UPSTREAM_FAILURES as e:
        # ③ 上游故障:与"资料就这么多"是两件事——调用方该重试,不该接受现状。
        # ⚠️ **本 catch 覆盖"上游故障"整类,不只是 `UpstreamError`**(2026-09-29,
        # code review High-1 收口)。原先只 catch `UpstreamError`,于是:
        #   * `URLError` / `socket.timeout`(真实网络抖动、20s 超时)
        #   * `json.JSONDecodeError`(上游返回非 JSON:网关错误页、截断 body)
        # 这两种**真实观测到**的形态会一路穿透到 `cli._guard` → `internal_error`,
        # **把已取回的回答整包丢弃**(实测 8 条 → 0 条),且连 `UPSTREAM_ERR`
        # 日志都没有 —— 比"首页被丢"更差,因为调用方拿到的是"内部错误",
        # 会去查 bug 而不是重试。
        # 现已与检索侧(`_manifest._search_manifest` 的路由级 catch)同口径:凡属上游故障,一律
        # 置 `upstream_error` 并把**已取回的页交出去**(见 `pages` 的绑定说明)。
        # 程序缺陷(AttributeError/TypeError 等)**刻意不在**本元组里,仍会响亮穿透。
        code = getattr(e, "code", None)
        # ⚠️ **日志带上"失败规模"与失败页号**(2026-09-29,code review M-1):
        # 原先无论 1 页失败还是 5 页全失败,日志都只有一行、形态完全相同 ——
        # 排查者看不出这次是"抖了一下"还是"基本没取到"。
        # 页号列表取自 `failed_pages`(按页号,**与线程调度无关**)。
        # ⚠️ 这**只改善日志**,对外返回体**未变** —— 让调用方也能分辨失败规模
        # 需要新增契约字段(`failedPages` 之类),属契约演进,本轮刻意不做。
        log("UPSTREAM_ERR:", "route=question_detail qid=%s code=%s failedPages=%s msg=%s"
            % (qid, code, sorted(failed_pages) or "n/a",
               str(getattr(e, "message", "") or e)[:200]))
        # ⚠️ 原此处 `total_pages = None` 是**死写**(后面无读点),已删(工单 #30/H4)。
        # ⚠️ 枚举值取自声明(2026-10-01,D12):调用方靠它区分"该重试"与"接受现状"。
        truncated = tvals["upstreamError"]
    if truncated:
        out["truncated"] = truncated
    out["answersTaken"] = len(answers)
    out["answersTotal"] = d.get("answers")
    out["answers"] = answers
    # ---- 问答帖的 url:与**清单侧同一套规则**(2026-10-01,K1) ----
    #
    # ⚠️ **必须在这里定,不能在 `out` 里定**:回答列表(`answers`)要先建好,
    # 回答号要在**候选集**上才能选 —— 原先在 `out` 里按 `bestAnswer[0]` 单点取法,
    # 于是无采纳帖给不出链接,与清单侧分叉。
    #
    # 候选集 = 采纳答案(`bestAnswer`,标为已采纳)+ 回答列表的 `(id, adopted)`。
    # `_pick_answer_id` 的规则:采纳优先 → 否则上游首条 → 否则 None。
    #
    # ⚠️ **两侧必然同号的理由**(别以为还是两套规则):上面 `answers` 已做过
    # `answers.sort(key=lambda a: (not a["adopted"]))` —— 即"采纳在前、其余保持
    # 上游顺序",与 `_pick_answer_id` 的语义**相同**。故对同一构造,清单侧
    # (`_manifest_merge` 的 `ns`,上游返回顺序)与 read 侧选出的是同一个回答号。
    #
    # ⚠️ **残留边界(如实记,不假装已消除)**:若上游搜索**压根没召回该帖的采纳回答**,
    # 清单只知道"这帖有采纳答案"(`adopted` 为真)却不知道是哪条 → 只回落到首条;
    # 而 read 拿得到 `bestAnswer` → 两侧仍可能不同。这是**信息可见性**的差
    # (上游那一轮没把采纳回答返给我们),**不是规则的分叉** —— 规则只有一套。
    # 处理方式与顶层 `total` 那次相同 —— **写清,不假装**(那个字段本身已于 v6.9 删除;
    # 留下的是当时那条处置原则,不是字段)。
    if best_t is not None:
        cand = [(str(best_t.get("id") or ""), True)]
    else:
        cand = []
    cand += [(a.get("id"), a.get("adopted")) for a in (out.get("answers") or [])]
    out["url"] = link_for_item("question", out.get("id"), cand)
    return out


def _article_detail(aid, rate=None):
    d = _net._get_json(VIP + "/api/articles/" + str(aid), rate)
    classes = [c.get("name") for c in (d.get("classifies") or []) if c.get("name")]
    return {"ok": True, "id": str(aid), "type": "article", "title": d.get("title"),
            "contentText": html2text(d.get("content")),
            "url": link_for_item("article", aid),
            "products": classes[:3], "supports": d.get("supports"), "views": d.get("views"),
            "updatedAt": d.get("updatedAt")}


def _detail(kind, oid, rate=None):
    """详情统一入口(纯在线,不写穿落地缓存)。

    保留它是因为 3 个 kind 的分发点只应有一处;调用方无需知道分发表存在。
    URL 由各 kind 函数经 `_links` 统一构造(`link_for_item`),不在此处补齐。
    `refresh` 形参已删除(2026-09-18):内核恒在线,该形参在原实现里恒无效。

    ⚠️ **`other` 档是合法 kind 但没有全文端点**(2026-09-29,工单 #32):
    清单里会出现 `type: "other"` 的条目,故调用方照抄 `type` 传进来是**正确用法**,
    必须给出**准确**的提示(说清"这一档没有全文端点"),而不是让 `_detail` 直接
    `KeyError` —— 那会被 `cli._guard` 兜成 `internal_error`("这是 bug 而非用法问题"),
    把调用方引向"我是不是传错了"的方向,而它其实没传错。

    ⚠️ **这一档的"分类"由本处声明**(2026-09-29 收口):`code="unsupported_kind"` 是
    机器可判的唯一分类来源,CLI 只读 `InternalError.code`,**不再对文案做子串匹配**
    —— 原先 CLI 靠 `"没有它的全文端点" in str(e)` 判定,于是**改一个措辞就会让
    分类静默漂移**(exit 1 退化成 exit 2)。文案与分类现在完全解耦:上面这段 message
    可以随便重写,分类不变(有回归钉子)。
    """
    fn = _DETAIL_FN.get(kind)
    if fn is None:
        if kind in ENTITY_KINDS:
            # 合法 kind、但没有全文端点:这是**已知的能力边界**,不是调用方错误。
            raise InternalError(
                "kind=%r 是合法类型,但内核**没有它的全文端点**:这一档收容的是"
                "上游罕见实体(课程/学习路径/专题/直播等),各类型的详情端点形状不一"
                "(部分无端点、个别 url 在第三方域),故未接入 read。"
                "清单条目本身已给出 title 与 upstreamType,可据此自行判断。" % (kind,),
                code="unsupported_kind")
        raise InternalError("bad kind: %s(%s)" % (kind, "|".join(_DETAIL_KINDS)))
    # 票 06:完整 payload 原样上送,只在公开 seam(`_public.read` 注入 stats
    # 之后)投影一次。这里投影会让 stats 绕过声明闸门,且同一字段投影两遍。
    return fn(oid, rate=rate)


def project_read(payload, kind):
    """按 `read` 声明投影深读返回体(**声明的生产消费者**,2026-10-01,D12)。

    与 `_manifest.project_top`(search 侧)同构:声明里列了哪些键,最终返回体就只有
    哪些键 —— 「声明即闸门」这条机制在两个面上形状一致。

    ⚠️ **为什么要投影**:此前 read 的键集只活在三个档函数手写的 dict 里
    (`_knowledge_article` / `_question_detail` / `_article_detail`),声明与代码之间
    没有任何约束关系 —— 从 `contract.json` 删一个键,真实输出不会有任何变化。
    收进声明段后,投影点是这条约束的**唯一执行者**(有回归钉子证明两个方向都会红)。

    ⚠️ **缺键就"不产出",绝不 `payload[k]`**(取值用 `k in allowed`):这是从 search
    侧 `stats` 那条负路径学来的教训 —— 用下标取值时"从声明删一个键"会直接 `KeyError`,
    把「删声明即删输出」退化成「删声明即崩溃」。声明缺一个键是**允许的配置状态**,
    它的正确后果是"这个字段不出现",不是"整个 read 炸掉"。

    ⚠️ **键序:按返回体自身顺序过滤,不按声明顺序拼接**(与 `project_top` 的写法不同,
    这是刻意的):read 三档里公共键被**专属键插开** —— question 档的真实顺序是
    `… rewardCoins, products, createdAt, updatedAt …`(`products` 是从公共段来的),
    按"公共段拼专属段"产出会把 `products`/`updatedAt` 提前,键序当场变化。而键序是
    可观测的对外行为(CLI 输出的是有序 JSON),本段定位是「把既有事实收成单一来源」,
    **不是改契约**。故声明在这里管**键集**,键序仍由构造顺序承载。

    ⚠️ **调用点是公开 seam 一处**(票 06):`_public.read` 注入 `stats` 之后。
    此前 `_detail` 里也投影一次,那是同一字段投两遍,且让 stats 绕过闸门。
    """
    allowed = read_keys(kind)
    return {k: v for k, v in payload.items() if k in allowed}


_DETAIL_FN = {"knowledge": _knowledge_article, "question": _question_detail,
              "article": _article_detail}
# ⚠️ `_DETAIL_KINDS` 是**真的有全文端点**的那几档 —— 它决定 `read` 的 `--kind`
# 可选值(CLI choices)与分发表。`other` **刻意不在其中**(见 `_detail` 的论证)。
# ⚠️ 但 `read(kind="other")` 仍须能被**区分**出来 —— 故 `_detail` 里先查
# `ENTITY_KINDS` 再报错,而不是一律 `bad kind`。两处合起来才是完整语义:
#   `_DETAIL_KINDS` = 可读全集的档;`other` = 合法但不可读。
_DETAIL_KINDS = tuple(_DETAIL_FN)
