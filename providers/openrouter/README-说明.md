# OpenRouter 免费模型清单与连通性 — 说明

最近更新：2026-09-18 19:47 ~ 19:56 (GMT+8) ｜ 端点：`https://openrouter.ai/api/v1/chat/completions`
上一轮存档：2026-09-07（清单 21 个 → 本轮 25 个）

## 目录结构

| 目录/文件 | 内容 |
|---|---|
| 工具集/diff_free_models.py | 联网拉官方全量清单 → 过滤「免费 + 文本输出」→ 与上一版做新增/下线/字段变更差异，落盘带日期快照 |
| 工具集/openrouter_connectivity_test.py | 连通性实测脚本（纯标准库：逐个 chat/completions → 失败重试 → 429 复测 → 存 JSON）。支持 `--skip-fetch` `--only=a,b` `--no-retry` `--out=文件`；已加全局节流（默认最小请求间隔 3.3s）以贴住 20 次/分限额。密钥从环境变量 `OPENROUTER_API_KEY` 或本地未提交的 `local_secret.py` 读取（模板见同目录 `local_secret.example.py`） |
| 工具集/build_report.py | 从 JSON 结果生成带日期的 HTML 报告（不联网），样式取 工具集/report_style.css |
| 工具集/data/connectivity_test.json | **本轮（2026-09-18）** 全量实测：25 模型逐个状态、延迟、provider、路由、finish_reason、usage、重试记录 |
| 工具集/data/connectivity_test-20260907.json | 上一轮（2026-09-07）实测存档 |
| 工具集/data/probe_results.json | 上一轮能力探针 + 复测原始结果（v2 报告数据源） |
| 工具集/data/raw/free_text_models.json | 当前口径的免费+文本模型清单（连通性脚本读这份） |
| 工具集/data/raw/free_text_models_20260907.json | 上一轮清单快照（21 个） |
| 工具集/data/raw/free_models_diff_20260907_vs_20260918.json | 两轮差异：新增 6 / 下线 2 / 字段变更 0 |
| 工具集/data/raw/models_all_2026090{7,18}.json | 官方全量目录快照（430 → 445） |
| 工具集/data/raw/models_maxprice0_20260918.json | `GET /models?max_price=0` 响应（网站价格筛选同源） |
| 工具集/data/raw/frontend_free_models_20260918.json | 网站前端接口 `api/frontend/v1/models/find?max_price=0` 响应（99 行全模态） |
| 工具集/data/raw/key_info.json | 密钥状态 |
| 最终报告/openrouter-免费模型连通性实测-20260907.html | v1 连通性实测报告（历史） |
| 最终报告/openrouter-免费模型能力排序-v2-20260907.html | v2 429 复测 + 能力探针 + 综合排序（历史） |
| 最终报告/openrouter-免费模型清单更新与连通性实测-20260918.html | **最新**：清单变更 + 25 模型全量实测 + 网站口径核对 |

## 核心结论速览（2026-09-18）

- 免费 + 文本输出口径 **25 个**模型（含 `openrouter/free` 路由器）→ **18 个实测可用**（17 个直连 + `z-ai/glm-5.2:free` 重试后可用）
- 3 个上游共享池限流 429：`google/gemma-4-26b-a4b-it:free`、`google/gemma-4-31b-it:free`（均为 Google AI Studio）、`qwen/qwen3.8-27b:free`（ModelRun，新上架容量未扩）
- 4 个硬性不可用 403：Google Lyria ×2（地区封锁）、Thinking Machines inkling ×2（仅限 agentic harness 调用）—— 与上一轮完全相同，无变化
- 全部可用模型 cost=0；延迟 2.18s ~ 42.23s，中位约 9.8s。最快 `cohere/north-mini-code:free`，最慢 `nvidia/nemotron-3.5-content-safety:free`（42.23s，且是审核分类器）
- 无一例失败源于密钥无效或网络不通：403/429 全部是上游策略
- 官方限额未变（docs/api-reference/limits）：`:free` 模型 20 次/分；累计充值 < $10 → 50 次/天，≥ $10 → 1000 次/天。本密钥累计消费 $0.074，仍在 50 次/天档

## 清单变化（相对 2026-09-07）

新增 6 个免费模型，5 个实测可用：

