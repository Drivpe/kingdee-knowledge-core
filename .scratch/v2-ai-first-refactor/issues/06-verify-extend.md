# 06: 回归扩展:read×3 / ai 正常与降级 / manifest 命令面

**What to build:** 端到端回归(verify_ksearch.py)覆盖新命令面:kd read 三种实体、kd ai 正常路径(本地假 OpenAI 兼容端点)与降级路径(死通道)、manifest 含 kd read/kd ai 且旧命令退役;全量一键 PASS。

**Blocked by:** 04, 05

**Status:** done(22/22 PASS)

- [x] 回归脚本不改即指向任意环境(KSEARCH_URL/KD_PY)
- [x] 22/22 PASS
