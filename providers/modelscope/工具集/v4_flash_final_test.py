# -*- coding: utf-8 -*-
"""ModelScope DeepSeek V4-Flash-0731 连通性测试"""
import json, os, urllib.request, urllib.error, time


def _resolve_api_key():
    """解析 ModelScope 密钥，优先级：环境变量 -> 本地未提交的 local_secret.py。

    仓库内不保存任何密钥。本地开发只需在同目录建一个 local_secret.py：
        MODELSCOPE_API_KEY = "ms-..."
    （local_secret.py 已在 .gitignore 中，不会被提交）
    """
    v = (os.environ.get("MODELSCOPE_API_KEY") or "").strip()
    if v:
        return v
    try:
        import local_secret
        return (getattr(local_secret, "MODELSCOPE_API_KEY", "") or "").strip()
    except Exception:
        return ""


API_KEY = _resolve_api_key()  # 从环境变量或 local_secret.py 读取，见 local_secret.example.py
BASE_URL = "https://api-inference.modelscope.cn/v1"
MODEL_ID = "deepseek-ai/DeepSeek-V4-Flash-0731"

def test():
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        method='POST'
    )
    
    for attempt in range(3):
        try:
            start = time.time()
            with urllib.request.urlopen(req, timeout=60) as resp:
                elapsed = time.time() - start
                result = json.loads(resp.read().decode('utf-8'))
                
                if 'choices' not in result or not result['choices']:
                    return {'status': 'empty_response', 'elapsed': elapsed, 'attempt': attempt+1}
                
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                usage = result.get('usage', {})
                return {'status': 'ok', 'elapsed': round(elapsed, 2), 
                       'content_length': len(content), 'usage': usage, 'attempt': attempt+1}
                    
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            print(f"  重试 {attempt+1}: HTTP {e.code} | {body[:200]}")
            time.sleep(2)
        except Exception as e:
            print(f"  重试 {attempt+1}: {e}")
            time.sleep(2)
    
    return {'status': 'fail'}

print("=" * 60)
print("DeepSeek-V4-Flash-0731 (最新版) 连通性测试")
print(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
print("=" * 60)
print()
print(f"测试 {MODEL_ID} ...")

result = test()

if result['status'] == 'ok':
    print(f"   ✅ 成功 | 耗时：{result['elapsed']}s | 输出：{result['content_length']} chars")
elif result['status'] == 'empty_response':
    print(f"   ❌ 空响应 (尝试 {result['attempt']} 次)")
else:
    print(f"   ❌ 失败")
