from routes.main import main_bp
from routes.auth import auth_bp
from routes.article import article_bp
from routes.other import other_bp
from routes.ai import ai_bp

__all__ = ['main_bp', 'auth_bp', 'article_bp', 'other_bp', 'ai_bp']