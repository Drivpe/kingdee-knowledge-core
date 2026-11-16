<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-STATUS: closed -->
<!-- DSH-BLOCKED-BY: 03, 04 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-5ffd3457-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:34.000Z -->
# 05: SKILL.md 只留流程，拆词规范移出成 reference

**What to build:** `skills/kingdee-knowledge/skills/kingdee-knowledge/SKILL.md` 现 537 行。三步流程（search → read → 合成）占 92 行，而「拆词规范」一节省 162 行（四个维度 / 一句排序原则 / 反例 / 五种固定套路），排在流程中间。

**Blocked by:** 03, 04

**Status:** resolved

- [x] 新建 `skills/kingdee-knowledge/skills/kingdee-knowledge/WORD-SPLITTING.md`，「拆词规范」整节（含四个维度、排序原则、反例、五种固定套路、`--kw` 的实测依据）逐字搬入，不压缩
- [x] SKILL.md 在「清单召回不理想」这条分支上留一句指针（例：清单全是泛词命中、没有精确命中时，读 `WORD-SPLITTING.md` 换词重搜）
- [x] SKILL.md 删掉搬走的 162 行，剩余结构按装载顺序排：定案 → PATH 自举 → 第 1 步 search → 第 2 步 read → 第 3 步合成 → 站外兜底 → 异常处理 → 禁止事项
- [x] 「产品线路由（历史事故记录）」与「产品线语义识别（你的职责）」两节合并：前者是已撤销规则的事故记录，降为一段；后者是每次都要用的判定口径，留在流程里
- [x] SKILL.md 行数降到 300 行以内；`grep -c "拆词"` 在 SKILL.md 里不超过 3（都是指针）
- [x] 票 03 新增的「文件指针目标存在」断言覆盖 `WORD-SPLITTING.md`；删掉该文件后断言必须红
- [x] 装机后 `~/.agents/skills/kingdee-knowledge/` 里含 `WORD-SPLITTING.md`
- [x] 抽查：只读 SKILL.md 的 agent 能走完 search → read → 合成 三步，不需要读 reference。判据是把 `WORD-SPLITTING.md` 临时改名成 `.bak`，按 SKILL.md 走一遍常规问题仍能走通
- [x] `python3 tests/kd_regression.py` 离线组全绿（`t_docs_no_dead_mechanisms` 与挑选判据那条会扫 SKILL.md，同批确认）

按 writing-for-agents 的判据，拆词细则属于**分支材料**：只有「清单召回不理想、要换词重搜」这一条分支才需要它，而它现在压在任何一次全程加载的路上。

这张票把拆词规范移出成 reference，SKILL.md 只留三步流程、指针、硬边界。




## 背景

writing-for-agents 的原话：**inline what every branch needs, push behind a pointer what only some branches reach**。以及前一句：a document with steps, in-file reference that should be disclosed buries them and turns attending to them into a coin-flip。

本仓还有一个具体约束：装机是 `cp -r "$SKILL_SRC/."` 整目录拷，所以文件只要在技能目录内就自动装机。

⚠️ 拆词规范是召回效果的主要变量（ADR-0016 把生成权移交调用层之后，拆词质量全在调用方）。所以是**移动，不是压缩、不是删除** —— 压成 60 行会丢掉实测脚注，删掉等于把召回质量交给运气。

## 做了什么

提交 `b41998c`。

**搬迁是移动,不是压缩。** `WORD-SPLITTING.md`（94 行）承接原「拆词规范」整节：四个维度、
一句排序原则、反例表 4 条（11547 / 15180 / 掉出前 30 / BOM 第 2→第 12）、整句实测表
（第 1 vs 第 23）、`total` 自 v6.9 不再返回的脚注、位次 ±1 抖动脚注,全部在位。
规范化 diff（去掉标题层级与留在 SKILL.md 的收词上限块）**内容差异 0 行**。

只有两处形式调整,都写进了文件开头:
1. 标题降一级（原文 `###` → 这里 `##`）;
2. 「收词上限 7 路」那 4 行**留在** `SKILL.md` 的参数速查 —— 那个数字只许有一个出生地
   （票 04 的额度表登记 `maxKeywords` 文档侧额度 = 1 份）。

**SKILL.md 485 → 299 行**,按装载顺序重排:定案 → PATH 自举 → 三步 → 站外兜底 → 异常
→ 禁止事项。`grep -c 拆词` = **1**,那一处就是指针,且落在**第 2 步「挑选判据」第 6 条**
（读清单不顺手的那一刻）,不是文件里随便哪处。

**产品线两节合并成「产品线判定」**,作为第 1 步的子节留在流程里（判定发生在传 `--product`
之前,却排在 search 语法之后 —— 这是唯一的妥协,理由是它必须和 `--product N` 的值域说明挨着）。
事故记录降为一段 blockquote,事实一件没少。候选项规模的实测数字退成指针,留证在
`contract.json` 的 `productIds.evidence`,文档侧不再有第二个出生地。

### 判据实测

| 判据 | 读数 |
| --- | --- |
| 离线组 | **71 通过 / 0 失败**（开工基线 71/0,不回退）|
| 变异:删掉 `WORD-SPLITTING.md` | **69 通过 / 2 失败** → 还原 71/0 |
| 变异:指针挪出第 2 步（塞进「禁止事项」）| **70 通过 / 1 失败** → 还原 71/0 |
| `SKILL.md` 行数 | 485 → **299**（票面要求 < 300）|
| `grep -c 拆词` | **1**（票面允许 ≤ 3）|
| 抽查:reference 改名 `.bak` 后走三步 | `kd search` → ok / 9 条 / `effectiveProductId=93`;`kd read` → 正文 3393 字;**三步不依赖 reference** |
| 装机 | `~/.agents/skills/kingdee-knowledge/` 四份齐（含 `WORD-SPLITTING.md`),`diff -r` 与源目录 **IDENTICAL** |

