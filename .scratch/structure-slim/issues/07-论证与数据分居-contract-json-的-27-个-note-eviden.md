<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 04 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-2af26fdf-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:48.457Z -->
<!-- DSH-ASSIGNEES: agent -->
# 07: 论证与数据分居：contract.json 的 27 个 note/evidence 键移出去

**What to build:** `src/kd/contract.json` 20 486 B，其中 9 280 B（45%）在 27 个 `note`/`evidence` 键里。最大的三块：`linkPolicy.evidence` 1 168 B、`search.note` 724 B、`read.note` 626 B。

**Blocked by:** 04

**Status:** closed

- [x] 逐键分类 27 个 `note`/`evidence`：哪些是纯论证（人读）、哪些含代码会读的结构化信息（机器读）。后者留在 `contract.json`
- [x] 新建 `docs/contract-rationale.md`（位置自定，也可拆进 `docs/adr/`），把纯论证类整块搬入，按键路径分节
- [x] `contract.json` 原地留指针：每个被搬走的键留一行形如 `"_note": "见 docs/contract-rationale.md#<anchor>"`，或统一在文件顶部留一个 `rationalePointer` 键
- [x] **顺序要求**：先建新址、再把指针放进原处，不做一次性剪切。每一步之后 `python3 tests/kd_regression.py` 都要绿
- [x] `contract.json` 体积降到 12 000 B 以内
- [x] 检查每条被搬走的论证都有落点：`grep` 原 27 个键的内容在新文件里都能找到；不允许「搬丢了」
- [x] 声明必须有消费者的纪律不破：搬走之后，每个仍留在 `contract.json` 的键仍被代码读（这一条是本仓的核心纪律，见 `_config.py:176`）
- [x] `python3 tests/kd_regression.py` 离线组全绿
- [x] 若某条 `evidence` 被回归用例对着断言（例如链接政策那条），断言改为读新位置，且仍绿

它们记的是「为什么这么定」和实测数字，与「代码要读哪个键」是两种读者。结果是这个文件同时是 schema、变更日志、实测档案；代码读它时把 45% 的字节也读进了内存。

这张票把它们分居：数据留在这里，论证移出去并在原地留指针。判据是「代码会不会读它」。




## 背景

这条最不确定该不该动 —— 架构审查报告里对它标的是「Speculative」。理由：那些 note 正在真实地阻止重复犯错，好几条记着「这里曾经判错过」（例如 `search.note_totalRemoved` 记着 `total: 74` 而 `results: []` 的实测、`linkPolicy.evidence` 记着「只看首跳状态码会双向判错」）。

所以判据不是「文件该不该瘦」，而是「两种读者的内容该不该同处一个字典」。如果逐键分类后发现绝大多数 note 都含代码要读的结构化信息，这张票的正确结论就是**不做**，届时把结论写进票面并关闭。

⚠️ `contract.json` 是包内唯一数据文件（`pyproject.toml` 的 `package-data` 只登记了它），任何新增文件都不进包 —— 所以搬出去的论证必须是 `docs/` 侧的人读文档，不能是运行期依赖。

## 进度

## 进度

**2026-11-17 交付完成(73 通过 / 0 失败)。结论:做,而且分类是干净的。**

### 逐键分类(判据:代码会不会读它)

27 个键里 **26 个是纯论证 + 1 个嵌在父节里的 `note`**(`productIds.evidence.note`,
票面那个 27 = 26 + 1)。用两层证据判的,没有靠读文字猜:

1. **代码侧**:把 `src/kd/**/*.py` 的字符串字面量全抽出来(剥注释保字符串),再拿
   `contract.json` 的每个叶子键名去对。声明里真正被读的键名只有这些:
   `topKeys` / `resultKeysCommon` / `resultKeysByType` / `resultForbiddenKeys` /
   `keysByType` / `conditionalByType` / `truncatedValues` / `rule` / `default` /
   `maxKeywords` / `maxDetail` / `rate`(`burst`/`rps`/`jitterMs`)/ `names` /
   `version`。**27 个 note/evidence 键里,一个都没有。**
2. **用例侧**:唯一对着论证断言的是 `t_link_policy` 的 `lp["evidence"]`(票面点名的
   那一条),别的用例连键名都没出现过。

所以票面背景里那条反向判据(「若绝大多数 note 都含机器读的结构化信息,正确结论是不做」)
**不成立** —— 一个都没有。分类结论:全部搬,没有一条要留。

### 做法(按票面的顺序要求)

