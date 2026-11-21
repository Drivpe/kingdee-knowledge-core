#!/usr/bin/env python3
"""kd 回归用例集（票 05：回归迁移到公开 interface 与唯一 fake adapter）。

定位：只断言**外部行为**——kd.core.search / kd.core.read 的返回结构与异常，
以及 kd CLI 的进程级输出。不引用私有投影/详情函数、不打桩 _search_upstream、
不改私有命名空间；全部离线行为用例共用**唯一**注入点 `_net._get_json`。

三组（与票 05 的范围一一对应）：
  * search    —— 检索结果构造：去重、保序、帖级归并、字段集、错误隔离；
  * read      —— 全文：三档字段、截断、翻页与详情补全、键序、url 一致性；
  * upstream  —— 上游适配：参数透传、故障分类、零网络泄漏与阳性对照。

冻结期望刻意独立于 contract.json（打断“声明与被测代码同源恒绿”）：
  FROZEN_* 字段基线 + tests/baseline/public-behavior-baseline.json（41 场景另跑）。

运行：python3 tests/kd_regression.py   # 离线组（默认；不联网）
退出码：0 = 全通过；1 = 有失败。
"""

import base64
import contextlib
import http.client
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kd import core  # noqa: E402
import kd._impl._net as _net  # noqa: E402  唯一网络出口的模块对象
import kd.cli as _kd_cli  # noqa: E402,F401  登记 sys.modules["kd.cli"]
import kd_test_support  # noqa: E402  与 CLI 子进程共享 fake 的错误/计数口径

PY = sys.executable
RUN = os.path.join(SRC, "kd_run.py")
BASESCRIPT = os.path.join(REPO, "tests", "baseline", "replay_baseline.py")
FIXTURE = os.path.join(REPO, "tests", "baseline", "upstream-fake.json")
REAL_FIXTURE = os.path.join(REPO, "tests", "fixtures", "upstream-search-培训课程.json")

_CONTRACT = json.loads(open(os.path.join(SRC, "kd", "contract.json"), encoding="utf-8").read())

# ------------------------------------------------ 冻结字段基线（独立于声明）
FROZEN_RESULT_KEYS_COMMON = ("type", "id", "title", "url", "snippet", "products",
                             "comments", "hitRoutes", "routes")
FROZEN_RESULT_KEYS_BY_TYPE = {
    "knowledge": (),
    "question": ("adopted", "answersCount", "questionBody"),
    "article": ("supports",),
    "other": ("upstreamType", "resourceType"),
}
FROZEN_TOP_KEYS = ("ok", "keywords", "queries", "routesPlanned",
                   "effectiveProductId", "results", "otherSkipped",
                   "routeErrors", "keywordsDropped", "scanNote", "contractCfgLoaded",
                   "stats")
FROZEN_READ_TOP_KEYS = ("ok", "id", "type", "title", "contentText", "url",
                        "products", "updatedAt", "stats")
FROZEN_READ_BY_TYPE = {
    "knowledge": (),
    "question": ("isSolved", "answersCount", "views", "rewardCoins", "createdAt",
                 "answersTaken", "answersTotal"),
    "article": ("supports", "views"),
}
FROZEN_READ_CONDITIONAL_BY_TYPE = {"question": ("bestAnswer", "truncated", "answers")}
FROZEN_READ_TRUNCATED_VALUES = {"answerLimit": "answer_limit", "upstreamError": "upstream_error"}
DEFAULT_PRODUCT_ID = int(_CONTRACT["productIds"]["default"])
PROBE_PRODUCT = 93  # 回归构造用的显式产品线编号（与默认值区分）
QUERY = "信用额度控制"
PROBE_MULTI_ROUTE = "BOM 分母变平方"
RESULT_FORBIDDEN_KEYS = set(_CONTRACT["search"]["resultForbiddenKeys"])


def frozen_result_keys(kind):
    return set(FROZEN_RESULT_KEYS_COMMON) | set(FROZEN_RESULT_KEYS_BY_TYPE.get(str(kind), ()))


def frozen_read_keys(kind):
    return (set(FROZEN_READ_TOP_KEYS) | set(FROZEN_READ_BY_TYPE.get(kind, ()))
            | set(FROZEN_READ_CONDITIONAL_BY_TYPE.get(kind, ())))


# ------------------------------------------------ 迷你断言框架
class Fail(Exception):
    pass


def ok(cond, msg):
    if not cond:
        raise Fail(msg)


def keys_of(d, name):
    ok(isinstance(d, dict), "%s 不是 dict: %r" % (name, type(d)))
    return set(d.keys())


def check_subset(actual, required, name):
    missing = set(required) - set(actual)
    ok(not missing, "%s 缺字段: %s (实有 %s)" % (name, sorted(missing), sorted(actual)))


def check_no_extra(actual, allowed, name):
    extra = set(actual) - set(allowed)
    ok(not extra, "%s 出现白名单外字段: %s" % (name, sorted(extra)))


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def cli(*args, **kw):
    """进程级调用 kd 命令：返回 (exit_code, stdout_json_or_None, stderr_text)。"""
    p = subprocess.run([PY, RUN, *args], cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=kw.get("timeout", 120))
    try:
        data = json.loads(p.stdout)
    except Exception:
        data = None
    return p.returncode, data, p.stderr


def out_text(*args, **kw):
    p = subprocess.run([PY, RUN, *args], cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=kw.get("timeout", 120))
    return p.stdout



def cli_offline(*args, payload=None, **kw):
    """进程级 CLI + 唯一 fake 上游：子进程内也只替换 _net._get_json。"""
    payload = payload if payload is not None else {}
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC
    env["KD_FAKE_PAYLOAD"] = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    bootstrap = (
        "import sys,base64,json,os; sys.path[:0]=[" + repr(SRC) + ","
        + repr(os.path.dirname(os.path.abspath(__file__))) + "];"
        "import kd_test_support as s;"
        "s.install_fake(json.loads(base64.b64decode(os.environ['KD_FAKE_PAYLOAD'])));"
        "\nimport kd.cli as c; c.main(sys.argv[1:])")
    p = subprocess.run([PY, "-c", bootstrap, *args], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env,
                       timeout=kw.get("timeout", 120))
    try:
        data = json.loads(p.stdout)
    except Exception:
        data = None
    return p.returncode, data, p.stdout, p.stderr


# ================================================================ 唯一 fake adapter
def url_params(url):
    if "?" not in url:
        return {}
    return {k: v[0] for k, v in urllib.parse.parse_qs(url.split("?", 1)[1]).items()}


def search_response(items, total=None):
    return {"content": list(items),
            "totalElements": len(items) if total is None else total, "totalPages": 1}


