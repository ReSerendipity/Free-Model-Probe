# -*- coding: utf-8 -*-
"""
ModelScope 报告生成工具（可复用）
=================================
用途：读取 fetch_data.py 生成的 data/models.json，按编程能力从高到低排序，
渲染 Fathom 科学期刊风格 HTML 报告，并输出排序后的 CSV。

用法：
    python build_report.py                 # 默认输出到 output/
    python build_report.py --out my.html   # 指定输出文件
    python build_report.py --no-csv        # 只生成 HTML

排序规则（可配置）：
    1. 有公开基准（swe_bench_verified / swe_bench_pro / terminal_bench /
       livecodebench / humaneval / aime 任一命中）→ 按主基准降序；
    2. 无基准 → 按 downloads 降序排在后面，标注「无公开编程基准」。
依赖：仅 Python 3.8+ 标准库。
"""
import argparse
import csv
import html
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(BASE_DIR, "data", "models.json")
OUT_DIR = os.path.join(BASE_DIR, "output")

# 主排序基准优先级（第一个有值的作为排序键）
BENCH_PRIORITY = ["swe_bench_verified", "terminal_bench", "swe_bench_pro",
                  "livecodebench", "humaneval", "aime"]
BENCH_LABEL = {
    "swe_bench_verified": "SWE-bench Verified",
    "swe_bench_pro": "SWE-Bench Pro",
    "terminal_bench": "Terminal Bench 2.1",
    "livecodebench": "LiveCodeBench",
    "humaneval": "HumanEval",
    "aime": "AIME",
}

NAVY = "#1b2a4a"
ACCENT = "#c8a24a"

# 用于「统一编程总分」的编码类基准（不含 AIME 数学竞赛分）
CODING_BENCH = ["swe_bench_verified", "swe_bench_pro", "terminal_bench",
               "livecodebench", "humaneval"]


def coding_score(model: dict):
    """统一编程总分：各编码类 harness 分数（0-100）的均值；无编码基准返回 None。

    说明：SWE-bench Verified/Pro、Terminal Bench、LiveCodeBench、HumanEval 量纲均为
    0-100 百分比，取均值仅作跨模型快速比较之用，不代表严格加权总分；AIME（数学）不计入。
    """
    b = model.get("benchmarks") or {}
    vals = []
    for k in CODING_BENCH:
        v = b.get(k)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def sort_key(model: dict):
    """排序键：(是否无基准, 统一编程总分, 下载量)。"""
    s = coding_score(model)
    if s is None:
        return (1, 0.0, -(model.get("downloads") or 0))
    return (0, -float(s), -(model.get("downloads") or 0))


def bench_summary(model: dict) -> tuple[str, str]:
    """返回 (基准文本, 是否无基准)。"""
    b = model.get("benchmarks") or {}
    parts = []
    for k in BENCH_PRIORITY:
        if b.get(k) is not None:
            parts.append(f"{BENCH_LABEL[k]} {b[k]:g}")
    if parts:
        return "；".join(parts), False
    return "无公开编程基准", True


def cost_badge(cost):
    if cost is None:
        return '<span class="cost-badge cost-0">第三方</span>'
    cls = "cost-2" if cost >= 2 else "cost-1"
    return f'<span class="cost-badge {cls}">{cost} 魔粒/次</span>'


def stability_label(s):
    return "实验/预览" if s == "实验/预览" else "稳定"


def modality_label(tasks_str):
    """根据 tasks 字段推断模态标签（避免把多模态模型误标为纯文本）。"""
    t = (tasks_str or "").lower()
    if "image-text-to-text" in t or "multi-modal" in t or "视觉" in t or "图文" in t:
        return "多模态(图文)"
    if "text" in t or "文本" in t:
        return "文本"
    if not t or t == "—":
        return "—"
    return html.escape(tasks_str)


