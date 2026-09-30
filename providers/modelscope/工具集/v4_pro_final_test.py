# -*- coding: utf-8 -*-
"""
ModelScope DeepSeek V4 系列最终连通性测试
使用 ModelScope 正确模型 ID 格式
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
    {"name": "deepseek-ai/DeepSeek-V4-Pro", "label": "DeepSeek-V4-Pro (最新版)"},
]

def test_model(model_id, max_tokens=100):
    """测试单个模型"""
    url = f"{BASE_URL}/chat/completions"
    
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "你好"}],
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
        with urllib.request.urlopen(req, timeout=60) as response:
            elapsed = time.time() - start_time
            result = json.loads(response.read().decode('utf-8'))
            
            if 'choices' not in result or not result['choices']:
                return {'status': 'empty_response', 'elapsed': elapsed}
            
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
            'body': error_body[:300]
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def main():
    print("=" * 70)
    print("ModelScope DeepSeek V4-Pro (最新版) 连通性测试")
    print(f"端点：{BASE_URL}")
    print(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    print("=" * 70)
    print()
    
    for model in MODELS_TO_TEST:
        model_id = model["name"]
        label = model["label"]
        
        print(f"测试 {label} ...")
        print(f"   Model ID: {model_id}")
        
        result = test_model(model_id)
        
        if result['status'] == 'ok':
            print(f"   ✅ 成功 | 耗时：{result['elapsed']}s | 输出：{result['content_length']} chars")
        elif result['status'] == 'empty_response':
            print(f"   ❌ 空响应")
        elif result['status'] == 'http_error':
            print(f"   ❌ HTTP {result['code']} | {result['reason']}")
            if 'body' in result:
                print(f"   详情：{result['body']}")
        else:
            print(f"   ❌ 错误：{result.get('error', 'unknown')}")
        
        print()
    
    # 保存结果
    output_file = os.path.join(DATA_DIR, "v4_pro_final_test_20260825.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': BASE_URL,
            'results': [{'model': m['name'], 'label': m['label'], 'result': test_model(m['name'])} for m in MODELS_TO_TEST]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"📁 结果已保存到：{output_file}")

if __name__ == "__main__":
    main()
