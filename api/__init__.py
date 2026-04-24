from flask import Blueprint, jsonify, request
from models import Article, Category, Tag
from config import Config

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/articles')
def articles_list():
    page = 1
    status = 'published'
    
    query = Article.query.filter_by(status=status)
    pagination = query.order_by(Article.created_at.desc()).paginate(
        page=page, per_page=Config.ARTICLES_PER_PAGE, error_out=False
    )
    
    return jsonify({
        'articles': [article.to_dict() for article in pagination.items],
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'total': pagination.total,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num
        }
    })

@api_bp.route('/articles/<int:id>')
def article_detail(id):
    article = Article.query.get_or_404(id)
    if article.status != 'published':
        return jsonify({'error': '文章不可访问'}), 403
    return jsonify(article.to_dict(include_comments=True))

@api_bp.route('/categories')
def categories_list():
    categories = Category.query.all()
    return jsonify({'categories': [category.to_dict() for category in categories]})

@api_bp.route('/tags')
def tags_list():
    tags = Tag.query.all()
    return jsonify({'tags': [tag.to_dict() for tag in tags]})

@api_bp.route('/search')
def search_articles():
    query_str = request.args.get('q', '')
    if not query_str:
        return jsonify({'articles': []})
    
    articles = Article.query.filter(
        (Article.title.like(f'%{query_str}%') | 
         Article.content.like(f'%{query_str}%')) &
        (Article.status == 'published')
    ).order_by(Article.created_at.desc()).limit(20).all()
    
    return jsonify({'articles': [article.to_dict() for article in articles]})