### 守卫加了两条（都是评审实测出来的洞）

- `t_doc_pointers_resolve` 的扫描面扩到 `WORD-SPLITTING.md`,并把基线计数 6 → 10（实际 11）。
- **新增「指针必须落在第 2 步那一节内」**。原来只判「文件里出现过」,实测把指针从第 2 步
  删掉、塞进末尾「禁止事项」**照样绿** —— 而票面要求的是「在**清单召回不理想**这条分支上」。
  现在按所在小节判,上面第二组变异就是它的证据。
- 载体清单登记 `WORD-SPLITTING`（`retired-mechanisms`）:它是 agent 真会照抄的 `kd` 示例,
  理由与安装脚本进同一档相同;下限 8 → 9,并在清单里写明**为什么是它进来**。

⚠️ `CITATION-EVIDENCE.md` **没有**一并纳入指针钉子,这是刻意的:它那三条 `docs/research/*.md`
是仓库内取证档,文件自己就写明「不随装机」;算它们断链的唯一修法是删掉那三条留证 ——
拿守卫去消灭证据。理由写进了用例 docstring,免得下一个人以为是漏了。

### 票面数字更正

票面写「「拆词规范」一节省 162 行」**与实测不符**:逐版本量（`## 拆词规范` 到 `### 第 2 步`
的行距）536 行版 = 90、484 行版 = 90、485 行版 = 91。162 既非该节长度,也非净删行数（净删 186）。
验收以 **91** 为准。

### 评审后修正（两轴评审,均已落进同一提交）

**误删 5 条行为规则,已逐条找回。** 合并两节时把它们连带压掉了,全仓无副本:
「切换产品线时在答案里说清楚」、「产品过滤对每一路都生效」、「给确认渠道」、
「单条 hitRoutes 高但内容泛 ⇒ 别当权威依据」、「或精简后重搜」。这不是搬走的那一节,
是顺带压缩 —— 票面明说「移动不是压缩、不是删除」,这一条差点被自己违反。

另外三条:

- `kd health` 的说明从「预算上限」改成它实际回吐的字段（`maxKeywords`/`rateProfile`/`textMax`）
  —— 预算机制 v6.6 已删,而 SKILL.md 是 `retired-mechanisms` 载体。
- 指针措辞「复测数字留证在 `contract.json`」**不准确**:声明里只有 10/10 与 9/9,
  889 / 11104 / 1127 并不在那里。改成按事实分开写,并把「候选集规模不作判据」说清。
- `WORD-SPLITTING.md` 开头原写「逐字搬入」,**与事实不符**（有 5 处标题降级 + 收词上限块未随迁）。
  改成如实说明那两处形式调整,否则后来人拿这句话当核对依据会先撞上 5 处差异。

### 一处判断(不是漏做)

**ADR 里的旧地址没改。** `docs/adr/0009` 与 `0016` 共 5 处仍写「拆词规范住在 SKILL.md」。
规格的 Out of Scope 明令「**不动 ADR / specs / tickets / research 的正文**——它们被按编号引用」,
票 03 的评审也就同一形态做过同样处置。ADR 记的是**当时**的决策语境,地址跟着搬家会改写历史叙事;
真源现在是 `WORD-SPLITTING.md` 本身与 `AGENTS.md`/README/GLOSSARY 里那 9 处活指针。

## 进度

- 进度：100%（2026-11-16T15:35:00+08:00）：拆词规范整节搬入 `WORD-SPLITTING.md`（逐字，规范化 diff 内容差异 0 行）；SKILL.md 485 → 299 行、`grep -c 拆词` = 1 且落在第 2 步；产品线两节合并为「产品线判定」（事故记录降为一段 blockquote）；守卫扩扫描面并新增「指针必须在第 2 步内」的位置判据；载体清单登记 WORD-SPLITTING（下限 8→9）；变异两组均红、还原 71/0；装机四份齐且 `diff -r` IDENTICAL；抽查 reference 改名 `.bak` 后三步仍走通；评审后找回误删的 5 条规则。提交 `b41998c`。收口。

## Comments

### local — 2026-11-16T15:35:00.000Z

交付完成。核心读数：`WORD-SPLITTING.md` 94 行（原节 91 行 + 搬迁说明），规范化 diff 内容差异 0 行；
`SKILL.md` 485 → 299 行，`grep -c 拆词` = 1（就是指针，落在第 2 步「挑选判据」第 6 条）；
产品线两节合并成「产品线判定」并作为第 1 步的子节。

守卫两条新增：
① `t_doc_pointers_resolve` 扫描面扩到 `WORD-SPLITTING.md`，基线计数 6 → 10（实际 11）；
② 指针必须落在「第 2 步」那一节内 —— 原来只判「文件里出现过」，实测把指针塞进末尾
   「禁止事项」照样绿（评审实测），而票面要求的是「在清单召回不理想这条分支上」。

变异验证（均已还原）：删掉 `WORD-SPLITTING.md` → 69/2 红；指针挪出第 2 步 → 70/1 红；还原 71/0。

评审后修正：合并两节时误删的 5 条行为规则（切换产品线要在答案里说清 / 产品过滤对每一路都生效 /
给确认渠道 / `hitRoutes` 泛文别当权威 / 或精简后重搜）已逐条找回；`kd health` 的说明
从已删的「预算上限」改成实际回吐的字段；「复测数字留证在 contract.json」那句不准确，已按事实改写。

票面数字更正：原写「拆词规范一节省 162 行」与实测不符，逐版本量都是 91 行，验收以 91 为准。
