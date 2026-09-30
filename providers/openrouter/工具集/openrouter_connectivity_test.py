# -*- coding: utf-8 -*-
"""
OpenRouter 免费模型连通性测试（一键脚本）
流程：拉取模型清单 -> 过滤免费+文本输出 -> 并发实测 chat/completions -> 失败重试 -> 429 复测 -> 保存 JSON
用法：python openrouter_connectivity_test.py [--skip-fetch]
依赖：仅 Python 标准库
"""
import json
import urllib.request
import urllib.error
import time
import os
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

def _resolve_api_key():
    """解析 OpenRouter 密钥，优先级：环境变量 -> 本地未提交的 local_secret.py。

    仓库内不保存任何密钥。本地开发只需在同目录建一个 local_secret.py：
        OPENROUTER_API_KEY = "sk-or-v1-..."
    （local_secret.py 已在 .gitignore 中，不会被提交）
    """
    v = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if v:
        return v
    try:
        import local_secret
        return (getattr(local_secret, "OPENROUTER_API_KEY", "") or "").strip()
    except Exception:
        return ""


API_KEY = _resolve_api_key()  # 从环境变量或 local_secret.py 读取，见 local_secret.example.py
BASE = "https://openrouter.ai/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RAW = os.path.join(DATA, "raw")

import concurrent.futures
import threading

MAX_TOKENS = 400
TIMEOUT = 75
WORKERS = 3
QUESTION = "你好，请用一句话简短介绍你自己。"
CTX = ssl.create_default_context()

# :free 模型官方限流 20 次/分；用最小请求间隔做全局节流，避免自造 429
MIN_INTERVAL = float(os.environ.get("OR_MIN_INTERVAL", "3.3"))
_throttle_lock = threading.Lock()
_next_slot = [0.0]

def throttle():
    with _throttle_lock:
        now = time.time()
        wait = _next_slot[0] - now
        _next_slot[0] = max(now, _next_slot[0]) + MIN_INTERVAL
    if wait > 0:
        time.sleep(wait)

def http_json(url, method="GET", payload=None, timeout=30):
    req = urllib.request.Request(url, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }, data=json.dumps(payload).encode("utf-8") if payload else None, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))

def call_model(model_id):
    payload = {"model": model_id,
               "messages": [{"role": "user", "content": QUESTION}],
               "max_tokens": MAX_TOKENS}
    start = time.time()
    try:
        throttle()
        result = http_json(f"{BASE}/chat/completions", "POST", payload, timeout=TIMEOUT)
        elapsed = round(time.time() - start, 2)
        choices = result.get("choices") or []
        if not choices:
            return {"status": "empty_response", "elapsed": elapsed, "raw": str(result)[:300]}
        msg = choices[0].get("message", {}) or {}
        content = msg.get("content") or ""
        usage = result.get("usage", {})
        return {"status": "ok", "elapsed": elapsed,
                "finish_reason": choices[0].get("finish_reason"),
                "content_len": len(content),
                "content_head": content[:100].replace("\n", " "),
                "reasoning_len": len(msg.get("reasoning") or ""),
                "provider": result.get("provider"), "routed_model": result.get("model"),
                "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens", "cost") if k in usage}}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return {"status": "http_error", "code": e.code, "elapsed": round(time.time() - start, 2), "body": body[:400]}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}", "elapsed": round(time.time() - start, 2)}

def test_with_retry(model_id):
    r = call_model(model_id)
    if r["status"] != "ok":
        time.sleep(22 if r.get("code") == 429 else 6)
        r2 = call_model(model_id)
        r2["retried"] = True
        r2["first_attempt"] = {k: r[k] for k in ("status", "code", "error", "body") if k in r}
        return r2
    return r

def arg_value(name):
    prefix = f"--{name}="
    for a in sys.argv:
        if a.startswith(prefix):
            return a[len(prefix):]
    return None

