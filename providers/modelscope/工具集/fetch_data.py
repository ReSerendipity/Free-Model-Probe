# -*- coding: utf-8 -*-
"""
ModelScope 模型数据抓取工具（可复用）
=====================================
用途：抓取 ModelScope「推理 API-Inference」可调用模型清单、逐模型魔粒费用、
模型详情（README 编程基准关键词），缓存原始 JSON 到 data/raw/，输出结构化
JSON 与 CSV 到 data/。

用法：
    python fetch_data.py                 # 全量抓取（清单 + 费用 + 详情）
    python fetch_data.py --skip-detail   # 只更新清单与费用（详情读缓存）

输出：
    data/models.json        结构化汇总（清单 + 费用 + 基准）
    data/models.csv         可直接用 Excel 打开的台账
    data/raw/               原始响应缓存（list.json + {model}.json）
    data/fetch_meta.json    抓取时间、模型数、失败清单

依赖：仅 Python 3.8+ 标准库（urllib/json/csv/re），无第三方包。
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# Windows 控制台/管道下 UTF-8 安全输出（GBK 终端会因 emoji 崩溃）
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - 非 TTY 环境下 reconfigure 可能不可用
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) modelscope-updater/1.0"}
TIMEOUT = 30
RETRY = 3
RETRY_WAIT = 2.0
DETAIL_TTL = 24 * 3600  # 详情缓存有效期（秒）

# ModelScope 公开接口（2026-08 实测可用，无需登录）
LIST_API = "https://api-inference.modelscope.cn/v1/models"  # OpenAI 兼容可调用清单
FEE_API = "https://modelscope.cn/api/v1/inference/list_model_providers?ModelId={mid}"  # 魔粒费用
DETAIL_API = "https://modelscope.cn/api/v1/models/{mid}"  # 详情 + README
# 网站核验补充清单：LIST_API(/v1/models) 抓不到、但确有魔搭社区免费推理的模型。
# 该清单是 OpenAI 兼容部署清单，并不等于 ModelScope 全部免费推理模型；
# 经 modelscope.cn/models 网站核验发现、却不在 /v1/models 的模型，手动列入此文件，
# 工具自动并入，避免重跑时被丢弃。格式见 data/supplement_models.txt。
SUPPLEMENT_FILE = os.path.join(DATA_DIR, "supplement_models.txt")

# 明确不可用于 agent 的专用模型关键词（抓取后自动剔除）
NON_AGENT_PATTERNS = [
    "image-edit", "xiyansql", "compassjudger", "antangelmed", "longcat",
    "internvl", "-vl-", "/ernie-4.5-vl-",
]

# 明确不可用 / 不应进入「可接 Agent」报告的模型（手工确认，附原因，避免反复误纳入）
EXCLUDED_MODELS = {
    "MiniMax/MiniMax-M3": "v3.0 连通性实测确认不可用，且无魔搭社区提供方（仅第三方）",
}

# 预训练/基座模型关键词：非对话/推理 agent 模型，从清单剔除（例如 ERNIE-4.5-*-PT）
BASE_MODEL_PATTERNS = ["-pt", "-base", "pretrained"]


def safe_filename(mid: str) -> str:
    """模型 id 白名单化，防止路径注入/Windows drive 语义。"""
    return re.sub(r"[^\w.-]", "_", mid)


def http_get(url: str) -> str:
    """带重试的 GET，返回 UTF-8 文本；仅对网络/5xx 重试，404 等直接抛错。"""
    last_err = None
    for attempt in range(RETRY):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status >= 500:
                    raise urllib.error.HTTPError(url, resp.status, "server error",
                                                 resp.headers, None)
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code < 500:  # 4xx 永久错误不重试
                raise
            last_err = e
        except Exception as e:  # noqa: BLE001 - 网络错误类型繁多，统一重试
            last_err = e
        if attempt < RETRY - 1:
            time.sleep(RETRY_WAIT * (attempt + 1))
    raise RuntimeError(f"GET 失败（重试 {RETRY} 次）: {url} -> {last_err}")


def load_json(text: str):
    return json.loads(text)


def fetch_model_list() -> list[str]:
    """拉取 API 可调用模型 ID 清单。"""
    data = load_json(http_get(LIST_API))
    items = data.get("data")
    if not isinstance(items, list):
        raise ValueError(f"清单接口返回格式异常（data 非 list）: {type(items).__name__}")
    ids = [m["id"] for m in items if isinstance(m, dict) and m.get("id")]
    return sorted(ids)


def load_supplement() -> set[str]:
    """读取网站核验补充清单（一行一个 model id，# 开头为注释）。

    背景：LIST_API(/v1/models) 是 OpenAI 兼容部署清单，并不等于 ModelScope 全部
    免费推理模型；部分模型有魔搭社区免费推理（魔粒计价）却不在该清单里。
    这些模型经 modelscope.cn/models 网站核验发现，需手动列入以免重跑时被丢弃。
    """
    ids: set[str] = set()
    if not os.path.exists(SUPPLEMENT_FILE):
        return ids
    with open(SUPPLEMENT_FILE, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            ids.add(s)
    return ids


def parse_fee(body: str) -> dict:
    """解析费用接口响应：魔搭社区自营提供方的魔粒费用。"""
    data = load_json(body)
    providers = (data.get("Data") or {}).get("Providers") or []
    ms_cost, ms_tier, providers_txt = None, None, []
    for p in providers:
        if not isinstance(p, dict):
            continue
        name = p.get("ChineseName") or p.get("Name") or ""
        cost = p.get("EstimatedMagicGrainCost")
        tier = p.get("CostTier") or ""
        providers_txt.append(f"{name}:{cost if cost is not None else ''}魔粒/{tier}")
        if name == "魔搭社区":
            ms_cost = cost
            ms_tier = tier
    return {
        "providers": " | ".join(providers_txt),
        "magic_cost": ms_cost if ms_cost is not None else None,
        "cost_tier": ms_tier or "",
    }


def fetch_fee(mid: str) -> tuple[dict, str]:
    """拉取某模型的魔粒费用，返回 (解析结果, 原始响应文本)。"""
    body = http_get(FEE_API.format(mid=mid))
    return parse_fee(body), body


def parse_detail(body: str) -> dict:
    """解析模型详情 JSON：下载量、任务类型、README（用于基准提取）。"""
    data = load_json(body)
    d = data.get("Data") or {}
    tasks = d.get("Tasks") or []
    task_names = []
    for t in tasks:
        if isinstance(t, dict):
            task_names.append(t.get("Name") or t.get("DomainName") or str(t.get("ChineseName") or ""))
        else:
            task_names.append(str(t))
    return {
        "downloads": d.get("Downloads"),
        "tasks": [n for n in task_names if n],
        "support_inference": d.get("SupportInference"),
        "experience": d.get("SupportExperience"),
        "readme": d.get("ReadMeContent") or "",
    }


# 编程基准正则（从 README 纯文本提取）
# 年份防护：(?!20\d{2}(?:[.\-]\d+)?\b) 拒绝 "2025" / "2025.06" / "2025-06" 等年份
_YEAR_GUARD = r"(?!20\d{2}(?:[.\-]\d+)?\b)"
BENCH_PATTERNS = [
    ("swe_bench_verified", re.compile(
        rf"SWE[- ]bench\s*Verified[^0-9]{{0,50}}{_YEAR_GUARD}(\d+(?:\.\d+)?)", re.I)),
    ("swe_bench_pro", re.compile(
        rf"SWE[- ]bench\s*Pro[^0-9]{{0,50}}{_YEAR_GUARD}(\d+(?:\.\d+)?)", re.I)),
    # 版本号放宽为可选（抓 "Terminal Bench 2" / "Terminal Bench 2.1" 都命中）
    # 关键修复（v5.3.1）：旧式 `Terminal[- ]Bench\s*\d*...[^0-9]{0,50}(\d+)` 会把
    # 版本号本身（如 "Terminal-Bench 2.1" 的方法学说明句）误抓为分数（GLM-5.3-Flash
    # 曾抓到 terminal_bench=2.1）。现改为：先消费版本号 `(?:v?\d+...)?`，再允许 0-15 个
    # 非数字分隔，最后只接受两位整数分的（>=10，过滤版本号/Claude Code 版本等误命中）。
    ("terminal_bench", re.compile(
        rf"Terminal[- ]Bench\s*(?:v?\d+(?:\.\d+)?)?\D{{0,15}}{_YEAR_GUARD}(\d{{2}}(?:\.\d+)?)", re.I)),
    # 允许 "LiveCodeBench v6" 这种带版本号的写法（原正则把字母 v 排除导致漏抓）
    ("livecodebench", re.compile(
        rf"LiveCodeBench(?:\s*v\d+)?[^0-9]{{0,50}}{_YEAR_GUARD}(\d{{2,}}(?:\.\d+)?)", re.I)),
    ("humaneval", re.compile(
        rf"HumanEval[^0-9]{{0,50}}{_YEAR_GUARD}(\d{{2,}}(?:\.\d+)?)", re.I)),
    ("aime", re.compile(
        rf"AIME[^0-9]{{1,50}}(?!\d{{4}}\b)(\d{{2,}}(?:\.\d+)?)", re.I)),
]


# 已知模型家族关键词（用于识别「对比表」中的竞品，避免误抓竞品分）
KNOWN_FAMILIES = [
    "deepseek", "glm", "qwen", "nex", "mistral", "intern", "ernie",
    "minimax", "step", "llama", "gpt", "claude", "yi-", "baichuan",
    "chatglm", "aquila", "phi-", "gemma", "command-r", "spark", "abab",
    "kimi", "moonshot", "doubao", "hunyuan",
]


def _model_family(mid: str) -> str:
    """从 model id 推断所属家族 token（用于对比表识别）。"""
    name = mid.split("/")[-1].lower()
    org = mid.split("/")[0].lower()
    return name.split("-")[0] if name else org


def extract_benchmarks(readme: str, mid: str = "") -> tuple:
    """从 README 提取编程基准分数，尽量限定到模型「自身」章节，避免误抓对比表竞品分。

    返回 (分数dict, 警告list)。警告list 含被怀疑取自对比表的基准 key（需人工核对）。
    策略：对每个关键词，取所有命中；优先选上下文含「自身模型名」者；上下文含其他家族
    （对比表）则跳过；若全部命中都在对比上下文，取首个并告警。
    """
    plain = re.sub(r"<[^>]+>", " ", readme)
    plain = re.sub(r"\s+", " ", plain)
    family = _model_family(mid)
    own_name = mid.split("/")[-1].lower()
    out, warns = {}, []
    for key, pat in BENCH_PATTERNS:
        hits = list(pat.finditer(plain))
        if not hits:
            continue
        chosen = None
        for m in hits:
            s = max(0, m.start() - 300)
            e = min(len(plain), m.end() + 100)
            ctx = plain[s:e].lower()
            if own_name and own_name in ctx:  # 上下文含自身模型名 → 强认定自身
                chosen = m
                break
            others = [f for f in KNOWN_FAMILIES if f != family and f in ctx]
            if others:  # 上下文含其他家族 → 视为对比表，跳过
                continue
            chosen = m
            break
        if chosen is None:  # 所有命中都在对比上下文：取首个但告警
            chosen = hits[0]
            warns.append(key)
        try:
            score = float(chosen.group(1))
        except ValueError:
            continue
        if 0 < score < 100:  # 分数合理性校验（年份等误匹配在此被过滤）
            out[key] = score
    return out, warns


def is_non_agent(mid: str) -> bool:
    low = mid.lower()
    return any(p in low for p in NON_AGENT_PATTERNS)


def is_base_model(mid: str) -> bool:
    """预训练/基座模型（非对话/推理 agent 模型），从清单剔除。"""
    low = mid.lower()
    return any(p in low for p in BASE_MODEL_PATTERNS)


def detect_stability(mid: str) -> str:
    """根据模型 id 推断稳定性档位（实验/预览 vs 稳定），避免误选非 GA 模型。"""
    low = mid.lower()
    if any(t in low for t in ["early-access", "preview", "-exp", "exp-",
                              "flash-next", "-next", "experimental"]):
        return "实验/预览"
    return "稳定"


def _warn_family_dup(rows: list):
    """家族级基准重复校验：多个模型基准 dict 完全相同，疑似共用家族表被误判为各自分数。"""
    from collections import defaultdict
    grp = defaultdict(list)
    for r in rows:
        b = r.get("benchmarks") or {}
        if b:
            grp[json.dumps(b, sort_keys=True)].append(r["model_id"])
    for k, v in grp.items():
        if len(v) > 1:
            print(f"      ⚠️ 基准完全相同（疑似家族级共享表，被误判为各自分数）：{v} -> {k[:100]}")


def _warn_cost_none_no_bench(rows: list):
    """无魔粒成本且无编程基准：疑似不可用 / 仅第三方，提醒确认是否应剔除。"""
    for r in rows:
        if r.get("magic_cost_per_call") is None and not (r.get("benchmarks") or {}):
            print(f"      ⚠️ 无魔粒成本且无编程基准（疑似不可用/仅第三方）：{r['model_id']} "
                  f"（提供方：{r.get('providers')}）")


def _warn_bench_compare(rows: list):
    """基准疑似取自「对比表」（竞品分）的告警汇总（Fix 1 的 extract_benchmarks 标注）。

    extract_benchmarks 在无法在「自身章节」定位基准、所有命中都落在含其他家族名的
    对比表上下文时，会把基准 key 列入 warns。此处逐模型打印，便于人工核对模型卡。
    """
    flagged = [(r["model_id"], r.get("bench_warns") or []) for r in rows
               if r.get("bench_warns")]
    if not flagged:
        return
    print("      ⚠️ 以下模型的部分基准疑似取自模型卡「对比表」（可能是竞品分数，需人工核对）：")
    for mid, keys in flagged:
        print(f"         - {mid}: {', '.join(keys)}")


def main():
    ap = argparse.ArgumentParser(description="ModelScope 可接 agent 模型数据抓取")
    ap.add_argument("--skip-detail", action="store_true", help="跳过详情/README 抓取（更快）")
    ap.add_argument("--keep-non-agent", action="store_true", help="保留专用模型（默认剔除）")
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    fetch_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("[1/4] 拉取 API 可调用模型清单 ...")
    try:
        ids = fetch_model_list()
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"清单拉取失败（请检查网络或接口 URL）: {e}")
    with open(os.path.join(RAW_DIR, "list.json"), "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=1)
    print(f"      清单 {len(ids)} 个模型")

    # 合并"网站核验补充清单"：/v1/models OpenAI 清单抓不到、但有魔搭社区免费推理的模型
    supplement_ids = load_supplement()
    if supplement_ids:
        before = len(ids)
        ids = sorted(set(ids) | supplement_ids)
        print(f"      补充清单并入 {len(ids) - before} 个（网站核验模型，不在 /v1/models 清单）")

    # 默认剔除专用模型 / 基座模型 / 确认不可用模型：提前算好，跳过其费用/详情抓取
    excluded = [mid for mid in ids
                if (is_non_agent(mid) or is_base_model(mid) or mid in EXCLUDED_MODELS)
                and not args.keep_non_agent]
    kept = [mid for mid in ids if mid not in excluded]
    if excluded:
        reasons = []
        for mid in excluded:
            if mid in EXCLUDED_MODELS:
                reasons.append(f"{mid}(确认不可用)")
            elif is_base_model(mid):
                reasons.append(f"{mid}(基座/PT)")
            else:
                reasons.append(mid)
        print(f"      剔除 {len(excluded)} 个: {', '.join(reasons[:8])}{'...' if len(reasons) > 8 else ''}")

    print("[2/4] 逐模型拉取魔粒费用 ...")
    fees = {}
    fee_failures = []
    for i, mid in enumerate(kept, 1):
        raw_f = os.path.join(RAW_DIR, safe_filename(mid) + "__fee.json")
        try:
            fee, body = fetch_fee(mid)
            with open(raw_f, "w", encoding="utf-8") as f:
                f.write(body)
            fees[mid] = fee
        except Exception as e:  # noqa: BLE001
            fees[mid] = {"providers": f"ERROR:{e}", "magic_cost": None, "cost_tier": ""}
            fee_failures.append(mid)
            if mid in supplement_ids:
                print(f"      ⚠️ 补充清单模型 {mid} 费用抓取失败：{e}（请核实是否已下架）")
        print(f"      [{i}/{len(kept)}] {mid} -> {fees[mid]['magic_cost']}魔粒/{fees[mid]['cost_tier']}")
        time.sleep(0.2)

    print("[3/4] 拉取详情与编程基准（优先读缓存） ...")
    details = {}
    for i, mid in enumerate(kept, 1):
        raw_f = os.path.join(RAW_DIR, safe_filename(mid) + "__detail.json")
        cached = False
        if os.path.exists(raw_f):
            age = time.time() - os.path.getmtime(raw_f)
            if age < DETAIL_TTL:
                cached = True
        if cached:
            try:
                with open(raw_f, encoding="utf-8") as f:
                    body = f.read()
                det = parse_detail(body)
                det["benchmarks"], det["bench_warns"] = extract_benchmarks(det.pop("readme"), mid)
                details[mid] = det
                os.utime(raw_f)  # 刷新 mtime，保证高频运行时缓存不过期
            except Exception:  # noqa: BLE001 - 缓存损坏则删除并重拉
                cached = False
                try:
                    os.remove(raw_f)
                except OSError:
                    pass
        if not cached:
            if args.skip_detail:
                details[mid] = {"downloads": None, "tasks": [], "benchmarks": {},
                                "note": "cache-miss"}
                print(f"      [{i}/{len(kept)}] {mid} (无缓存，已跳过)")
                continue
            try:
                body = http_get(DETAIL_API.format(mid=mid))
                with open(raw_f, "w", encoding="utf-8") as f:
                    f.write(body)
                det = parse_detail(body)
                det["benchmarks"], det["bench_warns"] = extract_benchmarks(det.pop("readme"), mid)
                details[mid] = det
            except Exception as e:  # noqa: BLE001
                details[mid] = {"downloads": None, "tasks": [], "benchmarks": {}, "error": str(e)}
        print(f"      [{i}/{len(kept)}] {mid}")
        time.sleep(0.2)

    print("[4/4] 汇总输出 ...")
    rows = []
    for mid in kept:
        fee = fees.get(mid, {})
        det = details.get(mid, {})
        rows.append({
            "model_id": mid,
            "organization": mid.split("/")[0],
            "api_callable": True,
            "mainstream": ("官方机构发布 + 网站核验补充（不在 API-Inference /v1/models 清单，但魔搭社区提供免费推理）"
                           if mid in supplement_ids else
                           "官方机构发布 + ModelScope 官方 API-Inference 清单在列"),
            "non_agent": False,
            "magic_cost_per_call": fee.get("magic_cost"),
            "cost_tier": fee.get("cost_tier"),
            "billing": ("魔粒/次" if fee.get("magic_cost") is not None else "第三方/无魔粒"),
            "stability": detect_stability(mid),
            "billing_unit": "每次调用",
            "providers": fee.get("providers", ""),
            "downloads": det.get("downloads"),
            "tasks": ",".join(det.get("tasks") or []),
            "support_inference": det.get("support_inference"),
            "experience": det.get("experience"),
            "benchmarks": det.get("benchmarks", {}),
            "bench_warns": det.get("bench_warns", []),
            "bench_warn": " | ".join(det.get("bench_warns", [])),
            "fetched_at": fetch_ts,
        })

    print("      数据质量校验 ...")
    _warn_family_dup(rows)
    _warn_cost_none_no_bench(rows)
    _warn_bench_compare(rows)

    with open(os.path.join(DATA_DIR, "models.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    with open(os.path.join(DATA_DIR, "models.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "model_id", "organization", "api_callable", "mainstream", "non_agent",
            "magic_cost_per_call", "cost_tier", "billing", "billing_unit", "stability",
            "providers", "downloads", "tasks", "support_inference", "experience",
            "swe_bench_verified", "swe_bench_pro", "terminal_bench",
            "livecodebench", "humaneval", "aime", "bench_warn", "fetched_at",
        ])
        w.writeheader()
        for r in rows:
            b = r["benchmarks"]
            w.writerow({
                **{k: r[k] for k in ("model_id", "organization", "api_callable", "mainstream",
                                     "non_agent", "magic_cost_per_call", "cost_tier",
                                     "billing", "billing_unit", "stability", "providers",
                                     "downloads", "tasks", "support_inference",
                                     "experience", "bench_warn", "fetched_at")},
                **{k: b.get(k, "") for k in ("swe_bench_verified", "swe_bench_pro",
                                             "terminal_bench", "livecodebench",
                                             "humaneval", "aime")},
            })

    meta = {
        "fetched_at": fetch_ts,
        "list_total": len(ids),
        "kept_after_filter": len(rows),
        "non_agent_excluded": len(excluded),
        "failures": fee_failures + [mid for mid, det in details.items()
                                    if isinstance(det, dict) and "error" in det],
    }
    with open(os.path.join(DATA_DIR, "fetch_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print(f"\n完成：清单 {meta['list_total']} 个，剔除专用 {meta['non_agent_excluded']} 个，"
          f"保留 {meta['kept_after_filter']} 个")
    print("输出：data/models.json / data/models.csv / data/fetch_meta.json")
    if meta["failures"]:
        print(f"抓取失败：{meta['failures']}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
