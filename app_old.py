# 个人博客系统 - 作者：王宅凯 学号：2023214509
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import time

# 尝试导入Redis
redis_client = None
try:
    import redis
    # Redis连接池配置
    redis_pool = redis.ConnectionPool(
        host='localhost',  # 生产环境中替换为实际的Redis服务器地址
        port=6379,
        db=0,
        max_connections=50,  # 连接池大小
        decode_responses=True
    )
    redis_client = redis.Redis(connection_pool=redis_pool)
except ImportError:
    print("Redis模块未安装，将不使用缓存功能")
except Exception as e:
    print(f"Redis连接失败: {e}，将不使用缓存功能")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 数据库模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    articles = db.relationship('Article', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    articles = db.relationship('Article', backref='category', lazy=True)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    articles = db.relationship('Article', secondary='article_tag', backref='tags', lazy=True)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)  # 标题索引
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False, index=True)  # 分类索引
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # 用户索引
    status = db.Column(db.String(20), default='published', index=True)  # 状态索引
    views = db.Column(db.Integer, default=0, index=True)  # 浏览量索引
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), index=True)  # 创建时间索引
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp(), index=True)  # 更新时间索引
    comments = db.relationship('Comment', backref='article', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # 用户索引
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False, index=True)  # 文章索引
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True, index=True)  # 父评论索引
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), index=True)  # 创建时间索引
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)

class ArticleTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False, index=True)  # 文章索引
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False, index=True)  # 标签索引

# 装饰器：登录验证
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 装饰器：管理员权限
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user.is_admin:
            flash('无管理员权限', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 缓存装饰器
def cache(expire=3600):
    def decorator(f):
        def wrapper(*args, **kwargs):
            # 如果Redis不可用，直接执行函数
            if not redis_client:
                return f(*args, **kwargs)
            
            # 生成缓存键
            cache_key = f"{f.__name__}:{json.dumps(kwargs)}"
            
            # 尝试从缓存获取
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    try:
                        return json.loads(cached_data)
                    except:
                        pass
            except:
                pass
            
            # 执行函数
            result = f(*args, **kwargs)
            
            # 缓存结果
            try:
                redis_client.setex(cache_key, expire, json.dumps(result, default=str))
            except:
                pass
            
            return result
        return wrapper
    return decorator

# 清除缓存
def clear_cache(pattern):
    if redis_client:
        try:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
        except:
            pass

# 工具函数：生成摘要
def generate_summary(content):
    # 移除HTML标签
    plain_text = re.sub(r'<[^>]+>', '', content)
    # 截取前100个字符
    return plain_text[:100] + '...' if len(plain_text) > 100 else plain_text

# 初始化数据库和预设数据
with app.app_context():
    db.create_all()
    # 检查是否已有分类
    if Category.query.count() == 0:
        categories = ['技术', '生活', '读书', '旅行', '其他']
        for name in categories:
            category = Category(name=name)
            db.session.add(category)
        db.session.commit()
    
    # 检查是否已有用户
    if User.query.count() == 0:
        # 创建预设用户
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            bio='系统管理员',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
    
    # 检查是否已有文章
    if Article.query.count() == 0:
        # 获取预设用户
        admin = User.query.filter_by(username='admin').first()
        # 获取分类
        tech = Category.query.filter_by(name='技术').first()
        life = Category.query.filter_by(name='生活').first()
        reading = Category.query.filter_by(name='读书').first()
        travel = Category.query.filter_by(name='旅行').first()
        
        # 创建预设文章
        articles = [
            {
                'title': 'Flask 入门指南',
                'content': 'Flask 是一个轻量级的 Python Web 框架，非常适合构建小型到中型的 Web 应用。\n\n本教程将介绍 Flask 的基本使用方法，包括路由、模板、表单处理等内容。\n\n通过本教程的学习，你将能够构建一个简单但功能完整的 Flask 应用。',
                'category': tech,
                'tags': ['Flask', 'Python', 'Web开发']
            },
            {
                'title': '日常生活小窍门',
                'content': '在日常生活中，我们经常会遇到各种小问题，这里分享一些实用的生活小窍门。\n\n1. 用牙膏清洁银器\n2. 用白醋去除水垢\n3. 用香蕉皮擦皮鞋\n\n这些小窍门可以帮助你解决生活中的一些小问题，让生活更加方便。',
                'category': life,
                'tags': ['生活', '小窍门']
            },
            {
                'title': '《百年孤独》读后感',
                'content': '《百年孤独》是加西亚·马尔克斯的代表作，讲述了布恩迪亚家族七代人的传奇故事。\n\n这部小说充满了魔幻现实主义色彩，通过一个家族的兴衰，反映了拉丁美洲的历史和文化。\n\n读完全书，我被作者的叙事能力和想象力所震撼，这是一部值得反复阅读的经典之作。',
                'category': reading,
                'tags': ['读书', '读后感', '经典文学']
            },
            {
                'title': '日本旅行攻略',
                'content': '日本是一个充满魅力的国家，有着独特的文化和风景。\n\n推荐景点：\n1. 东京：富士山、浅草寺、涩谷\n2. 京都：金阁寺、清水寺、岚山\n3. 大阪：大阪城、环球影城\n\n最佳旅行时间是春季（樱花季）和秋季（红叶季）。',
                'category': travel,
                'tags': ['旅行', '日本', '攻略']
            },
            {
                'title': '人工智能的发展前景',
                'content': '人工智能是当今科技领域的热门话题，正在各个行业产生深远的影响。\n\n随着技术的不断进步，人工智能将在医疗、教育、交通等领域发挥越来越重要的作用。\n\n然而，人工智能也带来了一些挑战，如就业问题、隐私问题等，需要我们认真思考和应对。',
                'category': tech,
                'tags': ['人工智能', '科技', '未来']
            }
        ]
        
        # 生成更多文章
        # 技术类文章
        tech_articles = [
            {'title': 'Python 装饰器的深入理解', 'content': '装饰器是 Python 中一种强大的特性，它允许我们在不修改原函数代码的情况下，对函数的行为进行增强。\n\n装饰器本质上是一个返回函数的函数，它接收一个函数作为参数，并返回一个新的函数。\n\n通过装饰器，我们可以实现日志记录、性能测试、权限验证等功能，使代码更加模块化和可维护。\n\n本文将深入探讨装饰器的工作原理，并通过实例展示如何创建和使用装饰器。'},
            {'title': 'Flask 蓝图的使用方法', 'content': 'Flask 蓝图是一种组织 Flask 应用的方式，它允许我们将应用分解为多个可重用的模块。\n\n通过蓝图，我们可以将路由、模板和静态文件组织到不同的模块中，使代码结构更加清晰。\n\n本文将介绍 Flask 蓝图的基本概念和使用方法，并通过实例展示如何在大型应用中使用蓝图。'},
            {'title': 'SQLAlchemy  ORM 最佳实践', 'content': 'SQLAlchemy 是 Python 中最流行的 ORM 库之一，它提供了一种面向对象的方式来操作数据库。\n\n本文将介绍 SQLAlchemy 的基本概念和使用方法，包括模型定义、查询构建、关系映射等。\n\n同时，本文还将分享一些 SQLAlchemy 的最佳实践，帮助你编写更加高效和可维护的数据库代码。'},
            {'title': 'JavaScript 异步编程详解', 'content': '异步编程是 JavaScript 中的一个重要概念，它允许我们在不阻塞主线程的情况下执行耗时操作。\n\n本文将介绍 JavaScript 异步编程的发展历程，从回调函数到 Promise，再到 async/await。\n\n通过实例展示如何使用这些异步编程技术，以及如何处理异步操作中的错误和异常。'},
            {'title': 'React Hooks 完全指南', 'content': 'React Hooks 是 React 16.8 引入的新特性，它允许我们在函数组件中使用状态和其他 React 特性。\n\n本文将介绍 React Hooks 的基本概念和使用方法，包括 useState、useEffect、useContext 等常用 Hooks。\n\n通过实例展示如何使用 Hooks 来构建更加简洁和可维护的 React 组件。'},
            {'title': 'Docker 容器化实践', 'content': 'Docker 是一种容器化技术，它允许我们将应用及其依赖打包到一个轻量级的容器中。\n\n本文将介绍 Docker 的基本概念和使用方法，包括镜像构建、容器管理、网络配置等。\n\n通过实例展示如何使用 Docker 来部署和管理应用，以及如何与 Docker Compose 配合使用。'},
            {'title': 'Git 高级技巧', 'content': 'Git 是目前最流行的版本控制系统之一，它提供了强大的分支管理和代码协作功能。\n\n本文将介绍 Git 的一些高级技巧，包括交互式 rebase、 stash、 bisect 等命令的使用方法。\n\n通过实例展示如何使用这些技巧来解决日常开发中遇到的问题，提高代码管理的效率。'},
            {'title': 'RESTful API 设计最佳实践', 'content': 'RESTful API 是一种基于 HTTP 协议的 API 设计风格，它强调资源的概念和无状态的特性。\n\n本文将介绍 RESTful API 的基本概念和设计原则，包括资源命名、HTTP 方法使用、状态码设计等。\n\n通过实例展示如何设计和实现一个符合 RESTful 规范的 API，以及如何使用工具来测试和文档化 API。'},
            {'title': '机器学习入门指南', 'content': '机器学习是人工智能的一个重要分支，它允许计算机从数据中学习规律并做出预测。\n\n本文将介绍机器学习的基本概念和工作原理，包括监督学习、无监督学习、强化学习等。\n\n通过实例展示如何使用 Python 和 scikit-learn 库来实现简单的机器学习模型，以及如何评估模型的性能。'},
            {'title': '前端性能优化技巧', 'content': '前端性能是影响用户体验的重要因素，它直接关系到页面的加载速度和交互响应速度。\n\n本文将介绍前端性能优化的基本原理和常用技巧，包括资源压缩、代码分割、缓存策略等。\n\n通过实例展示如何使用工具来分析和优化前端性能，以及如何建立性能监控体系。'}
        ]
        
        # 生活类文章
        life_articles = [
            {'title': '如何保持工作与生活的平衡', 'content': '在当今快节奏的社会中，保持工作与生活的平衡变得越来越重要。\n\n本文将分享一些实用的方法和技巧，帮助你在忙碌的工作中找到生活的平衡点。\n\n包括时间管理、优先级设置、放松技巧等方面的建议，以及如何在工作和生活之间建立健康的边界。'},
            {'title': '健康饮食的重要性', 'content': '健康的饮食是保持身体健康的基础，它直接影响我们的能量水平、情绪状态和长期健康。\n\n本文将介绍健康饮食的基本原则，包括均衡营养、适量摄入、多样化选择等。\n\n同时，本文还将分享一些实用的健康饮食技巧，帮助你在日常生活中做出更健康的食物选择。'},
            {'title': '有效的时间管理方法', 'content': '时间是我们最宝贵的资源之一，有效的时间管理可以帮助我们提高效率，减少压力，实现更多的目标。\n\n本文将介绍一些有效的时间管理方法，包括四象限法则、番茄工作法、任务清单等。\n\n通过实例展示如何制定合理的计划，如何避免时间浪费，以及如何在有限的时间内完成更多的任务。'},
            {'title': '如何培养良好的阅读习惯', 'content': '阅读是获取知识、拓展视野的重要途径，良好的阅读习惯可以帮助我们不断学习和成长。\n\n本文将介绍如何培养良好的阅读习惯，包括选择适合的书籍、制定阅读计划、提高阅读效率等。\n\n同时，本文还将分享一些阅读技巧，帮助你更好地理解和记忆所读内容。'},
            {'title': '家居收纳技巧', 'content': '一个整洁有序的家居环境可以提高生活质量，减少压力，让我们更加放松和舒适。\n\n本文将分享一些实用的家居收纳技巧，包括空间利用、分类整理、收纳工具选择等。\n\n通过实例展示如何根据不同的空间和物品类型，选择合适的收纳方法，打造一个整洁有序的家。'}
        ]
        
        # 读书类文章
        reading_articles = [
            {'title': '《人类简史》读后感', 'content': '《人类简史》是尤瓦尔·赫拉利的代表作，它从宏观的角度讲述了人类从石器时代到21世纪的发展历程。\n\n本文将分享我阅读《人类简史》的心得体会，包括书中的主要观点、对历史的新认识、以及对未来的思考。\n\n通过分析书中的核心概念，探讨人类发展的规律和趋势，以及我们应该如何面对未来的挑战。'},
            {'title': '《百年孤独》的魔幻现实主义', 'content': '《百年孤独》是加西亚·马尔克斯的代表作，它以魔幻现实主义的手法讲述了布恩迪亚家族七代人的传奇故事。\n\n本文将分析《百年孤独》中的魔幻现实主义元素，包括超自然现象、循环时间、象征符号等。\n\n通过解读书中的关键情节和人物，探讨魔幻现实主义的艺术魅力和深刻内涵。'},
            {'title': '《活着》的生命意义', 'content': '《活着》是余华的代表作，它讲述了一个人在经历了种种苦难后依然坚强活着的故事。\n\n本文将分析《活着》中的生命意义，包括苦难与希望、亲情与责任、生存与尊严等主题。\n\n通过解读主人公福贵的人生经历，探讨生命的价值和意义，以及我们应该如何面对生活中的困难和挫折。'},
            {'title': '《三体》的科幻世界', 'content': '《三体》是刘慈欣的代表作，它构建了一个宏大的科幻世界，探讨了人类与外星文明的接触和冲突。\n\n本文将分析《三体》中的科幻元素，包括三体文明、黑暗森林法则、面壁计划等。\n\n通过解读书中的科学概念和哲学思考，探讨人类文明的未来和宇宙的奥秘。'},
            {'title': '《小王子》的哲理', 'content': '《小王子》是安托万·德·圣-埃克苏佩里的代表作，它通过一个小王子的星际之旅，传递了深刻的人生哲理。\n\n本文将分析《小王子》中的哲理，包括友谊、爱情、责任、成长等主题。\n\n通过解读书中的对话和情节，探讨童心的珍贵和成人世界的荒谬，以及我们应该如何保持内心的纯真。'}
        ]
        
        # 旅行类文章
        travel_articles = [
            {'title': '日本京都之旅', 'content': '京都是日本的古都，它保存了大量的历史文化遗产，是一个充满魅力的旅游目的地。\n\n本文将分享我的京都之旅，包括必访的景点、美食推荐、交通攻略等。\n\n通过详细的行程安排和实用的旅行建议，帮助你规划一次完美的京都之旅。'},
            {'title': '意大利托斯卡纳地区的乡村风光', 'content': '托斯卡纳是意大利中部的一个地区，它以美丽的乡村风光、丰富的艺术遗产和美味的葡萄酒而闻名。\n\n本文将分享我的托斯卡纳之旅，包括锡耶纳、圣吉米尼亚诺、基安蒂等地方的特色。\n\n通过详细的景点介绍和旅行建议，帮助你体验托斯卡纳的独特魅力。'},
            {'title': '云南大理的风花雪月', 'content': '大理是云南省的一个历史文化名城，它以风花雪月四大景观和白族文化而闻名。\n\n本文将分享我的大理之旅，包括苍山洱海、古城古镇、民族风情等。\n\n通过详细的行程安排和实用的旅行建议，帮助你体验大理的独特魅力。'},
            {'title': '法国普罗旺斯的薰衣草田', 'content': '普罗旺斯是法国东南部的一个地区，它以薰衣草田、向日葵田和中世纪小镇而闻名。\n\n本文将分享我的普罗旺斯之旅，包括阿维尼翁、圣十字湖、瓦朗索勒等地方的特色。\n\n通过详细的景点介绍和旅行建议，帮助你体验普罗旺斯的浪漫风情。'},
            {'title': '新西兰南岛的自然奇观', 'content': '新西兰南岛以其壮丽的自然景观而闻名，包括山脉、湖泊、冰川、海滩等。\n\n本文将分享我的新西兰南岛之旅，包括皇后镇、米尔福德峡湾、蒂卡普湖等地方的特色。\n\n通过详细的行程安排和实用的旅行建议，帮助你体验新西兰南岛的自然奇观。'}
        ]
        
        # 生成更多文章
        article_index = 6
        # 添加技术类文章
        for i, article in enumerate(tech_articles):
            articles.append({
                'title': article['title'],
                'content': article['content'],
                'category': tech,
                'tags': ['技术', '编程', '科技']
            })
            article_index += 1
        
        # 添加生活类文章
        for i, article in enumerate(life_articles):
            articles.append({
                'title': article['title'],
                'content': article['content'],
                'category': life,
                'tags': ['生活', '日常', '经验']
            })
            article_index += 1
        
        # 添加读书类文章
        for i, article in enumerate(reading_articles):
            articles.append({
                'title': article['title'],
                'content': article['content'],
                'category': reading,
                'tags': ['读书', '阅读', '文学']
            })
            article_index += 1
        
        # 添加旅行类文章
        for i, article in enumerate(travel_articles):
            articles.append({
                'title': article['title'],
                'content': article['content'],
                'category': travel,
                'tags': ['旅行', '游记', '探索']
            })
            article_index += 1
        
        # 生成剩余的文章
        while article_index <= 50:
            # 循环使用分类
            categories = [tech, life, reading, travel, tech]
            category = categories[(article_index - 1) % 5]
            
            # 生成文章标题和内容
            article_title = f'深度解析：{article_index - 5}个实用技巧'
            article_content = f'这是一篇关于实用技巧的深度解析文章。\n\n'
            article_content += '在日常生活和工作中，我们经常会遇到各种挑战和问题，掌握一些实用的技巧可以帮助我们更高效地解决这些问题。\n\n'
            article_content += '本文将分享多个实用技巧，包括时间管理、学习方法、工作效率、生活品质等方面。\n\n'
            article_content += '通过学习和应用这些技巧，你可以提高自己的能力和生活质量，更好地应对各种挑战。'
            
            # 生成标签
            tags = []
            if category == tech:
                tags = ['技术', '编程', '科技']
            elif category == life:
                tags = ['生活', '日常', '经验']
            elif category == reading:
                tags = ['读书', '阅读', '文学']
            elif category == travel:
                tags = ['旅行', '游记', '探索']
            
            # 添加到文章列表
            articles.append({
                'title': article_title,
                'content': article_content,
                'category': category,
                'tags': tags
            })
            article_index += 1
        
        # 添加文章到数据库
        for article_data in articles:
            article = Article(
                title=article_data['title'],
                content=article_data['content'],
                summary=generate_summary(article_data['content']),
                category_id=article_data['category'].id,
                user_id=admin.id
            )
            db.session.add(article)
            db.session.flush()
            
            # 添加标签
            for tag_name in article_data['tags']:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()
                article_tag = ArticleTag(article_id=article.id, tag_id=tag.id)
                db.session.add(article_tag)
        
        db.session.commit()
        
        # 清除缓存
        clear_cache('*')

# 路由
@app.route('/')
def index():
    # 获取搜索参数
    search_query = request.args.get('q')
    
    # 尝试从缓存获取
    if not redis_client or search_query:
        # Redis不可用或有搜索参数时，直接查询
        return _get_index_data(search_query)
    
    cache_key = f'index:all'
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            try:
                data = json.loads(cached_data)
                return render_template('index.html', **data)
            except:
                pass
    except:
        pass
    
    # 缓存未命中，获取数据
    articles = Article.query.filter_by(status='published').order_by(Article.created_at.desc()).all()
    
    # 获取热门标签
    tags = Tag.query.all()
    # 按使用频率排序（简单实现）
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]  # 只显示前10个热门标签
    
    categories = Category.query.all()
    
    # 准备缓存数据
    try:
        cache_data = {
            'articles': [{
                'id': a.id,
                'title': a.title,
                'summary': a.summary,
                'created_at': str(a.created_at),
                'views': a.views,
                'category': {'id': a.category.id, 'name': a.category.name},
                'author': {'id': a.author.id, 'username': a.author.username},
                'tags': [{'id': t.id, 'name': t.name} for t in a.tags]
            } for a in articles],
            'categories': [{'id': c.id, 'name': c.name} for c in categories],
            'tags': [{'id': t.id, 'name': t.name} for t in tags],
            'search_query': search_query
        }
        redis_client.setex(cache_key, 300, json.dumps(cache_data))
    except:
        pass
    
    return render_template('index.html', articles=articles, categories=categories, tags=tags, search_query=search_query)

