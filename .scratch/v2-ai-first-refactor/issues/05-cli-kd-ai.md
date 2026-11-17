# 05: CLI:kd ai 入仓(带自动降级)

**What to build:** kd ai "问题" 两段 LLM(关键词规划→按 ANSWER-SPEC 合成)输出带 references 的 Markdown 回答;KAI_BASE(OpenAI 兼容,勿带 /v1)/KAI_MODEL 环境变量;通道不可用/合成失败自动降级返回 ask 资料包 + fallback:true + fallbackReason,退出码 0;python-urllib 伪装 UA 铁律;关键词规划失败退化为原句检索。

**Blocked by:** 04(同文件顺序编辑)

**Status:** done(verify 22/22,含假通道正常路径与死通道降级路径)

- [x] 有通道:ok=true, fallback=false, answer 为 Markdown
- [x] 无通道:fallback=true 且 sources 可用
- [x] 服务错误不走降级(按错误契约退出)
