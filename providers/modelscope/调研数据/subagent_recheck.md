# 交叉核验报告：ModelScope 费用接口 + 12 模型编程基准复核

> 核验员：subagent（复核与核验）｜时间：2026-08-08 18:37+08:00
> 工作目录：`C:\Users\Doro\.openclaw-autoclaw\workspace\.cluster`
> 方法：curl.exe 直接探测 + 前端 JS 逆向定位真实接口 + web_search 交叉验证

---

## 1. 费用接口探测结果

### 1.1 任务指定 URL 探测（均 404，含 POST）

| # | URL | HTTP 状态 | 是否有费用字段 |
|---|---|---|---|
| 1 | GET /api/v1/models/deepseek-ai/DeepSeek-V4-Flash-0731/inference-api | 404（body: `404 page not found`，非 JSON） | 无 |
| 2 | GET /api/v1/models/.../inference-api/query | 404 | 无 |
| 3 | GET /api/v1/models/.../api-inference | 404 | 无 |
| 4 | GET /openapi/v1/models/.../inference | 404 | 无 |
| 5 | GET /api/v1/models/.../dash-inference/example | 404 | 无 |
| 6 | GET /api/v1/models/.../openai | 404 | 无 |
| 7 | GET /api/v1/models/.../inference/quota | 404 | 无 |
| 8 | GET /api/v1/models/.../example | 404 | 无 |
| 9 | **POST** /api/v1/models/.../inference-api（body `{}`，Content-Type: application/json） | 404 | 无 |

另试 11 个猜测端点（inference/detail、inference/query、inference-service、dash-inference、endpoints、inference-api-info、providers、api-providers、inference/providers、inference-api/providers、api-inference/providers）→ **全部 404**。

### 1.2 定位过程（前端逆向，找到真实接口）

- 模型详情页为 SPA（umi.js 2.13.120），页面内嵌 `window.__detail_data__`（= GET /api/v1/models/{path}，200）——**该 JSON 无任何魔粒/价格字段**，且 `SupportApiInference:false`（对未登录/元数据而言不代表不可用）。
- 逆向 `p__modelDetail__Summary__index.async.js`：弹出窗文案 id `ApiProviders.CodeModal.MagicCubeUnitPrice` = "预计魔粒扣减 {EstimatedMagicGrainCost}"，`MagicCubeUnitPriceText` = "{n}魔粒/次"；provider 弹窗说明 `ModelDetail.InferenceProvider.Popover.ItemDesc1` = "**社区注册用户可免费限额使用**"。
- 服务层模块（76150.async.js）暴露 `v9 = GET /v1/inference/list_model_providers?ModelId={path}`，响应 `Data.Providers[]`，每项含 `EstimatedMagicGrainCost`（魔粒/次）、`CostTier`（cost 档位）、`Name/ChineseName/Hosted/Logo`。
- 页面 `MODELSCOPE_WEB_PROXY_URL` 含 `/magicube` —— 魔粒 = MagicCube（魔粒=魔力同义，用户说法确认）。
- `/api/v1/quota/status` → **401 user not logged in**（存在，需登录态）。

### 1.3 ✅ 真实费用接口（已验证可用，无需登录）

```
GET https://modelscope.cn/api/v1/inference/list_model_providers?ModelId=deepseek-ai/DeepSeek-V4-Flash-0731
→ 200 {"Code":200,"Data":{"Providers":[{"ChineseName":"魔搭社区","Name":"ModelScope",
   "EstimatedMagicGrainCost":2,"CostTier":"ultra",...},{"ChineseName":"阿里云百炼","Name":"DashScope",...}],...}}
```

### 1.4 12 个重点模型魔粒费用台账（ModelScope 官方接口实测，2026-08-08）

