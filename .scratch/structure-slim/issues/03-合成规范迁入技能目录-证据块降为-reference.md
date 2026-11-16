<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 01 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-ad8fcb9d-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:21.016Z -->
# 03: 合成规范迁入技能目录，证据块降为 reference

**What to build:** `docs/ANSWER-SPEC.md`（176 行）自称「合成回答格式的单一事实源」，而装机脚本只拷 `skills/kingdee-knowledge/skills/kingdee-knowledge` 整目录（`install.sh:190-198` 的 `SKILL_SRC` + `cp -r "$SKILL_SRC/."`），`docs/` 不在拷贝范围。SKILL.md 在八处引用它，客户端 agent 照指针走过去是空的。

**Blocked by:** 01

**Status:** resolved

- [x] 新建 `skills/kingdee-knowledge/skills/kingdee-knowledge/ANSWER-SPEC.md`，内容为现 `docs/ANSWER-SPEC.md` 全文
- [x] 同一目录新建 `CITATION-EVIDENCE.md`，把现文里那段 `url_effective` 重定向实测证据（含三档 `knowledge`/`article`/`question` 的可点性数字、`/school/detail/<id>` 同型第五例、被迁移成知识文档的那条、以及「登录态假阴性」那段）整块搬进去；ANSWER-SPEC 里在原位留一行指针
- [x] 删除 `docs/ANSWER-SPEC.md`（`git rm`），全仓指针从 `docs/ANSWER-SPEC.md` 改为技能目录内路径
- [x] `tests/kd_regression.py:2819`（`t_answer_spec_diagnostics_wording`）与 `:4263`（挑选判据归属那条）的路径常量改为新位置，两条用例仍绿
- [x] SKILL.md 里「三段式 / 原因分析 / 根因引用规则 / 来自社区经验 / otherSkipped」这几处复述收成：流程节一句「按 ANSWER-SPEC 写」加指针，形态细节只在 ANSWER-SPEC 里存在一次。判据是 `grep -c "三段"` 在 SKILL.md 里降到 1
- [x] SKILL.md 里八处 `ANSWER-SPEC` 指针全部指向技能目录内的新路径
- [x] `t_docs_no_dead_mechanisms` 的载体清单（票 01 建的）里，ANSWER-SPEC 那条路径同步更新
- [x] 新增一条断言：SKILL.md 与 AGENTS.md 里每一条形如 `` `path/to/file.md` `` 的文件指针，目标文件必须真在盘上。删掉新 ANSWER-SPEC 后此断言必须红
- [x] `install.sh` 与 `install.ps1` 末尾那句 `echo "再由你按 docs/ANSWER-SPEC.md 自己合成。"` 改为技能目录内的相对说法（客户端读的是 SKILL.md，不是仓库路径）
- [x] 装机后 `~/.agents/skills/kingdee-knowledge/` 里含 `SKILL.md`、`ANSWER-SPEC.md`、`CITATION-EVIDENCE.md` 三份（本机当前没有这个目录，需先跑一次 install.sh 验证）

本机实测：`~/.agents/skills/` 这个目录根本不存在 —— 这份技能一次都没装上过，所以这个断链从未被任何东西发现。

这张票把合成规范迁进技能目录，并把 SKILL.md 里散落的四份复述收成一处加指针。




## 做了什么

提交 `762031e`（`install.sh` / `install.ps1` 各一处指针改写落在 `f5d6cd1`，与本票同批但不是同一提交）。

- 新建技能目录内的 `ANSWER-SPEC.md`（原 docs 全文，删掉证据块后 175 → 167 行），
  `git rm docs/ANSWER-SPEC.md`
- 同目录新建 `CITATION-EVIDENCE.md`（43 行）：`url_effective` 判定规则、三档复测数字
  （14/14、12/12、22/22 —— 从原表格的「匿名复测」列移出）、三个反例（question 最终 200 落到
  404 页、`/school/detail/<id>` 同型第五例、`article/248777993676668672` 被迁移成知识文档）、
  登录态假阴性那段。ANSWER-SPEC 原位留一行指针，指到同目录的这个文件
- SKILL.md：第 3 步的「答案形态」五条 + 那个 36 行 `text` 代码块（合成规范全文复述）+ 末尾
  「## 回答规范」整节，收成一句「按同目录 `ANSWER-SPEC.md` 写」加指针，另只留三条**流程侧**
  提醒（结论先行 / 照抄 `url` / 反问澄清）。`wc -l` 536 → 484
- 指针迁移：README 6 处、GLOSSARY、SKILL.md 全篇（改成裸文件名，因为就在同目录）、
  `src/kd/cli.py` 的 `--help` 文案（只改字符串，不改行为）、`docs/agents/doc-sync-targets.md`
  的载体路径、`tests/kd_regression.py` 两处路径常量
