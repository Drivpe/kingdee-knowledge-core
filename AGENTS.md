# AGENTS.md — kingdee-knowledge-kit

## Agent skills

### Issue tracker

本地 markdown:票与规格是 `.scratch/<feature>/` 下的文件(`spec.md` + `issues/<NN>-<slug>.md`),一个目录一套。
See `docs/agents/issue-tracker.md`.

### Triage labels

五个默认 triage 角色,名字 = 角色名(needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix),
落在票文件的 `Status:` 行与头部 `DSH-LABELS` 注释里。
See `docs/agents/triage-labels.md`.

### Domain docs

single-context:根 `GLOSSARY.md` + `docs/adr/`。
See `docs/agents/domain.md`.
