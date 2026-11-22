# kingdee-knowledge-core

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)

kd 是一个可 import 的金蝶云社区**检索内核**,附带一个薄 CLI。
它零账号、零 cookie、零模型依赖:检索和全文读取全走匿名上游。
内核**只出清单、不合成回答**:`search` 给出标题清单,调用方自己挑,`read` 取全文。
回答格式、拆词规范及技能四件套(SKILL.md / ANSWER-SPEC.md / WORD-SPLITTING.md /
CITATION-EVIDENCE.md)与插件清单(plugin.json / marketplace.json)等调用层资产已迁出到 agent
集成仓,不在本仓;本仓只保留检索内核与公开 search/read 契约。

## 安装

只走标准打包:

```bash
pipx install kingdee-knowledge-kit     # 推荐
# 或
pip install kingdee-knowledge-kit
```

没有定制安装脚本。`pyproject.toml` 提供 `kd` 命令,包内 `contract.json` 随包分发。
纯标准库,无第三方运行时依赖。

## import 用法

```python
from kd.core import search, read

pack = search(keywords=["信用额度控制", "应收单 信用"], product_id=93)
hit  = pack["results"][0]
doc  = read(hit["type"], hit["id"])   # type 照抄清单条目的 type
```

公开面是 `search` / `read` 与三个异常类;请求参数、JSON 字段与键序的单一真源是
包内 `src/kd/contract.json`,变更理由在 [docs/contract-rationale.md](docs/contract-rationale.md)。

## CLI

```bash
kd search --kw "词1" --kw "词2" [--product 93] [--global] [--include-other]
kd read <id> [--kind knowledge|question|article]
```

- `--kw` 可重复,每个词一路;内核原样按序发送,只去重、不拆词、不排序。
- `--product`:产品线编号与标签的单一真源是 `src/kd/contract.json` 的 `productIds.names`,
  不在此复述数字矩阵;不传时用默认产品线,显式 `0` 表示不过滤。
- stdout 永远是 JSON,进度在 stderr,错误是带 `hint` 的 JSON;退出码 0 成功 / 1 上游或内部错误 / 2 用法错误。
- `kd --help` 自曝命令面;没有 `kd health`,也没有 `kd ask`。

## 最小检索流程

1. 调用方按自己的拆词规范把问题拆成几个关键词,逐字逐序传给 `--kw`。
2. `kd search` 出**帖级标题清单**(罕见类型归入 `other` 档,默认隐藏)。
3. 调用方按标题自己挑,再 `kd read` 取全文。
4. 调用方自己合成回答并对召回是否足够作判断;本仓不产出成品答案。

## 测试

```bash
python3 tests/kd_regression.py          # 离线组:不联网、无需环境变量
python3 tests/baseline/replay_baseline.py   # 公开行为基线重放
```

改内核后先跑离线组与基线重放。离线套件没有 `--online`;在线验收由维护者按需手动跑一次 search→read smoke,不执行高频在线回归。

## 长期文档

只保留决策档案 [docs/adr/](docs/adr/) 与契约依据 [docs/contract-rationale.md](docs/contract-rationale.md)。
研究、施工、票与治理档案已随本轮裁剪移除,历史从 git 取回。

## License

MIT
