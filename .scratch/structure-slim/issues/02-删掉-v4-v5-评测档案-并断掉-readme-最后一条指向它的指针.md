<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 01 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-055e33da-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:20.675Z -->
# 02: 删掉 v4/v5 评测档案，并断掉 README 最后一条指向它的指针

**What to build:** docs 根有 23 个被跟踪文件，其中 22 个是 v4/v5 时代的评测档：15 个 `eval-*`（`.md` 与 `.json`）、`discovery-report-v5.md`、`fullsnapshot-report-v5.1.md`、`releasenotes-probe-2026-09-06.md`、2 个 `releasenotes-ingest-2026-09-06-run*.json`、2 个 `rg-eval-report-v5.1*`。另有 `docs/eval-runs-v4/` 整目录 6 个文件同属这套体系。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `git rm` 删除 docs 根上述 22 个文件（不用 `rm`，删除动作要进历史）
- [ ] `git rm -r` 删除 `docs/eval-runs-v4/` 的 6 个文件
- [ ] `README.md:69` 那句「详见 `docs/eval-report-v4.md` 与 `docs/adr/0003`」改写：保留结论（信号重排与同义词变体被评测否决，recall 反降/无增益），指针改成「评测体系已随去服务化删除（ADR-0011），原文见 git 历史」
- [ ] 全仓搜 `eval-report|eval-baseline|discovery-report|fullsnapshot-report|releasenotes-|rg-eval` 的命中，除 ADR / specs / tickets / research 里的历史记录外，其余清零
- [ ] 在 `docs/adr/0011-decommission-http-service.md` 末尾追加一行：这批评测档案已删除，取回走 git 历史。不新建文件
- [ ] 删除后 `python3 tests/kd_regression.py` 离线组仍全绿（若有用例读这些文件，本票同批改掉）
- [ ] `git status --short` 只显示预期内的删除，没有意外的改动混进来

它们是 ADR-0011 已整体删除的那套本地落盘与评测体系的产物。实测：19 个零引用（docs 内外都没人提），1 个（`docs/eval-report-v4.md`）只被 `README.md:69` 的 v4 历史小节提到。

删掉之后 docs 根只剩 `ANSWER-SPEC.md`（它随后由另一张票迁走）与 `agents/`。




## 背景

这批文件是 v6 之前「corpus 预囤 + run_eval 评测」路线的产物。ADR-0011 去服务化后那套体系的代码、脚本、数据目录都已删除，只剩这些跑出来的结论档案。留着它们的代价不是磁盘，是「这套体系还在不在」这个判断每轮都要重新做一遍。

⚠️ 不要连带删除 `docs/adr/`、`docs/specs/`、`docs/tickets/`、`docs/research/`。它们被 ADR 与代码按编号与行号引用，删了就是断链。实测：`docs/tickets/` 17 个文件全部被编号引用（`票 #NN` / `工单 #NN` 形态），`docs/specs/` 10 个里 8 个被引用。

## 进度
