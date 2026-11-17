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
| `ANSWER-SPEC` | `skills/kingdee-knowledge/skills/kingdee-knowledge/ANSWER-SPEC.md` | `link-policy`, `retired-mechanisms` |
| `SKILL.md` | `skills/kingdee-knowledge/skills/kingdee-knowledge/SKILL.md` | `link-policy`, `retired-mechanisms` |
| `WORD-SPLITTING` | `skills/kingdee-knowledge/skills/kingdee-knowledge/WORD-SPLITTING.md` | `retired-mechanisms` |
| `README` | `README.md` | `link-policy`, `link-policy-pointer`, `retired-mechanisms` |
| `GLOSSARY.md` | `GLOSSARY.md` | `link-policy`, `link-policy-pointer`, `retired-mechanisms` |
| `_upstream.py` | `src/kd/_impl/_upstream.py` | `link-policy` |
| `_links.py` | `src/kd/_impl/_links.py` | `link-policy` |
| `install.sh` | `install.sh` | `retired-mechanisms` |
| `install.ps1` | `install.ps1` | `retired-mechanisms` |
| `__init__.py` | `src/kd/__init__.py` | `retired-mechanisms` |
| `core.py` | `src/kd/core.py` | `retired-mechanisms` |
| `contract-rationale` | `docs/contract-rationale.md` | `contract-rationale-pointer` |

`_upstream.py` 与 `_links.py` 都收着链接论证:前者是条目归一化时保留上游 `url` 的那一段,
后者是模板 / 必需段 / 回答号选取 / 政策闸门。两个都进表,是因为 2026-10-01 的 K1 把论证
搬了家而钉子照着旧地方照过 —— 一处论证在谁身上,表里就得有谁。

`WORD-SPLITTING` 是 **2026-11-16(票 05)新增的载体**,下限随之从 8 抬到 9。它进的是
`retired-mechanisms`:它是**用户（agent）真会照抄的 `kd search` 示例**（「固定套路」一节的
两条命令），而 2026-09-28 那批拆除留下的已删参数与已删机制，一旦回写进示范命令，
agent 照抄就是 argparse 退出码 2。这和安装脚本进本档的理由是同一个：**会被照抄的地方就得在册**。
它不挂 `link-policy`：讲拆词的那个文件不承担「链接给不给」的表态职责。

安装脚本与包文档进的是 `retired-mechanisms`:安装脚本末尾的"试一试"是用户装机后第一眼
看到的用法,照抄必撞 argparse 退出码 2,所以它和主文档同等重要。

`contract-rationale` 是 **2026-11-17(票 07)新增的载体**,下限随之从 9 抬到 10。它进的是
`contract-rationale-pointer`:论证与实测从 `contract.json` 搬来之后,这份文件成了「为什么这么定」
的唯一所在地,而**它自己必须被指向**。判据是**单箭头的**:`contract.json` 的 `rationalePointer`
必须解析到它、且它不得落进技能目录(装机单元只拷技能目录)。反向不要求 —— 表里那份载体清单
是本仓内部的维护地图,它指向 `docs/` 侧文件是常态(`link-policy` 那几条同理),拿一份仓库侧
文档去要求仓库根文档回指,只会逼出一堆为了满足判据而存在的指针。

`README` 与 `GLOSSARY.md` 额外挂着 `link-policy-pointer`:它们不只是"口径别写反",还必须
**明确指向**唯一真源。这两份历史上都自己另立过一套(README 写"引用做成可点击角标";
术语表断言 `linkPolicy.question` 仍为 `no-link`),所以对它们的要求比别的载体高一层。
内核两个 `.py` 只在注释里论证政策,不承担"给读者一个指针"的职责,故不进这一档。

## 事实表

| 事实 id | 唯一真源 | 载体数下限 | 一致性判据(由哪条钉子执行) |
| --- | --- | --- | --- |
| `link-policy` | `src/kd/contract.json` 的 `linkPolicy` | 6 | 载体不得留着未标废止的旧口径;每份载体按 kind 分档说明 |
| `link-policy-pointer` | 同上 | 2 | 载体里存在一行**活的**指针:同一行既有 `linkPolicy` 又有 `contract.json`,且不在版本史段落里 |
| `contract-rationale-pointer` | `src/kd/contract.json` 的 `rationalePointer` | 1 | 该指针解析出的文件真在盘上、且不在技能目录里(由 `t_contract_rationale_split` 的 ① 段执行) |
| `retired-mechanisms` | `src/kd/cli.py` 的 argparse 定义(现行开关)+ `docs/adr/0016-检索词生成权移交调用层.md`(为什么删) | 9 | 载体不得出现"现在可以这样用"形态的已删参数与已删数据文件;说明变更的段落须带变更标记词 |