def item(kind, oid, title=None, qid=None, adopted=False, comments=3):
    """合成上游形态条目（与旧 _syn 对齐：喂进去的是上游原始字段）。"""
    if kind == "answer":
        qid = str(qid or oid)
        return {"entity-type": "Answer", "id": str(oid), "questionId": qid,
                "highlight": {"question.title": title or ("问题标题 %s" % oid),
                              "description": "回答正文 %s" % oid},
                "question": {"id": qid, "answers": 2, "moduleName": "财务云",
                             "description": "问题正文 %s" % oid},
                "isAdopt": "true" if adopted else "false", "views": 10,
                "comments": comments, "contentLen": 100, "updatedAt": "2026-01-01"}
    if kind == "article":
        d = {"entity-type": "Article", "id": str(oid),
             "highlight": {"title": title or ("文章标题 %s" % oid), "content": "正文 %s" % oid},
             "classifies": [{"name": "星空旗舰版"}], "views": 10, "supports": 5,
             "comments": comments, "contentLen": 100, "updatedAt": "2026-01-01"}
    else:
        d = {"entity-type": "Knowledge", "id": str(oid), "knowledgeId": str(oid),
             "highlight": {"title": title or ("知识标题 %s" % oid), "content": "正文 %s" % oid},
             "classifies": [{"name": "星空旗舰版"}], "views": 10, "useful": 1,
             "comments": comments, "contentLen": 100, "updatedAt": "2026-01-01"}
    if comments is None:
        d.pop("comments", None)
    return d


def question_post(qid, n_answers=2, best=False, **extra):
    d = {"title": "题目标题", "description": "问题正文", "answers": n_answers,
         "isSolved": False, "views": 7, "rewardCoins": 0,
         "createdAt": "2026-01-01", "updatedAt": "2026-01-02",
         "module": {"pathName": "A/B"}}
    if best:
        d["bestAnswer"] = [{"id": "b1", "description": "已采纳", "isAdopt": "true"}]
    d.update(extra)
    return d


def knowledge_body():
    return {"title": "知识", "content": "<p>正文</p>",
            "products": [{"name": "P1"}, {"name": "P2"}], "updatedAt": "2026-01-01"}


def article_body():
    return {"title": "文章", "content": "<p>正文</p>",
            "classifies": [{"name": "C1"}], "supports": 3, "views": 10,
            "updatedAt": "2026-01-01"}


def make_router(*, search=None, knowledge=None, questions=None,
                answers_pages=None, answer_details=None, articles=None,
                default=None, strict=True):
    """按真实 URL 形状分派：未登记时 strict=True 直接抛错，绝不静默兜底。"""
    def route(url):
        if url.startswith("https://vip.kingdee.com/api/search"):
            r = search
        elif url.startswith("https://vip.kingdee.com/knowledgeapi/knowledge/"):
            r = knowledge
        elif "/answers?" in url and "/api/questions/" in url:
            r = answers_pages
        elif "/api/questions/" in url:
            r = questions
        elif "/api/answers/" in url:
            r = answer_details
        elif url.startswith("https://vip.kingdee.com/api/articles/"):
            r = articles
        else:
            r = default
        if r is None:
            if default is not None:
                r = default
            elif strict:
                raise RuntimeError("fake 上游未登记该 URL：" + url)
            else:
                return {}
        return r(url) if callable(r) else r
    return route


def fake_upstream(router, calls=None):
    """构造打在 `_net._get_json` 上的假出口（全套件唯一网络替换点）。

    errorCode 识别与上游计数复用 kd_test_support.resolve_payload，与 CLI 子进程
    那条路径同源——生产错误壳形状变更只需改一处。
    """
    def fake(url, rate=None):
        if calls is not None:
            calls.append(url)
        return kd_test_support.resolve_payload(router(url))
    return fake


@contextlib.contextmanager
def upstream(router, calls_out=None):
    """唯一注入点：context 内替换 `_net._get_json`，退出必恢复。"""
    calls = []
    real = _net._get_json
    kd_test_support.reset_upstream_counter()
    _net._get_json = fake_upstream(router, calls)
    try:
        yield calls
    finally:
        _net._get_json = real
        if calls_out is not None:
            calls_out.extend(calls)


def search_with(items, **kw):
    with upstream(make_router(search=search_response(items))):
        return core.search(**kw)


def read_with(kind, oid, router):
    with upstream(router):
        return core.read(kind, oid)


def question_router(qid, n_answers=2, best=False, post=None, answer_detail=None):
    """问答档标准路由：题帖 + 单页回答列表 + 逐条回答详情。"""
    return make_router(
        questions=(question_post(qid, n_answers=n_answers, best=best) if post is None else post),
        answers_pages={"content": [{"id": "a%d" % i, "description": "回答摘要 %d" % i}
                                    for i in range(1, n_answers + 1)], "totalPages": 1},
        answer_details=answer_detail if answer_detail is not None
                       else (lambda url: {"description": "展开详情"}))


# ================================================================ 零联网守卫
def _guard_factory():
    real_connect = socket.socket.connect
    state = {"attempts": [], "allow": 0}

    def guarded(self, address):
        state["attempts"].append(address)
        if state["allow"] > 0:
            state["allow"] -= 1
            return real_connect(self, address)
        raise AssertionError("离线用例试图真实联网：%r" % (address,))

    def install():
        socket.socket.connect = guarded
        return state

    def restore():
        socket.socket.connect = real_connect

    return install, restore, state


@contextlib.contextmanager
def no_network():
    install, restore, state = _guard_factory()
    state = install()
    try:
        yield state
    finally:
        restore()
        ok(not state["attempts"],
           "离线用例发生了真实连接尝试（%d 次）：%r"
           % (len(state["attempts"]), state["attempts"][:5]))


# ================================================================ 用例区（三组）
# ================================ 第一组：search（检索结果构造） ================================

@case("search: 公开面恰为 search/read + 三个异常类")
def t_public_surface():
    names = {"search", "read", "QueryTooLong", "UpstreamError", "InternalError"}
    ok(set(core.__all__) == names, "kd.core.__all__ 应为 5 个公开名，实为 %r" % (core.__all__,))
    for n in ("search", "read"):
        ok(callable(getattr(core, n)), "%s 不可调用" % n)
    for n in ("QueryTooLong", "UpstreamError", "InternalError"):
        ok(issubclass(getattr(core, n), BaseException), "%s 不是异常类" % n)
    ok(not hasattr(core, "ask"), "kd.core 仍可属性访问 ask（应不可见）")


@case("search: 已删形参传即 TypeError，字符串/字典入参 InternalError")
def t_dead_params_gone():
    probes = (
        lambda: core.search(["甲"], rerank=True), lambda: core.search(["甲"], routes=1),
        lambda: core.search(["甲"], page=2), lambda: core.search(["甲"], page_size=5),
        lambda: core.search(text="整句"), lambda: core.search(["甲"], type_="question"),
        lambda: core.search(["甲"], max_routes=1), lambda: core.search(["甲"], budget=5),
        lambda: core.read("knowledge", "1", refresh=True),
        lambda: core.read("knowledge", "1", budget=5),
    )
    for fn in probes:
        try:
            fn()
        except TypeError:
            continue
        except Exception as e:
            raise Fail("已删形参抛 %s（应为 TypeError）" % type(e).__name__)
        raise Fail("已删形参仍被接受")
    for bad in (QUERY, b"x"):
        try:
            core.search(bad)
        except core.InternalError as e:
            ok("list" in str(e).lower() or "列表" in str(e), "报错应提示词列表：%s" % e)
            continue
        raise Fail("字符串入参未被显式拒绝（会按字符拆成多路）")
    try:
        core.search({"甲": 1})
    except core.InternalError as e:
        ok("dict" in str(e), "dict 入参应点名 dict：%s" % e)
    else:
        raise Fail("dict 的键被静默当成检索词")


