#!/usr/bin/env python3
"""kd._impl._concurrent —— 有序并发执行：保序、逐项失败收集、确定性重抛。

本模块只做一件事：把一批任务并发跑完，把成功结果按输入键归位，把
"可预期的局部失败"逐项交给调用方处理；程序缺陷按最小键确定性地交还，
中断则立即穿透。它不知道路由、页号、回答、routeErrors、truncated、内容合并这些
业务政策——那些都留在各自的调用方。

## 不变量（三条链路共享，ADR-0020 决策 1）

1. 完成先后不泄漏进结果。成功结果按调用方给的键（路号/页号/下标）归位；
   results 的插入序仍是完成序，调用方必须按键排序后消费，不得读取完成序。
2. 局部失败不拖掉成功结果。单任务失败只记录进 failures，收集循环不中断；
   成功后即使其它任务失败也照样归位。调用方决定失败怎么表现
   （记入 routeErrors、置 truncated、或忽略）。
3. 程序缺陷/中断确定性交还。非预期异常按最小键重抛（同输入恒抛同一个，
   与线程调度无关）；KeyboardInterrupt / SystemExit 立即穿透，不等收齐。

## 参数

tasks        键 -> 零参可调用对象；键必须是可比较、可排序的标量
              （路号/页号/下标），用于归位与确定性重抛。
max_workers  并发上界，由调用方按自己的声明算出后传入；本模块不自造
             第二个限速器（单一来源纪律）。
expected     被当作"局部失败"收集的异常类型元组；其余异常一律按程序缺陷记账。
             默认空（全部按缺陷）。调用方按业务政策声明，模块不预设"什么叫上游故障"。
on_failure   可选：每个局部失败收集时的回调 (key, exc)，记日志等。
on_bug       可选：每个程序缺陷的回调 (key, exc)，记日志等。

## 返回

(results, failures)：
  results   键 -> 成功结果；插入序只是完成序，调用方消费前必须 sorted。
  failures  键 -> (exc_type, exc, traceback)，仅 expected 类。
程序缺陷（非 expected 类）按最小键重抛，带原 traceback；本模块不返回它们。
中断类立即穿透。空任务集返回 ({}, {})。
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_INTERRUPTS = (KeyboardInterrupt, SystemExit)


def _raise_min(accounted):
    """按最小键重抛记账的异常，带原 traceback（确定性，不随线程调度漂移）。

    `accounted` 是 `{键: sys.exc_info() 三元组}`。取 `min(键)` 是确定性要求，
    不是"取最早" —— 后者取决于完成顺序（本仓硬契约：完成先后不得泄漏进结果）。
    键是路号/页号/下标；空字典不得调用（调用方须先判空）。
    """
    tb = accounted[min(accounted)]
    raise tb[1].with_traceback(tb[2])


def run_ordered(tasks, max_workers, expected=(), on_failure=None, on_bug=None):
    """并发执行 tasks，按输入键归位成功结果并收集局部失败。

    这是三处并发链路（多路检索、翻页、逐条详情）共用的唯一执行机制。
    expected 里的异常类型由调用方按业务政策声明；本模块不 import _net，
    也不预设"什么叫上游故障"。
    """
    results = {}
    failures = {}
    bugs = {}
    if not tasks:
        return results, failures
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn): key for key, fn in tasks.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results[key] = fut.result()
                continue
            except _INTERRUPTS:
                # 人已中断：立即响应，不等收齐（其余 future 由 with 退出时等待）。
                raise
            except expected as e:
                failures[key] = sys.exc_info()
                if on_failure is not None:
                    on_failure(key, e)
                continue
            except BaseException as e:
                # 程序缺陷：按输入键记账（不是完成顺序），响亮穿透。
                bugs[key] = sys.exc_info()
                if on_bug is not None:
                    on_bug(key, e)
                continue
    if bugs:
        _raise_min(bugs)   # 最小键重抛，带原 traceback；确定性，不随调度漂移
    return results, failures
