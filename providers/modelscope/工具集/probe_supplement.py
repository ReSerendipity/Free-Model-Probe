# -*- coding: utf-8 -*-
"""
supplement_models.txt 增量探测脚本（Fix 2）
=========================================
背景（见 fetch_data.py 注释）：ModelScope 的 /v1/models 是 OpenAI 兼容部署清单，
并不等于「全部免费推理模型」。部分模型（如 deepseek-ai/DeepSeek-V4-Flash-Vision-Exp、
ZhipuAI/GLM-5.3-Flash）确有魔搭社区免费推理（魔粒计价）却不在该清单里。

本脚本的目的：自动发现这类「清单外、但有魔搭社区免费推理」的新模型，避免每次都要
人工去 modelscope.cn/models 网站翻找。

做法：
  1. 读种子清单（probe_watchlist.txt，一行一个家族基础 model id，或 --seed 指定）。
  2. 对每个种子，自动生成「下一版本 + 变体后缀」候选 id（如 V4→V5/V4.1，
     + -Flash/-Pro/-Vision/-Mini/-Turbo/-Max/-Next/-Lite/-Air/-Plus/-Exp/-Thinking）。
  3. 逐个探测 FEE_API（list_model_providers）：凡返回含「魔搭社区」提供方者，
     即视为有免费推理能力的新模型。
  4. 过滤已知 id（data/raw/list.json 缓存 + supplement_models.txt），新发现的：
     - 默认 dry-run：仅报告，不改文件；
     - 加 --apply：追加写入 supplement_models.txt（带探测日期注释）。

注意：候选 id 是「猜测 + 探测」生成，绝大多数会 404/无魔搭社区而自然过滤；
命中率取决于种子与命名规律，本脚本只负责「自动探测 + 不漏报」，最终是否纳入
仍由具名模型卡核验（fetch_data 的 DETAIL_API 会拉真实 README）。

依赖：仅复用 fetch_data.py 的 http_get / parse_fee / FEE_API（同目录）。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# 复用 fetch_data.py 的底层能力（仅模块级定义，不会触发其 main）
import fetch_data as fd

# 探测用的快速失败参数：清单外候选 id 多为无效，FEE_API 对无效 id 会重试 3 次、
# 每次 ~2s 等待，导致单轮探测长达数分钟。探测场景降低重试与超时，无效 id 尽快跳过。
fd.RETRY = 1
fd.RETRY_WAIT = 0.5
fd.TIMEOUT = 15

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = fd.RAW_DIR
SUPPLEMENT_FILE = fd.SUPPLEMENT_FILE
WATCHLIST_FILE = os.path.join(BASE_DIR, "probe_watchlist.txt")

# 变体后缀：在种子原 id 后追加，覆盖常见能力/规格分支
SUFFIX_VARIANTS = ["-Flash", "-Pro", "-Vision", "-Mini", "-Turbo", "-Max",
                   "-Next", "-Lite", "-Air", "-Plus", "-Exp", "-Thinking"]


def gen_candidates(seed_mid: str) -> list[str]:
    """基于种子 id 生成「下一版本 + 变体后缀」候选 id。"""
    if "/" not in seed_mid:
        return []
    org, name = seed_mid.split("/", 1)
    cands = set()
    m = re.search(r"(v?)(\d+)(?:[._](\d+))?(?:[._](\d+))?", name, re.I)
    if m:
        prefix = name[:m.start()]          # 版本前的部分（含可能的连字符）
        vmaj = int(m.group(2))
        vmin = int(m.group(3)) if m.group(3) else None
        bumps = []
        if vmin is not None:
            bumps += [f"{vmaj}.{vmin + 1}", f"{vmaj}.{vmin + 2}",
                      f"{vmaj + 1}.0", f"{vmaj + 1}.{vmin}", f"{vmaj}.{vmin + 5}"]
        else:
            bumps += [str(vmaj + 1), str(vmaj + 2), f"{vmaj}.1", f"{vmaj}.5"]
        for b in bumps:
            cands.add(f"{org}/{prefix}{b}")
    # 变体后缀（保留原版本）
    for s in SUFFIX_VARIANTS:
        cands.add(f"{org}/{name}{s}")
    # 去掉与种子自身完全相同的项
    cands.discard(seed_mid)
    return sorted(cands)


def probe_one(mid: str):
    """探测某 id 是否有魔搭社区免费推理。返回 fee dict 或 None（不存在/无免费推理）。"""
    try:
        body = fd.http_get(fd.FEE_API.format(mid=mid))
    except Exception:  # noqa: BLE001 - 404/网络错误一律视为不存在
        return None
    fee = fd.parse_fee(body)
    # 信号：提供方列表含「魔搭社区」→ 有魔搭社区免费推理
    if "魔搭社区" in fee["providers"]:
        return fee
    return None


def load_known_ids() -> set[str]:
    """合并已知 id（清单缓存 + 补充清单），用于去重，避免重复探测/写入。"""
    known: set[str] = set()
    list_json = os.path.join(RAW_DIR, "list.json")
    if os.path.exists(list_json):
        try:
            with open(list_json, encoding="utf-8") as f:
                known |= set(json.load(f))
        except Exception:  # noqa: BLE001
            pass
    known |= fd.load_supplement()
    return known


def main():
    ap = argparse.ArgumentParser(description="supplement_models.txt 增量探测")
    ap.add_argument("--apply", action="store_true", help="将发现写入 supplement_models.txt（默认仅报告）")
    ap.add_argument("--seed", action="append", help="种子 model id（可多次指定），与 watchlist 合并")
    args = ap.parse_args()

    seeds = list(args.seed or [])
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    seeds.append(s)
    if not seeds:
        print("无种子：probe_watchlist.txt 为空且未指定 --seed，退出。")
        return

    known = load_known_ids()
    print(f"种子 {len(seeds)} 个，已知 id（去重基准）{len(known)} 个")
    found = []
    seen = set()
    for seed in seeds:
        cands = gen_candidates(seed)
        for cand in cands:
            if cand in known or cand in seen:
                continue
            seen.add(cand)
            fee = probe_one(cand)
            if fee:
                found.append((cand, fee))
                print(f"      ✅ 发现新模型（魔搭社区免费推理）: {cand} -> {fee['providers']}")
            time.sleep(0.3)

    if not found:
        print("未发现新模型（候选均已过滤/无魔搭社区提供方）。")
        return
    print(f"\n共发现 {len(found)} 个候选（已过滤已知 id）。")
    if args.apply:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(SUPPLEMENT_FILE, "a", encoding="utf-8") as f:
            for cand, fee in found:
                f.write(f"\n# 自动探测 {ts}: {fee['providers']}\n{cand}\n")
        print(f"已写入 supplement_models.txt（{len(found)} 个）。下次 fetch_data.py 会自动并入。")
    else:
        print("dry-run：未写入文件。加 --apply 写入 supplement_models.txt。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
