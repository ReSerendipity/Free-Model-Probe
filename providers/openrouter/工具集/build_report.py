# -*- coding: utf-8 -*-
"""
读取 data/ 下的清单差异与连通性实测结果，生成带日期的 HTML 报告。
用法：python build_report.py [--day=20260918] [--out=最终报告/xxx.html]
仅依赖标准库；不联网。
"""
import json
import os
import re
import sys
import time
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
RAW = os.path.join(DATA, "raw")


def arg(name, default=None):
    p = f"--{name}="
    for a in sys.argv:
        if a.startswith(p):
            return a[len(p):]
    return default


def load(rel):
    return json.load(open(os.path.join(DATA, rel) if not os.path.isabs(rel) else rel, encoding="utf-8"))


def ctx_h(n):
    if not n:
        return "-"
    return f"{n/1e6:.0f}M" if n >= 1e6 else f"{n/1000:.0f}K"


def _key_tail():
    """取密钥末 4 位用于脱敏展示。来源与 openrouter_connectivity_test.py 一致：
    环境变量 OPENROUTER_API_KEY -> 本地未提交的 local_secret.py -> 旧版明文常量（兼容）。"""
    v = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not v:
        try:
            import local_secret
            v = (getattr(local_secret, "OPENROUTER_API_KEY", "") or "").strip()
        except Exception:
            v = ""
    if not v:
        try:
            src = open(os.path.join(HERE, "openrouter_connectivity_test.py"), encoding="utf-8").read()
            v = re.search(r'API_KEY\s*=\s*"([^"]+)"', src).group(1)
        except Exception:
            v = ""
    return v[-4:]


def mask(label):
    tail = ""
    try:
        tail = _key_tail()
    except Exception:
        pass
    return "sk-or-…" + (tail or (label or "")[-4:])


CSS = open(os.path.join(HERE, "report_style.css"), encoding="utf-8").read()


def badge(v):
    if v["status"] == "ok" or v.get("retest", {}).get("status") == "ok":
        r = v.get("retest") if v.get("retest", {}).get("status") == "ok" else v
        if v["status"] != "ok":
            return '<span class="st warn"><span class="dot warn"></span>可用（重试后）</span>', r
        return '<span class="st ok"><span class="dot ok"></span>可用</span>', r
    if v.get("code") == 429:
        return '<span class="st warn"><span class="dot warn"></span>限流 429</span>', v
    if v.get("code") == 403:
        return '<span class="st bad"><span class="dot bad"></span>不可用 403</span>', v
    return '<span class="st bad"><span class="dot bad"></span>失败</span>', v


def reason_of(v):
    body = v.get("body") or ""
    if "not available in your region" in body:
        return "地区封锁（geo restriction）"
    if "only available on agentic harnesses" in body:
        return "仅限 agentic harness 调用"
    if "temporarily rate-limited upstream" in body:
        pn = body.split('"provider_name":"')[1].split('"')[0] if '"provider_name":"' in body else "上游"
        return f"上游共享池容量不足（{pn}）"
    return (v.get("error") or body[:60] or "未知")[:60]


