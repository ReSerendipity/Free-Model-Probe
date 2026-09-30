# ModelScope 全部交付包 — 说明

打包时间：2026-09-21 ｜ 数据核对时间：2026-09-21（接口 + 网站双重核验）

## 目录结构

| 目录 | 内容 | 用途 |
|---|---|---|
| 工具集/ | fetch_data.py + build_report.py + readme.md + data/ + output/ | 可复用更新工具：一键刷新模型清单、魔粒费用、排序报告（纯 Python 标准库，无需安装依赖） |
| 最终报告/ | HTML 报告 + 2 份 CSV 台账（11 列完整版 / 精简版） | 本次调研的最终交付物，可直接打开查看 |
| 调研数据/ | 原始接口响应、核验报告、进度文档、中间数据 | 全部过程留痕，可追溯每条数据来源 |

## 关键入口

- 看报告：最终报告/modelscope-编程模型排序与魔粒费用报告.html（浏览器打开）
- 看台账：最终报告/modelscope_agent_ledger_full.csv（Excel 打开）
- 日常更新：进入 工具集/ 执行
  python fetch_data.py
  python build_report.py
- 了解工具：工具集/readme.md（运行方式、排序规则、修改指南、已知局限）

## 核心结论速览

> ⚠️ 本速览为**人工撰写快照**，可能与工具实际输出有出入。精确排序、魔粒费用与编程基准分数**以 `最终报告/` 与 `工具集/data/models.json` 为准**；重跑 `fetch_data.py` + `build_report.py` 后以报告为准。

- 报告现含 **24 个**可接 agent 的对话/推理模型（清单 37 → 剔除 13：9 专用 + 3 基座/PT（`ERNIE-4.5-*-PT`）+ 1 确认不可用 `MiniMax-M3`；含 2 个网站核验补充，见 v5.0）
- 魔粒费用（每次调用）：ultra 档 2 魔粒/次 ×6，standard 档 1 魔粒/次 ×16，lite 档 0.5 魔粒/次 ×2；**无第三方/无魔粒项**（MiniMax-M3 等已剔除，见 v5.1）
- 稳定性：24 个中 4 个为「实验/预览」档（`DeepSeek-V4-Flash-Vision-Exp`、`Qwen3.8-Flash-Next`、`Intern-S2-Preview`、`EA-29B-A4B`），生产用途建议优先选「稳定」档
- 免费额度：每日 2000 次免费调用（UTC+8 0:00 重置，超额 429）；魔粒每日登录 +150、任务最高 +450/日
- 用户示例核实：DeepSeek-V4-Flash-0731 = 2 魔粒/次，与页面弹窗一致

## 调研数据文件索引（调研数据/）

| 文件 | 内容 |
|---|---|
| subagent_recheck.md | 子 Agent 交叉核验报告（费用接口定位、12 模型基准、魔粒规则、3 处基准修正） |
| tools_review.md | 工具审查报告（问题清单与修复对照） |
| spotcheck_summary.md / spotcheck_v2_summary.md | 抽查复核记录（4+3 个模型四维度验证） |
| PROGRESS-20260808.md | 任务进度总结与后续指示（含接口清单） |
| fee_ledger.json / fee_all/ | 43 模型魔粒费用台账 + 逐模型费用接口原始响应 |
| detail_raw/ | 44 个主流代表模型详情原始响应（含 README） |
| list_raw/ | 模型列表 30 页原始数据（1500 模型） |
| spotcheck/ spotcheck_v2/ | 抽查复核原始响应 |
| bench_struct.txt bench_extract.txt | README 基准提取结果 |
| readme_0..11.md | 12 个重点模型卡原文 |

注：调研数据/ 中 alt/probe/d/doc/learn/prov 等 json 为探测过程中的临时文件，可忽略。
---

## v3.0 更新（2026-08-11）

新增「最终报告/modelscope-可用模型清单-v3.html」：整合 v1 基准/费用 + v2 连通性实测 + 2026-08-11 复测修正。
- 实测可用 9 个：2 魔粒（DeepSeek-V4-Flash-0731、Qwen3.5-397B-A17B）+ 1 魔粒（Qwen3.5-122B-A10B 等 7 个）
- 确认不可用 5 个：MiniMax-M3、GLM-4.7-Flash、Hy3、DeepSeek-V4-Pro（状态恶化）、GLM-5.2（状态恶化）
- 1 魔粒档最优解：Qwen3.5-122B-A10B（可用 + SWEV 72.4 最强）
- 详细复测记录：工作区 DELIVERY/连通性复测记录-20260811.md

## v5.0 更新（2026-09-21 · 接口 + 网站双重核验）

用户质疑「只有 4 个新模型」并点名 DeepSeek V4 视觉版。经网站（modelscope.cn/models）与接口双重核验，确认原工具 `fetch_data.py` 存在**方法论盲区**：

