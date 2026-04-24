#!/usr/bin/env python3
"""
千问API测试工具
帮助您测试API密钥和调用方式
"""
import requests
import json

# 您的API密钥
API_KEY = "sk-54b6678580fa41539bfc3a58588cd031"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

def test_qianwen_api():
    """测试千问API调用"""
    print("=" * 60)
    print("千问API测试工具")
    print("=" * 60)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": "你是一个友好的助手。"},
            {"role": "user", "content": "你好，请用简单的方式介绍一下自己"}
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": False
    }
    
    print("\n测试1: 尝试调用千问API...")
    print(f"API URL: {API_URL}")
    print(f"API Key: {API_KEY[:15]}...")  # 只显示前15个字符
    print("=" * 60)
    
    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=30)
        
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API调用成功！")
            result = response.json()
            print(f"\n完整响应:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if 'choices' in result and len(result['choices']) > 0:
                ai_reply = result['choices'][0]['message']['content']
                print(f"\nAI回复: {ai_reply}")
            return True
        else:
            print("❌ API调用失败！")
            print(f"\n响应内容:")
            try:
                print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            except:
                print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_streaming_api():
    """测试流式API"""
    print("\n" + "=" * 60)
    print("测试2: 流式API测试")
    print("=" * 60)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": "你是一个友好的助手。"},
            {"role": "user", "content": "请用简单的方式介绍一下Python"}
        ],
        "temperature": 0.7,
        "max_tokens": 200,
        "stream": True
    }
    
    try:
        print("\n正在测试流式API...")
        with requests.post(API_URL, headers=headers, json=data, timeout=60, stream=True) as response:
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ 流式API调用成功！")
                print("\nAI回复（流式显示）:")
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
                            except json.JSONDecodeError:
                                pass
            else:
                print("❌ 流式API调用失败！")
                print(f"响应内容: {response.text}")
                
    except Exception as e:
        print(f"❌ 流式API错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("千问API测试工具")
    print("=" * 60)
    print("这个工具会帮助您测试API是否正常工作")
    print("=" * 60)
    
    success = test_qianwen_api()
    
    if success:
        answer = input("\n是否继续测试流式API? (y/n): ").strip().lower()
        if answer == 'y':
            test_streaming_api()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
