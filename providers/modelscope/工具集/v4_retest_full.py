# -*- coding: utf-8 -*-
"""
ModelScope V4 模型连通性完整复测
覆盖 v3 报告中的所有可用模型 + V4 系列最新实测
"""
import json
import os
import urllib.request
import urllib.error
import time

# 输出目录基于脚本自身位置，随项目整体迁移而不失效
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

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

MODELS_TO_TEST = [
    # 2 魔粒档（v3 报告可用 + V4 新版）
    {"name": "deepseek-v4-pro", "label": "DeepSeek-V4-Pro (最新版)"},
    {"name": "qwen/Qwen3.5-397B-A17B", "label": "Qwen3.5-397B-A17B"},
    
    # 1 魔粒档（v3 报告全部可用）
    {"name": "qwen/Qwen3.5-122B-A10B", "label": "Qwen3.5-122B-A10B"},
    {"name": "qwen/Qwen3.5-35B-A3B", "label": "Qwen3.5-35B-A3B"},
    {"name": "qwen/Qwen3.5-27B", "label": "Qwen3.5-27B"},
    {"name": "stepfun-ai/Step-3.7-Flash", "label": "Step-3.7-Flash"},
    {"name": "minimax/MiniMax-M1-80k", "label": "MiniMax-M1-80k"},
    {"name": "stepfun-ai/Step-3.5-Flash", "label": "Step-3.5-Flash"},
]

def test_model(model_id, max_tokens=100, retries=3):
    """测试单个模型的连通性，带重试机制"""
    url = f"{BASE_URL}/chat/completions"
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "你好"}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            },
            method='POST'
        )
        
        try:
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=60) as response:
                elapsed = time.time() - start_time
                result = json.loads(response.read().decode('utf-8'))
                
                if 'choices' not in result or not result['choices']:
                    return {
                        'status': 'empty_response',
                        'elapsed': elapsed,
                        'attempts': attempt + 1,
                        'error': '空响应 (choices=null)'
                    }
                
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                usage = result.get('usage', {})
                
                return {
                    'status': 'ok',
                    'elapsed': round(elapsed, 2),
                    'content_length': len(content),
                    'usage': usage,
                    'attempts': attempt + 1
                }
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return {
                'status': 'http_error',
                'code': e.code,
                'reason': e.reason,
                'body': error_body[:200]
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return {
                'status': 'error',
                'error': str(e)
            }
    
    return {'status': 'fail', 'error': '未知错误'}

def main():
    results = []
    
    print("=" * 70)
    print("ModelScope V4 模型连通性完整复测")
    print(f"端点：{BASE_URL}")
    print(f"测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    print(f"API Key: ms-****-8777")
    print("=" * 70)
    print()
    
    ok_count = 0
    fail_count = 0
    
    for i, model in enumerate(MODELS_TO_TEST, 1):
        model_id = model["name"]
        label = model["label"]
        
        print(f"[{i}/{len(MODELS_TO_TEST)}] 测试 {label} ...")
        
        result = test_model(model_id)
        
        results.append({
            'model': model_id,
            'label': label,
            'result': result
        })
        
        if result['status'] == 'ok':
            ok_count += 1
            print(f"   ✅ 成功 | 耗时：{result['elapsed']}s | 输出：{result['content_length']} chars | 尝试次数：{result['attempts']}")
        elif result['status'] == 'empty_response':
            fail_count += 1
            print(f"   ❌ 空响应 | 尝试次数：{result['attempts']} | {result['error']}")
        elif result['status'] == 'http_error':
            fail_count += 1
            print(f"   ❌ HTTP {result['code']} | {result['reason']}")
        else:
            fail_count += 1
            print(f"   ❌ 失败 | {result.get('error', 'unknown')}")
        
        print()
    
    # 保存结果
    output_file = os.path.join(DATA_DIR, "v4_retest_full_20260825.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': BASE_URL,
            'api_key_masked': 'ms-****-8777',
            'total_models': len(MODELS_TO_TEST),
            'ok_count': ok_count,
            'fail_count': fail_count,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print("=" * 70)
    print(f"📊 汇总：✅ {ok_count} 个可用 | ❌ {fail_count} 个不可用 | 总计：{len(MODELS_TO_TEST)}")
    print(f"📁 结果已保存到：{output_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