> OpenAI 兼容清单 `api-inference.modelscope.cn/v1/models` **不等于** ModelScope 全部免费推理模型。
> 部分模型有魔搭社区免费推理（魔粒计价），却不在该 OpenAI 清单里——例如下方两个。

- **真实新增且可免费调用的模型（共 6 个）**：
  - 接口清单内新增 4 个：`DeepSeek-V4.1-Flash`(2 魔粒/次)、`Qwen3.8-Flash-Next`(1)、`Nex-N2.5-Pro`(1)、`Nex-N2.5-mini`(0.5)
  - **网站核验补回 2 个（原被漏掉）**：`deepseek-ai/DeepSeek-V4-Flash-Vision-Exp`(1 魔粒/次，V4 家族首个多模态/视觉实验模型，用户点名项)、`ZhipuAI/GLM-5.3-Flash`(1 魔粒/次)
- **核验过但不在「魔搭社区免费推理」范畴、未纳入报告**：
  - `ZhipuAI/GLM-5.3`：仅智谱/Z.ai 第三方提供方（需 API Key，无魔粒）
  - `Intern-S2-397B` / `MiniCPM5-2B` / `Agnes-3.0-Flash` / `Ling-3.0-flash-Fin`：仅开放权重，需自部署
  - `MiniMax-H3`：视频生成模型，非对话/推理 LLM，无推理 API
  - `Atria-Dawn-Preview` / `Xing4.0-29B-A4B`：接口返回 500，id 未确认
- **重要提醒**：`fetch_data.py` 以 `/v1/models` 为唯一清单来源，**裸跑会丢弃上述 2 个网站核验模型**。后续如需重抓，请先手动合并 `data/models.json` 中这 2 行，或扩展 `fetch_data.py` 的清单来源。
- 备份位于 `工具集/data/backup-20260921-115129/`。

## v5.1 更新（2026-09-21 下午 · 数据质量二次核查 + 防复发加固）

用户质疑"内容不匹配/过时"，二次核查发现并修复了报告层的系统性隐患（非时间过时，`fetched_at` 为当日）：

- **基准提取正则缺陷（根因）**：`terminal_bench` 写死 `2\.1` 漏抓 "Terminal Bench 2 31.9"；`livecodebench` 用 `[^0-9v]` 把字母 `v` 排除漏抓 "LiveCodeBench v6 90.3"。已放宽版本号与 `v` 前缀，**"有基准"模型 18→19**，并补回 Qwen3.8-27B 等的 LiveCodeBench 分。
- **过滤加固（防噪声反复进入报告）**：
  - 新增 `BASE_MODEL_PATTERNS`（`-pt`/`-base`/pretrained），自动剔除预训练基座模型（如 `ERNIE-4.5-*-PT`，非 agent 对话模型）；
  - 新增 `EXCLUDED_MODELS` 显式剔除**已确认不可用**模型（如 `MiniMax/MiniMax-M3`，v3.0 连通性实测不可用且无魔搭社区提供方）；
  - 报告模型数 28 → **24**。
- **稳定性标签**：依据模型 id 推断 `稳定` / `实验/预览` 档（`Exp`/`Preview`/`early-access`/`Flash-Next` 等），报告与台账新增「稳定性」列，避免误选非 GA 模型。
- **计费口径**：`cost=None`（仅第三方/无魔粒）的模型不再混入魔粒表，报告标注「第三方」；台账新增 `billing` 字段。
- **数据质量校验（每次运行自动告警）**：`fetch_data.py` 新增 `_warn_family_dup` / `_warn_cost_none_no_bench`——
  - 家族级基准重复：多个模型基准 dict 完全相同（如 `Qwen3.5-122B/35B/27B` 共享 `{LCB80.5,SWEV72,TB31.9}`），提示系 README 家族表被误判为各自分数；
  - 无成本且无基准：疑似不可用/仅第三方，提示确认是否应剔除。
- **已知残留局限（暂未自动修复，需人工注意）**：① 同族模型 README 共用一张基准表，正则抓到同一行 → 显示相同分数，应按"同族按尺寸/价格选"而非独立分；② 基准分数取自 README 全文**首个命中**，若卡内含对比表可能误抓竞品分；③ SWE-bench Verified / Pro / Terminal / LiveCodeBench 分属不同 harness，不可直接横比；④ 详情缓存 24h，模型卡更新最多滞后 24h；⑤ `supplement_models.txt` 仍靠人工维护（网站有、清单无的模型不会被自动发现）。
- 报告 HTML 新增「模态 / 稳定性」两列；`build_report.py` 排序与渲染同步更新。

## v5.2 更新（2026-09-21 · 报告层收敛：同族去重 + 统一编程总分）

继续收敛 v5.1 遗留 5 条局限中**报告层可修**的两条（家族重复 / 跨基准不可横比）：

