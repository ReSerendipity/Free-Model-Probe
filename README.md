# free_model_probe — 免费模型清单调研与连通性测试台

一个统一的项目：**Web 端通用连通性测试台** + **两个平台（ModelScope / OpenRouter）的免费模型清单调研包**。

三个原本独立的文件夹（`ModelScope`、`OpenRouter`、`TestWebUI`）在 2026-09-30 整合到这里。

---

## 目录结构

```
free_model_probe/
├─ README.md                    本文件：项目总览与入口导航
├─ start_webui.bat              根启动器 → 启动 webui/server.py
├─ .gitignore
├─ webui/                       【通用工具】模型连通性测试台（原 TestWebUI）
│   ├─ server.py                纯标准库后端，默认 http://127.0.0.1:8777
│   ├─ index.html               三种测试：单轮连通性 / 多轮负载 / 扫描新增模型
│   ├─ start.bat                测试台自身启动器
│   └─ snapshots/               扫描新增用的基线快照（key = md5(base_url|filter)）
└─ providers/
    ├─ modelscope/              【平台包】原 ModelScope
    │   ├─ README-说明.md        平台包详细说明（含 v3.0~v5.3 全部版本记录）
    │   ├─ 工具集/               fetch_data.py + build_report.py + probe_supplement.py + data/ + output/
    │   ├─ 最终报告/             HTML 报告 + 2 份 CSV 台账
    │   └─ 调研数据/             原始接口响应留痕（可追溯每条数据来源）
    └─ openrouter/              【平台包】原 OpenRouter
        ├─ README-说明.md        平台包详细说明
        ├─ 工具集/               diff_free_models.py + openrouter_connectivity_test.py + build_report.py + data/
        └─ 最终报告/             3 份 HTML 报告（含历史版本）
```

**分工**：`webui/` 是与平台无关的通用测试工具（已内置 OpenRouter / ModelScope 两个地址预设）；`providers/<平台>/` 各自维护该平台的清单抓取、费用/基准数据、报告生成与历史留痕。两者互不依赖——测试台可直接对任意 OpenAI 兼容端点使用。

---

## 快速开始

### ① 用 Web 测试台（最常用）

```bash
start_webui.bat            # 或 cd webui && python server.py
```

浏览器打开 <http://127.0.0.1:8777>，填写 **Base URL** + **API Key**（密钥仅本地使用，不落盘），点顶部预设按钮可一键填入 OpenRouter / ModelScope 地址。三个功能：

| 功能 | 作用 |
|---|---|
| ① 单轮连通性 | 拉 `/models` 按过滤（全部 / 仅免费 / 免费+文本）筛选，逐模型发一次请求，看状态与延迟 |
| ② 多轮负载 | N 个并发会话 × 每会话 M 轮对话，统计成功率 / 吞吐 / p50·p95 延迟 / 429 率 |
| ③ 扫描新增 | 拉清单 → 与上次快照 diff → 只对**新增**模型自动测连通性 |

改端口：`PORT=9000 python server.py`。

### ② ModelScope 平台包

```bash
cd providers/modelscope/工具集
python fetch_data.py          # 抓清单 + 魔粒费用 + README 基准 → data/models.json / models.csv
python build_report.py        # 读 data/models.json，生成排序报告 → output/
python probe_supplement.py    # 周期性探测「网站有、清单无」的模型（默认仅报告）
python probe_supplement.py --apply   # 确认后写入 supplement_models.txt
```

### ③ OpenRouter 平台包

```bash
cd providers/openrouter/工具集
python diff_free_models.py                                   # 拉官方清单 + 与上版 diff
python openrouter_connectivity_test.py --skip-fetch --out=connectivity_test.json
python build_report.py                                       # 生成带日期的 HTML 报告
```

---

## 当前结论速览

**ModelScope**（2026-09-21 核验）— 24 个可接 agent 的对话/推理模型（原始清单 37 → 剔除 13：9 专用 + 3 基座 PT + 1 确认不可用）。魔粒费用三档：ultra 2 粒/次 ×6、standard 1 粒/次 ×16、lite 0.5 粒/次 ×2；每日 2000 次免费调用（UTC+8 0:00 重置）。编程总分 Top：`DeepSeek-V4-Pro-0813`(87.9) > `DeepSeek-V4-Flash-Vision-Exp`(83.9) > `DeepSeek-V4-Flash-0731`(82.7)。

**OpenRouter**（2026-09-18 实测）— 免费+文本输出 25 个 → 18 个可用（17 直连 + `z-ai/glm-5.2:free` 重试后可用）。3 个上游共享池 429、4 个地区/策略 403 硬不可用。延迟 2.18s~42.23s，中位约 9.8s。限额：`:free` 模型 20 次/分。

> 精确数字以各平台包 `最终报告/` 与 `工具集/data/` 为准；两个平台包自己的 `README-说明.md` 有完整结论、复现步骤与已知局限。

---

## 整合记录（2026-09-30）

| 原路径 | 现路径 |
|---|---|
| `TODO\ModelScope` | `free_model_probe\providers\modelscope` |
| `TODO\OpenRouter` | `free_model_probe\providers\openrouter` |
| `TODO\TestWebUI` | `free_model_probe\webui` |

**备份**：`TODO\.backup-20260930-215151\`（12M，363 + 19 + 3 个文件，与迁移前逐一核对一致）。确认新项目无误后可自行删除。

**本次一并修复的问题**：

1. `webui/start.bat` 原为 **LF 行尾**（不是 CRLF）——LF-only 的 `.bat` 在 `if (...)` 括号块处会出错，已转 CRLF。
2. `providers/modelscope/工具集/v4_connectivity_test.py`、`v4_pro_final_test.py`、`v4_retest_full.py` 里写死了 `C:\Users\Doro\Desktop\ModelScope\工具集\data\...`（该路径在文件夹移入 `TODO` 后**早已失效**），已改为基于 `__file__` 的 `DATA_DIR`，随项目整体迁移不再失效。
3. 两个 `.bat` 内容改为**纯 ASCII 英文**（原文件含中文字符串，命令行下易乱码），符合 `AGENTS.md` 2.6 的脚本编码规范。
4. 新增根启动器 `start_webui.bat` 与 `.gitignore`（忽略 `__pycache__/`、`*.pyc`）。

其余脚本原本就用 `__file__` 相对定位（`BASE_DIR` / `HERE` / `ROOT`），迁移后路径全部有效，已逐个 `py_compile` 通过。

---

## 注意事项

- **密钥管理（已外置）**：`providers/*/工具集/` 下的脚本**不再内置明文密钥**，统一从环境变量读取，其次回退到同目录本地未提交的 `local_secret.py`：
  - OpenRouter：`OPENROUTER_API_KEY`
  - ModelScope：`MODELSCOPE_API_KEY`
  - 首次使用把 `local_secret.example.py` 复制为 `local_secret.py` 并填入密钥即可（`local_secret.py` 已被 `.gitignore` 忽略，不会入库）。
- **数据缓存**：ModelScope 详情缓存 24h（`DETAIL_TTL`），模型卡更新最多滞后 24h；强制刷新删 `data/raw/{model}__detail.json`。
- **基准分局限**：ModelScope 的基准分由 README 自动提取，v5.3 起已收敛「误抓竞品对比表」，但高精度场景仍建议人工核对 `bench_warns`。
- **接口边界**：ModelScope 无登录态无法枚举全量目录（`/api/v1/models` 返回 404/401），故用「种子家族版本/变体探测」策略。