四条事实对应**三条**钉子:`link-policy` 与 `link-policy-pointer` 都由
`t_link_policy_docs_in_sync` 执行,`retired-mechanisms` 由 `t_docs_no_dead_mechanisms`
执行,`contract-rationale-pointer` 由 `t_contract_rationale_split` 执行(票 07)。
一个用例执行两条事实是正常的 —— 它们查的是同一批载体的不同侧面。

⚠️ `contract-rationale-pointer` **不**走 `_sync_targets()` 取载体:它的载体是"指针解析出来的
那一份",路径只存在于 `contract.json` 的 `rationalePointer` 里。若在这里再写一遍路径,就制造
了第二个出生地 —— 改名时两处不同步,红的又是守卫而不是它要守的东西。

**载体数下限**是防「载体表被删掉一行」的闸。光靠列举拦不住:少一行就少扫一份文件,
扫描本身不会报错,而少扫这件事没有任何可见信号。下限把"少扫"变成一条失败:
2026-11-11 实测 —— 删掉术语表那一行,两条钉子同时以「登记了下限 6 份载体,清单里
只剩 5 份」红。确实要摘掉一份载体时,把下限一起改小,并在这里写一句它当初是因为
哪次漂移进来的。

事实 id 与钉子按上面的对应关系挂接。新增一条一致性判据时,这里登记一行,
再让钉子用 `_sync_targets("<事实 id>")` 取载体。钉子拿不到载体、或拿到的比下限少,
都会红 —— 扫了个空还显示绿是这份清单最不能出现的结果。

## 数字类事实与重述额度

**这一节治的是「同一个数字有六个出生地」。** 2026-11-11 实测：`productLineId` 的中文标签在
README 与 ANSWER-SPEC 之间已经对不上（`1` 一处写「星空企业版/标准版」、一处写「企业版标准版」），
而两份都自称权威。判据不是「对齐一次」，是**额度**：每项数字类事实在文档侧的出生地数上限登记在
下面这张表里，由 `t_numeric_facts_single_home` 执行，超一处就红。

额度不是零，是因为**装机侧的 agent 读不到仓库**：装机只带走技能那一个目录，`SKILL.md` 与
`ANSWER-SPEC.md` 必须留下可执行的那一处，否则 agent 拿不到「上限是几」「87 是哪条线」。
仓库根的两份（README / GLOSSARY）是维护者与 CLI 读者看的，额度更紧。

| 事实 id | 唯一真源（声明键） | 文档侧额度（份） | 现行重述位置 |
| --- | --- | --- | --- |
| `maxKeywords` | `src/kd/contract.json` 的 `limits.maxKeywords` | 1 | `SKILL.md` 的「收词上限」那一段（说明行带数字，指针在相邻行；计数按文档份） |
| `productIds` | `src/kd/contract.json` 的 `productIds.names` | 3 | `README.md`（CLI 速查）/ `ANSWER-SPEC.md`（值→含义表）/ `SKILL.md`（产品线判定节） |
| `truncatedValues` | `src/kd/contract.json` 的 `read.truncatedValues` | 2 | `ANSWER-SPEC.md`（反例节，既有钉子要求它在）/ `SKILL.md`（逐档行动表） |
| `otherVisibility` | `docs/contract-rationale.md` 的 `search.note_otherSkipped` | 4 | `README.md`（`otherSkipped` 字段说明）/ `GLOSSARY.md`（other 档词条）/ `SKILL.md`（`--include-other` 触发条件）/ `ANSWER-SPEC.md`（判定信号） |

两条纪律：

1. **额度的分母是「份」不是「行」** —— 一份文档里写三遍和写一遍同罪，读者不会数第二遍；
   但换一份文档就是换一个读者，所以要分开算。
2. **降重述的写法只有两种**：指向声明键，或标「历史数字 / 旧口径」并说明现行值去哪看。
   第三种只有一个：这一处就是那唯一一处正文说明 —— 它必须带指针，否则读者不知道权威在哪。

⚠️ `linkPolicy` **不在本表**：它的判据比额度更强（载体表 + 按 kind 的极性比对 + 活指针），
由 `t_link_policy_docs_in_sync` 执行，登记在本文件的「事实表」里，不在这里重复计一遍。
⚠️ `otherVisibility` 目前**只有散文声明**（`search.note_otherSkipped` 解释「隐藏必须可见」），
没有一个可执行的布尔键 —— 这是已知的洞，额度先按现状登记；把它提升成真正的声明键时本表同步收窄。
2026-11-17（票 07）起它的出生地是 `docs/contract-rationale.md` 的同名小节：**散文归论证档案，
声明只留代码会读的键**。`t_numeric_facts_single_home` 解析「唯一真源」时会两处都找（见该用例注释）。
