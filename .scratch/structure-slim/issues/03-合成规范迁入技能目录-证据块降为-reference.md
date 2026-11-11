<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 01 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-ad8fcb9d-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:21.016Z -->
# 03: 合成规范迁入技能目录，证据块降为 reference

**What to build:** `docs/ANSWER-SPEC.md`（176 行）自称「合成回答格式的单一事实源」，而装机脚本只拷 `skills/kingdee-knowledge/skills/kingdee-knowledge` 整目录（`install.sh:190-198` 的 `SKILL_SRC` + `cp -r "$SKILL_SRC/."`），`docs/` 不在拷贝范围。SKILL.md 在八处引用它，客户端 agent 照指针走过去是空的。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 新建 `skills/kingdee-knowledge/skills/kingdee-knowledge/ANSWER-SPEC.md`，内容为现 `docs/ANSWER-SPEC.md` 全文
- [ ] 同一目录新建 `CITATION-EVIDENCE.md`，把现文里那段 `url_effective` 重定向实测证据（含三档 `knowledge`/`article`/`question` 的可点性数字、`/school/detail/<id>` 同型第五例、被迁移成知识文档的那条、以及「登录态假阴性」那段）整块搬进去；ANSWER-SPEC 里在原位留一行指针
- [ ] 删除 `docs/ANSWER-SPEC.md`（`git rm`），全仓指针从 `docs/ANSWER-SPEC.md` 改为技能目录内路径
- [ ] `tests/kd_regression.py:2819`（`t_answer_spec_diagnostics_wording`）与 `:4263`（挑选判据归属那条）的路径常量改为新位置，两条用例仍绿
- [ ] SKILL.md 里「三段式 / 原因分析 / 根因引用规则 / 来自社区经验 / otherSkipped」这几处复述收成：流程节一句「按 ANSWER-SPEC 写」加指针，形态细节只在 ANSWER-SPEC 里存在一次。判据是 `grep -c "三段"` 在 SKILL.md 里降到 1
- [ ] SKILL.md 里八处 `ANSWER-SPEC` 指针全部指向技能目录内的新路径
- [ ] `t_docs_no_dead_mechanisms` 的载体清单（票 01 建的）里，ANSWER-SPEC 那条路径同步更新
- [ ] 新增一条断言：SKILL.md 与 AGENTS.md 里每一条形如 `` `path/to/file.md` `` 的文件指针，目标文件必须真在盘上。删掉新 ANSWER-SPEC 后此断言必须红
- [ ] `install.sh` 与 `install.ps1` 末尾那句 `echo "再由你按 docs/ANSWER-SPEC.md 自己合成。"` 改为技能目录内的相对说法（客户端读的是 SKILL.md，不是仓库路径）
- [ ] 装机后 `~/.agents/skills/kingdee-knowledge/` 里含 `SKILL.md`、`ANSWER-SPEC.md`、`CITATION-EVIDENCE.md` 三份（本机当前没有这个目录，需先跑一次 install.sh 验证）

本机实测：`~/.agents/skills/` 这个目录根本不存在 —— 这份技能一次都没装上过，所以这个断链从未被任何东西发现。

这张票把合成规范迁进技能目录，并把 SKILL.md 里散落的四份复述收成一处加指针。




## 背景

manifest 层的事实：`SKILL_SRC="$REPO/skills/kingdee-knowledge/skills/kingdee-knowledge"`，`cp -r "$SKILL_SRC/."` 整目录拷。所以只要文件在技能目录内，就自动装机，且它属于 writing-for-agents 的「disclosed reference」层——占指针的一行，不占每次全程加载的额度。

被搬走的证据块约 30 行，它只在「链接看起来不对」这一条分支上才需要，不该占常驻额度。

⚠️ ANSWER-SPEC 与 SKILL.md 里 `linkPolicy` 都指向 `contract.json`，那条指针保持不动 —— 它是链接政策唯一的真源，且代码真的读它。

## 进度
