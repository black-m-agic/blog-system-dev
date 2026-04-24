#!/usr/bin/env python3
"""
简化的流式API测试
"""
import requests
import json

API_KEY = "sk-54b6678580fa41539bfc3a58588cd031"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

def test_streaming():
    print("测试流式API...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": "你是一个友好的助手。"},
            {"role": "user", "content": "用3句话介绍一下Python"}
        ],
        "temperature": 0.7,
        "max_tokens": 200,
        "stream": True
    }
    
    try:
        with requests.post(API_URL, headers=headers, json=data, timeout=60, stream=True) as response:
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ 流式API成功！")
                print("\nAI回复:")
                full_content = ""
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            if line_str == 'data: [DONE]':
                                print("\n[完成]")
                                break
                            
                            try:
                                json_str = line_str[6:]
                                chunk = json.loads(json_str)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        print(content, end='', flush=True)
                                        full_content += content
                            except json.JSONDecodeError:
                                pass
                print(f"\n\n完整内容: {full_content}")
            else:
                print(f"❌ 错误: {response.text}")
                
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_streaming()
