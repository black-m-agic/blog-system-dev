import os
import re
import logging
from functools import wraps
from flask import request, jsonify, session
from datetime import datetime, timedelta
import bleach

# 配置日志
logging.basicConfig(level=logging.INFO)
security_logger = logging.getLogger('security')

# 速率限制存储
rate_limit_storage = {}

# 允许的HTML标签和属性（用于XSS防护）
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 
    'i', 'li', 'ol', 'strong', 'ul', 'br', 'p', 'h1', 'h2', 
    'h3', 'h4', 'h5', 'h6', 'pre', 'div', 'span'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
}


def clean_html(html_content):
    """清理HTML内容，防止XSS攻击"""
    if not html_content:
        return ''
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )


def validate_username(username):
    """验证用户名格式"""
    if not username or len(username) < 3 or len(username) > 50:
        return False, "用户名长度应在3-50个字符之间"
    if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
        return False, "用户名只能包含字母、数字、下划线和中文"
    return True, ""


def validate_email(email):
    """验证邮箱格式"""
    if not email or len(email) > 100:
        return False, "邮箱格式不正确"
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, "邮箱格式不正确"
    return True, ""


def validate_article_title(title):
    """验证文章标题"""
    if not title or len(title) < 1 or len(title) > 100:
        return False, "标题长度应在1-100个字符之间"
    return True, ""


def validate_article_content(content):
    """验证文章内容"""
    if not content or len(content) < 1:
        return False, "内容不能为空"
    if len(content) > 50000:  # 限制50KB
        return False, "内容过长，最多50000个字符"
    return True, ""


def validate_comment_content(content):
    """验证评论内容"""
    if not content or len(content) < 1:
        return False, "评论不能为空"
    if len(content) > 2000:  # 限制2KB
        return False, "评论过长，最多2000个字符"
    return True, ""


def validate_ai_message(message):
    """验证AI消息"""
    if not message or len(message) < 1:
        return False, "消息不能为空"
    if len(message) > 5000:  # 限制5KB
        return False, "消息过长，最多5000个字符"
    return True, ""


def rate_limit(limit, per_seconds):
    """
    速率限制装饰器
    :param limit: 允许的请求次数
    :param per_seconds: 时间窗口（秒）
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # 获取客户端标识符
            client_id = get_client_id()
            
            # 清理过期的记录
            clean_expired_records()
            
            # 检查速率限制
            now = datetime.now()
            key = f"{client_id}:{request.endpoint}"
            
            if key not in rate_limit_storage:
                rate_limit_storage[key] = {
                    'count': 0,
                    'reset_time': now + timedelta(seconds=per_seconds)
                }
            
            record = rate_limit_storage[key]
            
            # 检查是否需要重置
            if now > record['reset_time']:
                record['count'] = 0
                record['reset_time'] = now + timedelta(seconds=per_seconds)
            
            # 检查是否超过限制
            if record['count'] >= limit:
                security_logger.warning(f"Rate limit exceeded: {client_id} - {request.endpoint}")
                return jsonify({
                    'success': False,
                    'error': '请求过于频繁，请稍后再试'
                }), 429
            
            # 增加计数
            record['count'] += 1
            
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_client_id():
    """获取客户端唯一标识符"""
    # 优先使用用户ID（如果已登录）
    if 'user_id' in session:
        return f"user:{session['user_id']}"
    
    # 否则使用IP地址
    return f"ip:{request.remote_addr}"


def clean_expired_records():
    """清理过期的速率限制记录"""
    now = datetime.now()
    keys_to_delete = []
    
    for key, record in rate_limit_storage.items():
        if now > record['reset_time']:
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        del rate_limit_storage[key]


def log_security_event(event_type, details):
    """记录安全事件"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'client_id': get_client_id(),
        'endpoint': request.endpoint,
        'method': request.method,
        'ip': request.remote_addr,
        'details': details
    }
    
    security_logger.warning(f"Security Event: {event_type} - {details}")
    return log_data


def generate_secure_secret_key():
    """生成安全的SECRET_KEY"""
    return os.urandom(32).hex()


def get_security_headers():
    """获取安全响应头"""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' ws: wss:",
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }
