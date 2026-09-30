# -*- coding: utf-8 -*-
"""
OpenRouter 免费文本模型清单：拉取 + 差异对比
用法：
  python diff_free_models.py                 # 联网拉最新清单并与上一版对比
  python diff_free_models.py --no-fetch --new-file=data/raw/models_all_20260918.json
产物（data/raw/）：
  free_text_models.json                      当前口径的免费+文本模型清单（连通性脚本读这份）
  free_text_models_<YYYYMMDD>.json           每次运行前的上一版快照
  models_all_<YYYYMMDD>.json                 官方全量清单快照
  models_maxprice0_<YYYYMMDD>.json           网站价格筛选（max_price=0）同源数据
  free_models_diff_<旧>_vs_<新>.json         差异结果
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_KEY = None  # 清单接口无需密钥；如需密钥从环境变量 OPENROUTER_API_KEY 读取
BASE = "https://openrouter.ai/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get("OR_RAW_DIR") or os.path.join(HERE, "data", "raw")


def arg_value(name, default=None):
    prefix = f"--{name}="
    for a in sys.argv:
        if a.startswith(prefix):
            return a[len(prefix):]
    return default


def http_json(url):
    headers = {"Accept": "application/json"}
    key = API_KEY or os.environ.get("OPENROUTER_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def is_free_text(m):
    mid = m.get("id", "")
    pricing = m.get("pricing", {}) or {}
    out_mods = (m.get("architecture", {}) or {}).get("output_modalities") or ["text"]
    zero = str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0"
    return (mid.endswith(":free") or zero) and "text" in out_mods


def normalize(m):
    arch = m.get("architecture", {}) or {}
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "created": m.get("created"),
        "context_length": m.get("context_length"),
        "output_modalities": arch.get("output_modalities") or ["text"],
        "input_modalities": arch.get("input_modalities") or [],
        "supported_parameters": m.get("supported_parameters") or [],
        "pricing": m.get("pricing", {}) or {},
        "top_provider": m.get("top_provider") or {},
        "description": (m.get("description") or "")[:400],
    }


def save(name, obj):
    path = os.path.join(RAW, name)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return path


def fetch_snapshots(today):
    all_data = http_json(f"{BASE}/models")
    save(f"models_all_{today}.json", all_data)
    try:
        save(f"models_maxprice0_{today}.json", http_json(f"{BASE}/models?max_price=0"))
    except urllib.error.HTTPError as e:
        print(f"(skipped max_price=0: HTTP {e.code})")
    return all_data.get("data", [])


def main():
    os.makedirs(RAW, exist_ok=True)
    today = time.strftime("%Y%m%d")
    cur_file = os.path.join(RAW, "free_text_models.json")
    old_list = json.load(open(cur_file, encoding="utf-8")) if os.path.exists(cur_file) else []

    new_file = arg_value("new-file")
    if new_file and not os.path.isabs(new_file):
        new_file = os.path.join(HERE, new_file)
    if "--no-fetch" in sys.argv and new_file:
        new_raw = json.load(open(new_file, encoding="utf-8")).get("data", [])
    else:
        print("fetching live catalog ...")
        new_raw = fetch_snapshots(today)

    new_list = sorted([normalize(m) for m in new_raw if is_free_text(m)], key=lambda x: x["id"])
    old_ids = {m["id"] for m in old_list}
    new_ids = {m["id"] for m in new_list}
    old_map = {m["id"]: m for m in old_list}
    old_day = arg_value("old-day", "20260907")

    added = [m for m in new_list if m["id"] not in old_ids]
    removed = [m for m in old_list if m["id"] not in new_ids]
    changed = []
    for m in new_list:
        o = old_map.get(m["id"])
        if not o:
            continue
        delta = {k: {"old": o.get(k), "new": m.get(k)} for k in ("context_length", "name") if o.get(k) != m.get(k)}
        if delta:
            changed.append({"id": m["id"], "delta": delta})

    save(f"free_models_diff_{old_day}_vs_{today}.json", {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "old_day": old_day, "new_day": today,
        "old_count": len(old_list), "new_count": len(new_list),
        "added": added, "removed": removed, "changed": changed,
        "kept_unchanged": sorted(m["id"] for m in new_list if m["id"] in old_ids),
    })

    if old_list:
        save(f"free_text_models_{old_day}.json", old_list)
    save("free_text_models.json", new_list)

    print(f"catalog={len(new_raw)}  free+text: {len(old_list)} -> {len(new_list)} "
          f"(added={len(added)} removed={len(removed)} changed={len(changed)})")
    for m in added:
        print(f"  + {m['id']:58s} ctx={m['context_length']:<8} in={','.join(m['input_modalities'])}")
    for m in removed:
        print(f"  - {m['id']}")
    for c in changed:
        print(f"  ~ {c['id']}: {json.dumps(c['delta'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