def _get_index_data(search_query):
    """获取首页数据"""
    if search_query:
        # 搜索文章
        articles = Article.query.filter(
            (Article.title.like(f'%{search_query}%') | 
             Article.content.like(f'%{search_query}%')) &
            (Article.status == 'published')
        ).order_by(Article.created_at.desc()).all()
    else:
        # 显示所有已发布文章
        articles = Article.query.filter_by(status='published').order_by(Article.created_at.desc()).all()
    
    # 获取热门标签
    tags = Tag.query.all()
    # 按使用频率排序（简单实现）
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]  # 只显示前10个热门标签
    
    categories = Category.query.all()
    return render_template('index.html', articles=articles, categories=categories, tags=tags, search_query=search_query)

@app.route('/article/<int:id>')
def article(id):
    # 尝试从缓存获取
    if redis_client and ('user_id' not in session):
        cache_key = f'article:{id}'
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                try:
                    data = json.loads(cached_data)
                    # 异步增加阅读次数
                    try:
                        redis_client.incr(f'article_views:{id}')
                    except:
                        pass
                    return render_template('article.html', **data)
                except:
                    pass
        except:
            pass
    
    article = Article.query.get_or_404(id)
    # 只显示已发布的文章
    if article.status != 'published' and ('user_id' not in session or article.user_id != session['user_id']):
        flash('文章不存在或无权限访问', 'error')
        return redirect(url_for('index'))
    # 增加阅读次数
    article.views += 1
    db.session.commit()
    # 获取评论
    comments = Comment.query.filter_by(article_id=id, parent_id=None).order_by(Comment.created_at.desc()).all()
    categories = Category.query.all()
    # 获取热门标签
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]
    
    # 缓存结果（仅缓存已发布的文章）
    if redis_client and article.status == 'published':
        try:
            cache_data = {
                'article': {
                    'id': article.id,
                    'title': article.title,
                    'content': article.content,
                    'summary': article.summary,
                    'created_at': str(article.created_at),
                    'views': article.views,
                    'category': {'id': article.category.id, 'name': article.category.name},
                    'author': {'id': article.author.id, 'username': article.author.username},
                    'tags': [{'id': t.id, 'name': t.name} for t in article.tags]
                },
                'categories': [{'id': c.id, 'name': c.name} for c in categories],
                'tags': [{'id': t.id, 'name': t.name} for t in tags],
                'comments': [{
                    'id': c.id,
                    'content': c.content,
                    'created_at': str(c.created_at),
                    'author': {'id': c.author.id, 'username': c.author.username},
                    'replies': [{
                        'id': r.id,
                        'content': r.content,
                        'created_at': str(r.created_at),
                        'author': {'id': r.author.id, 'username': r.author.username}
                    } for r in c.replies]
                } for c in comments]
            }
            redis_client.setex(f'article:{id}', 600, json.dumps(cache_data))
        except:
            pass
    
    return render_template('article.html', article=article, categories=categories, tags=tags, comments=comments)