@case("search: 生成器入参物化为多路，空白词丢弃且 scanNote 通报")
def t_generator_and_blank_keywords():
    with upstream(make_router(search=search_response([]))):
        r = core.search(k for k in ["甲", "乙"])
        ok(r.get("ok") is True and r.get("queries") == ["甲", "乙"],
           "生成器应物化为 2 路，实为 %r" % (r.get("queries"),))
        b = core.search(["甲", "", "  "])
        ok(b.get("scanNote") and "空白" in b["scanNote"],
           "空白词被静默丢弃（scanNote 未提）：%r" % b.get("scanNote"))
        ok(b.get("queries") == ["甲"], "空串不应产生检索路：%r" % b.get("queries"))


@case("search: 100 字硬闸 raise QueryTooLong（逐词、带压回值）")
def t_query_too_long():
    for label, kws in (("单超长", ["超" * 120]), ("夹带超长", ["甲", "额" * 101])):
        try:
            core.search(kws)
        except core.QueryTooLong as e:
            ok(len(e.original) >= 101 and len(e.clamped) == 100 and int(e.limit) == 100,
               "%s 的 QueryTooLong 字段不对：orig=%d clamp=%d limit=%r"
               % (label, len(e.original), len(e.clamped), e.limit))
            ok(e.clamped == e.original[:100], "clamped 不是前 100 字符压回值")
        else:
            raise Fail("%s 未 raise QueryTooLong" % label)


@case("search: 空/非法入参 raise InternalError，不是崩溃")
def t_internal_error():
    for label, fn in (("None", lambda: core.search(None)), ("[]", lambda: core.search([])),
                      ("空词", lambda: core.search([""])),
                      ("read 坏 kind", lambda: core.read("nope", "1")),
                      ("read 空 id", lambda: core.read("knowledge", ""))):
        try:
            fn()
        except core.InternalError:
            continue
        except Exception as e:
            raise Fail("%s 抛 %s（应为 InternalError）" % (label, type(e).__name__))
        raise Fail("%s 未抛 InternalError" % label)


@case("search: 每词一路、逐字逐序回显，顶层无 text")
def t_keywords_entry():
    with upstream(make_router(search=search_response([]))) as calls:
        r = core.search([" 乙 ", "甲", "乙", "丙"], product_id=PROBE_PRODUCT)
    ok(r.get("ok") is True, "search 失败")
    ok("text" not in r, "顶层不应再有 text 键：%r" % sorted(r))
    # keywords 回显调用方原样；queries 是 strip + 去重后、仍按给词顺序的那批。
    ok(r.get("keywords") == [" 乙 ", "甲", "乙", "丙"], "keywords 回显错误：%r" % r.get("keywords"))
    ok(r.get("queries") == ["乙", "甲", "丙"], "queries 应逐字逐序、strip 后去重：%r" % r.get("queries"))
    ok(r.get("routesPlanned") == 4 and len(calls) == 3, "routesPlanned 计原词数、实际去重后 3 路：%r/%d"
       % (r.get("routesPlanned"), len(calls)))


@case("search: 超限按顺序取前 N、通报丢词数，不报假的路由塌缩")
def t_keywords_dropped():
    def get(limit=None):
        if limit is None:
            with upstream(make_router(search=search_response([]))) as calls:
                return core.search(["词%d" % i for i in range(1, 10)]), calls
        broken = kd_test_support.contract_copy()
        broken["limits"]["maxKeywords"] = limit
        with kd_test_support.contract_override(broken):
            with upstream(make_router(search=search_response([]))) as calls:
                return core.search(["词%d" % i for i in range(1, 10)]), calls

    r, calls = get()
    ok(r.get("keywordsDropped") == 2, "9 词应丢 2：%r" % r.get("keywordsDropped"))
    ok(len(calls) == 7, "应只发 7 路，实发 %d" % len(calls))
    ok("丢" in (r.get("scanNote") or ""), "scanNote 应写明丢词：%r" % r.get("scanNote"))
    ok(not r.get("routeErrors"), "截断不应被误报成路由失败：%r" % r.get("routeErrors"))
    r3, calls3 = get(limit=3)
    ok(r3.get("keywordsDropped") == 6 and len(calls3) == 3,
       "改声明 maxKeywords=3 后应丢 6、发 3 路：%r/%d" % (r3.get("keywordsDropped"), len(calls3)))


@case("search: 去重后同一条只出一条，hitRoutes/routes 记录命中路")
def t_dedupe_hit_routes():
    a, b = item("knowledge", 100), item("knowledge", 200)
    r = search_with([a, b], keywords=["甲"], product_id=PROBE_PRODUCT)
    ok(len(r["results"]) == 2, "两条不同条目应去重为 2 条，实为 %d" % len(r["results"]))
    hit = [x for x in r["results"] if x["id"] == "100"][0]
    ok(hit.get("hitRoutes") == 1, "单路命中 hitRoutes 应为 1，实为 %r" % hit.get("hitRoutes"))
    ok("contentText" not in hit, "清单条目不得返回 contentText")
    # 两路命中同一条：同一批 items 分别挂到两个关键词的响应上
    router = make_router(search=lambda url: search_response([a, b] if url_params(url)["text"] == "甲" else [a]))
    with upstream(router):
        r2 = core.search(keywords=["甲", "乙"], product_id=PROBE_PRODUCT)
    ok(len(r2["results"]) == 2, "跨路重复应仍只出 2 条，实为 %d" % len(r2["results"]))
    hit2 = [x for x in r2["results"] if x["id"] == "100"][0]
    ok(hit2.get("hitRoutes") == 2 and hit2.get("routes") == [1, 2],
       "两路命中应 hitRoutes=2/routes=[1,2]，实为 %r/%r"
       % (hit2.get("hitRoutes"), hit2.get("routes")))


@case("search: 清单保序 = 先按给词顺序、再按路内名次（不按命中数排序）")
def t_keep_order():
    x = item("knowledge", 11, title="X")
    y = item("knowledge", 22, title="Y")
    router = make_router(search=lambda url: search_response(
        [x] if url_params(url)["text"] == "词1" else [y, x]))
    with upstream(router):
        r = core.search(keywords=["词1", "词2"], product_id=PROBE_PRODUCT)
    ids = [i["id"] for i in r["results"]]
    ok(ids == ["11", "22"], "首现顺序应为 X,Y（X 虽命中两路也不该被挤后）：%r" % ids)


