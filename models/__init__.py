from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    articles = db.relationship('Article', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='sender', lazy='dynamic', cascade='all, delete-orphan')
    chat_rooms = db.relationship('ChatRoomMember', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'bio': self.bio,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat()
        }

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    articles = db.relationship('Article', backref='category', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

article_tag = db.Table(
    'article_tag',
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='published', index=True)
    views = db.Column(db.Integer, default=0, index=True)
    likes = db.Column(db.Integer, default=0, index=True)
    dislikes = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    tags = db.relationship('Tag', secondary=article_tag, backref='articles', lazy='dynamic')
    comments = db.relationship('Comment', backref='article', lazy='dynamic', cascade='all, delete-orphan')
    user_likes = db.relationship('Like', backref='article', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, include_comments=False):
        data = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'category': self.category.to_dict(),
            'author': self.author.to_dict(),
            'status': self.status,
            'views': self.views,
            'likes': self.likes,
            'dislikes': self.dislikes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'tags': [tag.to_dict() for tag in self.tags]
        }
        if include_comments:
            data['comments'] = [comment.to_dict() for comment in self.comments]
        return data

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    def to_dict(self, include_replies=True):
        data = {
            'id': self.id,
            'content': self.content,
            'author': self.author.to_dict(),
            'created_at': self.created_at.isoformat()
        }
        if include_replies:
            data['replies'] = [reply.to_dict(include_replies=False) for reply in self.replies]
        return data

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False, index=True)
    type = db.Column(db.String(10), nullable=False)  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'article_id', name='_user_article_uc'),
    )

class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    members = db.relationship('ChatRoomMember', backref='chat_room', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='chat_room', lazy='dynamic', cascade='all, delete-orphan')

class ChatRoomMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False, index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'chat_room_id', name='_user_chat_room_uc'),
    )

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'user': self.sender.to_dict(),
            'created_at': self.created_at.isoformat()
        }