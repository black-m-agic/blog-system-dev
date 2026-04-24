import re
import logging
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

def generate_summary(content):
    plain_text = re.sub(r'<[^>]+>', '', content)
    return plain_text[:100] + '...' if len(plain_text) > 100 else plain_text

def validate_password_strength(password):
    if len(password) < 8:
        return False, "密码长度至少需要8位"
    if not re.search(r'[A-Z]', password):
        return False, "密码需要包含大写字母"
    if not re.search(r'[a-z]', password):
        return False, "密码需要包含小写字母"
    if not re.search(r'[0-9]', password):
        return False, "密码需要包含数字"
    return True, "密码强度合格"

def setup_logger(app):
    if not app.debug:
        file_handler = logging.FileHandler('logs/app.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.WARNING)
        app.logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    return app.logger

def escape_text(text):
    from werkzeug.utils import escape
    return escape(text)