@app.route('/category/<int:id>')
def category(id):
    category = Category.query.get_or_404(id)
    articles = Article.query.filter_by(category_id=id, status='published').order_by(Article.created_at.desc()).all()
    categories = Category.query.all()
    # 获取热门标签
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]
    return render_template('category.html', category=category, articles=articles, categories=categories, tags=tags)

# 标签页
@app.route('/tag/<int:id>')
def tag(id):
    tag = Tag.query.get_or_404(id)
    # 只显示已发布的文章
    articles = [article for article in tag.articles if article.status == 'published']
    articles.sort(key=lambda a: a.created_at, reverse=True)
    categories = Category.query.all()
    # 获取热门标签
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]
    return render_template('tag.html', tag=tag, articles=articles, categories=categories, tags=tags)

# 个人资料页
@app.route('/user/<int:id>')
def user_profile(id):
    user = User.query.get_or_404(id)
    # 只显示已发布的文章
    articles = Article.query.filter_by(user_id=id, status='published').order_by(Article.created_at.desc()).all()
    categories = Category.query.all()
    # 获取热门标签
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]
    return render_template('user_profile.html', user=user, articles=articles, categories=categories, tags=tags)

# 评论提交
@app.route('/comment/<int:article_id>', methods=['POST'])
@login_required
def add_comment(article_id):
    article = Article.query.get_or_404(article_id)
    content = request.form['content']
    parent_id = request.form.get('parent_id')
    
    comment = Comment(
        content=content,
        user_id=session['user_id'],
        article_id=article_id,
        parent_id=parent_id if parent_id else None
    )
    db.session.add(comment)
    db.session.commit()
    
    flash('评论成功', 'success')
    return redirect(url_for('article', id=article_id))