def render_html(models: list, fetched_at: str) -> str:
    n = len(models)
    n_cost = sum(1 for m in models if m.get("magic_cost_per_call") is not None)
    n_bench = sum(1 for m in models if (m.get("benchmarks") or {}))
    n_2 = sum(1 for m in models if (m.get("magic_cost_per_call") or 0) >= 2)

    # 家族级共享基准检测：多个模型基准 dict 完全相同 → 标注「同族共享基准」
    from collections import defaultdict
    _grp = defaultdict(list)
    for m in models:
        b = m.get("benchmarks") or {}
        if b:
            _grp[json.dumps(b, sort_keys=True)].append(m.get("model_id"))
    family_shared = {}
    for v in _grp.values():
        if len(v) > 1:
            for mid in v:
                family_shared[mid] = [s for s in v if s != mid]

    rows_first, rows_rest = [], []
    for i, m in enumerate(models, 1):
        btxt, no_bench = bench_summary(m)
        score = coding_score(m)
        mid_raw = m.get("model_id") or ""
        # 同族共享基准标注（避免把家族表分数误当各模型独立分数）
        fam_span = ""
        if mid_raw in family_shared:
            fam_span = f' <span class="fam">⚠ 同族共享基准（{", ".join(family_shared[mid_raw])}）</span>'
        # 对比表取值待核验标注（Fix 1：基准疑似取自模型卡对比表，可能是竞品分）
        cmp_span = ""
        warns = m.get("bench_warns") or []
        if warns:
            cmp_span = f' <span class="cmpwarn">⚠ 对比表取值待核验（{", ".join(warns)}）</span>'
        org = html.escape(m.get("organization") or "")
        mid = html.escape(mid_raw)
        tier = html.escape(m.get("cost_tier") or "")
        dl = m.get("downloads")
        dl_txt = f"{dl:,}" if dl is not None else "-"
        extra = f'<span class="muted">下载 {dl_txt} · {tier}</span>' if tier else f'<span class="muted">下载 {dl_txt}</span>'
        stab = m.get("stability") or "稳定"
        stab_cls = "stab-exp" if stab == "实验/预览" else "stab-stable"
        row = (f'<tr><td class="rank">{i}</td>'
               f'<td><b>{mid}</b><br>{extra}</td>'
               f'<td>{cost_badge(m.get("magic_cost_per_call"))}</td>'
               f'<td class="mod">{modality_label(m.get("tasks"))}</td>'
               f'<td class="stab {stab_cls}">{stability_label(stab)}</td>'
               f'<td class="score">{score if score is not None else "—"}</td>'
               f'<td>{html.escape(btxt)}{fam_span}{cmp_span}</td></tr>')
        if no_bench:
            rows_rest.append(row)
        else:
            rows_first.append(row)

    table_first = ("<table><tr><th style='width:5%'>#</th><th style='width:26%'>模型</th>"
                   "<th style='width:10%'>计费</th><th style='width:12%'>模态</th>"
                   "<th style='width:10%'>稳定性</th><th style='width:9%'>编程总分</th>"
                   "<th>编程基准（官方/权威）</th></tr>"
                   + "".join(rows_first) + "</table>") if rows_first else ""
    table_rest = ("<h3>无公开基准（按下载量排序）</h3>"
                  "<table><tr><th style='width:5%'>#</th><th style='width:26%'>模型</th>"
                  "<th style='width:10%'>计费</th><th style='width:12%'>模态</th>"
                  "<th style='width:10%'>稳定性</th><th style='width:9%'>编程总分</th>"
                  "<th>备注</th></tr>"
                  + "".join(rows_rest) + "</table>") if rows_rest else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ModelScope 可接 Agent 模型：编程能力排序与魔粒费用（自动生成 {fetched_at}）</title>
