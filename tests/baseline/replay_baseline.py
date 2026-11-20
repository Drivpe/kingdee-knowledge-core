#!/usr/bin/env python3
"""kd 公开行为基线 —— 票 01「冻结公开行为基线」的离线重放器。

**它冻结什么**:kd.core.search / kd.core.read 这两个公开入口的**全部对外可观测行为**
—— 发给上游的请求参数(URL 逐字)、返回的 JSON 字段、字段的**键序**、错误分类
(QueryTooLong / UpstreamError / InternalError(code=…))、stats、read 的 truncated
与链接结果;外加 kd CLI 的进程级 stdout / stderr / 退出码。

**它不冻结什么**(如实声明,别把它读成"全量契约"):
  * 限速器的实际等待时长与抖动(_RateLimiter 不参与本基线,见下);
  * stats.elapsedMs(时序量,记录时归一成占位符 <elapsedMs>);
  * 私有实现名、模块结构、HTTP 状态码(与 tests/kd_regression.py 同口径:
    只断言外部行为)。

**为什么是"独立"基线**:期望值**不是**从 contract.json 派生的。tests/kd_regression.py
从声明派生字段名(那份是"声明即闸门"的守门用例),本基线是**先在冻结的 fake 上游上
录下真实输出,再逐字段比对**。两份的分工不重叠:一份防"声明与代码同源恒绿",
一份防"改动后外部行为变了却没人发现"。

**固定 fake 上游**:upstream-fake.json 是逐 URL 登记的固定响应,**未登记的 URL 直接
抛错**(绝不静默兜底成空结果——那正是本仓最忌的"把没读懂伪装成没有")。
只有 answers 段允许 __default__ 模板,因为逐条详情展开是对一批回答号的批量循环。

**网络出口**:全内核唯一的上游出口是 kd._impl._net._get_json,本基线在它上面打桩,
因此**零联网**。打桩点与 _upstream / _detail 的属性访问同源,故检索侧与深读侧
**同时**被拦住(这正是"出口统一"那条纪律要防的漏)。

**用法**:
    python3 tests/baseline/replay_baseline.py            # 与冻结基线逐字段比对
    python3 tests/baseline/replay_baseline.py --record  # 重新录制(改上游形状后才用)
    python3 tests/baseline/replay_baseline.py --list    # 列出场景名

退出码:0 = 逐字段一致;1 = 有漂移(或录制失败)。
"""
import argparse
import http.client
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kd import core
import kd._impl._net as _net
import kd._impl._config as _config
from kd._impl._errors import UpstreamError

FIXTURE_PATH = os.path.join(HERE, "upstream-fake.json")
BASELINE_PATH = os.path.join(HERE, "public-behavior-baseline.json")

# stats.elapsedMs 是时序量:记录时归一成占位符,比对时只看"键在、是数"这一事实。
ELAPSED_MASK = "<elapsedMs>"


# ------------------------------------------------------------------ fake 上游