1. 先建 `docs/contract-rationale.md`:27 个键**逐字**搬入,一个键一个小节,节标题就是原键路径
   (含 `.`,不改写法)。这一步之后跑套件:72 通过 / 0 失败(新址是纯新增,不动任何东西)。
2. 再往 `contract.json` 顶层放 `rationalePointer`,论证键**原地不动**:仍 72/0。这一步证明
   指针本身是无害增量。
3. 最后才删论证键。删完两条断言按预期红(`t_link_policy` 的 `evidence`、
   `t_numeric_facts_single_home` 的 `otherVisibility` 真源路径),**改成读新址后转绿**。
   全程没有出现过一次"一次性剪切 + 事后找哪条炸了"。

### 体积与落点

| | 之前 | 之后 |
|---|---|---|
| `src/kd/contract.json` | 20 480 B | **2 555 B**(-87%,判据是 < 12 000 B) |
| `docs/contract-rationale.md` | — | 22 138 B(人读,不进安装包) |

「搬丢了」的核对是**逐字**做的,不是抽查:把 27 个键展开成 35 个叶子串,拿每一条原文
去新文件里 `in` 一遍 —— **35/35 命中,零丢失**(9 073 个字符全部落地)。这一次性核对没有
进回归套件,理由写在用例注释里:逐字比对要把 9 073 字原文在 `tests/` 里再存一份,那正是
本票在治的"同一段话两个出生地"。日常回归改为守「节还在 + 正文非空 + 不掉到 20 字以下」。

### 声明必须有消费者(核心纪律)

搬完之后留在声明里的叶子键 21 个,**代码或本套件里都有字面量消费者**,唯一的具名例外是
`productIds.names.*` 五个标签(代码只取 `default`,标签由调用层读、由 `doc-sync-targets.md`
的 `productIds` 重述额度钉子整体比对)。这条判据**下沉到了叶子键**,不只查顶层 ——
只查顶层的话,`search.note_*` 这种"整段没人读"的病照样漏(它就是这么活了两年的)。

### 连带改动(都是"论证搬走"的直接后果,不是顺手)

- `t_link_policy`:证据断言从"声明里有 `evidence`"改成"论证档案的 `### linkPolicy.evidence.<kind>`
  小节存在**且正文非空**"。
- `t_numeric_facts_single_home`:`otherVisibility` 的唯一真源解析改为**两处都找**(声明 / 论证档案同名小节),
  判据仍是"解析后存在"。额度表那一列不改叫法 —— 节标题就是原键路径,同一个名字两个落点。
- `docs/agents/doc-sync-targets.md`:登记新载体 `contract-rationale`(下限 9 → 10)、新事实
  `contract-rationale-pointer`(单箭头判据,写明为什么不要求反向回指)。
- 活指针改指新址:`README` / `GLOSSARY` / `SKILL.md`(两处,原本指向 `productIds.evidence`)/
  `WORD-SPLITTING` / ADR-0017 / ADR-0019 / `docs/tickets/33` / `_config.py` / `_detail.py` /
  `_links.py` 的三处注释。
- 新增回归钉子 `t_contract_rationale_split`(四段:指针解析后存在且不落进技能目录 / 声明里
  不再有论证键 / 新址每节非空且有实质内容 / 剩下的键零消费者即红),以及
  `t_doc_pointers_resolve` 新增的第 ⑥ 段:**契约键路径指针**也要能解析,且不许"说它在
  `contract.json` 里而它已经不在"。

### 反向确认(证明断言不是恒绿)

每条判据都手动破过一次,全部转红、恢复后转绿:① 删 `rationalePointer` ② 指针指向不存在的
文件 ③ 指针落进技能目录 ④ 论证键回流声明 ⑤ 某节正文删空 ⑥ 某节削成一句占位
⑦ `SKILL.md` 写「留证在 `contract.json` 的 `productIds.evidence`」(键已搬走)。
第 ⑦ 条是两轴评审抓出来的:初版第 ⑥ 段只查"这个键能否在**某处**解析到",于是"说错了地方"
照样绿 —— 已收紧到**行级**。

### 已知边界(不假装覆盖)

- 逐字保真是**搬家时一次性核对**的,日常回归只守"节还在、有实质内容"。
- 消费者判据是"字符串字面量出现",本仓没有动态拼键所以有抓取力;将来若出现动态拼键,
  由各键自己的行为用例兜底。
- `rationalePointer` 在第 ④ 段上恒绿(本用例自己算消费者)。它的真判据是第 ① 段
  "解析后存在" —— 注释里写明了,没有把恒绿藏起来。