<style>
  :root{{--navy:{NAVY};--gray-900:#222831;--gray-700:#4a5568;--gray-500:#8a94a6;
    --gray-200:#e4e8ef;--gray-100:#f2f4f8;--bg:#fafbfd;--accent:{ACCENT};--green:#2e7d5b;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);
    color:var(--gray-900);line-height:1.65;font-size:15px;}}
  .wrap{{max-width:1100px;margin:0 auto;padding:48px 32px 80px;}}
  header{{border-bottom:3px solid var(--navy);padding-bottom:24px;margin-bottom:36px;}}
  .kicker{{font-size:12px;letter-spacing:.18em;color:var(--gray-500);text-transform:uppercase;margin-bottom:10px;}}
  h1{{font-size:28px;color:var(--navy);font-weight:700;line-height:1.3;}}
  .subtitle{{color:var(--gray-700);margin-top:10px;font-size:15px;}}
  .meta-line{{margin-top:14px;font-size:12.5px;color:var(--gray-500);}}
  h2{{font-size:20px;color:var(--navy);margin:44px 0 16px;padding-left:12px;border-left:4px solid var(--accent);font-weight:600;}}
  h3{{font-size:15px;color:var(--gray-900);margin:24px 0 10px;font-weight:600;}}
  table{{width:100%;border-collapse:collapse;background:#fff;margin:14px 0;font-size:13.5px;}}
  th{{background:var(--navy);color:#fff;text-align:left;padding:10px 12px;font-weight:600;font-size:12.5px;}}
  td{{padding:9px 12px;border-bottom:1px solid var(--gray-200);vertical-align:top;}}
  tr:nth-child(even) td{{background:var(--gray-100);}}
  .rank{{font-weight:700;color:var(--navy);font-size:14px;}}
  .muted{{color:var(--gray-500);font-size:12px;}}
  .mod{{font-size:12px;color:var(--gray-700);white-space:nowrap;}}
  .stab{{font-size:12px;white-space:nowrap;}}
  .stab-exp{{color:#b23b3b;font-weight:600;}}
  .stab-stable{{color:var(--green);}}
  .score{{font-weight:700;color:var(--navy);font-size:14px;white-space:nowrap;}}
  .fam{{font-size:11px;color:#b23b3b;}}
  .cmpwarn{{font-size:11px;color:#b23b3b;background:#fdeaea;padding:1px 6px;border-radius:6px;}}
  .cost-badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap;}}
  .cost-2{{background:#e8edf7;color:var(--navy);}}
  .cost-1{{background:#f0f4f1;color:var(--green);}}
  .cost-0{{background:#f9efef;color:#b23b3b;}}
  .metrics{{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0;}}
  .metric{{flex:1;min-width:150px;background:#fff;border:1px solid var(--gray-200);
    border-top:3px solid var(--navy);padding:16px 18px;}}
  .metric .num{{font-size:24px;font-weight:700;color:var(--navy);}}
  .metric .lbl{{font-size:12.5px;color:var(--gray-500);margin-top:4px;}}
  .note{{background:#fff;border:1px solid var(--gray-200);padding:16px 20px;margin:14px 0;
    font-size:13.5px;color:var(--gray-700);}}
  .footnotes{{border-top:1px solid var(--gray-200);margin-top:40px;padding-top:16px;
    font-size:12px;color:var(--gray-500);}}
  @media(max-width:760px){{.wrap{{padding:24px 14px 60px;}}h1{{font-size:22px;}}table{{font-size:12px;}}}}
</style>
</head>
<body><div class="wrap">
<header>
  <div class="kicker">ModelScope Model Survey · 自动生成</div>
  <h1>可接 Agent 的对话/推理模型：编程能力排序与魔粒费用</h1>
  <div class="subtitle">数据来自 ModelScope 公开接口（api-inference / list_model_providers / 模型详情），
  由 fetch_data.py + build_report.py 自动更新。</div>
  <div class="meta-line">📅 抓取时间：{fetched_at} ｜ 🧮 模型数：{n} ｜ 💳 有魔粒价：{n_cost} ｜ 📊 有编程基准：{n_bench}</div>
</header>

<div class="metrics">
  <div class="metric"><div class="num">{n}</div><div class="lbl">API 可调用模型（已剔除专用模型）</div></div>
  <div class="metric"><div class="num">{n_cost}</div><div class="lbl">魔搭社区自营提供方（魔粒计价）</div></div>
  <div class="metric"><div class="num">{n_bench}</div><div class="lbl">有公开编程基准分数</div></div>
  <div class="metric"><div class="num">{n_2}</div><div class="lbl">2 魔粒/次（ultra 档）</div></div>
</div>

<h2>一、编程能力排序（从高到低）</h2>
{table_first}
{table_rest}

<h2>二、费用与数据说明</h2>
<div class="note">
<b>魔粒 = 魔搭社区的「魔力」</b>。魔搭社区自营提供方按<b>每次调用</b>扣费：
ultra 档 2 魔粒/次、standard 档 1 魔粒/次；第三方提供方（百炼/智谱/Moonshot 等）走各自 API Key 计费。
每日累计 2000 次免费调用（UTC+8 0:00 重置，超额返回 429），魔粒可通过每日登录（+150）与任务（最高 +450/日）获取。
接入方式：base_url = <code>https://api-inference.modelscope.cn/v1</code>，OpenAI SDK 兼容（亦支持 Anthropic beta 协议）。
</div>

<div class="footnotes">
  生成工具：tools/modelscope-updater/fetch_data.py + build_report.py ｜
  <b>排序规则</b>：按「编程总分」降序（编程总分 = 各编码类 harness 分数 SWE-bench Verified / Pro、Terminal Bench、LiveCodeBench、HumanEval 的 0-100 均值，AIME 数学不计入）；无编码基准模型按下载量排后。
  <b>同族共享基准</b>：当多个模型基准 dict 完全相同（README 家族级共享表被抓取为同一行），表中以 ⚠ 标注并列出同族成员，应按「同族按尺寸/价格选」而非当作各自独立分数。
  <b>对比表取值待核验</b>：标 ⚠ 的模型，其部分基准在 README 中仅见于「多模型对比表」、且无法定位到该模型自身章节（可能是竞品分数），仅供粗览，精确排序请以官方模型卡为准。
  基准分数从模型卡 README 提取，跨厂商 harness 差异请以官方报告为准。
</div>
</div></body></html>"""


def write_csv(models: list, path: str):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["排名", "模型ID", "发布方/机构", "魔搭社区魔粒/次", "CostTier", "计费口径",
                    "模态", "稳定性", "编程总分", "编程基准", "下载量", "核对时间"])
        for i, m in enumerate(models, 1):
            btxt, _ = bench_summary(m)
            cost = m.get("magic_cost_per_call")
            cost_cell = cost if cost is not None else "第三方"
            score = coding_score(m)
            w.writerow([i, m.get("model_id"), m.get("organization"),
                        cost_cell,
                        m.get("cost_tier"), "每次调用",
                        modality_label(m.get("tasks")),
                        stability_label(m.get("stability") or "稳定"),
                        score if score is not None else "",
                        btxt,
                        m.get("downloads") or "",
                        m.get("fetched_at") or ""])


def main():
    ap = argparse.ArgumentParser(description="从 data/models.json 生成 HTML 报告与 CSV")
    ap.add_argument("--out", default=None, help="HTML 输出路径（默认 output/modelscope-报告.html）")
    ap.add_argument("--no-csv", action="store_true", help="不生成 CSV")
    ap.add_argument("--data", default=DATA_JSON, help="输入 JSON 路径")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        raise SystemExit(f"未找到 {args.data}，请先运行 python fetch_data.py")

    with open(args.data, encoding="utf-8") as f:
        models = json.load(f)
    if not isinstance(models, list) or not models:
        raise SystemExit(f"{args.data} 为空或格式不正确，请先运行 python fetch_data.py")
    models.sort(key=sort_key)

    os.makedirs(OUT_DIR, exist_ok=True)
    fetched_at = models[0].get("fetched_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_html = args.out or os.path.join(OUT_DIR, "modelscope-编程模型排序与魔粒费用报告.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(render_html(models, fetched_at))

    if not args.no_csv:
        out_csv = os.path.join(OUT_DIR, "modelscope_agent_models.csv")
        write_csv(models, out_csv)
        print(f"CSV: {out_csv}")

    print(f"HTML: {out_html}")
    print(f"模型总数: {len(models)}（有基准 {sum(1 for m in models if (m.get('benchmarks') or {}))}）")


if __name__ == "__main__":
    main()
