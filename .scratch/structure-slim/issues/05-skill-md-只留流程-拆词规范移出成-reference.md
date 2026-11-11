<!-- DSH-FORMAT: md-v1 -->
<!-- DSH-PARENT: 00 -->
<!-- DSH-LABELS: ready-for-agent -->
<!-- DSH-BLOCKED-BY: 03, 04 -->
<!-- DSH-IDEMPOTENCY-KEY: deck-5ffd3457-5981277 -->
<!-- DSH-CREATED: 2026-11-11T07:46:34.000Z -->
# 05: SKILL.md 只留流程，拆词规范移出成 reference

**What to build:** `skills/kingdee-knowledge/skills/kingdee-knowledge/SKILL.md` 现 537 行。三步流程（search → read → 合成）占 92 行，而「拆词规范」一节省 162 行（四个维度 / 一句排序原则 / 反例 / 五种固定套路），排在流程中间。

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] 新建 `skills/kingdee-knowledge/skills/kingdee-knowledge/WORD-SPLITTING.md`，「拆词规范」整节（含四个维度、排序原则、反例、五种固定套路、`--kw` 的实测依据）逐字搬入，不压缩
- [ ] SKILL.md 在「清单召回不理想」这条分支上留一句指针（例：清单全是泛词命中、没有精确命中时，读 `WORD-SPLITTING.md` 换词重搜）
- [ ] SKILL.md 删掉搬走的 162 行，剩余结构按装载顺序排：定案 → PATH 自举 → 第 1 步 search → 第 2 步 read → 第 3 步合成 → 站外兜底 → 异常处理 → 禁止事项
- [ ] 「产品线路由（历史事故记录）」与「产品线语义识别（你的职责）」两节合并：前者是已撤销规则的事故记录，降为一段；后者是每次都要用的判定口径，留在流程里
- [ ] SKILL.md 行数降到 300 行以内；`grep -c "拆词"` 在 SKILL.md 里不超过 3（都是指针）
- [ ] 票 03 新增的「文件指针目标存在」断言覆盖 `WORD-SPLITTING.md`；删掉该文件后断言必须红
- [ ] 装机后 `~/.agents/skills/kingdee-knowledge/` 里含 `WORD-SPLITTING.md`
- [ ] 抽查：只读 SKILL.md 的 agent 能走完 search → read → 合成 三步，不需要读 reference。判据是把 `WORD-SPLITTING.md` 临时改名成 `.bak`，按 SKILL.md 走一遍常规问题仍能走通
- [ ] `python3 tests/kd_regression.py` 离线组全绿（`t_docs_no_dead_mechanisms` 与挑选判据那条会扫 SKILL.md，同批确认）

按 writing-for-agents 的判据，拆词细则属于**分支材料**：只有「清单召回不理想、要换词重搜」这一条分支才需要它，而它现在压在任何一次全程加载的路上。

这张票把拆词规范移出成 reference，SKILL.md 只留三步流程、指针、硬边界。




## 背景

writing-for-agents 的原话：**inline what every branch needs, push behind a pointer what only some branches reach**。以及前一句：a document with steps, in-file reference that should be disclosed buries them and turns attending to them into a coin-flip。

本仓还有一个具体约束：装机是 `cp -r "$SKILL_SRC/."` 整目录拷，所以文件只要在技能目录内就自动装机。

⚠️ 拆词规范是召回效果的主要变量（ADR-0016 把生成权移交调用层之后，拆词质量全在调用方）。所以是**移动，不是压缩、不是删除** —— 压成 60 行会丢掉实测脚注，删掉等于把召回质量交给运气。

## 进度
