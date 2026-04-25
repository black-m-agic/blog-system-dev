from flask import Flask, redirect, url_for, request, render_template
from flask_wtf.csrf import CSRFProtect
import os
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from models import db, User, Category, Article, Tag
from routes import main_bp, auth_bp, article_bp, other_bp, ai_bp
from routes.socket import init_socketio
from utils import generate_summary
from utils.security import get_security_headers, generate_secure_secret_key, log_security_event

app = Flask(__name__)

# 安全配置 - 从环境变量加载或使用安全默认值
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = generate_secure_secret_key()
    print("⚠️  WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY environment variable for production!")

app.config['SECRET_KEY'] = SECRET_KEY
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "blog.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session安全配置
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('ENVIRONMENT') == 'production'  # HTTPS时启用
app.config['SESSION_COOKIE_HTTPONLY'] = True  # 防止XSS访问Cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 防止CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = 3600 * 24 * 7  # Session有效期7天

db.init_app(app)
csrf = CSRFProtect(app)

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(article_bp)
app.register_blueprint(other_bp)
app.register_blueprint(ai_bp)

# 豁免AI API路由的CSRF保护
csrf.exempt(ai_bp)

# 初始化 SocketIO
socketio = init_socketio(app)

_tables_created = False

@app.before_request
def create_tables():
    global _tables_created
    if _tables_created:
        return
    
    with app.app_context():
        db.create_all()
        
        from werkzeug.security import generate_password_hash
        
        if Category.query.count() == 0:
            categories = ['技术', '生活', '读书', '旅行', '其他']
            for name in categories:
                category = Category(name=name)
                db.session.add(category)
            db.session.commit()
        
        if User.query.count() == 0:
            import secrets
            random_password = secrets.token_urlsafe(12)
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash(random_password),
                bio='系统管理员',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("\n" + "="*60)
            print("⚠️  首次运行: 默认管理员账号已创建")
            print(f"   用户名: admin")
            print(f"   密码: {random_password}")
            print("   请务必尽快修改默认密码！")
            print("="*60 + "\n")
        
        if Article.query.count() == 0:
            categories = Category.query.all()
            admin = User.query.filter_by(username='admin').first()
            
            article_templates = [
                {
                    "title": "Python 入门指南",
                    "content": "Python 是一种简单易用但功能强大的编程语言。在本文中，我们将介绍 Python 的基本语法、数据类型和常用库...",
                    "category": 0,
                    "tags": ["Python", "编程", "入门"]
                },
                {
                    "title": "使用 Flask 构建 Web 应用",
                    "content": "Flask 是一个轻量级的 Python Web 框架，非常适合构建 Web 应用。本文将介绍如何使用 Flask 创建一个简单的博客系统...",
                    "category": 0,
                    "tags": ["Flask", "Web", "编程"]
                },
                {
                    "title": "我的一天：从清晨到黄昏",
                    "content": "今天是一个特殊的日子。我很早就起床了，看着窗外的日出，感受着新鲜的空气...",
                    "category": 1,
                    "tags": ["生活", "日常", "日记"]
                },
                {
                    "title": "阅读《代码大全》有感",
                    "content": "《代码大全》是一本经典的编程书籍，我最近花了一个月的时间读完了它，受益匪浅...",
                    "category": 2,
                    "tags": ["读书", "编程", "书籍"]
                },
                {
                    "title": "北京三日游旅行记",
                    "content": "第一次来北京，感受着这座城市的历史与现代的交融。我们去了故宫、长城、天坛等著名景点...",
                    "category": 3,
                    "tags": ["旅行", "北京", "风景"]
                },
                {
                    "title": "JavaScript 异步编程详解",
                    "content": "异步编程是 JavaScript 的核心特性之一。本文将详细介绍 callback、promise 和 async/await...",
                    "category": 0,
                    "tags": ["JavaScript", "编程", "异步"]
                },
                {
                    "title": "如何提高代码质量",
                    "content": "代码质量是程序员必须关注的问题。本文将分享一些提高代码质量的方法，包括代码审查、单元测试和重构...",
                    "category": 0,
                    "tags": ["编程", "代码质量", "最佳实践"]
                },
                {
                    "title": "周末的登山之旅",
                    "content": "上周六，我和朋友们一起去登山。虽然很累，但山顶的风景令人心旷神怡...",
                    "category": 1,
                    "tags": ["生活", "登山", "周末"]
                },
                {
                    "title": "《人类简史》读书笔记",
                    "content": "《人类简史》是一本让人思考很多的书。作者从宏观的角度讲述了人类的发展历程...",
                    "category": 2,
                    "tags": ["读书", "历史", "哲学"]
                },
                {
                    "title": "杭州西湖行",
                    "content": "西湖美景三月天，终于有机会亲身体验了。湖光山色，美不胜收...",
                    "category": 3,
                    "tags": ["旅行", "杭州", "西湖"]
                }
            ]
            
            for i in range(50):
                template = article_templates[i % len(article_templates)]
                category = categories[template["category"] % len(categories)]
                
                article = Article(
                    title=template["title"],
                    content=template["content"] * ((i % 3) + 1),
                    category_id=category.id,
                    user_id=admin.id,
                    status="published"
                )
                article.summary = generate_summary(article.content)
                db.session.add(article)
                db.session.flush()
                
                for tag_name in template["tags"]:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                        db.session.flush()
                    article.tags.append(tag)
            
            db.session.commit()
        
        from models import ChatRoom, ChatRoomMember
        if ChatRoom.query.count() == 0:
            public_room = ChatRoom(name="公共聊天室", is_public=True)
            db.session.add(public_room)
            db.session.flush()
            
            admin = User.query.filter_by(username='admin').first()
            if admin:
                member = ChatRoomMember(user_id=admin.id, chat_room_id=public_room.id)
                db.session.add(member)
            
            db.session.commit()
        
        _tables_created = True

@app.after_request
def add_security_headers(response):
    """添加安全响应头"""
    # 添加安全Headers
    security_headers = get_security_headers()
    for header, value in security_headers.items():
        response.headers[header] = value
    
    # 缓存控制
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'public, max-age=300'
    
    return response

# 全局错误处理器
@app.errorhandler(400)
def bad_request_error(error):
    log_security_event('error_400', str(error))
    return render_template('400.html'), 400

@app.errorhandler(403)
def forbidden_error(error):
    log_security_event('error_403', str(error))
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    log_security_event('error_404', request.path)
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    log_security_event('error_500', str(error))
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    log_security_event('unhandled_exception', str(error))
    return render_template('500.html'), 500

if __name__ == '__main__':
    # 判断是否为生产环境
    is_production = os.environ.get('ENVIRONMENT') == 'production'
    debug_mode = not is_production
    
    if is_production:
        print("🔒 Running in PRODUCTION mode - Debug disabled")
        socketio.run(app, host='0.0.0.0', port=8080, debug=False)
    else:
        print("⚠️ Running in DEVELOPMENT mode - Debug enabled")
        socketio.run(app, host='0.0.0.0', port=8080, debug=True, allow_unsafe_werkzeug=True)