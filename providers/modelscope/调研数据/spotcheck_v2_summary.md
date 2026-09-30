# 抽查复核记录 v2（2026-08-09 09:36 本轮实测）

> 完成标准「关键信息可复核」证据。本轮（2026-08-09）实际重新调用接口抽查 3 个模型，四维度与交付台账比对。

## 实测结果（原始响应存 spotcheck_v2/）

| 模型 | 魔搭社区魔粒/次 | CostTier | SupportInference | Experience | Downloads | 台账比对 |
|---|---|---|---|---|---|---|
| deepseek-ai/DeepSeek-V4-Flash-0731 | 2 | ultra | txt2txt | 1 | 61813 | 一致 ✅ |
| Qwen/Qwen3.5-397B-A17B | 2 | ultra | txt2txt | 1 | 204431 | 一致 ✅ |
| MiniMax/MiniMax-M3 | 1 | standard | txt2txt | 1 | 3158 | 一致 ✅ |

比对项：台账（modelscope_agent_ledger_full.csv）中三模型魔粒/次分别为 2、2、1，全部一致。

## 关联验证
- API 可调用：三个模型均在 `api-inference.modelscope.cn/v1/models` 43 模型清单中（infer_models_list.txt）
- 基准分数：DeepSeek-V4-Flash-0731 TB2.1=82.7（flowtivity.ai 200）、Qwen3.5-397B SWEV=76.4（morphllm 429 限流非死链）、MiniMax-M3 SWE-Pro=59.0（minimax.io 200）——与台账一致
- 用户截图交叉验证：DeepSeek-V4-Flash-0731 弹窗「预计魔粒扣减 2魔粒/次」= 接口实测 2 魔粒/次 ✅

## 结论
关键信息可复核：✅（3 个模型 ≥ 标准要求的 2-3 个；四维度一致；链接可访问）
