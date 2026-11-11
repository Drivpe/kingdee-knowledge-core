<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-IDEMPOTENCY-KEY: deck-91c82b9f-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:09.241Z -->
<!-- DSH-ASSIGNEES: agent -->
# 01: 止血：同步载体从清单读，后端声明对齐本地 markdown

**What to build:** 离线回归组现在是 67 通过 / 2 失败。两条失败同一成因：`CONTEXT.md` 已改名 `GLOSSARY.md`（暂存区 `R`），而 `tests/kd_regression.py:2746` 与 `:4336` 仍把旧路径写死在 `files` 字典里。后果不只是红——那个被改名保护起来的文件，现在没有任何测试在读它。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 新建同步载体清单（`docs/agents/doc-sync-targets.md`），逐条列出：载体名、相对路径、它必须与唯一真源保持一致的哪个事实
- [x] `t_link_policy_docs_in_sync` 的 `files` 字典改为遍历清单，用例正文里不再出现 `os.path.join(REPO, "...")` 形式的载体路径字面量
- [x] `t_docs_no_dead_mechanisms` 的 `files` 同上
- [x] 清单里那条术语表记录的路径写成 `GLOSSARY.md`；改回 `CONTEXT.md` 后两条用例必须红（实测 67 通过 / 2 失败）
- [x] 把清单里某份载体的真实漂移造出来，必须红 —— **实测只红一条**，见下方「与票面不符的一处」
- [x] `python3 tests/kd_regression.py` 离线组全绿，通过数不少于 67（实测 69 通过 / 0 失败）
- [x] `docs/agents/issue-tracker.md` 的标题行为 `# Issue tracker: Local Markdown`，正文与随包模板 `setup-matt-pocock-skills/issue-tracker-local.md` 逐句一致（`diff` 为空，sha256 相同）
- [x] `docs/agents/triage-labels.md` 去掉 `gh` 语境，改为本地文件里 `Status:` 行的取值说明
- [x] `AGENTS.md` 的 `### Issue tracker` 一行改为本地 markdown + `.scratch/`，不再提 GitHub 与 `gh` CLI

这张票把它修成「改名不再能打断守卫」：把同步载体从两条用例里的字面量，提成一份显式的清单文件，断言遍历清单。清单里只有一条记录写着术语表文件名，所以以后再改名只需改这一条。

同批把后端声明对齐到本地 markdown：`docs/agents/issue-tracker.md` 的标题行、`docs/agents/triage-labels.md` 里残留的 `gh label create` 语境、以及 `AGENTS.md` 的 `### Issue tracker` 那一行，都还是 GitHub 口径。

## 做了什么

提交 `6f4fe71`（提交信息里记着完整判据与实测数字；评审后的判据重写也在这一个提交里）。

**清单**是 `docs/agents/doc-sync-targets.md`：载体表（名 / 相对路径 / 它背哪几条事实）+ 事实表（事实 id / 唯一真源 / 载体数下限 / 判据由哪条钉子执行）。三条事实挂两条钉子 —— `link-policy` 与 `link-policy-pointer` 都由 `t_link_policy_docs_in_sync` 执行，`retired-mechanisms` 由 `t_docs_no_dead_mechanisms` 执行。载体路径的拼接与存在性断言只在 `_sync_targets()` 一处发生。

**载体数下限**是这次额外加的一道闸。光靠列举拦不住退化：载体表少一行，扫描本身不会报错，只是少扫一份文件，而少扫没有任何可见信号。下限把这件事变成一条失败——删掉术语表那行，两条钉子同时以「登记了下限 6 份载体，清单里只剩 5 份」红。

**指针判据从字符串改成了指针。** 原写法 `ok("linkPolicy" in txt)` 是这次两轴评审推翻的：术语表第 48 行是 6.5 版本史，那句同样含 `linkPolicy`，于是把所有活指针删光之后它照样绿。规格 US19 要的本来就是「指针目标存在」而不是「字符串出现过」。现在要求存在一行活的指针：同一行既有 `linkPolicy` 又有 `contract.json`，且不在版本史段落里，并核对真源里真有这个键。

**新增极性判据。** 原有 `stale` 词表只认几句已知措辞，换种说法写错就完全逃过——实测往 README 写「knowledge 与 article 不给链接，只有 question 给」，两条全绿，而那句话与声明方向相反。现在按 kind 分段比对 `contract.json` 的 `linkPolicy.rule`；记录旧口径被判错的段落（「更正 / 原先 / 错因」等）整段豁免，那些是防再犯的凭证。

**术语表补了两个词条**：「同步载体」与「钉子」。新清单整篇建立在这两个词上，而它们此前只有约定俗成的用法、没有定义。

## 与票面不符的一处

票面要求「造一份载体的真实漂移 → **两条用例必须红**」。实测做不到，也不该做到：两条钉子守的是两条不同事实（链接政策 / 已删机制），一份载体的链接政策漂移只该让守链接政策的那条红。让两条同时红只能注入两类互不相关的漂移——那是凑数，不是验收。

按「漂移必须被抓住」这个真实意图，实测如下（每项单独施加、跑完即还原）：

| 注入 | 结果 |
| --- | --- |
| 清单里术语表路径改回 `CONTEXT.md` | 67 / **2** 红（两条都以载体不存在报错） |
| README 写反向链接政策（单一漂移） | 68 / **1** 红（link-policy 那条，指名 `article` 与声明相反） |
| 删掉载体表里术语表那一行 | 67 / **2** 红（下限闸） |
| 抹掉术语表所有活指针、保留版本史里的提法 | 68 / **1** 红（pointer 那条） |
| 删掉清单文件本身 | 67 / **2** 红 |

结论：改名不再打断守卫（改清单一行即可），而真实漂移逐项被抓住。票面那句「两条同时红」是判断失误，已按上表替代。

## 另外两件

评审还指出票的「背景」有一处前提是错的：`docs/agents/workspace.yaml` 在本次提交前**并不存在**（`git show 0b7c217:docs/agents/workspace.yaml` 报不存在），它是随后端切换一起新出现的未跟踪文件。本票没有把它纳入提交——它属另一批改动，仍在工作区等 UUID 决定归属。

同批落下了改名级联（`CONTEXT.md` → `GLOSSARY.md`、`domain.md` 与 `AGENTS.md` 的 GLOSSARY 指针）。这不是本票新增的范围，而是不自洽就没法提交：75 行文件照旧引一个已不存在的路径，提交完仓库就带着一条死链。

## 背景

`tests/kd_regression.py:2746` 与 `:4336` 是仅有的两处载体路径字面量。全仓 `CONTEXT.md` 的残留引用共 60 余处，但绝大多数在 ADR / specs / tickets / research 与注释里，属于「历史记录，保留原样」——它们不在本票范围，只改这两处用例的取路径方式。

后端切换已完成（`docs/agents/workspace.yaml` 已建、`backendId: markdown`）。本票只收尾声明文件的一致性。

## Comments

### local — 2026-11-11T08:41:31.662Z
载体清单落地、两条钉子改遍历清单、五组变异逐项验证；离线组 69/0。票面「两条同时红」一条按实测替代（单一漂移只该红对应那条），已在票面记明。

## 进度

- 进度：100%（2026-11-11T16:41:31+08:00）：提交 6f4fe71 + 150110a；离线组 69/0；收口
- 进度：100%（2026-11-11T16:40:00+08:00）：清单与两条钉子落地、指针与极性判据按评审重写、离线组 69/0、五组变异逐项验证；提交 6f4fe71