def load_fixture(path=FIXTURE_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _subst(obj, mapping):
    """把模板里的占位符替换成实际 id(供 answers 段的 __default__ 使用)。"""
    if isinstance(obj, dict):
        return {k: _subst(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_subst(v, mapping) for v in obj]
    if isinstance(obj, str):
        for key, val in mapping.items():
            obj = obj.replace("<" + key + ">", val)
        return obj
    return obj


def resolve(fixture, url):
    """固定 fake 上游的 URL 分派。查不到返回 None → 打桩函数抛错。"""
    if url.startswith("https://vip.kingdee.com/api/search"):
        q = urllib.parse.parse_qs(url.split("?", 1)[1])
        return fixture["search"].get(q["text"][0])
    if url.startswith("https://vip.kingdee.com/knowledgeapi/knowledge/"):
        return fixture["knowledge"].get(url.rsplit("/", 1)[1])
    if url.startswith("https://vip.kingdee.com/api/questions/") and "/answers" in url:
        body, _, query = url.partition("?")
        qid = body.split("/api/questions/", 1)[1].split("/answers", 1)[0]
        page = urllib.parse.parse_qs(query)["page"][0]
        return fixture["questionAnswers"].get(qid, {}).get(page)
    if url.startswith("https://vip.kingdee.com/api/questions/"):
        return fixture["questions"].get(url.rsplit("/", 1)[1])
    if url.startswith("https://vip.kingdee.com/api/answers/"):
        aid = url.rsplit("/", 1)[1]
        tbl = fixture["answers"]
        if aid in tbl:
            return tbl[aid]
        return _subst(tbl.get("__default__"), {"id": aid})
    if url.startswith("https://vip.kingdee.com/api/articles/"):
        return fixture["articles"].get(url.rsplit("/", 1)[1])
    return None


def make_fake(fixture, calls):
    """构造打在 _net._get_json 上的假出口。

    与真实 _get_json 的**两处同口径**:① 递增上游调用计数(_up_inc),
    否则 stats.upstreamCalls 恒为 0、冻结的就是假数;② 识别"假 200 + errorCode"
    并抛 UpstreamError。限速等待(_RATE.wait)刻意不做——它是时序量,且它的实际等待
    会拖慢整个基线;stats.upstreamCalls 与限速无关,不受影响。
    """
    def fake(url, rate=None):
        calls.append(url)
        _config._up_inc()
        entry = resolve(fixture, url)
        if entry is None:
            raise AssertionError("fake 上游未登记该 URL(基线禁止静默兜底): " + url)
        if "errorCode" in entry:
            raise UpstreamError(int(entry["errorCode"]),
                                str(entry.get("message") or "")[:200])
        if "__raise__" in entry:
            kind = entry["__raise__"]
            if kind == "URLError":
                raise urllib.error.URLError(entry.get("message"))
            if kind == "IncompleteRead":
                raise http.client.IncompleteRead(b"")
            raise AssertionError("未知的 __raise__ 取值: " + repr(kind))
        if "__raw__" in entry:
            return json.loads(entry["__raw__"])
        return entry
    return fake


# ------------------------------------------------------------------ 归一化

def normalize(obj):
    """把时序量归一成占位符,其余结构与键序**原样保留**。"""
    if isinstance(obj, dict):
        return {k: (ELAPSED_MASK if k == "elapsedMs" else normalize(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def diff_json(expected, actual, path="", out=None):
    """递归逐字段比对,返回差异文本列表。

    ⚠️ **键序必须真的比**:dict 在 Python 里保序,而 CLI 输出的是有序 JSON ——
    键序漂移是**对外可观测**的行为变更(见 _detail.project_read 的 docstring:
    键序刻意由构造顺序承载,而不是按声明顺序拼接)。本函数第一版只按键名比对、
    **不比较顺序**,变异测试当场把它抓了出来(把 read/question 的 createdAt 与
    updatedAt 对调,基线仍报"逐字段一致")。只比键名会让"键序不变"这条契约
    名义上覆盖、实际不覆盖 —— 正是本仓纪律所禁止的那一类。
    """
    if out is None:
        out = []
    if type(expected) is not type(actual):
        out.append(path + ": 类型变了 " + type(expected).__name__ + " -> "
                   + type(actual).__name__)
        return out
    if isinstance(expected, dict):
        ek, ak = list(expected), list(actual)
        # 键集相同而顺序不同 → 单独报一条(否则下面按键名的逐项比对会全部通过)。
        if ek != ak and set(ek) == set(ak):
            out.append(path + ": 键序变了 " + str(ek) + " -> " + str(ak))
        for k in expected:
            if k not in actual:
                out.append(path + "." + k + ": 键缺失(期望有)")
        for k in actual:
            if k not in expected:
                out.append(path + "." + k + ": 多出键(期望没有)")
        for k in expected:
            if k in actual:
                diff_json(expected[k], actual[k], path + "." + k, out)
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            out.append(path + ": 长度变了 " + str(len(expected)) + " -> "
                       + str(len(actual)))
        for i, (e, a) in enumerate(zip(expected, actual)):
            diff_json(e, a, path + "[" + str(i) + "]", out)
    elif expected != actual:
        out.append(path + ": " + repr(expected) + " -> " + repr(actual))
    return out


# ------------------------------------------------------------------ 场景定义

SEARCH_KW = ["资产", "BOM"]
OVER_LIMIT_KW = ["词1", "词2", "词3", "词4", "词5", "词6", "词7", "词8"]

SCENARIOS = [
    # ---- search:请求参数(每路一次、逐字逐序、product/global/sorts 透传)----
    {"name": "search/basic_multi", "mode": "core", "op": "search",
     "kwargs": {"keywords": list(SEARCH_KW)}},
    # 同时是 other 档**默认隐藏**的基线(otherSkipped=1 + scanNote 末句);
    # 显式打开那一路见 search/other_included。
    {"name": "search/product_default_omitted", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"]}},
    {"name": "search/product_explicit_zero", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "product_id": 0}},
    {"name": "search/product_explicit_87", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "product_id": 87}},
    {"name": "search/product_explicit_none", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "product_id": None}},
    {"name": "search/global_true", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "global_": True}},
    {"name": "search/sorts_type_zero", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "sorts_type": 0}},
    {"name": "search/sorts_type_two", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "sorts_type": 2}},
    # ---- search:截断 / 去重 / 空白词 ----
    {"name": "search/over_limit_eight", "mode": "core", "op": "search",
     "kwargs": {"keywords": list(OVER_LIMIT_KW)}},
    {"name": "search/duplicate_keywords", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产", "资产", "BOM"]}},
    {"name": "search/blank_partial", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产", "   ", "BOM"]}},
    # ---- search:other 档的显式打开(隐藏态见 product_default_omitted,同输入)----
    {"name": "search/other_included", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产"], "include_other": True}},
    # ---- search:entity-type 宽容层(不静默丢弃)----
    {"name": "search/entity_type_tolerance", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["BOM"]}},
    # ---- search:四类上游故障的路由级分类 ----
    {"name": "search/route_upstream_error", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产", "上游故障"]}},
    {"name": "search/route_url_error", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产", "传输故障"]}},
    {"name": "search/route_json_error", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产", "报文故障"]}},
    {"name": "search/route_http_exception", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["资产", "协议故障"]}},
    # ---- search:入参错误分类 ----
    {"name": "search/empty_keywords", "mode": "core", "op": "search",
     "kwargs": {"keywords": []}},
    {"name": "search/keywords_as_string", "mode": "core", "op": "search",
     "kwargs": {"keywords": "资产"}},
    {"name": "search/keywords_as_dict", "mode": "core", "op": "search",
     "kwargs": {"keywords": {"a": 1}}},
    {"name": "search/all_blank_keywords", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["", "  "]}},
    {"name": "search/query_too_long", "mode": "core", "op": "search",
     "kwargs": {"keywords": ["x" * 101]}},

    # ---- read:三档全文 + 翻页 / 截断 / 上游故障降级 ----
    {"name": "read/knowledge", "mode": "core", "op": "read",
     "kwargs": {"kind": "knowledge", "oid": "K1001"}},
    {"name": "read/question_simple", "mode": "core", "op": "read",
     "kwargs": {"kind": "question", "oid": "91001"}},
    {"name": "read/question_multi_page", "mode": "core", "op": "read",
     "kwargs": {"kind": "question", "oid": "91005"}},
    {"name": "read/question_answer_limit", "mode": "core", "op": "read",
     "kwargs": {"kind": "question", "oid": "91003"}},
    {"name": "read/question_upstream_error", "mode": "core", "op": "read",
     "kwargs": {"kind": "question", "oid": "91004"}},
    {"name": "read/article", "mode": "core", "op": "read",
     "kwargs": {"kind": "article", "oid": "A2001"}},
    # ---- read:上游业务错误直接透穿到调用方(三类异常里的 UpstreamError)----
    # ⚠️ 知识档与文章档**不抓**上游故障(只有问答档降级成 truncated),
    # 故 UpstreamError 会原样透穿到调用方 —— 这是冻结面里的「三类异常」之一。
    {"name": "read/knowledge_upstream_error", "mode": "core", "op": "read",
     "kwargs": {"kind": "knowledge", "oid": "K_BAD"}},
    {"name": "read/article_upstream_error", "mode": "core", "op": "read",
     "kwargs": {"kind": "article", "oid": "A_BAD"}},
    {"name": "read/unsupported_kind", "mode": "core", "op": "read",
     "kwargs": {"kind": "other", "oid": "6898"}},
    {"name": "read/bad_kind", "mode": "core", "op": "read",
     "kwargs": {"kind": "nope", "oid": "1"}},
    {"name": "read/missing_id", "mode": "core", "op": "read",
     "kwargs": {"kind": "knowledge", "oid": ""}},

    # ---- CLI:进程级 stdout=JSON / stderr=进度 / 退出码 ----
    {"name": "cli/search_basic", "mode": "cli",
     "argv": ["search", "--kw", "资产", "--kw", "BOM"]},
    {"name": "cli/search_include_other", "mode": "cli",
     "argv": ["search", "--kw", "资产", "--include-other"]},
    {"name": "cli/search_over_limit", "mode": "cli",
     "argv": ["search"] + [x for w in OVER_LIMIT_KW for x in ("--kw", w)]},
    {"name": "cli/read_knowledge", "mode": "cli",
     "argv": ["read", "K1001"]},
    {"name": "cli/read_question", "mode": "cli",
     "argv": ["read", "91001", "--kind", "question"]},
    {"name": "cli/read_unsupported_kind", "mode": "cli",
     "argv": ["read", "6898", "--kind", "other"]},
    {"name": "cli/read_bad_kind", "mode": "cli",
     "argv": ["read", "91001", "--kind", "nope"]},
    {"name": "cli/query_too_long", "mode": "cli",
     "argv": ["search", "--kw", "x" * 101]},
]


# ------------------------------------------------------------------ 执行

def run_core(op, kwargs):
    calls = []
    orig = _net._get_json
    _net._get_json = make_fake(load_fixture(), calls)
    _config._UP_N = 0
    try:
        try:
            result = core.search(**kwargs) if op == "search" else core.read(**kwargs)
            result = normalize(result)
        except AssertionError:
            # ⚠️ **本 harness 自己的守卫,不是内核行为** —— 必须原样上抛,
            # 绝不能像普通异常那样被录进基线。理由:一旦录进去,--record 就会把
            # "fixture 漏登记" 冻结成 "期望输出",之后每次重放都"通过" ——
            # 那是用一处静默换另一处静默,正是本仓最忌的形态。
            # (内核侧会先记一笔 ROUTE_BUG:AssertionError 不在 _net.UPSTREAM_FAILURES
            #  里,属程序缺陷 → 响亮穿透,这是对的。)
            raise
        except Exception as e:
            result = {"error": {"exception": type(e).__name__,
                                "message": str(e),
                                "code": getattr(e, "code", None)}}
    finally:
        _net._get_json = orig
    # ⚠️ **保留重复项**:每路恒 1 次请求是冻结面(规格决策 1:「路序、每路一次请求」不变)。
    # 旧写法 sorted(set(calls)) 丢掉了重数:「某路发了两次、另一路一次没发」会得到与正常相同的记录,
    # 那就是声称覆盖、实际不覆盖。排序保留(并发下完成顺序不得泄漏进结果),
    # 但**不去重** —— 计数因此可比。
    return {"requestCount": len(calls), "requests": sorted(calls), "result": result}


def run_cli_main(argv):
    """子进程内跑 CLI:同样打桩唯一网络出口,再把请求清单写到临时文件。"""
    calls = []
    orig = _net._get_json
    _net._get_json = make_fake(load_fixture(), calls)
    _config._UP_N = 0
    try:
        import kd.cli
        try:
            kd.cli.main(argv)
            rc = 0
        except SystemExit as e:
            code = e.code
            rc = code if isinstance(code, int) else (0 if code is None else 1)
        return rc
    finally:
        _net._get_json = orig
        path = os.environ.get("KD_BASELINE_CALLS")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sorted(set(calls)), f, ensure_ascii=False)


def run_cli(argv, calls_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + HERE
    env["KD_BASELINE_CALLS"] = calls_path
    bootstrap = (
        "import sys; sys.path[:0] = [" + repr(SRC) + ", " + repr(HERE) + "];"
        "import replay_baseline as rb; sys.exit(rb.run_cli_main(sys.argv[1:]))"
    )
    proc = subprocess.run([sys.executable, "-c", bootstrap] + argv,
                          capture_output=True, text=True, env=env, cwd=REPO)
    with open(calls_path, encoding="utf-8") as f:
        calls = json.load(f)
    if "fake 上游未登记该 URL" in proc.stderr or "未知的 __raise__ 取值" in proc.stderr:
        # 同 run_core:这是 harness 守卫触发,不是内核行为,不得录进基线。
        raise AssertionError("CLI 场景触发了 fake 上游守卫(基线禁止静默兜底): "
                             + proc.stderr.strip()[:400])
    stdout = proc.stdout
    try:
        stdout = normalize(json.loads(stdout)) if stdout.strip() else ""
    except ValueError:
        pass  # 非 JSON 输出(如 argparse 用法错误走 stderr)原样保留
    return {"requestCount": len(calls), "requests": calls,
            "exitCode": proc.returncode, "stdout": stdout,
            "stderr": proc.stderr}


def record_scenario(sc):
    if sc["mode"] == "core":
        rec = run_core(sc["op"], sc["kwargs"])
    else:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            rec = run_cli(sc["argv"], path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    rec["name"] = sc["name"]
    rec["mode"] = sc["mode"]
    return rec


# ------------------------------------------------------------------ 录制 / 比对

def meta_of():
    contract = json.loads(open(os.path.join(SRC, "kd", "contract.json"),
                               encoding="utf-8").read())
    return {"kernelVersion": core._impl().VERSION,
            "contractVersion": contract.get("version"),
            "scenarioCount": len(SCENARIOS),
            "notes": [
                "期望值是录制时在固定 fake 上游上的真实输出,不是从 contract.json 派生的。",
                "stats.elapsedMs 为时序量,录制时归一为 <elapsedMs>;其余键与键序逐字冻结。",
                "requests 是发往上游的 URL 清单(并发下完成顺序不定,故去重后排序),"
                "它冻结的是请求参数与每路请求次数,不冻结并发时序。",
                "限速器不参与本基线:它的等待是时序量,且不影响 stats.upstreamCalls。",
            ]}


def main(argv=None):
    global FIXTURE_PATH
    ap = argparse.ArgumentParser(description="kd 公开行为基线离线重放器")
    ap.add_argument("--record", action="store_true", help="重新录制基线")
    ap.add_argument("--list", action="store_true", help="列出场景名后退出")
    ap.add_argument("--fixture", default=FIXTURE_PATH)
    ap.add_argument("--baseline", default=BASELINE_PATH)
    args = ap.parse_args(argv)

    if args.list:
        for sc in SCENARIOS:
            print(sc["name"])
        return 0

    FIXTURE_PATH = args.fixture

    if args.record:
        data = {"meta": meta_of(),
                "scenarios": [record_scenario(sc) for sc in SCENARIOS]}
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=False, indent=2)
            f.write("\n")
        print("已录制 " + str(len(data["scenarios"])) + " 个场景 -> " + args.baseline)
        return 0

    with open(args.fixture, encoding="utf-8") as f:
        json.load(f)
    with open(args.baseline, encoding="utf-8") as f:
        expected = json.load(f)

    meta = meta_of()
    bad = 0
    if (expected.get("meta", {}).get("kernelVersion") != meta["kernelVersion"]
            or expected.get("meta", {}).get("contractVersion") != meta["contractVersion"]):
        bad += 1
        print("[漂移] meta: 内核版本/契约版本与冻结基线不一致")
    names = [sc["name"] for sc in expected.get("scenarios", [])]
    if names != [sc["name"] for sc in SCENARIOS]:
        bad += 1
        print("[漂移] 场景清单变了:")
        print("  冻结: " + ", ".join(names))
        print("  现在: " + ", ".join(sc["name"] for sc in SCENARIOS))
    exp_by_name = {sc["name"]: sc for sc in expected.get("scenarios", [])}
    for sc in SCENARIOS:
        name = sc["name"]
        if name not in exp_by_name:
            bad += 1
            print("[漂移] " + name + ": 冻结基线里没有这个场景")
            continue
        act = record_scenario(sc)
        diffs = diff_json(exp_by_name[name], act)
        if diffs:
            bad += 1
            print("[漂移] " + name + ":")
            for d in diffs[:25]:
                print("    " + d)
            if len(diffs) > 25:
                print("    ... 另有 " + str(len(diffs) - 25) + " 处")

    if bad:
        print("")
        print("比对结果: 有漂移(" + str(bad) + " 处场景/元信息不一致)")
        return 1
    print("")
    print("比对结果: " + str(len(SCENARIOS)) + " 个场景逐字段一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
