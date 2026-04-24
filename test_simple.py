#!/usr/bin/env python3
"""简单的千问API测试"""
import requests
import json
import sys

API_KEY = "sk-54b6678580fa41539bfc3a58588cd031"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

print("="*60)
print("测试千问API")
print("="*60)

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

data = {
    "model": "qwen-turbo",
    "messages": [
        {"role": "user", "content": "你好，介绍一下自己"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
}

print(f"\nAPI Key: {API_KEY[:15]}...")
print(f"API URL: {API_URL}")
print(f"请求数据: {data}")
print("="*60)

try:
    response = requests.post(API_URL, headers=headers, json=data, timeout=30)
    
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应头: {response.headers}")
    
    if response.status_code == 200:
        print("\n✅ API调用成功！")
        result = response.json()
        print(f"\n完整响应:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n❌ API调用失败！")
        print(f"\n响应内容: {response.text}")
        
except Exception as e:
    print(f"\n❌ 发生错误: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("测试完成")
print("="*60)
