<<<<<<< HEAD
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy.orm import joinedload
from models import db, Article, Category, Tag, Comment, User, Like
from utils.decorators import login_required
from utils import generate_summary, escape_text
from utils.cache import get_cache, set_cache, delete_cache_pattern
from utils.security import (
    rate_limit, 
    validate_article_title, 
    validate_article_content,
    validate_comment_content,
    log_security_event,
    clean_html
)

article_bp = Blueprint('article', __name__)
ARTICLES_PER_PAGE = 10

@article_bp.route('/article/<int:id>')
def article_detail(id):
    cache_key = f'article:{id}'
    cached_data = None
    
    if 'user_id' not in session:
        cached_data = get_cache(cache_key)
        if cached_data:
            return render_template('article.html', **cached_data)
    
    article = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).get_or_404(id)
    
    if article.status != 'published' and ('user_id' not in session or article.user_id != session.get('user_id')):
        flash('文章不存在或无权限访问', 'error')
        return redirect(url_for('main.index'))
    
    article.views += 1
    db.session.commit()
    
    comments = Comment.query.options(
        joinedload(Comment.author)
    ).filter_by(article_id=id, parent_id=None).order_by(Comment.created_at.desc()).all()
    
    categories = Category.query.all()
    
    # 获取本文标签
    article_tags = article.tags
    
    # 获取相似文章（基于相同标签）
    similar_articles = []
    if article_tags:
        tag_ids = [tag.id for tag in article_tags]
        similar_articles = Article.query.options(
            joinedload(Article.author),
            joinedload(Article.category)
        ).filter(
            Article.id != id,
            Article.status == 'published',
            Article.tags.any(Tag.id.in_(tag_ids))
        ).order_by(Article.created_at.desc()).limit(5).all()
    
    data = {
        'article': article,
        'categories': categories,
        'tags': article_tags,
        'comments': comments,
        'similar_articles': similar_articles
    }
    
    if 'user_id' not in session:
        set_cache(cache_key, {
            'article': article.to_dict(),
            'categories': [c.to_dict() for c in categories],
            'tags': [t.to_dict() for t in article_tags],
            'comments': [c.to_dict() for c in comments],
            'similar_articles': [a.to_dict() for a in similar_articles]
        }, expire=600)
    
    return render_template('article.html', **data)

@article_bp.route('/create', methods=['GET', 'POST'])
@login_required
@rate_limit(limit=10, per_seconds=60)  # 限制每分钟10次创建
def create():
    categories = Category.query.all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '')
        category_id = request.form.get('category')
        tags_str = request.form.get('tags', '')
        status = request.form.get('status', 'published')
        
        # 验证输入
        is_valid, error_msg = validate_article_title(title)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('create_article.html', categories=categories)
        
        is_valid, error_msg = validate_article_content(content)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('create_article.html', categories=categories)
        
        if not category_id:
            flash('请选择分类', 'error')
            return render_template('create_article.html', categories=categories)
        
        # 清理输入防止XSS
        title = escape_text(title)
        summary = generate_summary(content)
        
        article = Article(
            title=title,
            content=content,
            summary=summary,
            category_id=int(category_id),
            user_id=session['user_id'],
            status=status
        )
        
        db.session.add(article)
        db.session.flush()
        
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()
                article.tags.append(tag)
        
        db.session.commit()
        delete_cache_pattern('index:*')
        
        if status == 'published':
            flash('文章发布成功', 'success')
            return redirect(url_for('article.article_detail', id=article.id))
        else:
            flash('草稿保存成功', 'success')
            return redirect(url_for('article.drafts'))
    
    return render_template('create_article.html', categories=categories)

