<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 04 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-2af26fdf-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:48.457Z -->
# 07: 论证与数据分居：contract.json 的 27 个 note/evidence 键移出去

**What to build:** `src/kd/contract.json` 20 486 B，其中 9 280 B（45%）在 27 个 `note`/`evidence` 键里。最大的三块：`linkPolicy.evidence` 1 168 B、`search.note` 724 B、`read.note` 626 B。

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] 逐键分类 27 个 `note`/`evidence`：哪些是纯论证（人读）、哪些含代码会读的结构化信息（机器读）。后者留在 `contract.json`
- [ ] 新建 `docs/contract-rationale.md`（位置自定，也可拆进 `docs/adr/`），把纯论证类整块搬入，按键路径分节
- [ ] `contract.json` 原地留指针：每个被搬走的键留一行形如 `"_note": "见 docs/contract-rationale.md#<anchor>"`，或统一在文件顶部留一个 `rationalePointer` 键
- [ ] **顺序要求**：先建新址、再把指针放进原处，不做一次性剪切。每一步之后 `python3 tests/kd_regression.py` 都要绿
- [ ] `contract.json` 体积降到 12 000 B 以内
- [ ] 检查每条被搬走的论证都有落点：`grep` 原 27 个键的内容在新文件里都能找到；不允许「搬丢了」
- [ ] 声明必须有消费者的纪律不破：搬走之后，每个仍留在 `contract.json` 的键仍被代码读（这一条是本仓的核心纪律，见 `_config.py:176`）
- [ ] `python3 tests/kd_regression.py` 离线组全绿
- [ ] 若某条 `evidence` 被回归用例对着断言（例如链接政策那条），断言改为读新位置，且仍绿

它们记的是「为什么这么定」和实测数字，与「代码要读哪个键」是两种读者。结果是这个文件同时是 schema、变更日志、实测档案；代码读它时把 45% 的字节也读进了内存。

这张票把它们分居：数据留在这里，论证移出去并在原地留指针。判据是「代码会不会读它」。




## 背景

这条最不确定该不该动 —— 架构审查报告里对它标的是「Speculative」。理由：那些 note 正在真实地阻止重复犯错，好几条记着「这里曾经判错过」（例如 `search.note_totalRemoved` 记着 `total: 74` 而 `results: []` 的实测、`linkPolicy.evidence` 记着「只看首跳状态码会双向判错」）。

所以判据不是「文件该不该瘦」，而是「两种读者的内容该不该同处一个字典」。如果逐键分类后发现绝大多数 note 都含代码要读的结构化信息，这张票的正确结论就是**不做**，届时把结论写进票面并关闭。

⚠️ `contract.json` 是包内唯一数据文件（`pyproject.toml` 的 `package-data` 只登记了它），任何新增文件都不进包 —— 所以搬出去的论证必须是 `docs/` 侧的人读文档，不能是运行期依赖。

## 进度
