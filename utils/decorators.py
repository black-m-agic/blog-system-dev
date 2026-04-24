from functools import wraps
from flask import session, redirect, url_for, flash, request
from models import User
from utils.security import log_security_event

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('auth.login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            log_security_event('admin_access_denied', f'User: {session.get("user_id")}')
            flash('无管理员权限', 'error')
            return redirect(url_for('main.index'))
        # 记录管理员访问
        log_security_event('admin_access', f'Endpoint: {request.endpoint}')
        return f(*args, **kwargs)
    return decorated_function