def main():
    day = arg("day", time.strftime("%Y%m%d"))
    pretty = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    conn = load("connectivity_test.json")
    res = conn["results"]
    diff = load(os.path.join("raw", f"free_models_diff_20260907_vs_{day}.json"))
    inv = {m["id"]: m for m in load(os.path.join("raw", "free_text_models.json"))}
    ki = os.path.join("raw", "key_info.json")
    key = load(ki).get("data", {}) if os.path.exists(os.path.join(DATA, ki)) else {}

    usable = {k: v for k, v in res.items() if v["status"] == "ok" or v.get("retest", {}).get("status") == "ok"}
    lat = []
    for k, v in usable.items():
        r = v.get("retest") if v.get("retest", {}).get("status") == "ok" else v
        lat.append(round(r["elapsed"], 2))
    lat.sort()
    r429 = [k for k, v in res.items() if v.get("code") == 429 and k not in usable]
    r403 = [k for k, v in res.items() if v.get("code") == 403]

    H = []
    A = H.append
    A(f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenRouter 免费文本模型清单更新与连通性实测 · {pretty}</title>
<style>{CSS}</style></head><body><div class="canvas">''')

    A(f'''<div class="kicker">OpenRouter · Inventory Update &amp; Connectivity Test · {pretty}</div>
<h1>免费文本模型清单更新与连通性实测</h1>
<p class="lede">对比 {diff["old_day"][:4]}-{diff["old_day"][4:6]}-{diff["old_day"][6:]} 存档，重新拉取 OpenRouter 模型广场
（free 变体 + 文本输出口径）并逐个实测 <code style="font-family:var(--mono);font-size:13px">chat/completions</code>。
清单 {diff["old_count"]} → {diff["new_count"]} 个：新增 {len(diff["added"])}、下线 {len(diff["removed"])}。</p>
<div class="meta-row">
  <div class="meta-cell"><div class="meta-k">测试时间</div><div class="meta-v">{conn["test_time"]} GMT+8</div></div>
  <div class="meta-cell"><div class="meta-k">端点</div><div class="meta-v"><code>api/v1/chat/completions</code></div></div>
  <div class="meta-cell"><div class="meta-k">密钥</div><div class="meta-v"><code>{mask(key.get("label"))}</code> · free tier</div></div>
  <div class="meta-cell"><div class="meta-k">判定口径</div><div class="meta-v">HTTP 200 且返回真实文本</div></div>
</div>''')

    A(f'''<div class="metrics">
<div class="metric"><div class="num">{diff["new_count"]}</div><div class="lbl">免费文本模型</div><div class="sub">原 {diff["old_count"]} · 净 +{diff["new_count"]-diff["old_count"]}</div></div>
<div class="metric"><div class="num" style="color:var(--ok)">{len(usable)}</div><div class="lbl">实测可用</div><div class="sub">全部 cost = 0</div></div>
<div class="metric"><div class="num" style="color:var(--warn)">{len(r429)}</div><div class="lbl">上游限流 429</div><div class="sub">间歇可用 · 本轮未恢复</div></div>
<div class="metric"><div class="num" style="color:var(--bad)">{len(r403)}</div><div class="lbl">硬性不可用 403</div><div class="sub">地区 2 · 调用门槛 2</div></div>
<div class="metric"><div class="num">{min(lat):.1f}<small>–{max(lat):.1f}s</small></div><div class="lbl">延迟区间</div><div class="sub">中位 {st.median(lat):.1f}s</div></div>
</div>''')

    # 01 结论
    new_ok = [m["id"] for m in diff["added"] if m["id"] in usable]
    new_bad = [m["id"] for m in diff["added"] if m["id"] not in usable]
    A(f'''<section><div class="sec-head"><span class="sec-no">01</span><span class="sec-title">结论</span></div>
<p class="body"><b>{len(usable)}/{diff["new_count"]} 可用，新增模型全部完成实测。</b>
{len(diff["added"])} 个新增免费模型中 {len(new_ok)} 个实测可用（{'、'.join(new_ok)}），
{len(new_bad)} 个撞上游限流（{'、'.join(new_bad)}）。
上一轮 3 个 429 里 <code>poolside/laguna-xs-2.1:free</code> 本轮恢复正常（20.29s，但为 reasoning 模型、400 tokens 触顶）；
2 个 Google Gemma 与 MiniMax 的处境见下节。</p>
<p class="body"><b>MiniMax 退出免费层。</b><code>minimax/minimax-m2.7:free</code> 与 <code>minimax/minimax-m3:free</code> 的免费变体已从清单中整体删除，
基础模型仍在售（prompt $0.30/M、completion $1.20/M），本轮免费清单里已无 MiniMax。</p>
<p class="body"><b>网站口径与 API 完全一致。</b>网页价格滑杆（FREE）背后是
<code>api/frontend/v1/models/find?max_price=0</code>，返回 99 个零价格模型（含图像/视频/语音/rerank/embedding）；
叠加「文本输出」后恰为 24 个，与 <code>GET /api/v1/models?max_price=0</code> 逐个 ID 相等。
第 25 行 <code>openrouter/free</code> 是自动路由器，定价字段非零，故不出现在网站免费筛选中。</p></section>''')

    # 02 清单变更
    A('''<section><div class="sec-head"><span class="sec-no">02</span><span class="sec-title">清单变更 · 新增 6 / 下线 2</span>
<span class="sec-note">created 为模型自身上架日，不代表免费变体开放日</span></div>
<table><thead><tr><th style="width:26px">#</th><th>模型 ID</th><th class="num">上下文</th><th>输入模态</th><th class="num">上架</th><th>状态</th><th>说明</th></tr></thead><tbody>''')
    notes = {
        "deepseek/deepseek-v4-flash-0731:free": "MoE 284B/激活13B，编程与 agent 向；OpenInference 供路，4.91s",
        "inclusionai/ling-3.0-flash-vl:free": "Ling 3.0 Flash 的多模态版，支持图像+视频输入",
        "nex-agi/nex-n2.5-mini:free": "agentic coding 向，视觉反馈回路；自述身份一致",
        "nex-agi/nex-n2.5-pro:free": "同族大杯，与 mini 共用额度池",
        "qwen/qwen3.8-27b:free": "稠密视觉语言模型；本轮 ModelRun 上游 429 未恢复",
        "z-ai/glm-5.2:free": "首次 429（Decart overloaded），重试 9.78s 成功；reasoning 模型",
    }
    for i, m in enumerate(diff["added"], 1):
        mid = m["id"]
        inmod = ",".join(x[:3] for x in m["input_modalities"])
        listed_on = time.strftime("%Y-%m-%d", time.gmtime(m.get("created") or 0))
        b, r = badge(res[mid])
        A(f'<tr><td class="num">{i}</td><td class="mid">{mid}</td><td class="num">{ctx_h(m["context_length"])}</td>'
          f'<td>{inmod}</td><td class="num">{listed_on}</td><td>{b}</td><td class="note">{notes.get(mid,"")}</td></tr>')
    for i, m in enumerate(diff["removed"], 1):
        A(f'<tr class="dim"><td class="num">-{i}</td><td class="mid">{m["id"]}</td><td class="num">{ctx_h(m.get("context_length"))}</td>'
          f'<td>-</td><td class="num">-</td><td><span class="st bad"><span class="dot bad"></span>已下线</span></td>'
          f'<td class="note">免费变体从清单删除，仅保留付费版本</td></tr>')
    A('</tbody></table></section>')

    # 03 全量实测
    A(f'''<section><div class="sec-head"><span class="sec-no">03</span><span class="sec-title">全量实测 · {diff["new_count"]} 个模型</span>
<span class="sec-note">按模型 ID 字母序 · 延迟为最终成功那次</span></div>
<table><thead><tr><th style="width:26px">#</th><th>模型 ID</th><th class="num">上下文</th><th>提供方</th>
<th class="num">延迟</th><th>状态</th><th>备注</th></tr></thead><tbody>''')
    for i, mid in enumerate(sorted(res), 1):
        v = res[mid]
        b, r = badge(v)
        m = inv.get(mid, {})
        if v["status"] == "ok" or r.get("status") == "ok":
            fin = r.get("finish_reason")
            note = f'finish={fin}' if fin != "stop" else ''
            if v.get("retest"):
                note = ('重试后成功 · ' if note else '重试后成功') if not note else note
            A(f'<tr><td class="num">{i}</td><td class="mid">{mid}</td><td class="num">{ctx_h(m.get("context_length"))}</td>'
              f'<td>{r.get("provider") or "-"}</td><td class="num">{r.get("elapsed")}s</td><td>{b}</td>'
              f'<td class="note">{note}</td></tr>')
        else:
            A(f'<tr class="dim"><td class="num">{i}</td><td class="mid">{mid}</td><td class="num">{ctx_h(m.get("context_length"))}</td>'
              f'<td>-</td><td class="num">{v.get("elapsed")}s</td><td>{b}</td>'
              f'<td class="note">{reason_of(v)}</td></tr>')
    A('</tbody></table></section>')

    # 04 值得注意
    A(f'''<section><div class="sec-head"><span class="sec-no">04</span><span class="sec-title">值得注意</span></div>
<ul class="findings">
<li><b>身份自述与路由字段矛盾（延续上一轮）。</b><code>nvidia/nemotron-3-ultra-550b-a55b:free</code> 自称「我是 GLM，Z.ai 训练」；
<code>poolside/laguna-xs-2.1:free</code> 本轮自称「我是通义」。两者路由字段均显示各自原生名称。用前请自行验证权重。</li>
<li><b><code>openrouter/free</code> 仍不保证是聊天模型。</b>本次把请求路由到 <code>nvidia/nemotron-3.5-content-safety:free</code>，
返回 "User Safety: safe"（15.44s），与 2026-09-07 表现一致 —— 不要拿它当默认聊天端点。</li>
<li><b>reasoning 模型在 400 tokens 下全部触顶。</b><code>z-ai/glm-5.2:free</code>（reasoning 796 / content 26）、
<code>poolside/laguna-xs-2.1:free</code>（reasoning 1290 / content 7）、<code>nvidia/nemotron-3.5-lightning:free</code>、
<code>inclusionai/ling-3.0-flash-fin:free</code> 均 <code>finish=length</code>。接入 agent 时 max_tokens 需给到数千以上。</li>
<li><b>新模型的输入模态值得留意。</b>新增 6 个里有 4 个支持图像输入（<code>ling-3.0-flash-vl</code>、<code>qwen3.8-27b</code> 还支持视频，
<code>nex-n2.5-mini/pro</code> 支持图像），免费层首次具备较可用的视觉输入选项。</li>
<li><b><code>nvidia/nemotron-3.5-content-safety:free</code> 耗时 42.23s</b>，是清单里最慢的一个；它是审核分类器而非对话模型，不建议作对话用途。</li>
<li><b><code>z-ai/glm-5.2:free</code> 上下文只有 32K。</b>与同族宣称的 1M 窗口不符，是免费变体被上游裁剪过的结果。</li>
</ul></section>''')

    # 05 网站口径
    A('''<section><div class="sec-head"><span class="sec-no">05</span><span class="sec-title">网站免费模型口径核对</span></div>
<p class="body">网站 <code>/models?max_price=0</code> 是纯客户端渲染，抓 HTML 拿不到过滤结果（SSR 内容与不过滤时逐字节相同）。
价格滑杆值 0 即「FREE」标签，实际调用 <code>api/frontend/v1/models/find?max_price=0</code>。</p>
<table><thead><tr><th>口径</th><th class="num">数量</th><th>拆解</th></tr></thead><tbody>
<tr><td class="mid">网站 FREE 滑杆（全模态）</td><td class="num">99</td><td>image 34 · video 29 · text 22 · rerank 7 · embeddings 3 · speech 2 · audio+text 2</td></tr>
<tr><td class="mid">上述 + 文本输出（has_text_output）</td><td class="num">24</td><td>22 个 variant=free（即 <code>:free</code> ID）+ 2 个零价 standard（Google Lyria）</td></tr>
<tr><td class="mid"><code>GET /api/v1/models?max_price=0</code> + text 输出</td><td class="num">24</td><td>与网站集合逐个 ID 相等，无差集</td></tr>
<tr><td class="mid">本报告清单</td><td class="num">25</td><td>再加 <code>openrouter/free</code> 自动路由器（定价字段非零，不进网站筛选）</td></tr>
<tr><td class="mid">官方全量目录 <code>GET /api/v1/models</code></td><td class="num">445</td><td>2026-09-07 为 430；期间新上架 28、下架 13</td></tr>
</tbody></table></section>''')

    # 06 限额与密钥
    A(f'''<section><div class="sec-head"><span class="sec-no">06</span><span class="sec-title">免费层限额与密钥状态</span></div>
<p class="body">官方限额未变（docs/api-reference/limits）：<code>:free</code> 模型 <b>20 次/分</b>；累计充值 &lt; $10 → <b>50 次/天</b>，
≥ $10 → <b>1000 次/天</b>。本密钥累计消费 ${key.get("usage")}，仍在 50 次/天档内，故本轮拆成 13 + 12 两次运行并加全局节流（最小请求间隔 3.3s），
避免自造 429。</p>
<table><thead><tr><th>字段</th><th>值</th></tr></thead><tbody>
<tr><td class="mid">label</td><td><code>{mask(key.get("label"))}</code></td></tr>
<tr><td class="mid">is_free_tier</td><td>{key.get("is_free_tier")}</td></tr>
<tr><td class="mid">usage（累计消费）</td><td>${key.get("usage")}</td></tr>
<tr><td class="mid">limit / rateLimit</td><td>{"未设置" if key.get("limit") is None else key.get("limit")} / {"未设置" if key.get("rateLimit") is None else key.get("rateLimit")}</td></tr>
<tr><td class="mid">本轮请求成本</td><td>全部 cost = 0（25 个模型逐个 usage 校验）</td></tr>
</tbody></table></section>''')

    # 07 方法
    A(f'''<section><div class="sec-head"><span class="sec-no">07</span><span class="sec-title">复测方法</span></div>
<p class="body">两步：<code>python diff_free_models.py</code> 拉清单并出差异，<code>python openrouter_connectivity_test.py --skip-fetch</code>
跑连通性。提问「你好，请用一句话简短介绍你自己。」，max_tokens={conn["max_tokens"]}，timeout={conn["timeout"]}s。
失败自动重试一次（429 前置等待 22s），末尾对仍 429 的再等 60s 复测一轮。
本轮分两批（13 个新增+历史失败、12 个历史成功）以贴住 50 次/天额度。</p>
<p class="body">产物：<code>data/connectivity_test.json</code>（本轮全量）、<code>data/connectivity_test-20260907.json</code>（上一轮存档）、
<code>data/raw/free_models_diff_20260907_vs_{day}.json</code>（差异）、<code>data/raw/*_{day}.json</code>（清单快照）。</p></section>''')

    A('''<footer>本报告由 工具集/build_report.py 从 JSON 结果生成 · 结论以实测 JSON 为准</footer>
</div></body></html>''')

    out_dir = arg("out-dir", os.path.join(ROOT, "最终报告"))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, arg("out", f"openrouter-免费模型清单更新与连通性实测-{day}.html"))
    open(out, "w", encoding="utf-8").write("\n".join(H))
    print("wrote", out, len("\n".join(H)), "bytes")


if __name__ == "__main__":
    main()
