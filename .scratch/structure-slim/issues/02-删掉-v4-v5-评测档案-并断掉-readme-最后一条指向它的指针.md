<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 01 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-055e33da-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:20.675Z -->
# 02: 删掉 v4/v5 评测档案，并断掉 README 最后一条指向它的指针

**What to build:** docs 根有 23 个被跟踪文件，其中 22 个是 v4/v5 时代的评测档：15 个 `eval-*`（`.md` 与 `.json`）、`discovery-report-v5.md`、`fullsnapshot-report-v5.1.md`、`releasenotes-probe-2026-09-06.md`、2 个 `releasenotes-ingest-2026-09-06-run*.json`、2 个 `rg-eval-report-v5.1*`。另有 `docs/eval-runs-v4/` 整目录 6 个文件同属这套体系。

**Blocked by:** 01

**Status:** resolved

- [x] `git rm` 删除 docs 根上述 22 个文件（不用 `rm`，删除动作要进历史）
- [x] `git rm -r` 删除 `docs/eval-runs-v4/` 的 6 个文件
- [x] `README.md:69` 那句「详见 `docs/eval-report-v4.md` 与 `docs/adr/0003`」改写：保留结论（信号重排与同义词变体被评测否决，recall 反降/无增益），指针改成「评测体系已随去服务化删除（ADR-0011），原文见 git 历史」
- [x] 全仓搜 `eval-report|eval-baseline|discovery-report|fullsnapshot-report|releasenotes-|rg-eval` 的命中，除 ADR / specs / tickets / research 里的历史记录外，其余清零
- [x] 在 `docs/adr/0011-decommission-http-service.md` 末尾追加一行：这批评测档案已删除，取回走 git 历史。不新建文件
- [x] 删除后 `python3 tests/kd_regression.py` 离线组仍全绿（若有用例读这些文件，本票同批改掉）
- [x] `git status --short` 只显示预期内的删除，没有意外的改动混进来

它们是 ADR-0011 已整体删除的那套本地落盘与评测体系的产物。实测：19 个零引用（docs 内外都没人提），1 个（`docs/eval-report-v4.md`）只被 `README.md:69` 的 v4 历史小节提到。

删掉之后 docs 根只剩 `ANSWER-SPEC.md`（它随后由另一张票迁走）与 `agents/`。




## 做了什么

提交 `3f487c9`。

- `git rm` **28 份**：docs 根 22 份 + `docs/eval-runs-v4/` 6 份。删之前先用
  `git ls-files docs | grep -E '^docs/(eval-|discovery-report|fullsnapshot-report|releasenotes-|rg-eval)'`
  对过 —— 正好 28 = 22 + 6，与票面一致
- `README.md:69`（v4 历史小节）保留结论「信号重排、同义词变体被评测否决（recall 反降/无增益）」，
  指针改成「评测体系已随去服务化整体删除（ADR-0011），结论档案不入库、取回走 git 历史」。
  ⚠️ 改写时**刻意不再写旧文件名**：票面要求 README 也把 `eval-report` 清成零命中，
  留一次文件名那条 grep 立刻红
- ADR-0011 末尾补「附记：评测档案的删除（2026-11-16）」，记删除范围与取回方式，不新建归档目录

### 判据实测

- residual grep（`eval-report|eval-baseline|discovery-report|fullsnapshot-report|releasenotes-|rg-eval`，
  排除 ADR / specs / tickets / research / .scratch）→ **零命中**
- `python3 tests/kd_regression.py` → **69 通过 / 0 失败**（本票当时的基线；票 03 加新钉子后为 70）
- docs 根现在只剩 `adr/ agents/ research/ specs/ tickets/` —— 评测档与 ANSWER-SPEC 都已不在

### 与票面不符的一处

票面要「`git status --short` 只显示预期内的删除」。**这条做不到，原因不在本票**：开工时工作区
已有一批未提交的「PATH 自举」改动（AGENTS.md / README / install.sh / install.ps1 / SKILL.md）。
本票只 `git add` 了自己改的两个文件，但那两个文件里的既有改动也一并进了本次提交（README 的
PATH 警告段）。事后已单独补提交 `f5d6cd1` 把那批改动归位；本票的删除与指针改写本身没有夹带
其他改动。

## 背景

这批文件是 v6 之前「corpus 预囤 + run_eval 评测」路线的产物。ADR-0011 去服务化后那套体系的代码、脚本、数据目录都已删除，只剩这些跑出来的结论档案。留着它们的代价不是磁盘，是「这套体系还在不在」这个判断每轮都要重新做一遍。

⚠️ 不要连带删除 `docs/adr/`、`docs/specs/`、`docs/tickets/`、`docs/research/`。它们被 ADR 与代码按编号与行号引用，删了就是断链。实测：`docs/tickets/` 17 个文件全部被编号引用（`票 #NN` / `工单 #NN` 形态），`docs/specs/` 10 个里 8 个被引用。

## Comments

### local — 2026-11-16T13:26:00.000Z
删档 28 份（docs 根 22 + eval-runs-v4 6）、README 的 v4 小节改成「已随去服务化删除，取回走 git 历史」、ADR-0011 补附记；residual grep 零命中，离线组 69/0。票面「git status 只显示预期删除」一条按实测替代 —— 工作区原本就有一批 PATH 自举改动，事后单独提交 f5d6cd1 归位。

## 进度

- 进度：100%（2026-11-16T13:26:00+08:00）：28 份评测档删除、README 指针改写、ADR-0011 附记；离线组 69/0；提交 3f487c9；收口