| 模型 | ModelScope 提供方 | 预计魔粒扣减（魔粒/次） | CostTier | 其他提供方 |
|---|---|---|---|---|
| Qwen/Qwen3.5-397B-A17B | ✅ | **2** | ultra | DashScope、DashScope-Coding |
| Qwen/Qwen3.6-35B-A3B | ❌ Providers=null（当前无 API 提供方） | 未显示 | - | 无 |
| Qwen/Qwen3-Coder-480B-A35B-Instruct | ❌ | 未显示 | - | 仅 DashScope（阿里云百炼） |
| Qwen/Qwen3-Coder-30B-A3B-Instruct | ✅ | **1** | standard | DashScope |
| deepseek-ai/DeepSeek-V4-Pro | ✅ | **2** | ultra | DashScope、DeepSeek |
| deepseek-ai/DeepSeek-V4-Flash-0731 | ✅ | **2** | ultra | DashScope |
| ZhipuAI/GLM-5.2 | ✅ | **2** | ultra | DashScope、Zhipu-Coding、ZhipuAI |
| ZhipuAI/GLM-5 | ❌ | 未显示 | - | DashScope、DashScope-Coding、Zhipu-Coding、ZhipuAI |
| ZhipuAI/GLM-4.7 | ❌ | 未显示 | - | DashScope、Zhipu-Coding、ZhipuAI |
| moonshotai/Kimi-K2.7-Code | ❌ | 未显示 | - | 仅 Moonshot |
| moonshotai/Kimi-K3 | ❌ | 未显示 | - | Moonshot、Moonshot-Coding |
| stepfun-ai/Step-3.7-Flash | ✅ | **1** | standard | stepfun-ai |

要点：
- 「预计魔粒扣减 X 魔粒/次」仅对 **ModelScope（魔搭社区）自营提供方**显示；第三方提供方（百炼/智谱/Moonshot 等）走各自 API Key 计费，弹窗不显示魔粒价。
- 魔粒价与 CostTier 相关：本批 ultra=2 魔粒/次，standard=1 魔粒/次（tier 的官方定价语义未公开，为观测到的相关性）。
- Qwen3.6-35B-A3B 当前在 ModelScope **没有任何推理 API 提供方**（Providers=null），与"可通过 API 接入"前提冲突，建议主代理复核。

---

## 2. 魔粒规则说明（官方来源）

### 来源 1：魔搭平台免费资源 list（官方文章，2026-08 更新）
URL: https://www.modelscope.cn/learn/1409（正文经 https://modelscope.cn/api/v1/articles/1409 取得）
要点：
- **免费 API 调用**：多达 6 万+ 模型，每日累计 **2000 次免费调用**（Qwen/DeepSeek/GLM/MiniMax 等），API 列表见模型库「推理API-Inference」筛选。
- **魔粒获取方式**：
  - 每日初始额度：绑定阿里云账户后每日登录得 **150 魔粒**；
  - 每日激励任务（创作返图）：最高 **+200 魔粒/日**；
  - 每日任务奖励（点赞评论）：最高 **+50 魔粒/日**；
  - 模型使用奖励：同一模型单日使用超 3 次，每模型 +50 魔粒，最高 **+200 魔粒/日**。
- 魔粒消耗示例（AIGC）：图片生成 1-2 魔粒/张；视频生成 8-28 魔粒/次；LoRA 训练按数据集动态计算。
- 补充说明文档：https://modelscope.cn/docs/aigc/aigc-quota

### 来源 2：Cherry Studio 文档（第三方交叉验证，2026-08 更新）
URL: https://github.com/CherryHQ/cherry-studio-docs/blob/main/pre-basic/providers/modelscope.md（raw 已抓取）
要点：
- 免费额度：每位用户**每日 2000 次 API 调用**（*以官网最新规则为准）；
- 额度重置：每日 UTC+8 00:00 自动重置，**不支持跨日累计/升级**；
- 超额：返回 **429 错误**；API-Inference 覆盖模型范围随关注度迭代。

### 来源 3：社区实测（知乎 2026-04-13）
URL: https://zhuanlan.zhihu.com/p/2027042477937370465
- 每日最多约 2000 次，**单个模型约 500 次上限，部分模型更低（约 20 次）**。

### 来源 4：crazylxr 博客（2025-12-07）
URL: https://crazylxr.github.io/posts/claude-code-免费使用魔搭社区的任意模型
- ModelScope 支持 Anthropic 协议；每日 2000 次免费 API-Inference 调用，Qwen3-Coder 单独 500 次/天。

### 魔粒商城/公开价格表
**未找到**公开的「魔粒商城」或统一价格表页面（搜索无相关官方结果）；魔粒单价以模型详情页弹窗/上述接口为准，逐模型展示。

---

## 3. 12 模型编程基准分数表（可溯源）

> 列说明：分数 = 该模型自身数值；来源 URL 全部真实可访问。模型卡分数 = 从 ModelScope 模型卡 README 原文提取（readme_N.md 已存 .cluster）。

