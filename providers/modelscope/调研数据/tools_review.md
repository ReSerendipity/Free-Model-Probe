# tools/modelscope-updater 代码审查报告

审查对象：`fetch_data.py` / `build_report.py` / `readme.md`（含 `data/` 实际产物抽样核验）
审查时间：2026-08-09 ｜ 审查方式：静态阅读 + 实测复现（正则行为、BOM、GBK 控制台、路径处理）

---

## a) 健壮性

| # | 结论 | 详情 |
|---|---|---|
| a1 | **通过（附建议）** | 网络重试合理：3 次 + 线性退避（2s/4s，`fetch_data.py` L36-37, L51-57），有界。**建议**：当前对 404 等永久错误也重试 3 次，浪费等待；可仅在 `URLError`/`TimeoutError`/HTTP 5xx 时重试。 |
| a2 | **问题（轻微）** | JSON 解析/字段缺失兜底覆盖了费用与详情环节（外层 try/except 记 ERROR，不崩溃，L166-170/L190-197）；但**清单环节无兜底**：`fetch_model_list`（L70-73）解析失败或 `data` 键非 list（如 dict）时会直接崩溃（dict 迭代出字符串键 → `m.get` AttributeError）。**建议**：`data.get("data")` 后校验 `isinstance(..., list)`，并在 main 入口对清单失败给出友好报错（如提示检查网络/接口 URL）。 |
| a3 | **问题（中，已实测复现）** | 网络解码 `errors="replace"`（L58）、文件读写显式 utf-8、CSV `utf-8-sig`（实测两处 CSV 文件头均为 EF BB BF ✓）均正确。但 **Windows 控制台/管道输出**：L269 打印 `⚠️`（U+26A0）在 cp936(GBK) stdout 下抛 `UnicodeEncodeError`——审查中运行脚本即实测复现（`'gbk' codec can't encode character '\u26a0'`）；stdout 被重定向/管道化（`python fetch_data.py > log.txt`）或旧终端时必现。**建议**：main 开头加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（hasattr 保护，Python 3.7+），或去掉 emoji。 |
| a4 | **问题（中，最值得修）** | **费用接口每模型请求两次**：L161 已 `http_get(FEE_API...)` 下载并写盘，L164 又调 `fetch_fee(mid)`，而 `fetch_fee` 内部（L79）再次 `http_get` 同一接口。43 模型 ≈ 86 次费用请求（含重试更糟），耗时近翻倍、浪费服务端配额。**建议**：`fetch_fee` 改为接收已下载文本 `fetch_fee_from_body(body)`，L164 传入 L161 的 body。 |
| a5 | **问题（轻微）** | L158-160 死代码：`if os.path.exists(raw_f) and not args.skip_detail: pass` 是空操作，注释（"费用变化频繁，每次重拉"）与代码行为无关，易误导维护者。**建议**：删除该分支。 |

## b) 正确性

| # | 结论 | 详情 |
|---|---|---|
| b1 | **问题（中，已实测复现）** | **基准正则年份误匹配**：`swe_bench_verified`/`swe_bench_pro`/`livecodebench`/`humaneval` 四条正则（`fetch_data.py` L111-116）均无年份防护。实测：`"SWE-bench Verified 2025.06: 45.2%"` → 提取 **2025.06**；`"LiveCodeBench Feb 2024: 82.3"` → **2024**；`"HumanEval 2024 result 89.2"` → **2024**。这些是 README 常见表述（"SWE-bench Verified (2025-06)"、"LiveCodeBench (Feb 2024)"）。**建议**：仿照 AIME 的负向前瞻，在捕获数字前加 `(?!20\d{2}(?:[.\-]\d+)?\b)` 拒绝年份，或提取后校验 `0 < score < 100`。 |
| b2 | **问题（轻微）** | AIME 正则（L117）的 `(?!202[0-9]|25|26)`：`25|26` 两个备选是冗余且过激的（年份防护 `202[0-9]` 已足够），会误拒合法分数区间内的 "AIME 25.x/26.x"（若未来 AIME 计分扩展）。**建议**：简化为 `(?!\d{4}\b)`（拒绝一切 4 位数字年份）。 |
| b3 | **通过** | 排序逻辑与文档完全一致：`sort_key`（build_report.py L46-52）= (无基准, −主基准分数, −下载量)，Python 升序 → 有基准优先、分数降序、下载量兜底；`BENCH_PRIORITY`（L31）与 README/HTML 脚注的优先级顺序（SWE-bench Verified > Terminal Bench 2.1 > SWE-Bench Pro > LiveCodeBench > HumanEval > AIME）逐项吻合。**注意**：手工修正 `models.json` 时若 benchmarks 值为非数字字符串，L51 `float(b[k])` 抛 ValueError（实测确认）；README 应注明"只填数字"，或代码做类型容错。 |
| b4 | **通过（附注意）** | non_agent 剔除规则合理：实测当前 43 个模型剔除 12 个，全部为 VL/Image-Edit/XiYanSQL/CompassJudger/AntAngelMed/LongCat 等专用模型，无肉眼可见误伤；`/ernie-4.5-vl-` 与 `-vl-` 冗余但无害（L45-48）。**注意**：子串匹配 `-vl-` 未来可能误伤名称含该子串的通用模型，届时需人工复核剔除清单。 |
| b5 | **问题（轻微）** | 剔除逻辑在**全量抓取之后**执行：12 个注定被剔除的模型仍各浪费 1 次费用 + 1 次详情请求（≈24 次+重试）。**建议**：拿到清单后先算 `is_non_agent`，对默认剔除的模型跳过费用/详情抓取（`--keep-non-agent` 时再全量抓）。 |