def main():
    os.makedirs(RAW, exist_ok=True)
    skip_fetch = "--skip-fetch" in sys.argv
    no_retry = "--no-retry" in sys.argv
    free_text_file = os.path.join(RAW, "free_text_models.json")

    if not skip_fetch or not os.path.exists(free_text_file):
        # 1. 密钥状态
        try:
            key_info = http_json(f"{BASE}/auth/key")
            json.dump(key_info, open(os.path.join(RAW, "key_info.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("KEY:", json.dumps(key_info.get("data", {}).get("label")), "| usage:", key_info.get("data", {}).get("usage"))
        except Exception as e:
            print("key info failed:", e)
        # 2. 模型清单 + 过滤
        data = http_json(f"{BASE}/models")
        json.dump(data, open(os.path.join(RAW, "models_all.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        free_text = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            pricing = m.get("pricing", {}) or {}
            out_mods = (m.get("architecture", {}) or {}).get("output_modalities") or ["text"]
            if (mid.endswith(":free") or (str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0")) and "text" in out_mods:
                free_text.append({"id": mid, "name": m.get("name"), "context_length": m.get("context_length"),
                                  "output_modalities": out_mods, "pricing": pricing})
        free_text.sort(key=lambda x: x["id"])
        json.dump(free_text, open(free_text_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"models total={len(data.get('data', []))}, free+text={len(free_text)}")
    else:
        free_text = json.load(open(free_text_file, encoding="utf-8"))

    ids = [m["id"] for m in free_text]
    only = arg_value("only")
    if only:
        wanted = [x.strip() for x in only.split(",") if x.strip()]
        ids = [i for i in ids if i in wanted]
        missing = [w for w in wanted if w not in ids]
        if missing:
            print("NOT-IN-LIST:", missing)
    if no_retry:
        globals()["test_with_retry"] = call_model
    out_file = os.path.join(DATA, arg_value("out") or "connectivity_test.json")
    results = {}
    if only and os.path.exists(out_file):
        results = dict(json.load(open(out_file, encoding="utf-8")).get("results", {}))
    prior_total = len(results)
    print(f"testing {len(ids)} free models | workers={WORKERS} max_tokens={MAX_TOKENS} timeout={TIMEOUT}s")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(test_with_retry, mid): mid for mid in ids}
        done = 0
        for fut in as_completed(futs):
            mid = futs[fut]
            r = fut.result()
            done += 1
            results[mid] = r
            tag = {"ok": "OK   ", "http_error": f"HTTP{r.get('code')}", "empty_response": "EMPTY", "error": "ERR  "}.get(r["status"], "?   ")
            extra = (r.get("body") or r.get("error") or r.get("raw") or "")[:100]
            print(f"[{done:2d}/{len(ids)}] {tag} {mid:62s} {r['elapsed']:>6}s {extra}")

    # 3. 对 429 复测一轮（等 60s）
    still = [m for m, r in results.items() if r.get("code") == 429 and m in ids] if not no_retry else []
    if still:
        print(f"waiting 60s then retesting {len(still)} rate-limited models ...")
        time.sleep(60)
        for mid in still:
            r = call_model(mid)
            if r["status"] != "ok":
                time.sleep(20)
                r = call_model(mid)
            results[mid]["retest"] = r
            print(f"  retest {mid}: {r['status']} code={r.get('code')}")
            time.sleep(4)

    ok = [m for m, r in results.items() if r["status"] == "ok" or r.get("retest", {}).get("status") == "ok"]
    out = {"test_time": time.strftime("%Y-%m-%d %H:%M:%S"), "base_url": f"{BASE}/chat/completions",
           "max_tokens": MAX_TOKENS, "timeout": TIMEOUT, "question": QUESTION,
           "total_models": len(results), "ok_models": len(ok), "tested_this_run": len(ids),
           "prior_records": prior_total, "wall_seconds": round(time.time() - t0, 1), "results": results}
    json.dump(out, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"summary: {len(ok)}/{len(results)} usable (this run tested {len(ids)}) | saved: {out_file}")

if __name__ == "__main__":
    main()
