# 04: CLI:read 合并 + manifest 清单更新

**What to build:** kd read <id> [--kind] 取代 question/answer/article 三命令,--kind 照抄 search 结果的 type(knowledge/answer/article);/manifest 命令清单同步;agent 从检索结果到读全文零翻译。

**Blocked by:** None (can start immediately)

**Status:** done(verify 22/22)

- [x] kd read 三种实体全读通(knowledge/answer/article)
- [x] 旧三命令从 CLI 与 manifest 消失
- [x] 服务端 HTTP 端点面不变