# 草稿管理
@app.route('/drafts')
@login_required
def drafts():
    articles = Article.query.filter_by(user_id=session['user_id'], status='draft').order_by(Article.updated_at.desc()).all()
    categories = Category.query.all()
    # 获取热门标签
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(t.articles), reverse=True)
    tags = tags[:10]
    return render_template('drafts.html', articles=articles, categories=categories, tags=tags)

# RSS 订阅
@app.route('/rss')
def rss():
    articles = Article.query.filter_by(status='published').order_by(Article.created_at.desc()).limit(10).all()
    
    # 生成 RSS XML
    rss_root = ET.Element('rss')
    rss_root.set('version', '2.0')
    
    channel = ET.SubElement(rss_root, 'channel')
    ET.SubElement(channel, 'title').text = '个人博客系统'
    ET.SubElement(channel, 'link').text = 'http://localhost:8080'
    ET.SubElement(channel, 'description').text = '个人博客系统的最新文章'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    for article in articles:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = article.title
        ET.SubElement(item, 'link').text = f'http://localhost:8080/article/{article.id}'
        ET.SubElement(item, 'description').text = article.summary
        ET.SubElement(item, 'pubDate').text = article.created_at.strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # 生成响应
    xml_str = ET.tostring(rss_root, encoding='utf-8', xml_declaration=True)
    response = make_response(xml_str)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response

