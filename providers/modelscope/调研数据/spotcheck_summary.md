# 抽查复核记录（关键信息可复核 — 完成标准证据）

> 核对时间：2026-08-08 ~ 2026-08-09
> 方法：对入选模型逐项调用公开接口实测，与交付台账交叉比对
> 接口：`GET /api/v1/inference/list_model_providers?ModelId={id}`（魔粒费用）、`GET /api/v1/models/{owner}/{name}`（详情）、`GET api-inference.modelscope.cn/v1/models`（API 可调用清单）

## 一、模型抽查（4 个，超完成标准要求的 2-3 个）

### 1. deepseek-ai/DeepSeek-V4-Flash-0731（用户示例模型）
| 核对项 | 接口实测值 | 台账值 | 结论 |
|---|---|---|---|
| API 可调用 | 在 api-inference 43 模型清单中 ✅ | 入选 | 一致 |
| 魔粒费用 | 魔搭社区 2 魔粒/次（ultra） | 2 魔粒/次 | 一致（与用户截图「预计魔粒扣减 2魔粒/次」完全一致） |
| 详情字段 | SupportInference=txt2txt, Experience=1, Downloads=60935 | — | 支持在线推理 |
| 编程基准 | Terminal Bench 2.1 = 82.7 | 82.7 | 一致（来源 flowtivity.ai） |
| 原始响应 | spotcheck/deepseek-ai__DeepSeek-V4-Flash-0731_fee.json、detail_raw/ 同名文件 | — | 已落盘 |

### 2. Qwen/Qwen3.5-397B-A17B（排序第 3）
| 核对项 | 接口实测值 | 台账值 | 结论 |
|---|---|---|---|
| API 可调用 | 在清单中 ✅ | 入选 | 一致 |
| 魔粒费用 | 魔搭社区 2 魔粒/次（ultra），另有百炼/百炼-Coding | 2 魔粒/次 | 一致 |
| 详情字段 | SupportInference=txt2txt, Experience=1, Downloads=204430 | — | 支持在线推理 |
| 编程基准 | SWE-bench Verified 76.4（修正后） | 76.4 | 一致（原 README 提取 80.0 为列错位，子 Agent 核验修正为 76.4） |
| 原始响应 | spotcheck/Qwen__Qwen3.5-397B-A17B_fee.json、_detail.json | — | 已落盘 |

### 3. MiniMax/MiniMax-M3（排序第 8）
| 核对项 | 接口实测值 | 台账值 | 结论 |
|---|---|---|---|
| API 可调用 | 在清单中 ✅ | 入选 | 一致 |
| 魔粒费用 | 魔搭社区 1 魔粒/次（standard），另有 MiniMax 官方 | 1 魔粒/次 | 一致 |
| 详情字段 | SupportInference=txt2txt, Experience=1, Downloads=3158 | — | 支持在线推理 |
| 编程基准 | SWE-bench Pro 59.0 / Terminal-Bench 2.1 66.0 | 59.0 | 一致（来源 minimax.io 官方博客） |
| 原始响应 | spotcheck/MiniMax__MiniMax-M3_fee.json、_detail.json | — | 已落盘 |

### 4. ZhipuAI/GLM-5.2（排序第 4）
| 核对项 | 接口实测值 | 台账值 | 结论 |
|---|---|---|---|
| API 可调用 | 在清单中 ✅ | 入选 | 一致 |
| 魔粒费用 | 魔搭社区 2 魔粒/次（ultra），另有百炼/智谱-Coding/智谱 | 2 魔粒/次 | 一致 |
| 详情字段 | SupportInference=txt2txt, Experience=1, Downloads=188659 | — | 支持在线推理 |
| 编程基准 | SWE-bench Pro 62.1 / Terminal Bench 2.1 81.0/82.7 | 62.1 | 一致（来源 morphllm.com/swe-bench-pro） |
| 原始响应 | spotcheck/ZhipuAI__GLM-5.2_fee.json、_detail.json | — | 已落盘 |

## 二、排序前 3 名基准来源逐一核对
| 排名 | 模型 | 基准分数 | 来源 | 可访问性 |
|---|---|---|---|---|
| 1 | DeepSeek-V4-Pro | SWEV 80.6（Max） | 模型卡 + morphllm.com/swe-bench-pro | morphllm 429（反爬限流，子 Agent 已成功读取；非死链） |
| 2 | DeepSeek-V4-Flash-0731 | Terminal Bench 2.1 82.7 | 模型卡 + flowtivity.ai/blog/deepseek-v4-flash-agent-benchmarks | 200 ✅ |
| 3 | Qwen3.5-397B-A17B | SWEV 76.4 | 模型卡 + morphllm.com/qwen-3-5 | morphllm 429（同上） |

## 三、交付表格来源链接可访问性抽查（2026-08-09 实测）
| 链接 | HTTP 状态 |
|---|---|
| https://flowtivity.ai/blog/deepseek-v4-flash-agent-benchmarks | 200 ✅ |
| https://www.minimax.io/blog/minimax-m3 | 200 ✅ |
| https://www.swebench.com/ | 200 ✅ |
| https://modelscope.cn/learn/1409 | 200 ✅ |
| https://www.morphllm.com/swe-bench-pro | 429（限流，非 404 死链） |
| https://www.morphllm.com/qwen-3-5 | 429（限流，非 404 死链） |

## 四、费用完整性检查（最终交付前通读）
- 入选 31 个模型：30 个有魔搭社区魔粒价（计费口径：每次调用），已全部写入台账（modelscope_agent_ledger_full.csv 的「魔搭社区魔粒/次」「计费口径」「核对时间」三列）。
- Qwen/Qwen3-4B：无魔搭社区提供方（仅阿里云百炼），已在报告与台账中单独标注，未遗漏。
- 无免费（0 魔粒）模型：魔搭社区计价模型均为 1 或 2 魔粒/次；免费额度体现为「每日 2000 次调用不消耗魔粒」而非 0 魔粒标价，已在费用规则中说明。

## 结论
抽查 4 个模型（> 要求的 2-3 个）在「API 可调用」「魔粒费用」「编程基准」「详情字段」四个维度全部与交付台账一致；排序前 3 名基准来源真实存在；费用台账无遗漏。**关键信息可复核 ✅**