@article_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    article = Article.query.get_or_404(id)
    
    if article.user_id != session['user_id']:
        flash('无权限编辑此文章', 'error')
        return redirect(url_for('article.article_detail', id=id))
    
    categories = Category.query.all()
    tags_str = ','.join([tag.name for tag in article.tags])
    
    if request.method == 'POST':
        article.title = escape_text(request.form.get('title', '').strip())
        article.content = request.form.get('content', '')
        article.category_id = int(request.form.get('category', article.category_id))
        article.status = request.form.get('status', 'published')
        
        tags_str = request.form.get('tags', '')
        article.tags.clear()
        
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()
                article.tags.append(tag)
        
        article.summary = generate_summary(article.content)
        
        db.session.commit()
        delete_cache_pattern('index:*')
        delete_cache_pattern(f'article:{id}')
        
        if article.status == 'published':
            flash('文章更新成功', 'success')
            return redirect(url_for('article.article_detail', id=article.id))
        else:
            flash('草稿保存成功', 'success')
            return redirect(url_for('article.drafts'))
    
    return render_template('edit_article.html', 
                         article=article, 
                         categories=categories,
                         tags_str=tags_str)

@article_bp.route('/delete/<int:id>')
@login_required
def delete(id):
    article = Article.query.get_or_404(id)
    
    if article.user_id != session['user_id']:
        flash('无权限删除此文章', 'error')
        return redirect(url_for('article.article_detail', id=id))
    
    db.session.delete(article)
    db.session.commit()
    delete_cache_pattern('index:*')
    delete_cache_pattern(f'article:{id}')
    
    flash('文章删除成功', 'success')
    return redirect(url_for('main.index'))

@article_bp.route('/category/<int:id>')
def category(id):
    category = Category.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    
    pagination = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).filter_by(category_id=id, status='published').order_by(Article.created_at.desc()).paginate(
        page=page, per_page=ARTICLES_PER_PAGE, error_out=False
    )
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('category.html', 
                         category=category,
                         articles=pagination.items,
                         pagination=pagination,
                         categories=categories,
                         tags=tags)

@article_bp.route('/tag/<int:id>')
def tag(id):
    tag = Tag.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    
    articles = [a for a in tag.articles if a.status == 'published']
    articles.sort(key=lambda a: a.created_at, reverse=True)
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('tag.html', 
                         tag=tag,
                         articles=articles,
                         categories=categories,
                         tags=tags)

@article_bp.route('/user/<int:id>')
def user_profile(id):
    user = db.get_or_404(User, id)
    page = request.args.get('page', 1, type=int)
    
    pagination = Article.query.options(
        joinedload(Article.category)
    ).filter_by(user_id=id, status='published').order_by(Article.created_at.desc()).paginate(
        page=page, per_page=ARTICLES_PER_PAGE, error_out=False
    )
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('user_profile.html', 
                         user=user,
                         articles=pagination.items,
                         pagination=pagination,
                         categories=categories,
                         tags=tags)

@article_bp.route('/drafts')
@login_required
def drafts():
    articles = Article.query.options(
        joinedload(Article.category)
    ).filter_by(user_id=session['user_id'], status='draft').order_by(Article.updated_at.desc()).all()
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('drafts.html', 
                         articles=articles,
                         categories=categories,
                         tags=tags)

@article_bp.route('/comment/<int:article_id>', methods=['POST'])
@login_required
@rate_limit(limit=20, per_seconds=60)  # 限制每分钟20条评论
def add_comment(article_id):
    article = Article.query.get_or_404(article_id)
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id')
    
    # 验证输入
    is_valid, error_msg = validate_comment_content(content)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('article.article_detail', id=article_id))
    
    # 清理内容防止XSS
    content = clean_html(content)
    
    comment = Comment(
        content=content,
        user_id=session['user_id'],
        article_id=article_id,
        parent_id=int(parent_id) if parent_id else None
    )
    
    db.session.add(comment)
    db.session.commit()
    delete_cache_pattern(f'article:{article_id}')
    
    log_security_event('COMMENT_ADDED', f'Article: {article_id}')
    flash('评论成功', 'success')
    return redirect(url_for('article.article_detail', id=article_id))

