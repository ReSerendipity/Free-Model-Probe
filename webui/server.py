# -*- coding: utf-8 -*-
"""
模型连通性测试 Web UI 后端（仅标准库，无第三方依赖）
==================================================
通用 OpenAI 兼容接口测试台。用户提供「地址 + 钥匙」即可测试：
  - 单轮连通性：对每个候选模型发一次 chat/completions，记录状态/延迟/内容
  - 多轮负载连通性：N 个并发会话各做 M 轮多轮对话，统计成功率/吞吐/延迟分布/429 率
  - 扫描新增模型：拉 /models -> 应用过滤 -> 与上次快照 diff -> 对新增模型自动测连通性

启动：python server.py   （默认 http://127.0.0.1:8777）
改端口：PORT=9000 python server.py
"""
import json
import os
import sys
import time
import hashlib
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8777"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(SCRIPT_DIR, "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

# 运行中进程登记表（用于「停止」）
_PROC_LOCK = threading.Lock()
_STOP_EVENTS = {}      # run_id -> threading.Event
_RUN_COUNTER = [0]


# ============ 底层 HTTP ============
def _http_json(url, api_key, timeout, method="GET", payload=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer %s" % api_key
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_models(base_url, api_key, timeout):
    """拉取 /models，返回模型对象列表（尽力兼容 OpenAI 风格）。"""
    url = base_url.rstrip("/") + "/models"
    try:
        obj = _http_json(url, api_key, timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError("拉取模型清单失败 HTTP %s: %s" % (e.code, (e.read().decode("utf-8", "replace")[:200] if e.fp else "")))
    except Exception as e:
        raise RuntimeError("拉取模型清单失败: %s" % e)
    if isinstance(obj, dict):
        if isinstance(obj.get("data"), list):
            return obj["data"]
        # 有些实现直接返回数组在别的字段
        for k, v in obj.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "id" in v[0]:
                return v
    if isinstance(obj, list):
        return obj
    return []


def model_matches(m, filt):
    """按过滤条件判断模型是否入选。filt: all / free / free_text"""
    if filt in ("all", None, ""):
        return True
    mid = m.get("id", "")
    pricing = m.get("pricing") or {}
    prompt = str(pricing.get("prompt", "") or "")
    completion = str(pricing.get("completion", "") or "")
    is_free = mid.endswith(":free") or (prompt in ("0", "0.0", "") and completion in ("0", "0.0", ""))
    out_mods = (m.get("architecture") or {}).get("output_modalities") or ["text"]
    if filt == "free":
        return is_free
    if filt == "free_text":
        return is_free and "text" in out_mods
    return True


# 全局节流（免费层限速用）
_throttle_lock = threading.Lock()
_next_slot = [0.0]


def _throttle(min_interval):
    if not min_interval or min_interval <= 0:
        return
    with _throttle_lock:
        now = time.time()
        wait = _next_slot[0] - now
        _next_slot[0] = max(now, _next_slot[0]) + min_interval
    if wait > 0:
        time.sleep(min_interval if wait > min_interval else wait)


def call_once(base_url, api_key, model, messages, max_tokens, timeout, min_interval):
    """单次 chat/completions 调用。返回结构化结果字典。"""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    start = time.time()
    _throttle(min_interval)
    try:
        result = _http_json(url, api_key, timeout, "POST", payload)
        elapsed = round(time.time() - start, 2)
        choices = result.get("choices") or []
        if not choices:
            return {"status": "empty", "elapsed": elapsed,
                    "error": "空响应(choices=null)", "content": "", "content_head": "",
                    "finish_reason": None, "usage": result.get("usage")}
        msg = choices[0].get("message", {}) or {}
        content = msg.get("content") or ""
        return {"status": "ok", "elapsed": elapsed, "error": None,
                "content": content, "content_head": content[:120].replace("\n", " "),
                "finish_reason": choices[0].get("finish_reason"),
                "usage": result.get("usage")}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return {"status": "http_error", "elapsed": round(time.time() - start, 2),
                "code": e.code, "error": body[:300], "content": "", "content_head": "",
                "finish_reason": None, "usage": None}
    except urllib.error.URLError as e:
        return {"status": "error", "elapsed": round(time.time() - start, 2),
                "error": "网络错误: %s" % e.reason, "content": "", "content_head": "",
                "finish_reason": None, "usage": None}
    except Exception as e:
        return {"status": "error", "elapsed": round(time.time() - start, 2),
                "error": "%s: %s" % (type(e).__name__, e), "content": "", "content_head": "",
                "finish_reason": None, "usage": None}


def summarize(r):
    head = r.get("content_head") or r.get("error") or ""
    return {
        "status": r["status"],
        "code": r.get("code"),
        "elapsed": r.get("elapsed"),
        "finish_reason": r.get("finish_reason"),
        "preview": head[:120],
    }


# ============ 快照（扫描新增用）============
def _snap_key(base_url, filt):
    return hashlib.md5(("%s|%s" % (base_url, filt)).encode("utf-8")).hexdigest()


def load_snapshot(base_url, filt):
    p = os.path.join(SNAP_DIR, _snap_key(base_url, filt) + ".json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_snapshot(base_url, filt, ids):
    p = os.path.join(SNAP_DIR, _snap_key(base_url, filt) + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"base_url": base_url, "filter": filt,
                   "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "ids": ids}, f, ensure_ascii=False, indent=2)


# ============ SSE 辅助 ============
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _wlock(self):
        if not hasattr(self, "_wl"):
            self._wl = threading.Lock()
        return self._wl

    def emit(self, etype, data):
        payload = json.dumps({"type": etype, "data": data}, ensure_ascii=False)
        try:
            with self._wlock():
                self.wfile.write(("data: %s\n\n" % payload).encode("utf-8"))
                self.wfile.flush()
        except Exception:
            pass

    def log_message(self, *a):
        pass

    # ---- 请求路由 ----
    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            self._serve_index()
        elif p == "/api/snapshots":
            self._api_snapshots()
        else:
            self._serve_index()

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/single":
            self._run_stream(self.run_single)
        elif p == "/api/load":
            self._run_stream(self.run_load)
        elif p == "/api/scan":
            self._run_stream(self.run_scan)
        elif p == "/api/stop":
            self._api_stop()
        else:
            self._json({"error": "未知接口"}, 404)

    # ---- 通用 ----
    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_index(self):
        try:
            with open(os.path.join(SCRIPT_DIR, "index.html"), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self._json({"error": "index.html 缺失"}, 500)

    def _api_snapshots(self):
        out = []
        for fn in os.listdir(SNAP_DIR):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(SNAP_DIR, fn), encoding="utf-8") as f:
                    d = json.load(f)
                out.append({"base_url": d.get("base_url"), "filter": d.get("filter"),
                            "fetched_at": d.get("fetched_at"), "count": len(d.get("ids", []))})
            except Exception:
                continue
        self._json({"snapshots": out})

    def _api_stop(self):
        body = self._body()
        rid = body.get("run_id", "")
        with _PROC_LOCK:
            ev = _STOP_EVENTS.get(rid)
        if not ev:
            self._json({"ok": False, "error": "未找到运行中的任务 %s" % rid})
            return
        ev.set()
        self._json({"ok": True, "run_id": rid})

    def _run_stream(self, fn):
        body = self._body()
        with _PROC_LOCK:
            _RUN_COUNTER[0] += 1
            rid = "run-%d" % _RUN_COUNTER[0]
            stop = threading.Event()
            _STOP_EVENTS[rid] = stop
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.wfile.flush()
        self.emit("start", {"run_id": rid})
        try:
            fn(self, body, rid, stop)
        except Exception as e:
            self.emit("info", {"msg": "执行异常: %s" % e})
        finally:
            with _PROC_LOCK:
                _STOP_EVENTS.pop(rid, None)
            self.emit("exit", {"code": 0})
            try:
                self.wfile.flush()
            except Exception:
                pass

    # ============ 三种测试 ============
    def run_single(self, h, cfg, rid, stop):
        base = cfg.get("base_url", "").strip().rstrip("/")
        key = cfg.get("api_key", "").strip()
        filt = cfg.get("filter", "all")
        question = cfg.get("question", "你好，请用一句话简短介绍你自己。")
        max_tokens = int(cfg.get("max_tokens", 200))
        timeout = int(cfg.get("timeout", 60))
        workers = max(1, int(cfg.get("workers", 3)))
        min_interval = float(cfg.get("min_interval", 0) or 0)
        mode = cfg.get("models_mode", "auto")
        self.emit("info", {"msg": "单轮连通性测试 | 端点 %s | 过滤=%s | 并发=%d" % (base, filt, workers)})

        if mode == "auto":
            try:
                all_models = fetch_models(base, key, timeout)
            except RuntimeError as e:
                self.emit("info", {"msg": str(e)})
                return
            cands = [m for m in all_models if model_matches(m, filt)]
            self.emit("info", {"msg": "清单共 %d 个，应用过滤后 %d 个候选" % (len(all_models), len(cands))})
        else:
            text = cfg.get("models_text", "") or ""
            cands = [{"id": x.strip()} for x in text.replace("\n", ",").split(",") if x.strip()]

        if not cands:
            self.emit("info", {"msg": "无候选模型，结束。"})
            return
        ids = [c["id"] for c in cands]
        results = {}
        lock = threading.Lock()

        def work(mid):
            if stop.is_set():
                return
            r = call_once(base, key, mid, [{"role": "user", "content": question}], max_tokens, timeout, min_interval)
            with lock:
                results[mid] = r
            self.emit("row", {"model": mid, **summarize(r)})

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, ids))
        ok = sum(1 for v in results.values() if v["status"] == "ok")
        self.emit("summary", {"title": "单轮连通性结果", "lines": [
            "候选 %d 个" % len(results), "可用 %d" % ok, "不可用 %d" % (len(results) - ok)]})

    def run_load(self, h, cfg, rid, stop):
        base = cfg.get("base_url", "").strip().rstrip("/")
        key = cfg.get("api_key", "").strip()
        model = cfg.get("model", "").strip()
        question = cfg.get("question", "你好，请用一句话简短介绍你自己。")
        max_tokens = int(cfg.get("max_tokens", 200))
        timeout = int(cfg.get("timeout", 60))
        turns = max(1, int(cfg.get("turns", 5)))
        concurrency = max(1, int(cfg.get("concurrency", 3)))
        min_interval = float(cfg.get("min_interval", 0) or 0)
        if not model:
            self.emit("info", {"msg": "未指定模型，结束。"})
            return
        self.emit("info", {"msg": "多轮负载测试 | 模型 %s | 并发=%d 会话 | 每会话 %d 轮" % (model, concurrency, turns)})
        results = []
        lock = threading.Lock()
        t0 = time.time()

        def session(wid):
            messages = [{"role": "user", "content": question}]
            for t in range(turns):
                if stop.is_set():
                    break
                r = call_once(base, key, model, messages, max_tokens, timeout, min_interval)
                with lock:
                    results.append(r)
                self.emit("row", {"model": "%s [会话%d·轮%d]" % (model, wid + 1, t + 1), **summarize(r)})
                if r["status"] == "ok":
                    messages.append({"role": "assistant", "content": (r.get("content") or "")[:400]})
                    messages.append({"role": "user", "content": question})
                else:
                    # 失败也继续下一轮（负载测试关心整体表现）
                    messages.append({"role": "user", "content": question})

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            list(ex.map(session, range(concurrency)))
        wall = round(time.time() - t0, 2)
        total = len(results)
        ok = sum(1 for r in results if r["status"] == "ok")
        c429 = sum(1 for r in results if r.get("code") == 429)
        errs = sum(1 for r in results if r["status"] in ("error", "http_error", "timeout", "empty"))
        lats = sorted(r["elapsed"] for r in results if isinstance(r.get("elapsed"), (int, float)))
        p50 = lats[int(len(lats) * 0.5)] if lats else None
        p95 = lats[int(len(lats) * 0.95)] if lats else None
        avg = round(sum(lats) / len(lats), 2) if lats else None
        thr = round(ok / wall, 2) if wall > 0 else 0
        self.emit("summary", {"title": "多轮负载测试结果", "lines": [
            "总请求 %d | 成功 %d | 失败 %d | 429 %d" % (total, ok, errs, c429),
            "成功率 %.1f%%" % (100.0 * ok / total if total else 0),
            "延迟 avg=%s p50=%s p95=%s (s)" % (avg, p50, p95),
            "吞吐 %.2f 成功请求/秒 | 总耗时 %ss" % (thr, wall)]})

    def run_scan(self, h, cfg, rid, stop):
        base = cfg.get("base_url", "").strip().rstrip("/")
        key = cfg.get("api_key", "").strip()
        filt = cfg.get("filter", "free_text")
        question = cfg.get("question", "你好，请用一句话简短介绍你自己。")
        max_tokens = int(cfg.get("max_tokens", 200))
        timeout = int(cfg.get("timeout", 60))
        workers = max(1, int(cfg.get("workers", 3)))
        min_interval = float(cfg.get("min_interval", 0) or 0)
        self.emit("info", {"msg": "扫描新增模型 | 端点 %s | 过滤=%s" % (base, filt)})
        try:
            all_models = fetch_models(base, key, timeout)
        except RuntimeError as e:
            self.emit("info", {"msg": str(e)})
            return
        cands = [m for m in all_models if model_matches(m, filt)]
        cur_ids = [c["id"] for c in cands]
        cur_map = {c["id"]: c for c in cands}
        prev = load_snapshot(base, filt)
        if prev is None:
            self.emit("info", {"msg": "首次扫描，建立基线快照（%d 个模型），并对全部测连通性。" % len(cur_ids)})
            save_snapshot(base, filt, cur_ids)
            to_test = cur_ids
            self.emit("scan_diff", {"added": cur_ids, "removed": [], "unchanged": 0, "first": True})
        else:
            prev_ids = set(prev.get("ids", []))
            added = [i for i in cur_ids if i not in prev_ids]
            removed = [i for i in prev_ids if i not in set(cur_ids)]
            save_snapshot(base, filt, cur_ids)
            self.emit("scan_diff", {"added": added, "removed": removed,
                                    "unchanged": len(cur_ids) - len(added),
                                    "first": False})
            if not added:
                self.emit("info", {"msg": "未发现新增模型（相比上次 %s）。" % prev.get("fetched_at")})
                return
            self.emit("info", {"msg": "新增 %d 个模型，开始测连通性。" % len(added)})
            to_test = added

        results = {}
        lock = threading.Lock()

        def work(mid):
            if stop.is_set():
                return
            r = call_once(base, key, mid, [{"role": "user", "content": question}], max_tokens, timeout, min_interval)
            with lock:
                results[mid] = r
            self.emit("row", {"model": mid, **summarize(r), "is_new": True})

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, to_test))
        ok = sum(1 for v in results.values() if v["status"] == "ok")
        self.emit("summary", {"title": "扫描新增模型结果", "lines": [
            "新增待测 %d 个" % len(to_test), "可用 %d" % ok, "不可用 %d" % (len(to_test) - ok)]})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("模型连通性测试 Web UI 已启动: http://%s:%d" % (HOST, PORT))
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.shutdown()


if __name__ == "__main__":
    main()
