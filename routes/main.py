from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload
from sqlalchemy import func, select
from models import db, Article, Category, Tag, article_tag
from utils.cache import get_cache, set_cache
from utils.security import rate_limit, log_security_event

main_bp = Blueprint('main', __name__)
ARTICLES_PER_PAGE = 10

@main_bp.route('/')
@rate_limit(limit=30, per_seconds=60)
def index():
    search_query = request.args.get('q')
    page = request.args.get('page', 1, type=int)
    
    if search_query:
        return _search_articles(search_query)
    
    cache_key = f'index:page:{page}'
    cached_data = get_cache(cache_key)
    
    if cached_data:
        return render_template('index.html', **cached_data)
    
    pagination = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).filter_by(status='published').order_by(Article.created_at.desc()).paginate(
        page=page, per_page=ARTICLES_PER_PAGE, error_out=False
    )
    
    # 使用聚合查询一次性获取标签文章数量，避免N+1问题
    tag_counts = db.session.execute(
        select(
            Tag,
            func.count(article_tag.c.article_id).label('article_count')
        )
        .outerjoin(article_tag, Tag.id == article_tag.c.tag_id)
        .group_by(Tag.id)
        .order_by(func.count(article_tag.c.article_id).desc())
        .limit(10)
    ).all()
    
    tags = [tag for tag, _ in tag_counts]
    categories = Category.query.all()
    
    data = {
        'articles': pagination.items,
        'pagination': pagination,
        'categories': categories,
        'tags': tags,
        'search_query': None
    }
    
    set_cache(cache_key, {
        'articles': [a.to_dict() for a in pagination.items],
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num
        },
        'categories': [c.to_dict() for c in categories],
        'tags': [t.to_dict() for t in tags],
        'search_query': None
    }, expire=300)
    
    return render_template('index.html', **data)

@rate_limit(limit=15, per_seconds=60)
def _search_articles(query):
    # 验证搜索输入
    if not query or len(query.strip()) == 0 or len(query) > 100:
        log_security_event('invalid_search', 'Invalid search query length')
        return render_template('index.html', 
                             articles=[], 
                             categories=Category.query.all(), 
                             tags=[], 
                             search_query='',
                             pagination=None)
    
    log_security_event('search', f'Query: {query[:50]}')
    
    articles = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).filter(
        (Article.title.like(f'%{query}%') | 
         Article.content.like(f'%{query}%')) &
        (Article.status == 'published')
    ).order_by(Article.created_at.desc()).all()
    
    # 使用聚合查询获取热门标签
    tag_counts = db.session.execute(
        select(
            Tag,
            func.count(article_tag.c.article_id).label('article_count')
        )
        .outerjoin(article_tag, Tag.id == article_tag.c.tag_id)
        .group_by(Tag.id)
        .order_by(func.count(article_tag.c.article_id).desc())
        .limit(10)
    ).all()
    
    tags = [tag for tag, _ in tag_counts]
    categories = Category.query.all()
    
    return render_template('index.html', 
                         articles=articles, 
                         categories=categories, 
                         tags=tags, 
                         search_query=query,
                         pagination=None)