@article_bp.route('/like/<int:article_id>', methods=['POST'])
@login_required
def like_article(article_id):
    article = Article.query.get_or_404(article_id)
    user_id = session['user_id']
    
    existing_like = Like.query.filter_by(user_id=user_id, article_id=article_id).first()
    
    if existing_like:
        if existing_like.type == 'like':
            # 取消点赞
            db.session.delete(existing_like)
            article.likes = max(0, article.likes - 1)
        else:
            # 从差评改为点赞
            existing_like.type = 'like'
            article.dislikes = max(0, article.dislikes - 1)
            article.likes += 1
    else:
        # 新增点赞
        like = Like(user_id=user_id, article_id=article_id, type='like')
        db.session.add(like)
        article.likes += 1
    
    db.session.commit()
    delete_cache_pattern(f'article:{article_id}')
    
    return {'status': 'success', 'likes': article.likes, 'dislikes': article.dislikes}

@article_bp.route('/dislike/<int:article_id>', methods=['POST'])
@login_required
def dislike_article(article_id):
    article = Article.query.get_or_404(article_id)
    user_id = session['user_id']
    
    existing_like = Like.query.filter_by(user_id=user_id, article_id=article_id).first()
    
    if existing_like:
        if existing_like.type == 'dislike':
            # 取消差评
            db.session.delete(existing_like)
            article.dislikes = max(0, article.dislikes - 1)
        else:
            # 从点赞改为差评
            existing_like.type = 'dislike'
            article.likes = max(0, article.likes - 1)
            article.dislikes += 1
    else:
        # 新增差评
        like = Like(user_id=user_id, article_id=article_id, type='dislike')
        db.session.add(like)
        article.dislikes += 1
    
    db.session.commit()
    delete_cache_pattern(f'article:{article_id}')
    
    return {'status': 'success', 'likes': article.likes, 'dislikes': article.dislikes}#   ;NR/e�O9e 
=======
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy.orm import joinedload
from models import db, Article, Category, Tag, Comment, User, Like
from utils.decorators import login_required
from utils import generate_summary, escape_text
from utils.cache import get_cache, set_cache, delete_cache_pattern
from utils.security import (
    rate_limit, 
    validate_article_title, 
    validate_article_content,
    validate_comment_content,
    log_security_event,
    clean_html
)

article_bp = Blueprint('article', __name__)
ARTICLES_PER_PAGE = 10

@article_bp.route('/article/<int:id>')
def article_detail(id):
    cache_key = f'article:{id}'
    cached_data = None
    
    if 'user_id' not in session:
        cached_data = get_cache(cache_key)
        if cached_data:
            return render_template('article.html', **cached_data)
    
    article = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).get_or_404(id)
    
    if article.status != 'published' and ('user_id' not in session or article.user_id != session.get('user_id')):
        flash('文章不存在或无权限访问', 'error')
        return redirect(url_for('main.index'))
    
    article.views += 1
    db.session.commit()
    
    comments = Comment.query.options(
        joinedload(Comment.author)
    ).filter_by(article_id=id, parent_id=None).order_by(Comment.created_at.desc()).all()
    
    categories = Category.query.all()
    
    # 获取本文标签
    article_tags = article.tags
    
    # 获取相似文章（基于相同标签）
    similar_articles = []
    if article_tags:
        tag_ids = [tag.id for tag in article_tags]
        similar_articles = Article.query.options(
            joinedload(Article.author),
            joinedload(Article.category)
        ).filter(
            Article.id != id,
            Article.status == 'published',
            Article.tags.any(Tag.id.in_(tag_ids))
        ).order_by(Article.created_at.desc()).limit(5).all()
    
    data = {
        'article': article,
        'categories': categories,
        'tags': article_tags,
        'comments': comments,
        'similar_articles': similar_articles
    }
    
    if 'user_id' not in session:
        set_cache(cache_key, {
            'article': article.to_dict(),
            'categories': [c.to_dict() for c in categories],
            'tags': [t.to_dict() for t in article_tags],
            'comments': [c.to_dict() for c in comments],
            'similar_articles': [a.to_dict() for a in similar_articles]
        }, expire=600)
    
    return render_template('article.html', **data)