## c) 复用性

| # | 结论 | 详情 |
|---|---|---|
| c1 | **通过** | 参数齐全且均有文档：fetch（`--skip-detail`/`--keep-non-agent`，L140-141）、build（`--out`/`--no-csv`/`--data`，L200-202）。 |
| c2 | **问题（中）** | 24h 详情缓存 TTL 有缺陷：命中缓存时**不刷新 mtime**（L176-179），若两次运行间隔 <24h（例如每天早晚各跑一次），详情将**永不刷新**（TTL 从"原始下载时刻"起算而非"上次运行"），报告里的基准/下载量长期过期。**建议**：命中缓存时 `os.utime` 刷新 mtime，或改存抓取时间戳。另：损坏的缓存文件（上次写盘中断）会连续报错直至 24h 后才重拉；建议解析失败时删除缓存并立即重拉一次。 |
| c3 | **通过（附小瑕疵）** | README 结构清晰、命令可直接跑通（PowerShell 一键脚本可用）、已知局限披露诚实（Qwen3.5-397B 提取 80.0 vs 人工核验 76.4）、修改指南定位准确。**小瑕疵**：README 称 `data/raw/` 为"原始响应缓存"，但 `list.json` 存的是**提取后的 id 数组**而非原始响应（fee/detail 才是原始响应）；"约 2-3 分钟"的估算在修复 a4 双重请求后会明显缩短，可同步更新。 |

## d) 安全性

| # | 结论 | 详情 |
|---|---|---|
| d1 | **通过** | 无任何删除操作、无无限循环（清单/重试/睡眠均有界）、默认写入路径均约束在工具目录内（`BASE_DIR/data|output`）；`--out`/`--data` 为显式用户意图。 |
| d2 | **问题（低风险，加固建议）** | 远端返回的模型 id 进入文件名（L156, L173）：`replace("/", "__")` 已防住路径分隔符，但实测 `C:/evil` → `os.path.join` 结果 `'C:__evil__fee.json'`，Windows drive 语义会**丢弃 base 目录**把文件写到 CWD。当前 ModelScope id 格式受控（owner/name），实际风险极低；**建议**顺手加固：`re.sub(r'[^\w.-]', '_', mid)` 白名单化后再拼文件名。 |
| d3 | **通过（附注意）** | HTML 输出的 model_id/organization/tier/基准文本均 `html.escape`（build_report.py L83-85），XSS 卫生良好；`cost_badge`（L91）未 escape 但正常数据为数字，仅手工编辑 JSON 为字符串时存在注入面（与 b3 同一容错点）。 |
| d4 | **通过** | 无意外覆盖用户文件风险：写入的均为本工具管理的 `data/`、`output/` 及用户显式指定的 `--out`。 |

## e) 其他发现

| # | 结论 | 详情 |
|---|---|---|
| e1 | **问题（轻微）** | `fetch_meta.json` 的 `failures`（L260）只统计详情抓取失败，费用失败不会进入失败清单（仅体现在 `providers:"ERROR:..."`），运维时可能漏报。**建议**：费用失败也计入 failures。 |
| e2 | **问题（轻微，数据质量）** | `tasks` 字段是 dict repr 拼接（L221），实测 `models.json` 里是一长串 `{'ChineseName': '文本生成', 'Description': '', ...}`，CSV 台账中非常难看且含单引号。**建议**：只取 `Name`/`DomainName` 等关键字段，或存 JSON 字符串。 |
| e3 | **问题（轻微）** | `build_report.py` L213 `models[0]`：输入 JSON 为空列表时 IndexError 崩溃。**建议**：加 `if not models: raise SystemExit("models.json 为空")`。 |
| e4 | **通过** | 第二张"无基准"表的排名沿用全表序号（L81 全量 enumerate），视觉上延续总排名，确认非 bug；CSV 排序与 HTML 一致（同一 `models` 列表）。 |

---

## 总体结论：**需修复后交付**

核心链路（抓取→解析→过滤→排序→渲染）结构正确、文档诚实、无高危安全问题，数据结构与接口实测吻合（fee `Data.Providers`、detail `Data.ReadMeContent/Downloads/Tasks`、BOM、过滤结果均验证通过）。但存在 **2 个影响数据正确性/效率的中等问题**，建议修复后再交付：

1. **b1 基准年份误匹配**（实测复现，会写入错误分数）— 4 条正则加年份负向前瞻；
2. **a4 费用接口双重请求**（L161+L164/L79，耗时与配额翻倍）— 复用已下载 body；
3. 顺带建议：**c2 缓存 mtime 刷新**（否则高频运行时详情永不更新）、**a3 控制台 emoji 兼容**（重定向即崩溃，已实测）。

以上 4 项均为小改动（合计 <30 分钟），不影响整体架构；其余为轻微/加固项，可排期处理。修复后此工具集可作为"一键更新"例行流程交付。
