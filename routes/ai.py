from flask import Blueprint, render_template, request, jsonify, session, Response
import requests
import json
import random
import time

from utils.security import (
    rate_limit, 
    validate_ai_message, 
    log_security_event,
    clean_html
)
from utils.encryption import SecureKeyStorage

ai_bp = Blueprint('ai', __name__)

# 默认 AI API 配置 - 千问（通义千问）API
# 请前往 https://dashscope.console.aliyun.com/ 获取API密钥
DEFAULT_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_API_KEY = "sk-54b6678580fa41539bfc3a58588cd031"  # 使用您的API密钥

# 初始化安全存储
secure_storage = None

def get_secure_storage():
    """获取安全存储实例"""
    global secure_storage
    if secure_storage is None:
        secure_storage = SecureKeyStorage()
    return secure_storage

# 简单的演示回复
DEMO_RESPONSES = [
    "[思考] 用户向我打招呼，我应该友好地回应，并询问有什么可以帮助的。\n\n[回答] 你好！很高兴见到你。我是博客系统的AI助手，有什么我可以帮助你的吗？无论是关于文章内容、技术问题还是其他方面，我都很乐意为你解答。",
    "[思考] 用户问我叫什么名字，我应该清晰地介绍自己。\n\n[回答] 你好！我是博客系统的智能助手，你可以叫我小AI。我随时为你提供帮助，无论是关于博客内容、技术问题还是其他话题，都可以问我哦！",
    "[思考] 用户在感谢我，我应该礼貌地回应。\n\n[回答] 不客气！很高兴能帮到你。如果还有其他问题，随时都可以问我哦！",
    "[思考] 这是一个很好的问题！让我来详细为您分析一下。首先，我们需要从多个角度来看待这个问题，包括技术实现、用户体验以及实际应用场景。通过深入的分析，您会发现这个问题的解决方案其实非常有趣。\n\n[回答] 这是一个很好的问题！让我来详细为您分析一下。首先，我们需要从多个角度来看待这个问题，包括技术实现、用户体验以及实际应用场景。通过深入的分析，您会发现这个问题的解决方案其实非常有趣。希望我的回答对您有所帮助！如果还有其他问题，请随时问我。",
    "[思考] 根据我的了解，这个话题确实很有意思！让我从几个方面来为您详细解释。首先，我们要明白这个概念的基本原理，然后再探讨它在实际应用中的表现。\n\n[回答] 根据我的了解，这个话题确实很有意思！让我从几个方面来为您详细解释。首先，我们要明白这个概念的基本原理，然后再探讨它在实际应用中的表现。通过这样的方式，您应该能够全面地理解这个问题了。如果还有什么不明白的地方，请随时告诉我！",
    "[思考] 您提到的这个点非常有见解！让我结合博客系统的实际情况来为您解答。首先，我们来看一下这个功能在技术上是如何实现的，然后再讨论它能为用户带来什么价值。\n\n[回答] 您提到的这个点非常有见解！让我结合博客系统的实际情况来为您解答。首先，我们来看一下这个功能在技术上是如何实现的，然后再讨论它能为用户带来什么价值。我觉得这样的设计思路是非常合理的，能够很好地解决用户的需求。如果您还有其他疑问，我很乐意继续为您解答！",
    "[思考] 让我来为您详细解答这个问题。首先，我们需要了解一些基本的背景知识，然后再逐步深入分析。我会尽量用简单易懂的方式来解释，让您能够轻松理解。\n\n[回答] 让我来为您详细解答这个问题。首先，我们需要了解一些基本的背景知识，然后再逐步深入分析。我会尽量用简单易懂的方式来解释，让您能够轻松理解。希望我的解释能够帮助您更好地理解这个问题！如果还有其他问题，请随时提问。",
    "[思考] 这个问题确实值得深入讨论！让我从多个维度来为您分析。首先，我们看一下这个问题的背景和现状，然后再探讨可能的解决方案。\n\n[回答] 这个问题确实值得深入讨论！让我从多个维度来为您分析。首先，我们看一下这个问题的背景和现状，然后再探讨可能的解决方案。通过这样的分析，我相信您对这个问题会有更全面的认识。如果还有其他问题，我随时为您服务！"
]