- **统一编程总分（驱动排序）**：新增 `coding_score()` = 各编码类 harness（SWE-bench Verified/Pro、Terminal Bench、LiveCodeBench、HumanEval；AIME 数学不计入）0-100 分数的**均值**，按此降序排序，取代原固定优先级链（Verified>Terminal>Pro>…）。效果：① 消除"3.5 因 SWE-V 72 被误排到 3.8 之前"的错排——现 1 魔粒档 `Qwen3.8-27B`(75.0) > `Qwen3.5` 系(61.5)；② 全网 Top：`DeepSeek-V4-Pro-0813`(87.9) > `DeepSeek-V4-Flash-Vision-Exp`(83.9) > `DeepSeek-V4-Flash-0731`(82.7) > `Qwen3.8-Flash-Next`(77.2) > `Qwen3.8-27B`(75.0)。
- **同族共享基准标注**：`build_report.py` 检测基准 dict 完全相同的模型组（如 `Qwen3.5-122B/35B/27B` 共享 `{SWEV72,TB31.9,LCB80.5}`），表中以 ⚠「同族共享基准（列出成员）」标注，提示按"同族按尺寸/价格选"而非当作各自独立分数；脚本运行时 `_warn_family_dup` 同步告警。
- 报告与台账均新增「编程总分」列；`build_report.py` 页脚说明更新排序与同族标注规则。

> 仍未修复（属数据源层，非报告层能解，需人工）：① 基准取自 README 全文首个命中，对比表可能误抓竞品分；② 详情缓存 24h；③ `supplement_models.txt` 靠人工维护（网站有/清单无的模型不会被自动发现）。

## v5.3 更新（2026-09-21 晚 · 数据源层防复发：基准去竞品化 + 清单外模型自动探测）

针对 v5.1 / v5.2「仍未修复」中**数据源层**的两条残留局限（① 对比表误抓竞品分、③ 补充清单靠人工维护），落地两处修复，并实测确认 ModelScope 目录接口的可用性边界。

### Fix 1 — 基准提取限定到「模型自身」章节（防竞品误取）
- 重写 `fetch_data.py` 的 `extract_benchmarks(readme, mid)`：对每个基准关键词取**全部命中**，优先选上下文含「自身模型名」者；上下文含**其他已知家族名**（对比表）则跳过；若全部命中都在对比上下文，取首个并记入 `bench_warns` 告警（提示人工核对模型卡）。
- 新增校验例程 `_warn_bench_compare(rows)`：运行末逐模型打印「疑似取自对比表」的基准 key，与既有 `_warn_family_dup` / `_warn_cost_none_no_bench` 并列。
- `bench_warns` 同步落库：`data/models.json` 的 `bench_warns`（list）与 `data/models.csv` 的 `bench_warn`（竖线连接字符串）列，便于追溯。
- 直接消除 v5.1/v5.2 局限 ①：即便模型卡含竞品对比表，默认也不再静默抓错分；疑似项显式告警。

### Fix 2 — 清单外模型「增量探测」脚本（自动化补回网站有/清单无的模型）
- 新增 `工具集/probe_supplement.py`：基于种子家族（`工具集/probe_watchlist.txt`，一行一个基础 model id）**自动生成下一版本 + 变体后缀候选 id**（如 `V4→V5/V4.1`；`+ -Flash/-Pro/-Vision/-Mini/-Turbo/-Max/-Next/-Lite/-Air/-Plus/-Exp/-Thinking`），逐个探测 `FEE_API`（`list_model_providers`）：凡返回含「魔搭社区」提供方者即视为有免费推理的新模型。
- 复用 `fetch_data.py` 的 `http_get` / `parse_fee` / `FEE_API`，不重复造轮子；去重基准为 `data/raw/list.json` 缓存 + `supplement_models.txt`。
- **默认 dry-run 仅报告**；加 `--apply` 才把发现写入 `supplement_models.txt`（带探测日期注释）。下次 `fetch_data.py` 自动并入，杜绝重跑被丢弃。
- 直接消除 v5.1/v5.2 局限 ③：`supplement_models.txt` 不再纯人工维护，可周期性自动探测发现。

### 目录接口可用性边界（实测，影响 Fix 2 形态）
- 尝试全量枚举 ModelScope 目录：`GET https://modelscope.cn/api/v1/models` → **404**；`POST`（带 SearchText 等参数）→ **401 Unauthorized**（需登录）。即**无登录态无法枚举全量目录**，故 Fix 2 设计为「种子家族版本/变体探测」而非「全量遍历」，避免依赖不可用接口。
- 结论：保持双源策略——`/v1/models`（OpenAI 兼容清单，主力）+ `supplement_models.txt`（网站核验/探测补回的清单外模型）。

### 运行方式（更新）
```
# 日常更新（同前）
python fetch_data.py
python build_report.py

# 周期性自动探测清单外新模型（默认报告，不写文件）
python probe_supplement.py
# 确认无误后写入 supplement_models.txt
python probe_supplement.py --apply
# 仅探测指定家族：python probe_supplement.py --seed deepseek-ai/DeepSeek-V4
```
