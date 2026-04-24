from flask import Blueprint, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, ChatRoom, ChatRoomMember, Message, User
import json
import os
from utils.security import clean_html, log_security_event

chat_bp = Blueprint('chat', __name__)

# 存储当前在线用户的连接
online_users = {}
# 存储实时阅读文章的用户
reading_articles = {}

def init_socketio(app):
    # 配置CORS - 从环境变量读取或使用安全默认值
    allowed_origins = os.environ.get('SOCKETIO_ALLOWED_ORIGINS', 'http://localhost:8080,https://localhost:8080')
    cors_list = [origin.strip() for origin in allowed_origins.split(',')]
    
    socketio = SocketIO(app, cors_allowed_origins=cors_list)
    
    @socketio.on('connect')
    def handle_connect():
        user_id = session.get('user_id')
        if user_id:
            online_users[user_id] = request.sid
            emit('user_connected', {'user_id': user_id})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        user_id = None
        for uid, sid in online_users.items():
            if sid == request.sid:
                user_id = uid
                break
        if user_id:
            del online_users[user_id]
            # 从实时阅读中移除
            for article_id, users in reading_articles.items():
                if user_id in users:
                    users.remove(user_id)
                    emit('reading_update', {'article_id': article_id, 'count': len(users)}, room=f'article_{article_id}')
            emit('user_disconnected', {'user_id': user_id})
    
    @socketio.on('join_room')
    def handle_join_room(data):
        room_id = data.get('room_id')
        if room_id:
            join_room(str(room_id))
            emit('joined_room', {'room_id': room_id})
    
    @socketio.on('leave_room')
    def handle_leave_room(data):
        room_id = data.get('room_id')
        if room_id:
            leave_room(str(room_id))
            emit('left_room', {'room_id': room_id})
    
    @socketio.on('send_message')
    def handle_send_message(data):
        room_id = data.get('room_id')
        content = data.get('content')
        user_id = session.get('user_id')
        
        if not room_id or not content or not user_id:
            return
        
        # 验证消息内容长度
        if len(content.strip()) == 0 or len(content) > 2000:
            emit('message_error', {'error': '消息长度限制为1-2000字符'})
            return
        
        # 清理内容防止XSS
        cleaned_content = clean_html(content)
        
        user = User.query.get(user_id)
        if user:
            message = Message(
                content=cleaned_content,
                user_id=user_id,
                chat_room_id=room_id
            )
            db.session.add(message)
            db.session.commit()
            
            log_security_event('chat_message_sent', f'Room: {room_id}')
            
            emit('new_message', {
                'id': message.id,
                'content': message.content,
                'user': user.to_dict(),
                'created_at': message.created_at.isoformat()
            }, room=str(room_id))
    
    @socketio.on('start_reading')
    def handle_start_reading(data):
        article_id = data.get('article_id')
        user_id = session.get('user_id')
        
        if article_id and user_id:
            if article_id not in reading_articles:
                reading_articles[article_id] = set()
            reading_articles[article_id].add(user_id)
            
            join_room(f'article_{article_id}')
            emit('reading_update', {
                'article_id': article_id,
                'count': len(reading_articles[article_id])
            }, room=f'article_{article_id}')
    
    @socketio.on('stop_reading')
    def handle_stop_reading(data):
        article_id = data.get('article_id')
        user_id = session.get('user_id')
        
        if article_id and user_id:
            if article_id in reading_articles and user_id in reading_articles[article_id]:
                reading_articles[article_id].remove(user_id)
                
                leave_room(f'article_{article_id}')
                emit('reading_update', {
                    'article_id': article_id,
                    'count': len(reading_articles[article_id])
                }, room=f'article_{article_id}')
    
    return socketio