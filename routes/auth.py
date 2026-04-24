from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from utils.decorators import login_required
from utils import validate_password_strength
from utils.security import (
    rate_limit, 
    validate_username, 
    validate_email,
    log_security_event,
    clean_html
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@rate_limit(limit=10, per_seconds=60)  # 限制每分钟10次登录尝试
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # 验证输入
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            log_security_event('LOGIN_FAILED_INVALID_INPUT', error_msg)
            flash('用户名或密码错误', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            log_security_event('LOGIN_SUCCESS', f'User: {username}')
            flash('登录成功', 'success')
            return redirect(url_for('main.index'))
        else:
            log_security_event('LOGIN_FAILED', f'Failed login for: {username}')
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@rate_limit(limit=5, per_seconds=60)  # 限制每分钟5次注册
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # 验证输入
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('auth.register'))
        
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('两次密码不一致', 'error')
            return redirect(url_for('auth.register'))
        
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            flash(msg, 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'error')
            return redirect(url_for('auth.register'))
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        session['username'] = user.username
        log_security_event('REGISTRATION_SUCCESS', f'New user: {username}')
        flash('注册成功', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('已退出登录', 'success')
    return redirect(url_for('main.index'))