| 模型 | 上下文 | 输入模态 | 实测 |
|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731:free` | 1M | text | OK 4.91s（OpenInference） |
| `inclusionai/ling-3.0-flash-vl:free` | 262K | text, image, video | OK 8.03s（Novita） |
| `nex-agi/nex-n2.5-mini:free` | 262K | text, image | OK 11.1s（Nex AGI） |
| `nex-agi/nex-n2.5-pro:free` | 262K | text, image | OK 9.04s（Nex AGI） |
| `z-ai/glm-5.2:free` | **33K** | text | 首次 429（Decart overloaded），重试 OK 9.78s |
| `qwen/qwen3.8-27b:free` | 262K | text, image, video | 429 未恢复（ModelRun） |

下线 2 个：**MiniMax 退出免费层** —— `minimax/minimax-m2.7:free`、`minimax/minimax-m3:free` 的免费变体整体从清单删除，基础模型仍在售（prompt $0.30/M、completion $1.20/M）。本轮免费清单里已无 MiniMax。

复测状态翻转：上一轮 3 个 429 中 `poolside/laguna-xs-2.1:free` 本轮恢复正常（20.29s）。

## 网站免费模型口径（本轮核对）

- 网页 `/models?max_price=0` 是**纯客户端渲染**，抓 HTML 拿不到过滤结果（SSR 内容与不过滤时逐字节相同），别用 HTML 抓取来数模型
- 价格滑杆值 0（即 FREE 标签）实际调用 `api/frontend/v1/models/find?max_price=0` → **99 个**零价格模型：image 34 · video 29 · text 22 · rerank 7 · embeddings 3 · speech 2 · audio+text 2
- 叠加「文本输出」后恰为 **24 个**，与 `GET /api/v1/models?max_price=0` 逐个 ID 相等，无差集
- 本报告的第 25 行 `openrouter/free` 是自动路由器，定价字段非零，不出现在网站免费筛选中
- 官方全量目录 445 个（2026-09-07 为 430；期间新上架 28、下架 13）

## 值得注意

- `nvidia/nemotron-3-ultra-550b-a55b:free` 实测仍自述「我是 GLM，Z.ai 训练」；本轮 `poolside/laguna-xs-2.1:free` 自述「我是通义」。两者路由字段均显示各自原生名称——身份存疑，用前注意
- `openrouter/free` 自动路由器本次又把请求路由到 content-safety 分类器（回答 "User Safety: safe"，15.44s），与上一轮一致，不保证是聊天模型
- reasoning 模型在 400 max_tokens 下全部 `finish=length`：`z-ai/glm-5.2:free`（reasoning 796 / content 26）、`poolside/laguna-xs-2.1:free`（reasoning 1290 / content 7）、`nvidia/nemotron-3.5-lightning:free`、`inclusionai/ling-3.0-flash-fin:free`。接 agent 需给足 max_tokens
- `z-ai/glm-5.2:free` 上下文只有 33K，与同族宣称的 1M 窗口不符（免费变体被上游裁剪）
- 新增里有 4 个支持图像输入（`ling-3.0-flash-vl`、`qwen3.8-27b` 还支持视频；`nex-n2.5-mini/pro` 支持图像），免费层首次有较可用的视觉输入选项
- 清单里 `google/lyria-3-*` 与 `openrouter/free` 属于「口径内但非对话用途」——按 free + 文本输出的机械过滤会带进来，读数时注意

## 复现步骤

```bash
cd 工具集
python diff_free_models.py                    # 拉清单 + 出差异（会自动落带日期快照）
python openrouter_connectivity_test.py --skip-fetch --out=connectivity_test.json
python build_report.py                        # 生成当天 HTML 报告
```

当天额度紧张时分两批跑，并保留历史存档：

```bash
python openrouter_connectivity_test.py --skip-fetch --out=connectivity_test.json --only="<新增+历史失败>"
python openrouter_connectivity_test.py --skip-fetch --no-retry --out=connectivity_test.json --only="<历史成功>"
```

`--only` 模式会把结果合并进已有的 `--out` 文件而不是覆盖。

> 密钥管理：`openrouter_connectivity_test.py` **不再内置明文密钥**，改从环境变量 `OPENROUTER_API_KEY` 读取，其次回退到同目录本地未提交的 `local_secret.py`（模板见 `local_secret.example.py`，该文件已被 `.gitignore` 忽略）。