@article_bp.route('/create', methods=['GET', 'POST'])
@login_required
@rate_limit(limit=10, per_seconds=60)  # 限制每分钟10次创建
def create():
    categories = Category.query.all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '')
        category_id = request.form.get('category')
        tags_str = request.form.get('tags', '')
        status = request.form.get('status', 'published')
        
        # 验证输入
        is_valid, error_msg = validate_article_title(title)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('create_article.html', categories=categories)
        
        is_valid, error_msg = validate_article_content(content)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('create_article.html', categories=categories)
        
        if not category_id:
            flash('请选择分类', 'error')
            return render_template('create_article.html', categories=categories)
        
        # 清理输入防止XSS
        title = escape_text(title)
        summary = generate_summary(content)
        
        article = Article(
            title=title,
            content=content,
            summary=summary,
            category_id=int(category_id),
            user_id=session['user_id'],
            status=status
        )
        
        db.session.add(article)
        db.session.flush()
        
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()
                article.tags.append(tag)
        
        db.session.commit()
        delete_cache_pattern('index:*')
        
        if status == 'published':
            flash('文章发布成功', 'success')
            return redirect(url_for('article.article_detail', id=article.id))
        else:
            flash('草稿保存成功', 'success')
            return redirect(url_for('article.drafts'))
    
    return render_template('create_article.html', categories=categories)

@article_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    article = Article.query.get_or_404(id)
    
    if article.user_id != session['user_id']:
        flash('无权限编辑此文章', 'error')
        return redirect(url_for('article.article_detail', id=id))
    
    categories = Category.query.all()
    tags_str = ','.join([tag.name for tag in article.tags])
    
    if request.method == 'POST':
        article.title = escape_text(request.form.get('title', '').strip())
        article.content = request.form.get('content', '')
        article.category_id = int(request.form.get('category', article.category_id))
        article.status = request.form.get('status', 'published')
        
        tags_str = request.form.get('tags', '')
        article.tags.clear()
        
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()
                article.tags.append(tag)
        
        article.summary = generate_summary(article.content)
        
        db.session.commit()
        delete_cache_pattern('index:*')
        delete_cache_pattern(f'article:{id}')
        
        if article.status == 'published':
            flash('文章更新成功', 'success')
            return redirect(url_for('article.article_detail', id=article.id))
        else:
            flash('草稿保存成功', 'success')
            return redirect(url_for('article.drafts'))
    
    return render_template('edit_article.html', 
                         article=article, 
                         categories=categories,
                         tags_str=tags_str)

@article_bp.route('/delete/<int:id>')
@login_required
def delete(id):
    article = Article.query.get_or_404(id)
    
    if article.user_id != session['user_id']:
        flash('无权限删除此文章', 'error')
        return redirect(url_for('article.article_detail', id=id))
    
    db.session.delete(article)
    db.session.commit()
    delete_cache_pattern('index:*')
    delete_cache_pattern(f'article:{id}')
    
    flash('文章删除成功', 'success')
    return redirect(url_for('main.index'))

@article_bp.route('/category/<int:id>')
def category(id):
    category = Category.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    
    pagination = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).filter_by(category_id=id, status='published').order_by(Article.created_at.desc()).paginate(
        page=page, per_page=ARTICLES_PER_PAGE, error_out=False
    )
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('category.html', 
                         category=category,
                         articles=pagination.items,
                         pagination=pagination,
                         categories=categories,
                         tags=tags)

@article_bp.route('/tag/<int:id>')
def tag(id):
    tag = Tag.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    
    articles = [a for a in tag.articles if a.status == 'published']
    articles.sort(key=lambda a: a.created_at, reverse=True)
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('tag.html', 
                         tag=tag,
                         articles=articles,
                         categories=categories,
                         tags=tags)

