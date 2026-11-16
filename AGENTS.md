# AGENTS.md — kingdee-knowledge-kit

## Agent skills

### Issue tracker

本地 markdown:票与规格是 `.scratch/<feature>/spec.md` 与 `.scratch/<feature>/issues/<NN>-<slug>.md`,一个目录一套。
See `docs/agents/issue-tracker.md`.

### Triage labels

五个默认 triage 角色,名字 = 角色名(needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix),
落在票文件的 `Status:` 行与头部 `DSH-LABELS` 注释里。
See `docs/agents/triage-labels.md`.

### Domain docs

single-context:根 `GLOSSARY.md` + `docs/adr/`。
See `docs/agents/domain.md`.

## 金蝶知识检索

问金蝶产品问题一律走 `kd` CLI,**不要**用 `python3 src/kd_run.py`,也不要自己写脚本抓网页。

1. **先自举 PATH**(agent 是非交互 shell,读不到 `~/.bashrc` 里的导出,直接敲 `kd` 会报
   `command not found` —— 那不代表没装):
   `export PATH="$HOME/.local/bin:$HOME/.kingdee-kit/bin:$PATH"; kd --version`
2. 自举失败才回退绝对路径 `~/.kingdee-kit/bin/kd`;再失败才 `python3 src/kd_run.py search --kw "…"`
3. 检索形态:`kd search --kw "词1" --kw "词2"`(位置参数已删)→ 挑标题 → `kd read <id> --kind <type>`

完整流程见技能 `kingdee-knowledge`(`~/.agents/skills/kingdee-knowledge/SKILL.md`);
拆词规范是同目录的 `~/.agents/skills/kingdee-knowledge/WORD-SPLITTING.md`
(只在「清单召回不理想、要换词重搜」时才读)。
