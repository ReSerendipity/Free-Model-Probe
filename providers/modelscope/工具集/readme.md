# ModelScope 模型数据更新工具集

一键更新「可接 Agent 的对话/推理模型：编程能力排序与魔粒费用」HTML 报告与 CSV 台账。

## 文件结构

| 文件 | 用途 |
|---|---|
| `fetch_data.py` | 抓取：API 可调用清单 → 逐模型魔粒费用 → 详情/README 编程基准；输出 `data/models.json` + `data/models.csv` + 原始缓存 |
| `probe_supplement.py` | 清单外模型增量探测：基于 `probe_watchlist.txt` 种子生成版本/变体候选，探测 `FEE_API` 魔搭社区免费推理，dry-run 报告 / `--apply` 写入 `supplement_models.txt`（Fix 2） |
| `build_report.py` | 生成：读取 `data/models.json`，按编程能力排序，渲染 Fathom 风格 HTML 报告 + 排序 CSV 到 `output/` |
| `data/raw/` | 原始响应缓存（`list.json`、`{model}__fee.json`、`{model}__detail.json`），24h 内复用 |
| `data/models.json` | 结构化数据（清单 + 费用 + 基准），`build_report.py` 的输入 |
| `data/models.csv` | 全字段台账（UTF-8-BOM，Excel 直接打开） |
| `output/` | 最终交付物：HTML 报告 + 排序 CSV |

## 运行方式

```bash
# 完整更新（推荐，约 2-3 分钟）
python fetch_data.py
python build_report.py

# 只更新费用不动详情（更快，详情读缓存）
python fetch_data.py --skip-detail
python build_report.py

# 自定义输出
python build_report.py --out 我的报告.html --no-csv

# 周期性探测清单外新模型（Fix 2，默认仅报告）
python probe_supplement.py
# 确认无误后写入 supplement_models.txt（下次 fetch_data.py 自动并入）
python probe_supplement.py --apply
# 仅探测指定家族：python probe_supplement.py --seed deepseek-ai/DeepSeek-V4
```

一键脚本（Windows PowerShell）：

```powershell
cd tools\modelscope-updater
python fetch_data.py; python build_report.py
```

依赖：仅 Python 3.8+ 标准库（urllib/json/csv/re），无需 pip install。

## 数据来源（公开接口，无需登录）

| 数据 | 接口 |
|---|---|
| API 可调用清单 | `https://api-inference.modelscope.cn/v1/models` |
| 魔粒费用 | `https://modelscope.cn/api/v1/inference/list_model_providers?ModelId={id}` |
| 详情/README | `https://modelscope.cn/api/v1/models/{owner}/{name}` |

## 排序规则

1. 编程总分驱动排序（v5.2 起）：`build_report.py` 的 `coding_score()` = 各编码类 harness（SWE-bench Verified / Pro、Terminal Bench、LiveCodeBench、HumanEval；AIME 数学不计入）0-100 分数**均值**，按此降序排序；取代原固定优先级链。
2. 有基准模型按编程总分降序排前；无基准模型按下载量降序排后，标注「无公开编程基准」。
3. 同族共享基准标注：基准 dict 完全相同的模型组（如 `Qwen3.5-122B/35B/27B`）以 ⚠「同族共享基准（成员…）」标注，按"同族按尺寸/价格选"而非各自独立分。
4. 自动剔除不可用于 agent 的模型：`NON_AGENT_PATTERNS`（专用模型：image-edit/xiyansql/compassjudger/antangelmed/longcat/internvl/-vl-/ernie-4.5-vl-）、`BASE_MODEL_PATTERNS`（预训练基座：-pt/-base/pretrained，如 ERNIE-4.5-*-PT）、`EXCLUDED_MODELS`（已确认不可用，如 MiniMax-M3）；`--keep-non-agent` 可保留专用模型。

## 已知局限（重要）