def generate_streaming_response(message, article_data=None, all_articles_data=None, api_key=None, api_url=None):
    """生成流式响应"""
    
    # 使用真实的API - 如果用户设置了就用用户的，否则用默认值
    api_key = api_key if api_key else DEFAULT_API_KEY
    api_url = api_url if api_url else DEFAULT_API_URL
    
    print(f"使用真实API，用户问题: {message}")
    
    try:
        # 构建系统提示词，如果有文章ID，可以添加文章相关内容
        
        system_prompt = """你是一个博客系统的智能助手，友好、专业、乐于助人。你有以下能力：

1. 文章讲解：当用户问"这篇文章讲了什么"、"这篇文章的主要内容是什么"等问题时，详细总结当前文章
2. 文章推荐：当用户想要某种类型的文章时，从文章资料库中推荐相关文章
3. 技术解答：回答关于文章内容的技术问题

请直接回答用户的问题，提供有帮助、清晰的答案。"""
        
        # 如果有文章数据，添加到提示词
        if article_data:
            print(f"添加文章信息，标题: {article_data['title']}")
            system_prompt += f"\n\n【当前文章信息】\n标题：{article_data['title']}\n分类：{article_data['category'] or '未分类'}\n内容：{article_data['content'][:3000]}"
        
        # 如果有文章资料库数据，添加到提示词
        if all_articles_data:
            print(f"添加文章资料库，共{len(all_articles_data)}篇文章")
            system_prompt += "\n\n【文章资料库】"
            for i, art in enumerate(all_articles_data[:20], 1):
                system_prompt += f"\n{i}. 标题：{art['title']} | 分类：{art['category'] or '未分类'}"
                if art['content']:
                    system_prompt += f" | 摘要：{art['content'][:150]}..."
        
        system_prompt += "\n\n请根据以上信息回答用户的问题。如果推荐文章，请提供标题并简要说明推荐理由。"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "qwen-turbo",  # 使用千问的模型（qwen-turbo/qwen-plus/qwen-max）
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": True
        }
        print(f"API Key: {api_key[:15]}...")
        print(f"调用AI API(流式): {api_url}")
        print(f"请求数据: {data}")
        
        # 使用流式请求
        with requests.post(api_url, headers=headers, json=data, timeout=60, stream=True) as response:
            print(f"响应状态: {response.status_code}")
            try:
                response.raise_for_status()
            except Exception as e:
                print(f"HTTP错误: {e}")
                raise
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        if line_str == 'data: [DONE]':
                            yield f"data: {json.dumps({'content': '', 'done': True}, ensure_ascii=False)}\n\n"
                            break
                        
                        try:
                            json_str = line_str[6:]  # 去掉 'data: ' 前缀
                            chunk = json.loads(json_str)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield f"data: {json.dumps({'content': content, 'done': False}, ensure_ascii=False)}\n\n"
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        print(f"AI API 调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # API失败时的提示
        error_msg = f"[思考] API调用失败，我无法获取真实回答。请检查API配置。\n\n[回答] 抱歉，API调用失败了。请检查API配置是否正确。"
        for char in error_msg:
            yield f"data: {json.dumps({'content': char, 'done': False}, ensure_ascii=False)}\n\n"
            time.sleep(0.03)
        yield f"data: {json.dumps({'content': '', 'done': True}, ensure_ascii=False)}\n\n"

def get_ai_response(message, article_data=None, all_articles_data=None, api_key=None, api_url=None):
    """获取 AI 响应 - 非流式版本"""
    
    # 使用真实的API - 如果用户设置了就用用户的，否则用默认值
    api_key = api_key if api_key else DEFAULT_API_KEY
    api_url = api_url if api_url else DEFAULT_API_URL
    
    print(f"使用真实API（非流式），用户问题: {message}")
    
    try:
        # 构建系统提示词，如果有文章ID，可以添加文章相关内容
        
        system_prompt = """你是一个博客系统的智能助手，友好、专业、乐于助人。你有以下能力：

1. 文章讲解：当用户问"这篇文章讲了什么"、"这篇文章的主要内容是什么"等问题时，详细总结当前文章
2. 文章推荐：当用户想要某种类型的文章时，从文章资料库中推荐相关文章
3. 技术解答：回答关于文章内容的技术问题

请直接回答用户的问题，提供有帮助、清晰的答案。"""
        
        # 如果有文章数据，添加到提示词
        if article_data:
            print(f"添加文章信息，标题: {article_data['title']}")
            system_prompt += f"\n\n【当前文章信息】\n标题：{article_data['title']}\n分类：{article_data['category'] or '未分类'}\n内容：{article_data['content'][:3000]}"
        
        # 如果有文章资料库数据，添加到提示词
        if all_articles_data:
            print(f"添加文章资料库，共{len(all_articles_data)}篇文章")
            system_prompt += "\n\n【文章资料库】"
            for i, art in enumerate(all_articles_data[:20], 1):
                system_prompt += f"\n{i}. 标题：{art['title']} | 分类：{art['category'] or '未分类'}"
                if art['content']:
                    system_prompt += f" | 摘要：{art['content'][:150]}..."
        
        system_prompt += "\n\n请根据以上信息回答用户的问题。如果推荐文章，请提供标题并简要说明推荐理由。"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "qwen-turbo",  # 使用千问的模型（qwen-turbo/qwen-plus/qwen-max）
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False
        }
        print(f"调用AI API: {api_url}")
        print(f"请求数据: {data}")
        
        response = requests.post(api_url, headers=headers, json=data, timeout=15)
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"AI API 调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return "[思考] API调用失败，我无法获取真实回答。请检查API配置。\n\n[回答] 抱歉，API调用失败了。请检查API配置是否正确。"

