<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 01 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-6b4092d7-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:48.109Z -->
# 06: 版本变更史离开术语表，先补 6.9 删 total 的空洞

**What to build:** `GLOSSARY.md`（304 行）的前 52 行是版本变更史：6.4 → 6.5 → 6.6（两个补记）→ 6.7 → 6.8 → 6.9（两个段）→ v6.9 补记，`## Language` 从第 53 行才开始。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] **先补空洞**：新建 `docs/adr/0019-顶层删除-total.md`。现有 ADR 里没有任何一条覆盖 6.9 删 `total`，唯一出生地就是 `GLOSSARY.md:24-25` 那一段。它必须是完整 ADR：上下文（`total` 是各路上游 `totalElements` 的最大值，实测 `total: 74` 而 `results: []`）、决策（删除，差额由 `results` 长度 + `otherSkipped` + `keywordsDropped` + `routeErrors` 承担）、后果（破坏性变更；连带删除 `_route_search_once` 读 `totalElements` 那段；删除钉住它的三段在线断言与漂移基线常量 `6326`；`answersTotal` 未动；测试桩里的 `totalElements` 保留）、备选（不选：留着但同时劝退）
- [ ] 其余版本段（6.4 / 6.5 / 6.6 / 6.7 / 6.8 / v6.9 补记）逐条核对已有 ADR 覆盖：6.4→0014、6.5→0015、6.6→0016、6.7→0017、6.8→（无独立 ADR，是 6.7 落地的收尾轮，并入 0017 或新建）、v6.9 补记→0018
- [ ] 未覆盖的段落（至少 6.8）落成 ADR 或追加到对应 ADR 的末尾；不允许「搬丢了」
- [ ] `GLOSSARY.md` 删掉前 52 行，`## Language` 成为文件的第一个 `##`；开头的三行项目自述保留（它是术语表的引言，不是变更史）
- [ ] `pyproject.toml` 里那段注释版的变更说明改为指针（`# 版本史见 docs/adr/`），不再复述内容
- [ ] `GLOSSARY.md` 里所有 `docs/specs/...` 指针指向已删除或将要删除的 spec 时，改为指向对应 ADR
- [ ] 搬完之后 GLOSSARY 仍被 `t_link_policy_docs_in_sync` 与 `t_docs_no_dead_mechanisms` 读到（票 01 的载体清单里那条路径不变）
- [ ] `python3 tests/kd_regression.py` 离线组全绿
- [ ] 抽查：只看 `## Language` 以下的内容，能查到「检索内核 / 三种实体（现为四档）/ 清单 / 全文 / 链接政策 / 契约声明」这些术语，且每条不含函数名与实测数字

`/domain-modeling` 明写术语表只放术语、不放实现细节。而这 52 行里含函数名、实测数字、钉子编号、字段增删清单 —— 是变更日志，不是术语。同一段史在 `pyproject.toml` 里还有一份注释版。

这张票把版本史搬进 ADR，`## Language` 回到文件开头。




## 背景

`/domain-modeling` 的原话：**`GLOSSARY.md` should be totally devoid of implementation details. Do not treat `GLOSSARY.md` as a spec, a scratch pad, or a repository for implementation decisions.**

`docs/specs/2026-09-29-验收记录.md:266` 记过这件事已经发生过一次：M-3 项点名「`CONTEXT.md` 越界承载实现细节（函数名、实测数字、钉子编号），而本仓同时把 `CONTEXT.md` 当文档一致性钉子的载体 —— 形成结构性冲突」，当时只把 6.8 段落改写了一遍，冲突没解决。

⚠️ 顺序不能反。先建 ADR-0019 再删 GLOSSARY 的那一段 —— 反了就是「搬走唯一的出生地、没有新家」，那一段承载的是一个破坏性变更的全部判据。

## 进度