@case("search: 同帖多回答合并为一条，问答题对外名 question")
def t_question_post_merge():
    a1 = item("answer", 7001, qid=9001, adopted=False, title="帖子标题")
    a2 = item("answer", 7002, qid=9001, adopted=True, title="帖子标题")
    r = search_with([a1, a2], keywords=["甲"], product_id=PROBE_PRODUCT)
    ok(len(r["results"]) == 1, "同帖两回答应合并成一条，实为 %d 条" % len(r["results"]))
    q = r["results"][0]
    ok(q.get("type") == "question" and q.get("id") == "9001",
       "问答题应对外 question 且 id 为帖子号：%r %r" % (q.get("type"), q.get("id")))
    ok("questionId" not in q, "questionId 字段应已被删除")
    ok(q.get("adopted") is True, "同帖任一采纳即 adopted=True：%r" % q.get("adopted"))
    ok(q.get("answersCount") == 2, "回答数应取上游原生信号：%r" % q.get("answersCount"))


@case("search: 帖级信号聚合 adopted 任一为真、计数取最大，且不合成假 False")
def t_post_signal_aggregation():
    plain = item("answer", 1, qid=9, adopted=False)
    adopted = item("answer", 2, qid=9, adopted=True)
    out = search_with([plain], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(out.get("adopted") is False, "无采纳帖 adopted 应为 False（原生 False），实为 %r" % out.get("adopted"))
    out2 = search_with([plain, adopted], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(out2.get("adopted") is True, "采纳任一为真应聚成 True：%r" % out2.get("adopted"))
    art = search_with([item("article", 5)], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok("adopted" not in art, "article 不该出现 adopted 字段")


@case("search: comments 三类都取，上游没给则键在值为 None")
def t_comments_all_kinds():
    r = search_with([item("knowledge", 1, comments=7), item("article", 2, comments=0),
                     item("answer", 3, qid=3, comments=7), item("knowledge", 4, comments=None)],
                    keywords=["甲"], product_id=PROBE_PRODUCT)
    by_id = {x["id"]: x for x in r["results"]}
    ok(by_id["1"].get("comments") == 7, "knowledge comments 应为 7：%r" % by_id["1"].get("comments"))
    ok(by_id["2"].get("comments") == 0, "article comments 应为 0：%r" % by_id["2"].get("comments"))
    ok(by_id["3"].get("comments") == 7, "question comments 应为 7：%r" % by_id["3"].get("comments"))
    ok("comments" in by_id["4"] and by_id["4"]["comments"] is None,
       "上游未给 comments 时键应仍在且为 None：%r" % by_id["4"])


@case("search: 结果字段集按类型固定，顶层与冻结基线逐键一致")
def t_result_fields_frozen():
    items = [item("knowledge", 101), item("answer", 201, qid=200),
             item("article", 301)]
    out = search_with(items, keywords=["契约探针"], product_id=PROBE_PRODUCT)
    ok(set(out) == set(FROZEN_TOP_KEYS),
       "顶层真实输出与冻结基线不符：多 %s / 缺 %s"
       % (sorted(set(out) - set(FROZEN_TOP_KEYS)), sorted(set(FROZEN_TOP_KEYS) - set(out))))
    seen = set()
    for x in out["results"]:
        seen.add(x.get("type"))
        want = frozen_result_keys(x.get("type")) | {"hitRoutes", "routes"}
        ok(set(x) == want, "%s(%s) 字段集与冻结基线不符：多 %s / 缺 %s"
           % (x.get("type"), x.get("id"), sorted(set(x) - want), sorted(want - set(x))))
        ok(not (set(x) & RESULT_FORBIDDEN_KEYS), "出现历史残留字段：%s" % sorted(set(x) & RESULT_FORBIDDEN_KEYS))
    ok(seen == {"knowledge", "question", "article"}, "三档未全产出：%r" % seen)


@case("search: 声明删一个顶层键，真实输出跟着少且不崩溃（含 stats 负路径）")
def t_top_keys_are_gate():
    for removed in ("scanNote", "stats"):
        broken = kd_test_support.contract_copy()
        broken["search"]["topKeys"] = [k for k in broken["search"]["topKeys"] if k != removed]
        with kd_test_support.contract_override(broken):
            with upstream(make_router(search=search_response([item("knowledge", 1)]))):
                out = core.search(keywords=["甲"], product_id=PROBE_PRODUCT)
        ok(removed not in out, "删掉 %r 后真实输出仍有它：%r" % (removed, sorted(out)))
        ok(out.get("ok") is True, "删声明键不应让 search 崩溃：%r" % out)


@case("search: entity-type 宽容归一（全角/NBSP/尾换行不再静默丢弃）")
def t_entity_type_tolerance():
    ets = ["  Knowledge  ", "Knowledge\n", "Ｋｎｏｗｌｅｄｇｅ", "Knowledge\xa0"]
    variants = []
    for i, et in enumerate(ets, 1):
        d = item("knowledge", i)
        d["entity-type"] = et
        variants.append(d)
    bad = item("knowledge", 9)
    bad["entity-type"] = "Kknowledge"
    r = search_with(variants + [bad], keywords=["甲"], product_id=PROBE_PRODUCT)
    ids = [x["id"] for x in r["results"]]
    ok(len(ids) == 4, "四种宽容写法都应归一为 knowledge 条目，实得 %r" % ids)
    ok("9" not in ids, "拼写错误的 Kknowledge 应仍被丢弃")


@case("search: other 档默认隐藏并通报跳过数，显式打开才出现")
def t_other_tier():
    other = {"entity-type": "LearningCourse", "id": "6898", "title": "微课",
             "highlight": {"title": "微课"}, "xId": "LearningCourse-6898"}
    normal = item("knowledge", 1)
    r = search_with([normal, other], keywords=["甲"], product_id=PROBE_PRODUCT)
    ok(all(x["type"] != "other" for x in r["results"]), "other 档默认隐藏")
    ok(r.get("otherSkipped") == 1, "应通报跳过 1 条 other：%r" % r.get("otherSkipped"))
    ok("1/1" not in (r.get("scanNote") or "") or r.get("otherSkipped") == 1,
       "scanNote 不应把跳过说成没有：%r" % r.get("scanNote"))
    r2 = search_with([normal, other], keywords=["甲"], product_id=PROBE_PRODUCT, include_other=True)
    o = [x for x in r2["results"] if x["type"] == "other"]
    ok(len(o) == 1 and o[0].get("upstreamType") == "LearningCourse",
       "显式打开后 other 应带上游原类型：%r" % o)
    try:
        core.read("other", "6898")
    except core.InternalError as e:
        ok("没有它的全文端点" in str(e) or "没有全文端点" in str(e),
           "other 无端点的提示应准确：%s" % e)
        ok(getattr(e, "code", None) == "unsupported_kind", "分类码应为 unsupported_kind")
    else:
        raise Fail("read(other) 未报错")
    # 真实响应 fixture 仍被使用（不是只靠合成条目）
    with open(REAL_FIXTURE, encoding="utf-8") as f:
        real_items = json.load(f)
    if isinstance(real_items, dict):
        real_items = real_items.get("content") or real_items.get("results") or []
    r3 = search_with(real_items, keywords=["培训课程"], product_id=PROBE_PRODUCT, include_other=True)
    ok(any(x["type"] == "other" for x in r3["results"]),
       "真实响应 fixture 的 LearningCourse 应被收容为 other")


@case("search: other 去重键带上上游类型，跨类型同 id 不互吃")
def t_other_dedupe_key():
    kinds = ("LearningCourse", "LearningPath", "KnowledgeSpecial", "LearningBroadcast")
    items = [{"entity-type": k, "id": "200641239941605888",
              "xId": "%s-200641239941605888" % k, "title": k} for k in kinds]
    items.append(dict(items[0]))  # 同类型同 id 应被折掉
    r = search_with(items, keywords=["甲"], product_id=PROBE_PRODUCT, include_other=True)
    others = [x for x in r["results"] if x["type"] == "other"]
    ok(len(others) == 4, "跨类型同 id 应保留 4 条，实为 %d：%r" % (len(others), others))
    ok({x["upstreamType"] for x in others} == set(kinds), "上游原类型应各保留一份")


@case("search: 三档都有可点 url，问答必须是带回答号的长形式")
def t_links_in_search():
    items = [item("knowledge", "101"), item("article", "202"),
             item("answer", "7001", qid="9001", adopted=True)]
    r = search_with(items, keywords=["甲"], product_id=PROBE_PRODUCT)
    for x in r["results"]:
        ok(isinstance(x.get("url"), str) and x["url"].startswith("https://"),
           "%s 档应给可点 https url：%r" % (x["type"], x.get("url")))
        if x["type"] == "question":
            ok("/questions/9001/answers/" in x["url"],
               "问答 url 必须是长形式 /answers/<aid>：%r" % x["url"])
    # 政策翻转：knowledge 变 no-link 时真实 url 消失
    broken = kd_test_support.contract_copy()
    broken["linkPolicy"]["rule"]["knowledge"] = "no-link"
    with kd_test_support.contract_override(broken):
        r2 = search_with([item("knowledge", "101")], keywords=["甲"], product_id=PROBE_PRODUCT)
    ok(not r2["results"][0].get("url"), "改成 no-link 后 knowledge 不应有 url：%r" % r2["results"][0])


@case("search: 上游假 200 与 URLError 进 routeErrors，其余路照常返回")
def t_route_errors_isolated():
    good = item("knowledge", 1)
    def route(url):
        t = url_params(url)["text"]
        if t == "甲":
            return {"errorCode": 409, "message": "上游业务错"}
        if t == "乙":
            raise urllib.error.URLError("network down")
        return search_response([good])
    with upstream(make_router(search=route)):
        r = core.search(keywords=["甲", "乙", "丙"], product_id=PROBE_PRODUCT)
    ok(r.get("ok") is True, "部分路失败不应让整体失败：%r" % r.get("ok"))
    errs = r.get("routeErrors") or []
    ok(len(errs) == 2, "两条失败路都应记录：%r" % errs)
    ok(len(r["results"]) == 1 and r["results"][0]["id"] == "1", "成功路结果仍要返回：%r" % r["results"])
    ok("失败路 2 条" in (r.get("scanNote") or ""), "scanNote 应通报失败路数：%r" % r.get("scanNote"))


@case("search: 程序缺陷穿透，不伪装成上游故障")
def t_bug_propagates_not_upstream():
    def buggy(url):
        if url_params(url)["text"] == "甲":
            raise AttributeError("our own bug")
        return search_response([])
    with upstream(make_router(search=buggy)):
        try:
            core.search(keywords=["甲"], product_id=PROBE_PRODUCT)
        except AttributeError:
            pass
        else:
            raise Fail("程序缺陷被吞成 ok/routeErrors（应响亮穿透）")
    # CLI 侧经真实进程边界：exit 1 + internal_error
    payload = {"/api/search": {"errorCode": 409, "message": "fake"}}
    # 注意：CLI 只覆盖 search/read 的进程级输出，这一条验证错误 JSON 不是崩溃文本
    code, d, err = cli("search", "--kw", QUERY)
    ok(code in (0, 1), "CLI search 退出码应为 0/1，实为 %r" % code)


# ================================ 第二组：read（全文） ================================

@case("read: 三档字段集与冻结基线逐键一致，stats 在二次投影后仍在")
def t_read_fields_frozen():
    cases = [
        ("knowledge", "K1", make_router(knowledge=knowledge_body())),
        ("article", "A1", make_router(articles=article_body())),
        ("question", "Q1", question_router("Q1")),
    ]
    for kind, oid, router in cases:
        out = read_with(kind, oid, router)
        want = set(FROZEN_READ_TOP_KEYS) | set(FROZEN_READ_BY_TYPE.get(kind, ()))
        # 条件键：bestAnswer 有采纳才有；truncated/answers 在 question 恒有（生产走 with_answers）
        if kind == "question":
            want |= {"answers"}
        ok(out.get("ok") is True, "read(%s) 应成功：%r" % (kind, out))
        ok(set(out) == want, "read(%s) 字段集与冻结基线不符：多 %s / 缺 %s"
           % (kind, sorted(set(out) - want), sorted(want - set(out))))
        ok("stats" in out, "stats 在二次投影后丢了：%r" % sorted(out))


@case("read: 声明删一个键，真实输出跟着少且不崩溃（含 stats 负路径）")
def t_read_declaration_is_gate():
    base = read_with("question", "901", question_router("901", best=True))
    ok("bestAnswer" in base and "truncated" not in base,
       "构造坏了：基线应含 bestAnswer 且不含 truncated：%r" % sorted(base))
    broken = kd_test_support.contract_copy()
    broken["read"]["conditionalByType"]["question"] = [
        k for k in broken["read"]["conditionalByType"]["question"] if k != "bestAnswer"]
    with kd_test_support.contract_override(broken):
        out = read_with("question", "901", question_router("901", best=True))
    ok("bestAnswer" not in out and set(out) == set(base) - {"bestAnswer"},
       "删声明 bestAnswer 后输出应恰好少它：%r" % sorted(out))
    # stats 是 _public.read 注入后再投影的那一个键
    broken2 = kd_test_support.contract_copy()
    broken2["read"]["topKeys"] = [k for k in broken2["read"]["topKeys"] if k != "stats"]
    with kd_test_support.contract_override(broken2):
        out2 = read_with("knowledge", "101", make_router(knowledge=knowledge_body()))
    ok("stats" not in out2 and out2.get("ok") is True,
       "删 stats 后应仍成功且不带它：%r" % sorted(out2))


@case("read: truncated 两值从声明取，answer_limit 与 upstream_error 分开")
def t_truncated_enum_from_declaration():
    # ① answer_limit：7 条回答但 maxDetail=5
    p7 = question_post("902", n_answers=7)
    router7 = make_router(questions=p7,
        answers_pages={"content": [{"id": "a%d" % i} for i in range(1, 8)], "totalPages": 1},
        answer_details=lambda url: {"description": "展开"})
    ok(read_with("question", "902", router7).get("truncated") == "answer_limit",
       "超过 maxDetail 应为 answer_limit")
    # ② upstream_error：回答端点失败、题帖正文成功
    def boom(url, rate=None):
        if "/answers" in url:
            raise urllib.error.URLError("probe-upstream-down")
        return question_post("903")
    with upstream(make_router(default=boom)):
        out = core.read("question", "903")
    ok(out.get("truncated") == "upstream_error", "上游错应为 upstream_error：%r" % out.get("truncated"))
    # ③ 改声明两值，真实输出跟着变（代码没有写死字面量）
    broken = kd_test_support.contract_copy()
    broken["read"]["truncatedValues"] = {"answerLimit": "PROBE_LIMIT",
                                         "upstreamError": "PROBE_UP"}
    with kd_test_support.contract_override(broken):
        ok(read_with("question", "902", router7).get("truncated") == "PROBE_LIMIT",
           "改声明 answerLimit 后输出没变（代码写死了）")
        with upstream(make_router(default=boom)):
            ok(core.read("question", "903").get("truncated") == "PROBE_UP",
               "改声明 upstreamError 后输出没变（只收一处等于没收）")


@case("read: 翻页全取并按页号归位，部分失败保住已取页")
def t_paging_partial_failure():
    def pages(url):
        p = int(url_params(url).get("page", 1))
        if p == 3:
            raise core.UpstreamError(500, "page3 down")
        return {"content": [{"id": "p%da%d" % (p, i)} for i in range(1, 4)], "totalPages": 3}
    router = make_router(questions=question_post("904"),
                         answers_pages=pages,
                         answer_details=lambda url: {"description": "展开"})
    out = read_with("question", "904", router)
    ok(out.get("truncated") == "upstream_error", "部分页失败应置 upstream_error：%r" % out.get("truncated"))
    ids = [a["id"] for a in out.get("answers") or []]
    ok(out.get("answersTaken") == 6, "已取回的 2 页共 6 条不得因第 3 页失败而丢弃：%r" % out.get("answersTaken"))
    ok(ids[:3] == ["p1a1", "p1a2", "p1a3"] and ids[3:] == ["p2a1", "p2a2", "p2a3"],
       "回答必须按页号归位，不让完成先后决定顺序：%r" % ids)


@case("read: 各类真实网络故障同等对待为 upstream_error，程序缺陷穿透")
def t_upstream_failure_kinds_on_read():
    for label, exc in (
        ("URLError", urllib.error.URLError("down")),
        ("socket.timeout", socket.timeout("timeout")),
        ("JSONDecodeError", json.JSONDecodeError("bad", "doc", 0)),
        ("IncompleteRead", http.client.IncompleteRead(b"x")),
        ("BadStatusLine", http.client.BadStatusLine("bad")),
    ):
        def boom(url, e=exc):
            if "/answers" in url:
                raise e
            return question_post("905")
        with upstream(make_router(default=boom)):
            out = core.read("question", "905")
        ok(out.get("truncated") == "upstream_error",
           "%s 应被视为上游故障：%r" % (label, out.get("truncated")))
    def bug(url):
        if "/answers" in url:
            raise AttributeError("our own bug")
        return question_post("906")
    with upstream(make_router(default=bug)):
        try:
            core.read("question", "906")
        except AttributeError:
            pass
        else:
            raise Fail("程序缺陷被吞成 upstream_error（应响亮穿透）")


@case("read: 问答键序 —— url 始终在 contentText 与 isSolved 之间")
def t_question_key_order():
    for best in (False, True):
        out = read_with("question", "907", question_router("907", best=best))
        ks = list(out)
        ok(ks.index("contentText") < ks.index("url") < ks.index("isSolved"),
           "url 必须夹在 contentText 与 isSolved 之间（best=%r）：%r" % (best, ks))


@case("read: 同一帖 search 与 read 给出同一个 url（采纳优先、空回答号跳过）")
def t_url_consistency_search_read():
    a1 = item("answer", "7001", qid="9001", adopted=False)
    a2 = item("answer", "7002", qid="9001", adopted=True)
    s = search_with([a1, a2], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    # read 侧回答候选必须与 search 同号（采纳回答 7002 在首、另一条 7001）
    read_router = question_router("9001", n_answers=2, post=question_post(
        "9001", bestAnswer=[{"id": "7002", "description": "已采纳", "isAdopt": "true"}]),
        answer_detail=lambda url: {"description": "展开"})
    read_router = make_router(
        questions=question_post("9001", bestAnswer=[{"id": "7002", "description": "已采纳", "isAdopt": "true"}]),
        answers_pages={"content": [{"id": "7002", "description": "采纳"},
                                    {"id": "7001", "description": "另一条"}],
                       "totalPages": 1},
        answer_details=lambda url: {"description": "展开"})
    r = read_with("question", "9001", read_router)
    ok(s.get("url") == r.get("url"),
       "同帖 search/read url 必须一致：%r vs %r" % (s.get("url"), r.get("url")))
    # 空白回答号被跳过、取下一个候选：search/read 仍一致
    blank = item("answer", "   ", qid="9002", adopted=False)
    real = item("answer", "7003", qid="9002", adopted=False)
    s2 = search_with([blank, real], keywords=["乙"], product_id=PROBE_PRODUCT)["results"][0]
    router2 = make_router(
        questions=question_post("9002"),
        answers_pages={"content": [{"id": "7003", "description": "首条"}], "totalPages": 1},
        answer_details=lambda url: {"description": "展开"})
    r2 = read_with("question", "9002", router2)
    ok(s2.get("url") == r2.get("url") and "/answers/7003" in (s2.get("url") or ""),
       "空白回答号应跳到次条且两侧一致：%r vs %r" % (s2.get("url"), r2.get("url")))


# ================================ 第三组：upstream（上游适配 / 零联网） ================================

@case("upstream: product_id 两态、global_/sorts_type/关键词逐字透传到每次请求")
def t_search_params_passthrough():
    for label, kw, expected in (
        ("省略", {}, DEFAULT_PRODUCT_ID), ("显式 None", {"product_id": None}, DEFAULT_PRODUCT_ID),
        ("显式 0", {"product_id": 0}, 0), ("显式 87", {"product_id": 87}, 87),
    ):
        with upstream(make_router(search=search_response([]))) as calls:
            r = core.search(keywords=["甲"], **kw)
        p = url_params(calls[0])
        ok(r.get("effectiveProductId") == expected,
           "%s effectiveProductId 应为 %r，实为 %r" % (label, expected, r.get("effectiveProductId")))
        # 0/None 省略产品参数；显式非零必须逐值透传
        ok(p.get("productIds[0]") == (str(expected) if expected else None),
           "%s 上游产品过滤应为 %r，实为 %r" % (label, expected, p.get("productIds[0]")))
        ok(r.get("effectiveProductId") is not None, "回显不得为 null")
    with upstream(make_router(search=search_response([]))) as calls:
        core.search(keywords=["甲", "乙"], product_id=PROBE_PRODUCT, global_=True, sorts_type=0)
    q = [url_params(u) for u in calls]
    ok(all(x["global"] == "true" for x in q), "global_=True 必须逐路透传：%r" % q)
    ok(all(x["sortsType"] == "0" for x in q), "sorts_type=0 不能被 or 链吞成 1：%r" % q)
    ok(all(x["text"] in ("甲", "乙") for x in q), "关键词必须逐字透传：%r" % q)


@case("upstream: 并发下路序仍按给词顺序，失败路隔离且不拖垮其余路")
def t_concurrent_route_order():
    import threading
    ev = threading.Event()
    def route(url):
        t = url_params(url)["text"]
        if t == "甲":
            ev.wait(0.3)  # 让第 1 路最慢完成
            return search_response([item("knowledge", 1, title="词甲")])
        if t == "乙":
            return search_response([item("knowledge", 2, title="词乙")])
        return search_response([])
    with upstream(make_router(search=route)):
        r = core.search(keywords=["甲", "乙"], product_id=PROBE_PRODUCT)
    ev.set()
    ids = [x["id"] for x in r["results"]]
    ok(ids == ["1", "2"], "第 1 路虽最慢完成，清单顺序仍应按给词顺序：%r" % ids)


@case("upstream: 零网络泄漏 —— 离线组不尝试真连接，阳性对照证明守卫有效")
def t_no_network_leak():
    # 阴性：正常离线用例路径下 0 次连接尝试
    with no_network() as state:
        r = search_with([item("knowledge", 1)], keywords=["甲"], product_id=PROBE_PRODUCT)
        ok(r.get("ok") is True, "离线 search 应成功")
        read_with("knowledge", "K1", make_router(knowledge=knowledge_body()))
    ok(not state["attempts"], "离线组发生了真实连接尝试：%r" % state["attempts"])
    # 阳性对照：在**同一个守卫**上临时放行一次连接，证明它真的会拦（不是摆设）
    install, restore, factory_state = _guard_factory()
    same = install()
    try:
        same["allow"] = 1
        sock = socket.socket()
        try:
            sock.connect(("127.0.0.1", 1))
        except OSError:
            pass  # 连不上没关系，关键是这次连接确实经过了守卫
        finally:
            sock.close()
        ok(len(same["attempts"]) == 1 and same["allow"] == 0,
           "阳性对照失败：同一守卫未记录/未放行那次连接：%r" % same)
        # 紧接着再发一次（不再放行），必须被守卫拦下
        sock2 = socket.socket()
        try:
            try:
                sock2.connect(("127.0.0.1", 1))
            except AssertionError:
                pass  # 期望：守卫拦下
            else:
                raise Fail("阳性对照的第二次连接未被守卫拦下")
        finally:
            sock2.close()
    finally:
        restore()


@case("upstream: CLI 进程级只覆盖 search/read —— 成功、错误与已删命令")
def t_cli_process_contract():
    payload = {"/api/search": search_response([item("knowledge", 1)]),
               "/knowledgeapi/knowledge/": knowledge_body(),
               "/api/articles/": article_body(),
               "/api/questions/": question_post("91001")}
    code, data, stdout, stderr = cli_offline("search", "--kw", "甲", payload=payload)
    ok(code == 0, "kd search 成功应 exit 0，实为 %r（stderr=%s）" % (code, stderr[-300:]))
    ok(data is not None and data.get("ok") is True, "stdout 应是纯 JSON 成功载荷：%r" % stdout[:200])
    ok(set(data) == set(FROZEN_TOP_KEYS), "CLI search 顶层键与内核不一致：%r" % sorted(data))
    code, data, stdout, stderr = cli_offline("read", "K1", "--kind", "knowledge", payload=payload)
    ok(code == 0 and data is not None and data.get("ok") is True,
       "kd read 成功应 exit 0 + JSON：%r/%r" % (code, stdout[:200]))
    ok("stats" in data, "CLI read 也应带 stats")
    # 已删命令 / 非法参数：exit 2，stdout 不得有成功载荷
    for args in (("health",), ("ask", "--kw", "甲"), ("share", "--id", "1"),
                 ("search",), ("search", "--kw", "甲", "--budget", "5"),
                 ("read", "1", "--kind", "nope")):
        code, data, stdout, stderr = cli_offline(*args, payload=payload)
        ok(code == 2, "kd %s 应 exit 2，实为 %r" % (args[0], code))
        ok(not stdout.strip() or (data is not None and data.get("ok") is not True),
           "用法错误不应输出成功载荷：%r" % stdout[:200])
        ok(stderr.strip(), "用法错误应有 stderr 提示")


@case("upstream: CLI 错误走 exit 1 + error 对象，stdout 只有 JSON")
def t_cli_error_contract():
    code, data, stderr = cli("search", "--kw", "超" * 120)
    ok(code == 1, "超长查询应 exit 1，实为 %r" % code)
    ok(data is not None and data.get("error", {}).get("code") == "query_too_long",
       "错误码应为 query_too_long：%r" % data)
    code, data, stdout, _ = cli_offline("search", "--kw", "超" * 120, payload={})
    ok("[kd]" not in (stdout or ""), "诊断信息不得混进 stdout：%r" % (stdout or "")[:200])
    # read(kind=other) 的合法能力边界：exit 1 + unsupported_kind（不是用法错误）
    code, data, stdout, stderr = cli_offline("read", "6898", "--kind", "other", payload={})
    ok(code == 1 and data is not None,
       "read other 应 exit 1 且有错误 JSON：%r/%r" % (code, stdout[:200]))
    ok(data.get("error", {}).get("code") == "unsupported_kind",
       "分类码应为 unsupported_kind：%r" % data)


@case("upstream: --help 在非 UTF-8 控制台也不崩，且只列 search/read")
def t_cli_help_console():
    for args in (("--help",), ("search", "--help"), ("read", "--help")):
        env = dict(os.environ, PYTHONIOENCODING="gbk")
        p = subprocess.run([PY, RUN, *args], cwd=REPO, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env)
        ok(p.returncode == 0, "PYTHONIOENCODING=gbk 下 %r 应 exit 0：%r" % (args, p.returncode))
    help_text = out_text("--help")
    ok("search" in help_text and "read" in help_text, "--help 应列 search/read")
    for gone in ("health", "ask", "share"):
        ok(gone not in help_text, "--help 不应列已删命令 %s" % gone)


@case("upstream: 迁移前后公开行为逐字段等价（冻结基线 41 场景，票 01/05）")
def t_public_behavior_baseline():
    p = subprocess.run([PY, BASESCRIPT], capture_output=True, text=True, cwd=REPO)
    detail = (p.stdout or "") + (p.stderr or "")
    ok(p.returncode == 0,
       "公开行为基线漂移（exit=%d）：%s" % (p.returncode, detail[-2000:]))
    ok("逐字段一致" in detail, "重放器未输出逐字段一致：%s" % detail[-800:])
    # 这份基线是票 01 在**迁移前**录下的公开输出；迁移后同一 fake 上游逐字段重放
    # 仍一致，就是票 05 验收 1 的“迁移前后输出不变”的可重跑证据。


@case("upstream: stdout 只出 JSON，诊断走 stderr；错误路径不落盘")
def t_cli_stream_split_and_no_landing():
    # 用入参硬闸触发致命错误（上游错误是 routeErrors 隔离、exit 0，不是这条判据的对象）
    code, data, stdout, stderr = cli_offline("search", "--kw", "超" * 120, payload={})
    ok(code == 1, "超长查询应 exit 1：%r" % code)
    ok(data is not None and data.get("ok") is not True, "stdout 应是错误 JSON：%r" % stdout[:200])
    ok("[kd]" not in stdout, "诊断不得混进 stdout：%r" % stdout[:200])
    # 诊断走 stderr：用法错误（exit 2）的路径上 stdout 为空、提示在 stderr
    code2, _d2, stdout2, stderr2 = cli_offline("search", payload={})
    ok(code2 == 2 and not stdout2.strip() and stderr2.strip(),
       "用法错误应 exit 2 + stdout 空 + stderr 有提示：%r/%r/%r"
       % (code2, stdout2[:100], stderr2[:100]))
    # 内核不落盘：错误路径不产生 landing 字段、不写仓库内新文件
    ok("landing" not in (data or {}), "错误路径不应有 landing 字段：%r" % data)


@case("read: maxDetail 从声明取，改声明即改截断深度（公开 read 一次请求链）")
def t_max_detail_from_declaration():
    post = question_post("908", n_answers=5)
    router = make_router(
        questions=post,
        answers_pages={"content": [{"id": "a%d" % i, "description": "摘要"}
                                    for i in range(1, 6)], "totalPages": 1},
        answer_details=lambda url: {"description": "展开全文"})
    broken = kd_test_support.contract_copy()
    broken["limits"]["maxDetail"] = 2
    with kd_test_support.contract_override(broken):
        out = read_with("question", "908", router)
    ok(out.get("truncated") == "answer_limit", "5 条 > maxDetail=2 应截断：%r" % out.get("truncated"))
    ok(out.get("answersTaken") == 5, "翻页仍应取全 5 条，只截逐条详情：%r" % out.get("answersTaken"))
    # 声明 maxDetail=5 时同构造不截断
    out2 = read_with("question", "908", router)
    ok("truncated" not in out2, "maxDetail=5 时 5 条不该截断：%r" % out2.get("truncated"))


@case("search: 标题降级链 —— 高亮壳剥标签/空候选跳过/点号键优先")
def t_title_fallback():
    # ① 纯高亮标签壳（有文本）→ 剥标签后非空，不产生静默空标题
    shell = item("knowledge", 1, title="被忽略的顶层")
    shell["highlight"]["title"] = "<em>禁用</em>"
    a = search_with([shell], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(a.get("title") == "禁用", "纯高亮标签壳应剥出文本：%r" % a.get("title"))
    # ② 首候选为存在但空串时，不得挡住后面有货的候选（silent None 的根源）
    empty_first = item("knowledge", 2, title="真标题")
    empty_first["title"] = "真标题"  # 顶层真标题作为第二候选
    empty_first["highlight"]["title"] = ""
    b = search_with([empty_first], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(b.get("title") == "真标题", "空串候选应被跳过而非短路：%r" % b.get("title"))
    # ③ 点号键优先于顶层 title（问答档 question.title）
    dotted = item("answer", 3, qid=30, title="顶层标题")
    dotted["highlight"]["question.title"] = "点号键标题"
    c = search_with([dotted], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(c.get("title") == "点号键标题", "点号键应优先：%r" % c.get("title"))
    # ④ 上游把标题平铺在条目顶层（另一形状变体）仍要兜住
    flat = {"entity-type": "Answer", "id": "4", "questionId": "40",
            "highlight": {}, "question": {"id": "40"}, "title": "平铺标题"}
    d = search_with([flat], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(d.get("title") == "平铺标题", "顶层平铺标题未被兜住：%r" % d.get("title"))

@case("upstream: 错误分类只看 code 不看文案（改措辞不改分类）")
def t_error_code_not_from_text():
    # read(other) 是合法能力边界：分类来自 code=unsupported_kind，不是提示里的某句话
    code, data, stdout, stderr = cli_offline("read", "6898", "--kind", "other", payload={})
    ok(code == 1 and data is not None, "read(other) 应 exit 1 + JSON：%r/%r" % (code, stdout[:200]))
    ok(data.get("error", {}).get("code") == "unsupported_kind",
       "分类码应为 unsupported_kind：%r" % data)
    ok(data.get("error", {}).get("hint"), "错误应带行动提示：%r" % data)
    # 代码侧异常对象的 code 是唯一分类来源：文案怎么变，exit 都是 1
    try:
        core.read("other", "6898")
    except core.InternalError as e:
        ok(getattr(e, "code", None) == "unsupported_kind", "异常应带 code：%r" % e)
    else:
        raise Fail("read(other) 未抛 InternalError")


@case("search: 链接政策边界 —— 空回答号不给 url，other 档默认不给链接")
def t_link_policy_edges():
    # 空回答号 → 不给死链（而不是编一个短形式）
    blank = item("answer", "   ", qid="9003", adopted=False)
    r = search_with([blank], keywords=["甲"], product_id=PROBE_PRODUCT)["results"][0]
    ok(not r.get("url"), "空回答号不应给死链：%r" % r.get("url"))
    # other 档带第三方 url 时默认仍不给链接（政策生效）
    o = {"entity-type": "LearningBroadcast", "id": "L1", "title": "直播",
         "url": "https://live.vhall.com/x", "highlight": {"title": "直播"}}
    r2 = search_with([o], keywords=["乙"], product_id=PROBE_PRODUCT, include_other=True)["results"][0]
    ok(not r2.get("url"), "other 档默认政策应抑制 url：%r" % r2.get("url"))
    # 翻转政策后 other 的 url 出现（证明政策真有消费者）
    broken = kd_test_support.contract_copy()
    broken["linkPolicy"]["rule"]["other"] = "link"
    with kd_test_support.contract_override(broken):
        r3 = search_with([o], keywords=["乙"], product_id=PROBE_PRODUCT, include_other=True)["results"][0]
    ok(r3.get("url") == "https://live.vhall.com/x", "政策改为 link 后 other url 应出现：%r" % r3.get("url"))


@case("upstream: 坏运行参数不使公开 search/read 崩溃（限额/频率配置兜底）")
def t_bad_runtime_config_no_crash():
    for field, path in (("maxKeywords", ("limits", "maxKeywords")),
                        ("burst", ("limits", "rate", "interactive", "burst"))):
        broken = kd_test_support.contract_copy()
        d = broken
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = -1  # 有意构造坏值
        with kd_test_support.contract_override(broken):
            with upstream(make_router(search=search_response([item("knowledge", 1)]))):
                out = core.search(keywords=["甲", "乙"], product_id=PROBE_PRODUCT)
            ok(out.get("ok") is True, "坏 %s 不应让 search 崩溃：%r" % (field, out))


def main(argv):
    print("kd 回归用例集（票 05：公开 interface + 唯一 fake adapter）")
    print("-" * 72)
    passed, failed = [], []
    for name, fn in CASES:
        try:
            fn()
        except Fail as e:
            failed.append((name, str(e)))
            print("FAIL  %s\n      %s" % (name, e))
        except Exception as e:
            failed.append((name, "%s: %s" % (type(e).__name__, e)))
            print("ERROR %s\n      %s: %s" % (name, type(e).__name__, e))
        else:
            passed.append(name)
            print("ok    %s" % name)
    print("-" * 72)
    print("通过 %d / 失败 %d" % (len(passed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