- **基准分数为 README 自动提取**，可能受模型卡表格列错位影响（例：Qwen3.5-397B 自动提取 SWEV=80.0，人工核验为 76.4）。需要精确排序时，以人工核验为准，可在 `data/models.json` 中手工修正 `benchmarks` 字段后重跑 `build_report.py`。
- **家族级基准重复（2026-09-21 v5.1 验证）**：同族模型（如 `Qwen3.5-122B/35B/27B`）README 常共用一张基准表，正则抓到同一行 → 报告显示完全相同的分数。应按"同族按尺寸/价格选"，勿当作各自独立分数；运行时 `_warn_family_dup` 会自动告警。
- **基准可能误取自竞品（v5.3 已大幅收敛，仍建议人工核对）**：v5.3 起 `extract_benchmarks` 限定到「模型自身」章节（优先自身模型名上下文、跳过含其他家族名的对比表），疑似竞品分记入 `bench_warns` 并运行时告警（`_warn_bench_compare`）。高精度场景仍建议核对 `data/raw/{model}__detail.json` 原文与 `data/models.json` 的 `bench_warn` 列。
- **跨基准不可直接横比**：SWE-bench Verified / Pro / Terminal Bench / LiveCodeBench 分属不同 harness，报告排序按固定优先级（Verified>Terminal>Pro>LiveCodeBench>…），仅作参考。
- **清单来源盲区（2026-09-21 验证，v5.3 已自动化补回）**：`LIST_API`（`api-inference.modelscope.cn/v1/models`）是 OpenAI 兼容部署清单，**不等于** ModelScope 全部免费推理模型。部分模型有魔搭社区免费推理（魔粒计价）却不在该清单里（如 `deepseek-ai/DeepSeek-V4-Flash-Vision-Exp`、`ZhipuAI/GLM-5.3-Flash`）。v5.3 起用 `probe_supplement.py` 周期性自动探测清单外模型（种子见 `probe_watchlist.txt`，探测 `FEE_API` 魔搭社区提供方），`--apply` 写入 `supplement_models.txt` 后 `fetch_data.py` 自动并入，不再纯人工维护。注意：全量目录枚举不可行——`GET /api/v1/models` 返回 404、`POST` 返回 401（需登录），故探测设计为「种子家族版本/变体探测」而非全量遍历。
- **详情缓存 24h**：`DETAIL_TTL=24*3600`，模型卡（含 README 基准）更新最多滞后 24h；强制刷新请删除 `data/raw/{model}__detail.json`。
- **魔粒费用按「每次调用」计价**（魔搭社区自营提供方）：ultra=2 魔粒/次、standard=1 魔粒/次、lite=0.5 魔粒/次；第三方提供方（百炼/智谱/Z.ai 等）计费字段 `billing=第三方/无魔粒`，报告标注「第三方」。
- 免费额度：每日 2000 次免费调用（UTC+8 0:00 重置，超额 429），魔粒每日登录 +150、任务最高 +450/日。

## 修改指南

- **换排序基准**：改 `build_report.py` 里 `BENCH_PRIORITY` 列表顺序
- **加/减剔除关键词**：改 `fetch_data.py` 里 `NON_AGENT_PATTERNS`
- **改报告样式**：改 `build_report.py` 里 `render_html()` 的 CSS 与版式（颜色变量 `NAVY`/`ACCENT`）
- **换输出目录**：`build_report.py --out 路径`
- **手动修正数据**：编辑 `data/models.json` 后重跑 `build_report.py` 即可（无需重新抓取）
- **API 变化**：三个接口 URL 集中在 `fetch_data.py` 顶部常量（`LIST_API`/`FEE_API`/`DETAIL_API`）

## 更新流程（例行）

1. `python fetch_data.py`（重拉清单+费用，详情读缓存）
2. `python build_report.py`
3. 检查 `output/modelscope-编程模型排序与魔粒费用报告.html` 的模型数与排序是否合理
4. 需要时手工修正 `data/models.json` 基准并重跑步骤 2
