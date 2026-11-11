# 文档同步载体清单

**这份表是「哪些文档必须与哪份唯一真源保持一致」的唯一登记处。** 回归套件里的两条同步钉子
(`t_link_policy_docs_in_sync` / `t_docs_no_dead_mechanisms`)不再各自写死文件名,而是遍历本表:
载体改名、搬家、新增、摘除,都只改这里对应的那一行。

为什么要有它:2026-11-11 `CONTEXT.md` 改名 `GLOSSARY.md` 之后,两条用例仍读旧路径,离线组是
67 通过 / 2 失败,而那个被改名保护起来的文件**没有任何测试在读它**。改名本身不该打断守卫;
该打断守卫的是载体与真源之间的真实漂移。清单只有一条记录写着术语表文件名,所以以后再改名
只改这一条。

加一条新载体的判据:**它里面有一句断言,能被真源证伪**。只是提到某个词不算同步点。
摘掉一条载体时先问一句:它当初是因为哪次真实漂移被加进来的。

## 载体表

| 载体名 | 相对路径 | 必须与唯一真源一致的事实 |
| --- | --- | --- |
| `ANSWER-SPEC` | `docs/ANSWER-SPEC.md` | `link-policy`, `retired-mechanisms` |
| `SKILL.md` | `skills/kingdee-knowledge/skills/kingdee-knowledge/SKILL.md` | `link-policy`, `retired-mechanisms` |
| `README` | `README.md` | `link-policy`, `link-policy-pointer`, `retired-mechanisms` |
| `GLOSSARY.md` | `GLOSSARY.md` | `link-policy`, `link-policy-pointer`, `retired-mechanisms` |
| `_upstream.py` | `src/kd/_impl/_upstream.py` | `link-policy` |
| `_links.py` | `src/kd/_impl/_links.py` | `link-policy` |
| `install.sh` | `install.sh` | `retired-mechanisms` |
| `install.ps1` | `install.ps1` | `retired-mechanisms` |
| `__init__.py` | `src/kd/__init__.py` | `retired-mechanisms` |
| `core.py` | `src/kd/core.py` | `retired-mechanisms` |

`_upstream.py` 与 `_links.py` 都收着链接论证:前者是条目归一化时保留上游 `url` 的那一段,
后者是模板 / 必需段 / 回答号选取 / 政策闸门。两个都进表,是因为 2026-10-01 的 K1 把论证
搬了家而钉子照着旧地方照过 —— 一处论证在谁身上,表里就得有谁。

安装脚本与包文档进的是 `retired-mechanisms`:安装脚本末尾的"试一试"是用户装机后第一眼
看到的用法,照抄必撞 argparse 退出码 2,所以它和主文档同等重要。

`README` 与 `GLOSSARY.md` 额外挂着 `link-policy-pointer`:它们不只是"口径别写反",还必须
**明确指向**唯一真源。这两份历史上都自己另立过一套(README 写"引用做成可点击角标";
术语表断言 `linkPolicy.question` 仍为 `no-link`),所以对它们的要求比别的载体高一层。
内核两个 `.py` 只在注释里论证政策,不承担"给读者一个指针"的职责,故不进这一档。

## 事实表

| 事实 id | 唯一真源 | 载体数下限 | 一致性判据(由哪条钉子执行) |
| --- | --- | --- | --- |
| `link-policy` | `src/kd/contract.json` 的 `linkPolicy` | 6 | 载体不得留着未标废止的旧口径;每份载体按 kind 分档说明 |
| `link-policy-pointer` | 同上 | 2 | 载体里存在一行**活的**指针:同一行既有 `linkPolicy` 又有 `contract.json`,且不在版本史段落里 |
| `retired-mechanisms` | `src/kd/cli.py` 的 argparse 定义(现行开关)+ `docs/adr/0016-检索词生成权移交调用层.md`(为什么删) | 8 | 载体不得出现"现在可以这样用"形态的已删参数与已删数据文件;说明变更的段落须带变更标记词 |

三条事实对应**两条**钉子:`link-policy` 与 `link-policy-pointer` 都由
`t_link_policy_docs_in_sync` 执行,`retired-mechanisms` 由 `t_docs_no_dead_mechanisms`
执行。一个用例执行两条事实是正常的 —— 它们查的是同一批载体的不同侧面。

**载体数下限**是防「载体表被删掉一行」的闸。光靠列举拦不住:少一行就少扫一份文件,
扫描本身不会报错,而少扫这件事没有任何可见信号。下限把"少扫"变成一条失败:
2026-11-11 实测 —— 删掉术语表那一行,两条钉子同时以「登记了下限 6 份载体,清单里
只剩 5 份」红。确实要摘掉一份载体时,把下限一起改小,并在这里写一句它当初是因为
哪次漂移进来的。

事实 id 与钉子按上面的对应关系挂接。新增一条一致性判据时,这里登记一行,
再让钉子用 `_sync_targets("<事实 id>")` 取载体。钉子拿不到载体、或拿到的比下限少,
都会红 —— 扫了个空还显示绿是这份清单最不能出现的结果。