@ai_bp.route('/api/chat/stream', methods=['POST'])
@rate_limit(limit=30, per_seconds=60)  # 限制每分钟30次
def api_chat_stream():
    """AI 聊天接口 - 流式版本"""
    print("="*60)
    print("收到API请求")
    print("="*60)
    data = request.json
    message = data.get('message', '')
    article_id = data.get('article_id')
    
    # 验证输入
    is_valid, error_msg = validate_ai_message(message)
    if not is_valid:
        log_security_event('INVALID_INPUT', error_msg)
        return jsonify({"success": False, "error": error_msg}), 400
    
    # 解密获取API密钥
    storage = get_secure_storage()
    encrypted_key = session.get('ai_api_key_encrypted')
    api_key = None
    if encrypted_key:
        api_key = storage.decrypt(encrypted_key)
    # 如果没有用户的密钥，使用默认密钥
    if not api_key:
        api_key = DEFAULT_API_KEY
    
    api_url = session.get('ai_api_url') or data.get('api_url') or DEFAULT_API_URL
    
    if not message:
        return jsonify({"success": False, "error": "请输入消息"}), 400
    
    # 在路由中查询数据库
    from models import Article
    
    article_data = None
    all_articles_data = None
    
    # 查询当前文章
    if article_id:
        try:
            print(f"正在加载文章，ID: {article_id}")
            article = Article.query.get(article_id)
            if article:
                article_data = {
                    'title': article.title,
                    'category': article.category,
                    'content': article.content
                }
                print(f"成功加载文章，标题: {article.title}")
            else:
                print(f"未找到文章，ID: {article_id}")
        except Exception as e:
            print(f"加载文章失败: {e}")
    
    # 查询所有文章资料库
    try:
        all_articles = Article.query.all()
        print(f"加载文章资料库，共{len(all_articles)}篇文章")
        all_articles_data = []
        for art in all_articles:
            all_articles_data.append({
                'title': art.title,
                'category': art.category,
                'content': art.content
            })
    except Exception as e:
        print(f"加载文章资料库失败: {e}")
    
    print(f"准备调用生成函数，消息: {message}")
    print("="*60)
    
    # 不捕获异常，让它显示详细的错误信息
    return Response(
        generate_streaming_response(message, article_data, all_articles_data, api_key, api_url),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@ai_bp.route('/api/chat', methods=['POST'])
@rate_limit(limit=30, per_seconds=60)  # 限制每分钟30次
def api_chat():
    """AI 聊天接口 - 供前端调用"""
    data = request.json
    message = data.get('message', '')
    article_id = data.get('article_id')
    
    # 验证输入
    is_valid, error_msg = validate_ai_message(message)
    if not is_valid:
        log_security_event('INVALID_INPUT', error_msg)
        return jsonify({"success": False, "error": error_msg}), 400
    
    # 解密获取API密钥
    storage = get_secure_storage()
    encrypted_key = session.get('ai_api_key_encrypted')
    api_key = None
    if encrypted_key:
        api_key = storage.decrypt(encrypted_key)
    # 如果没有用户的密钥，使用默认密钥
    if not api_key:
        api_key = DEFAULT_API_KEY
    
    api_url = session.get('ai_api_url') or data.get('api_url') or DEFAULT_API_URL
    
    if not message:
        return jsonify({"success": False, "error": "请输入消息"}), 400
    
    # 在路由中查询数据库
    from models import Article
    
    article_data = None
    all_articles_data = None
    
    # 查询当前文章
    if article_id:
        try:
            print(f"正在加载文章，ID: {article_id}")
            article = Article.query.get(article_id)
            if article:
                article_data = {
                    'title': article.title,
                    'category': article.category,
                    'content': article.content
                }
                print(f"成功加载文章，标题: {article.title}")
            else:
                print(f"未找到文章，ID: {article_id}")
        except Exception as e:
            print(f"加载文章失败: {e}")
    
    # 查询所有文章资料库
    try:
        all_articles = Article.query.all()
        print(f"加载文章资料库，共{len(all_articles)}篇文章")
        all_articles_data = []
        for art in all_articles:
            all_articles_data.append({
                'title': art.title,
                'category': art.category,
                'content': art.content
            })
    except Exception as e:
        print(f"加载文章资料库失败: {e}")
    
    try:
        response = get_ai_response(message, article_data, all_articles_data, api_key, api_url)
        return jsonify({"success": True, "reply": response})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ai_bp.route('/ai/chat', methods=['POST'])
def ai_chat():
    """AI 聊天接口 - 兼容性接口"""
    return api_chat()

@ai_bp.route('/api/test', methods=['POST'])
def api_test():
    """测试接口"""
    print("="*60)
    print("收到测试请求")
    print("="*60)
    try:
        data = request.json
        print(f"测试请求数据: {data}")
        return jsonify({"success": True, "message": "测试成功"})
    except Exception as e:
        print(f"测试请求错误: {e}")
        return jsonify({"success": False, "error": str(e)})

@ai_bp.route('/ai/settings', methods=['GET', 'POST'])
@rate_limit(limit=10, per_seconds=60)  # 限制每分钟10次
def ai_settings():
    """AI 设置页面"""
    storage = get_secure_storage()
    
    if request.method == 'POST':
        api_key = request.form.get('api_key', '').strip()
        api_url = request.form.get('api_url', '').strip()
        
        # 加密存储API密钥
        if api_key:
            session['ai_api_key_encrypted'] = storage.encrypt(api_key)
        else:
            session.pop('ai_api_key_encrypted', None)
            
        # API URL不需要加密
        if api_url:
            session['ai_api_url'] = api_url
        else:
            session.pop('ai_api_url', None)
        
        log_security_event('AI_SETTINGS_UPDATED', 'API settings updated')
        return jsonify({"success": True, "message": "设置保存成功"})
    
    # 获取当前设置（不显示默认值，只显示用户自己设置的）
    api_key = ''  # 永远不显示密钥，只显示占位符
    api_url = session.get('ai_api_url', '')
    
    # 检查是否有设置模板
    try:
        return render_template('ai_settings.html', api_key=api_key, api_url=api_url)
    except:
        # 如果没有模板，返回一个简单的说明页面
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI 设置</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 50px auto; padding: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #0071e3; font-size: 1.3rem; margin-top: 30px; }}
                .setting-group {{ margin: 20px 0; }}
                label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
                button {{ padding: 10px 20px; background: #0071e3; color: white; border: none; border-radius: 5px; cursor: pointer; }}
                button:hover {{ background: #0066cc; }}
                .info {{ background: #f5f5f7; padding: 20px; border-radius: 10px; margin: 20px 0; }}
                .model-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                .model-table th, .model-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                .model-table th {{ background: #0071e3; color: white; }}
                .recommended {{ background: #e8f5e8; }}
                .badge {{ display: inline-block; padding: 3px 8px; background: #0071e3; color: white; border-radius: 4px; font-size: 0.8rem; margin-right: 5px; }}
                .tip {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ffc107; }}
                .tip h4 {{ margin-top: 0; color: #856404; }}
            </style>
        </head>
        <body>
            <h1>🤖 AI 助手设置</h1>
            
            <div class="info">
                <h2>📋 推荐模型</h2>
                <table class="model-table">
                    <tr>
                        <th>模型</th>
                        <th>特点</th>
                        <th>推荐程度</th>
                    </tr>
                    <tr class="recommended">
                        <td><strong>千问 (Qwen)</strong> <span class="badge">当前使用</span></td>
                        <td>阿里云的大语言模型，稳定可靠</td>
                        <td>⭐⭐⭐⭐⭐</td>
                    </tr>
                </table>
            </div>
            
            <div class="tip">
                <h4>📌 API 地址是什么？</h4>
                <p><strong>API 地址</strong>是发送请求到 AI 服务的网址端点。它告诉系统要把你的请求发送到哪里去获取 AI 回复。</p>
                <ul>
                    <li><strong>当前默认 API 地址</strong>: <code>https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions</code></li>
                    <li><strong>作用</strong>: 这个地址连接到阿里云的千问大模型服务</li>
                    <li><strong>注意</strong>: 通常情况下不需要修改，使用默认地址即可</li>
                </ul>
            </div>
            
            <div class="info">
                <h2>🚀 如何获取千问API密钥？</h2>
                <ol>
                    <li>访问 <a href="https://dashscope.console.aliyun.com/" target="_blank">阿里云百炼平台</a></li>
                    <li>注册/登录阿里云账号</li>
                    <li>进入 API-KEY 管理页面</li>
                    <li>点击"创建新的 API-KEY"</li>
                    <li>复制生成的 API Key</li>
                    <li>将 API Key 粘贴到下方表单中保存</li>
                </ol>
            </div>
            
            <form action="/ai/settings" method="post">
                <div class="setting-group">
                    <label for="api_key">API 密钥:</label>
                    <input type="password" id="api_key" name="api_key" value="{api_key}" placeholder="请输入您的API密钥（留空使用系统默认）">
                </div>
                <div class="setting-group">
                    <label for="api_url">API 地址:</label>
                    <input type="text" id="api_url" name="api_url" value="{api_url}" placeholder="请输入API地址（留空使用默认）">
                </div>
                <button type="submit">保存设置</button>
            </form>
            
            <p style="margin-top: 20px; color: #666;">
                <a href="/">返回首页</a>
            </p>
        </body>
        </html>
        """
        return html_content