| 模型 | 分数（基准） | 来源 URL |
|---|---|---|
| Qwen/Qwen3.5-397B-A17B | **SWE-bench Verified 76.4**；SWE-bench Multilingual 69.3；LiveCodeBench v6 83.6；Terminal Bench 2 52.5；AIME26 91.3 | 模型卡 https://modelscope.cn/models/Qwen/Qwen3.5-397B-A17B ；外部确认：https://www.morphllm.com/qwen-3-5 、https://deepinfra.com/blog/qwen3-5-397b-a17b-api-benchmarks 、https://llm-stats.com/models/compare/claude-sonnet-4-6-vs-qwen3.5-397b-a17b |
| Qwen/Qwen3.6-35B-A3B | **SWE-bench Verified 73.4**；SWE-bench Pro 49.5；SWE-bench Multilingual 67.2；Terminal-Bench 2.0 51.5；LiveCodeBench v6 80.4；MCPMark 37.0 | 模型卡 https://modelscope.cn/models/Qwen/Qwen3.6-35B-A3B |
| Qwen/Qwen3-Coder-480B-A35B-Instruct | **SWE-bench Verified 70.6**（Qwen3-Coder-Next 技术报告，teacher 模型，随 scaffold 波动 70.6%/…）；模型卡无数字，指向 blog | 模型卡（无分数）https://modelscope.cn/models/Qwen/Qwen3-Coder-480B-A35B-Instruct ；https://arxiv.org/html/2603.00729v1 ；https://www.swebench.com/ |
| Qwen/Qwen3-Coder-30B-A3B-Instruct | **SWE-bench Verified 51.6**（OpenHands 100 turns，官方答复）；另一独立评测 50.3%（Nebius 微调版对比） | 模型卡（无分数）https://modelscope.cn/models/Qwen/Qwen3-Coder-30B-A3B-Instruct ；https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/discussions/30 ；https://nebius.com/blog/posts/openhands-trajectories-with-qwen3-coder-480b |
| deepseek-ai/DeepSeek-V4-Pro | **SWE-bench Verified 80.6**（Max 模式）；SWE Pro 55.4；SWE Multilingual 76.2；LiveCodeBench 93.5；Codeforces 3206；Terminal Bench 2.0 67.9；HumanEval(base) 76.8 | 模型卡 https://modelscope.cn/models/deepseek-ai/DeepSeek-V4-Pro ；外部确认：https://www.morphllm.com/swe-bench-pro （"DeepSeek-V4-Pro-Max 80.6%"） |
| deepseek-ai/DeepSeek-V4-Flash-0731 | **Terminal Bench 2.1 = 82.7**（超 V4-Pro-Preview 72.1、GLM-5.2 81.0）；NL2Repo 54.2；DeepSWE 54.4；Cybergym 76.7；Toolathlon-Verified 70.3 | 模型卡 https://modelscope.cn/models/deepseek-ai/DeepSeek-V4-Flash-0731 ；外部确认：https://flowtivity.ai/blog/deepseek-v4-flash-agent-benchmarks （"82.7 on Terminal Bench 2.1, beating V4-Pro-Preview by 14.7%"） |
| ZhipuAI/GLM-5.2 | **SWE-bench Pro 62.1**；Terminal Bench 2.1 = 81.0（Terminus-2）/ **82.7（Best Reported Harness）**；AIME 2026 99.2；MCP-Atlas 76.8 | 模型卡 https://modelscope.cn/models/ZhipuAI/GLM-5.2 ；外部确认：https://www.morphllm.com/swe-bench-pro （"GLM-5.2 leads open weights at 62.1%"） |
| ZhipuAI/GLM-5 | **SWE-bench Verified 77.8**；SWE-bench Multilingual 73.3；Terminal-Bench 2.0 56.2/60.7（Terminus 2/Claude Code）；AIME 2026 I 92.7 | 模型卡 https://modelscope.cn/models/ZhipuAI/GLM-5 |
| ZhipuAI/GLM-4.7 | **SWE-bench Verified 73.8**；SWE-bench Multilingual 66.7；Terminal Bench 2.0 41.0；LiveCodeBench-v6 84.9；AIME 2025 95.7 | 模型卡 https://modelscope.cn/models/ZhipuAI/GLM-4.7 |
| moonshotai/Kimi-K2.7-Code | 模型卡**无 SWE-bench**：Kimi Code Bench v2 62.0、MCP Atlas 76.0、MCP Mark Verified 81.1、Program Bench 53.6；外部：SWE-bench **78.2%**（vals.ai 自测 harness）、**60.4%**（OpenRouter 自测 harness，两者口径不同） | 模型卡 https://modelscope.cn/models/moonshotai/Kimi-K2.7-Code ；https://www.vals.ai/models/kimi_kimi-k2.7-code ；https://openrouter.ai/moonshotai/kimi-k2.7-code |
| moonshotai/Kimi-K3 | **Terminal-Bench 2.1 = 88.3**（Kimi Code harness，官方博客同口径）；DeepSWE 67.5；ProgramBench 77.8；FrontierSWE 81.2；MCPMark-Verified 94.5；MCP-Atlas 84.2；BrowseComp 91.2（90.4 无上下文管理）；外部 **SWE-bench Verified 93.4%**（modelfit） | 模型卡 https://modelscope.cn/models/moonshotai/Kimi-K3 ；官方博客 https://www.kimi.com/blog/kimi-k3 ；https://modelfit.io/blog/can-you-run-kimi-k3-locally |
| stepfun-ai/Step-3.7-Flash | **SWE-Bench PRO 56.3**（第二名）；ClawEval-1.1 67.1；Toolathlon 49.5；HLE w/ Tool 48.1；Terminal-Bench 2.1 59.5；GDPVal-AA 45.8 | 模型卡 https://modelscope.cn/models/stepfun-ai/Step-3.7-Flash |