@article_bp.route('/user/<int:id>')
def user_profile(id):
    user = db.get_or_404(User, id)
    page = request.args.get('page', 1, type=int)
    
    pagination = Article.query.options(
        joinedload(Article.category)
    ).filter_by(user_id=id, status='published').order_by(Article.created_at.desc()).paginate(
        page=page, per_page=ARTICLES_PER_PAGE, error_out=False
    )
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('user_profile.html', 
                         user=user,
                         articles=pagination.items,
                         pagination=pagination,
                         categories=categories,
                         tags=tags)

@article_bp.route('/drafts')
@login_required
def drafts():
    articles = Article.query.options(
        joinedload(Article.category)
    ).filter_by(user_id=session['user_id'], status='draft').order_by(Article.updated_at.desc()).all()
    
    categories = Category.query.all()
    
    tags = Tag.query.all()
    tags.sort(key=lambda t: len(list(t.articles)), reverse=True)
    tags = tags[:10]
    
    return render_template('drafts.html', 
                         articles=articles,
                         categories=categories,
                         tags=tags)

@article_bp.route('/comment/<int:article_id>', methods=['POST'])
@login_required
@rate_limit(limit=20, per_seconds=60)  # 限制每分钟20条评论
def add_comment(article_id):
    article = Article.query.get_or_404(article_id)
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id')
    
    # 验证输入
    is_valid, error_msg = validate_comment_content(content)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('article.article_detail', id=article_id))
    
    # 清理内容防止XSS
    content = clean_html(content)
    
    comment = Comment(
        content=content,
        user_id=session['user_id'],
        article_id=article_id,
        parent_id=int(parent_id) if parent_id else None
    )
    
    db.session.add(comment)
    db.session.commit()
    delete_cache_pattern(f'article:{article_id}')
    
    log_security_event('COMMENT_ADDED', f'Article: {article_id}')
    flash('评论成功', 'success')
    return redirect(url_for('article.article_detail', id=article_id))

@article_bp.route('/like/<int:article_id>', methods=['POST'])
@login_required
def like_article(article_id):
    article = Article.query.get_or_404(article_id)
    user_id = session['user_id']
    
    existing_like = Like.query.filter_by(user_id=user_id, article_id=article_id).first()
    
    if existing_like:
        if existing_like.type == 'like':
            # 取消点赞
            db.session.delete(existing_like)
            article.likes = max(0, article.likes - 1)
        else:
            # 从差评改为点赞
            existing_like.type = 'like'
            article.dislikes = max(0, article.dislikes - 1)
            article.likes += 1
    else:
        # 新增点赞
        like = Like(user_id=user_id, article_id=article_id, type='like')
        db.session.add(like)
        article.likes += 1
    
    db.session.commit()
    delete_cache_pattern(f'article:{article_id}')
    
    return {'status': 'success', 'likes': article.likes, 'dislikes': article.dislikes}

@article_bp.route('/dislike/<int:article_id>', methods=['POST'])
@login_required
def dislike_article(article_id):
    article = Article.query.get_or_404(article_id)
    user_id = session['user_id']
    
    existing_like = Like.query.filter_by(user_id=user_id, article_id=article_id).first()
    
    if existing_like:
        if existing_like.type == 'dislike':
            # 取消差评
            db.session.delete(existing_like)
            article.dislikes = max(0, article.dislikes - 1)
        else:
            # 从点赞改为差评
            existing_like.type = 'dislike'
            article.likes = max(0, article.likes - 1)
            article.dislikes += 1
    else:
        # 新增差评
        like = Like(user_id=user_id, article_id=article_id, type='dislike')
        db.session.add(like)
        article.dislikes += 1
    
    db.session.commit()
    delete_cache_pattern(f'article:{article_id}')
    
    return {'status': 'success', 'likes': article.likes, 'dislikes': article.dislikes}#   �e�zd"}�R�� 
>>>>>>> feature/article-search
 