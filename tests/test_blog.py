import unittest
from app import app
from models import db, User, Article, Category
from werkzeug.security import generate_password_hash
import os

class BlogTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        
        if Category.query.count() == 0:
            category = Category(name='技术')
            db.session.add(category)
            db.session.commit()
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        if os.path.exists('test.db'):
            os.remove('test.db')
    
    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_register_user(self):
        response = self.client.post('/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'Test123!',
            'confirm_password': 'Test123!'
        }, follow_redirects=True)
        self.assertIn(b'注册成功', response.data)
    
    def test_login_logout(self):
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('Test123!')
        )
        db.session.add(user)
        db.session.commit()
        
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'Test123!'
        }, follow_redirects=True)
        self.assertIn(b'登录成功', response.data)
        
        response = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'已退出登录', response.data)
    
    def test_api_articles(self):
        response = self.client.get('/api/articles')
        self.assertEqual(response.status_code, 200)
        self.assertIn('articles', response.json)
    
    def test_api_categories(self):
        response = self.client.get('/api/categories')
        self.assertEqual(response.status_code, 200)
        self.assertIn('categories', response.json)

if __name__ == '__main__':
    unittest.main()