- 新增钉子 `t_doc_pointers_resolve`：扫 `AGENTS.md` 与技能目录 `SKILL.md` 里每条形如
  `` `path.md` `` 的指针，先按被扫文件目录、再按仓库根解析，**解析不到就红**；模板占位、
  家目录、URL 三类豁免。顺带把 AGENTS.md 那句裸 `spec.md` 改成完整模板路径 —— 否则
  裸文件名本身会被这条钉子判成断链

### 判据实测

| 判据 | 结果 |
| --- | --- |
| 离线组 | **70 通过 / 0 失败**（票 02 后基线 69，新增一条钉子）|
| 变异：把新 ANSWER-SPEC.md 移走 | **65 通过 / 5 失败**（新钉子 + 三条读该文档的旧钉子 + 载体路径）→ 还原后 70/0 |
| `grep -c 三段`（SKILL.md）| 2 → **1** |
| `grep -c 原因分析` | 4 → **1** |
| `grep -c 社区经验` | 4 → **1** |
| residual `docs/ANSWER-SPEC` | 历史目录（ADR/specs/tickets/research）之外零命中 |
| 装机 | `bash install.sh --root /tmp/kd-verify-root --no-path --no-verify --harness agents` → `~/.agents/skills/kingdee-knowledge/` 里 `SKILL.md` / `ANSWER-SPEC.md` / `CITATION-EVIDENCE.md` **三份齐** |

### 一处判断（不是漏做）

票面把 `otherSkipped` 也列进「复述」。但它在本仓落在两个不同位置：ANSWER-SPEC 第 5 条讲
「判定置信度时它是什么信号」，SKILL.md 第 2 步讲「读清单时看到它该做什么」——后者是**流程**，
要在票 05 把拆词规范移出时一起收。故 SKILL.md 里仍有 7 处 `otherSkipped`，都在读清单 / 诊断
这几条路上，属流程材料而非合成形态复述。

### 评审后修正(提交 `21d38d9`)

两轴评审(Standards / Spec)指出这条钉子**能红,但红的有时不是它自称要守的那件事**。四处已改:

- **值改成双向比对**:原判据用声明值拼正则数命中次数,文档把数字写错时压根命中不了,计数掉到 0
  反而更绿(实测「收词上限 7 路改成 8」仍是 71/0)。现在把文档里写出来的具体值与声明逐个比
- **判据不再手抄常量**:`maxKeywords` 的数值、`truncated` 的枚举串都从声明读,与同文件既有纪律一致
- **额度表改用 `_walk_pipe_table`**:坏行 `raise Fail` 不静默跳过;四项事实必须都登记(原来只硬编码
  三项,删掉 `otherVisibility` 那一行照样绿)
- **把 `kd --help` 与 `_public.py` 的 docstring 纳入值比对**(不进额度):`--help` 是 agent 的第一条
  命令,而它把 `1` 写成「企业版/标准版」,与声明不符 —— 这正是本票要治的形态,原来的扫描面看不到它

变异复验(每组单独施加、跑完即还原):README 标签写错 → 红;SKILL 收词上限 7→8 → 红;
`--help` 标签写错 → 红;ANSWER-SPEC 的 `1` 写错 → 红;删额度表一行 → 红;SKILL.md 指向仓内非装机
文件 → 红。还原后 71/0。

评审另提三条**没做**,理由:① 把指针钉子扩到 reference 层会让 `CITATION-EVIDENCE.md` 里那三条
「仓库内取证档,不随装机」的路径变红 —— 它们已显式标注不随装机,扩了就要删;② ADR 头部「关联」
行仍写着已删的旧路径,spec 明令不动 ADR 正文;③ 装机完整性(跑完 install 再断言)仍未做成一条钉子。

## 背景

manifest 层的事实：`SKILL_SRC="$REPO/skills/kingdee-knowledge/skills/kingdee-knowledge"`，`cp -r "$SKILL_SRC/."` 整目录拷。所以只要文件在技能目录内，就自动装机，且它属于 writing-for-agents 的「disclosed reference」层——占指针的一行，不占每次全程加载的额度。

被搬走的证据块约 30 行，它只在「链接看起来不对」这一条分支上才需要，不该占常驻额度。

⚠️ ANSWER-SPEC 与 SKILL.md 里 `linkPolicy` 都指向 `contract.json`，那条指针保持不动 —— 它是链接政策唯一的真源，且代码真的读它。

## Comments

### local — 2026-11-16T13:26:00.000Z
ANSWER-SPEC 与 CITATION-EVIDENCE 落进技能目录、docs 旧路径 git rm；SKILL.md 两处复述收成一句指针（grep -c 三段 2 → 1，文件 536 → 484 行）；新增 t_doc_pointers_resolve 并做变异验证（移走 ANSWER-SPEC → 65 通过 / 5 失败）；装机后 ~/.agents/skills/kingdee-knowledge/ 三份齐。

## 进度

- 进度：100%（2026-11-16T13:26:00+08:00）：合成规范迁入技能目录、证据块降为 reference、SKILL.md 复述收成指针、新增指针存在性钉子（含变异验证）、装机三份齐；离线组 70/0；提交 762031e；收口