---

## 4. 与 README 提取分数的差异/确认情况

| 主代理 README 数据 | 本次核验结果 | 判定 |
|---|---|---|
| Qwen3.5-397B SWE-bench Verified = **80.0** | 模型卡原文 Qwen3.5 列 = **76.4**；80.0 是表中 **GPT5.2** 列的值（列错位）。外部 4 个来源（morphllm/deepinfra/llm-stats/threads）均确认 **76.4** | ❌ **错误，需修正为 76.4** |
| Qwen3.6-35B SWEV = **75.0** | 模型卡 Qwen3.6-35BA3B 列 = **73.4**；75.0 是表中 **Qwen3.5-27B** 列的值（列错位） | ❌ **错误，需修正为 73.4** |
| GLM-5 SWEV = **77.8** | 模型卡 GLM-5 列 = 77.8 | ✅ 一致 |
| GLM-4.7 SWEV = **73.8** | 模型卡 GLM-4.7 列 = 73.8 | ✅ 一致 |
| KAT-Coder SWEV = **69.4** | 未找到任何来源支持。Kimi-K2.7-Code 模型卡**无 SWE-bench 行**；69.4 恰好是卡内 "MCP Atlas" 行 **Kimi K2.6** 列的值（疑为误标）。外部口径：vals.ai 78.2%、OpenRouter 60.4%（均非 69.4） | ❌ **无法溯源，疑为 MCP Atlas/K2.6 数值误标；SWE-bench 建议改用外部口径并注明 harness 差异** |
| GLM-5.2 SWE-bench Pro = **62.1** | 模型卡 62.1 + morphllm 外部确认 62.1（开源第一） | ✅ 一致 |
| GLM-5.2 Terminal Bench 2.1 = **81.0 / 82.7** | 模型卡 81.0（Terminus-2）/ 82.7（Best Reported Harness） | ✅ 一致 |

### 附：其他重要发现
1. **DeepSeek-V4-Flash-0731 卡片无 SWE-bench Verified/HumanEval**，主打 Terminal Bench 2.1=82.7（终端 agent 能力显著强于其 Pro preview 72.1，甚至高于 GLM-5.2 81.0）——编程排序时需注意「SWEV 缺失 vs 终端能力突出」的错位。
2. 各厂商 harness 不同（Qwen 自家 scaffold / OpenHands / Kimi Code / Claude Code / Codex），**跨模型直接比较分数需谨慎**，尤其 Kimi 系与 DeepSeek-V4 系。
3. Qwen3.6-35B-A3B 在 ModelScope 无 API 提供方（Providers=null）——若主报告把它列入"可 API 接入"清单，与事实冲突。
4. 魔粒/次与 CostTier 观察值：ultra→2 魔粒/次，standard→1 魔粒/次；无 ModelScope 自营提供方的模型不显示魔粒价（需第三方 Key）。

## 附：探测文件清单（.cluster 目录）
probe1-8.json / probe_post.json / alt1-6.json / prov1-5.json / providers.json(2,3) / fee_0..11.json（12 模型费用台账原始响应）/ readme_0..11.md（12 模型卡原文）/ tables_out.txt（表格提取）/ learn6.json（官方 1409 文章）/ cherry.md（Cherry 文档）/ chunk_summary.js / chunk76150.js（逆向依据）等。
