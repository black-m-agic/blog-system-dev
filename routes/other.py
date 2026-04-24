import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Blueprint, render_template, make_response
from sqlalchemy.orm import joinedload
from models import Article, User, Comment, Tag
from utils.decorators import admin_required

other_bp = Blueprint('other', __name__)

@other_bp.route('/rss')
def rss():
    articles = Article.query.options(
        joinedload(Article.author),
        joinedload(Article.category)
    ).filter_by(status='published').order_by(Article.created_at.desc()).limit(10).all()
    
    rss_root = ET.Element('rss')
    rss_root.set('version', '2.0')
    
    channel = ET.SubElement(rss_root, 'channel')
    ET.SubElement(channel, 'title').text = '个人博客系统'
    ET.SubElement(channel, 'link').text = 'http://localhost:8080'
    ET.SubElement(channel, 'description').text = '个人博客系统的最新文章'
    ET.SubElement(channel, 'lastBuildDate').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    for article in articles:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = article.title
        ET.SubElement(item, 'link').text = f'http://localhost:8080/article/{article.id}'
        ET.SubElement(item, 'description').text = article.summary
        ET.SubElement(item, 'pubDate').text = article.created_at.strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    xml_str = ET.tostring(rss_root, encoding='utf-8', xml_declaration=True)
    response = make_response(xml_str)
    response.headers['Content-Type'] = 'application/rss+xml'
    return response

@other_bp.route('/admin')
@admin_required
def admin_dashboard():
    total_articles = Article.query.count()
    total_users = User.query.count()
    total_comments = Comment.query.count()
    total_tags = Tag.query.count()
    
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(5).all()
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         total_articles=total_articles,
                         total_users=total_users,
                         total_comments=total_comments,
                         total_tags=total_tags,
                         recent_articles=recent_articles,
                         recent_comments=recent_comments)

@other_bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@other_bp.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500