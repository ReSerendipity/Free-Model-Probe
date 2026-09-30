# -*- coding: utf-8 -*-
"""
ModelScope V4 模型连通性测试
测试 DeepSeek-V4-Pro, DeepSeek-V4-Flash 等 V4 系列模型的可用性
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
    "deepseek-ai/DeepSeek-V4-Pro",
    "deepseek-ai/DeepSeek-V4-Flash-0731",
    "deepseek-ai/DeepSeek-V4-Pro-0813",
    "Qwen/Qwen3.5-397B-A17B",
    "ZhipuAI/GLM-5.2",
]

def test_model(model_id, max_tokens=100):
    """测试单个模型的连通性"""
    url = f"{BASE_URL}/chat/completions"
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请简短地回复我。"}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
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
        with urllib.request.urlopen(req, timeout=30) as response:
            elapsed = time.time() - start_time
            result = json.loads(response.read().decode('utf-8'))
            
            # 检查响应结构
            if 'choices' not in result or not result['choices']:
                return {
                    'status': 'empty_response',
                    'elapsed': elapsed,
                    'error': '空响应 (choices=null)'
                }
            
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = result.get('usage', {})
            
            return {
                'status': 'ok',
                'elapsed': round(elapsed, 2),
                'content_length': len(content),
                'usage': usage
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        return {
            'status': 'http_error',
            'code': e.code,
            'reason': e.reason,
            'body': error_body[:200]
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

def main():
    results = []
    
    print("=" * 60)
    print("ModelScope V4 模型连通性测试")
    print(f"端点：{BASE_URL}")
    print(f"测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    for i, model_id in enumerate(MODELS_TO_TEST, 1):
        print(f"[{i}/{len(MODELS_TO_TEST)}] 测试 {model_id} ...")
        
        # 首次测试
        result = test_model(model_id)
        
        # 如果失败，重试一次
        if result['status'] != 'ok':
            print(f"   首次测试失败，重试...")
            time.sleep(2)
            result = test_model(model_id)
        
        results.append({
            'model': model_id,
            'result': result
        })
        
        # 打印结果
        if result['status'] == 'ok':
            print(f"   ✅ 成功 | 耗时：{result['elapsed']}s | 输出长度：{result['content_length']} chars")
        elif result['status'] == 'empty_response':
            print(f"   ❌ 空响应 | {result['error']}")
        elif result['status'] == 'http_error':
            print(f"   ❌ HTTP {result['code']} | {result['reason']}")
        else:
            print(f"   ❌ 错误 | {result.get('error', 'unknown')}")
        
        print()
        time.sleep(1)  # 避免过快调用
    
    # 保存结果
    output_file = os.path.join(DATA_DIR, "v4_connectivity_test.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': BASE_URL,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"测试结果已保存到：{output_file}")
    
    # 汇总
    ok_count = sum(1 for r in results if r['result']['status'] == 'ok')
    fail_count = len(results) - ok_count
    
    print()
    print("=" * 60)
    print(f"汇总：{ok_count} 个可用，{fail_count} 个不可用")
    print("=" * 60)

if __name__ == "__main__":
    main()