# 后台管理面板
@app.route('/admin')
@admin_required
def admin_dashboard():
    # 统计数据
    total_articles = Article.query.count()
    total_users = User.query.count()
    total_comments = Comment.query.count()
    total_tags = Tag.query.count()
    
    # 最新文章
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(5).all()
    
    # 最新评论
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         total_articles=total_articles,
                         total_users=total_users,
                         total_comments=total_comments,
                         total_tags=total_tags,
                         recent_articles=recent_articles,
                         recent_comments=recent_comments)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('登录成功', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    categories = Category.query.all()
    return render_template('login.html', categories=categories)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 验证
        if len(password) < 6:
            flash('密码至少6位', 'error')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('两次密码不一致', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'error')
            return redirect(url_for('register'))
        
        # 创建用户
        password_hash = generate_password_hash(password)
        user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        
        # 自动登录
        session['user_id'] = user.id
        session['username'] = user.username
        flash('注册成功', 'success')
        return redirect(url_for('index'))
    categories = Category.query.all()
    return render_template('register.html', categories=categories)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('已退出登录', 'success')
    return redirect(url_for('index'))

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    categories = Category.query.all()
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category_id = request.form['category']
        tags_str = request.form['tags']
        status = request.form.get('status', 'published')
        
        # 生成摘要
        summary = generate_summary(content)
        
        # 创建文章
        article = Article(
            title=title,
            content=content,
            summary=summary,
            category_id=category_id,
            user_id=session['user_id'],
            status=status
        )
        db.session.add(article)
        db.session.flush()  # 获取文章ID
        
        # 处理标签
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',')]
            for tag_name in tag_names:
                if tag_name:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                        db.session.flush()
                    article_tag = ArticleTag(article_id=article.id, tag_id=tag.id)
                    db.session.add(article_tag)
        
        db.session.commit()
        if status == 'published':
            flash('文章发布成功', 'success')
            return redirect(url_for('article', id=article.id))
        else:
            flash('草稿保存成功', 'success')
            return redirect(url_for('drafts'))
    return render_template('create_article.html', categories=categories)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    article = Article.query.get_or_404(id)
    if article.user_id != session['user_id']:
        flash('无权限编辑此文章', 'error')
        return redirect(url_for('article', id=id))
    
    categories = Category.query.all()
    if request.method == 'POST':
        article.title = request.form['title']
        article.content = request.form['content']
        article.category_id = request.form['category']
        tags_str = request.form['tags']
        status = request.form.get('status', 'published')
        
        # 更新摘要
        article.summary = generate_summary(article.content)
        article.status = status
        
        # 清除旧标签
        ArticleTag.query.filter_by(article_id=id).delete()
        
        # 处理新标签
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',')]
            for tag_name in tag_names:
                if tag_name:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                        db.session.flush()
                    article_tag = ArticleTag(article_id=article.id, tag_id=tag.id)
                    db.session.add(article_tag)
        
        db.session.commit()
        if status == 'published':
            flash('文章更新成功', 'success')
            return redirect(url_for('article', id=article.id))
        else:
            flash('草稿保存成功', 'success')
            return redirect(url_for('drafts'))
    
    # 准备标签字符串
    tag_names = [tag.name for tag in article.tags]
    tags_str = ','.join(tag_names)
    
    return render_template('edit_article.html', article=article, categories=categories, tags_str=tags_str)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    article = Article.query.get_or_404(id)
    if article.user_id != session['user_id']:
        flash('无权限删除此文章', 'error')
        return redirect(url_for('article', id=id))
    
    # 删除相关标签关联
    ArticleTag.query.filter_by(article_id=id).delete()
    # 删除文章
    db.session.delete(article)
    db.session.commit()
    
    flash('文章删除成功', 'success')
    return redirect(url_for('index'))

# 错误处理
@app.errorhandler(404)
def page_not_found(e):
    categories = Category.query.all()
    return render_template('404.html', categories=categories), 404

@app.errorhandler(500)
def internal_server_error(e):
    categories = Category.query.all()
    return render_template('500.html', categories=categories), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
