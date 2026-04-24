from cryptography.fernet import Fernet
import base64
import hashlib
import os


def generate_key_from_string(string):
    """从字符串生成加密密钥"""
    # 使用SHA256哈希并转换为base64
    digest = hashlib.sha256(string.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_data(data, key):
    """加密数据"""
    if not data:
        return None
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(encrypted_data, key):
    """解密数据"""
    if not encrypted_data:
        return None
    try:
        fernet = Fernet(key)
        decoded = base64.urlsafe_b64decode(encrypted_data.encode())
        return fernet.decrypt(decoded).decode()
    except Exception:
        return None


class SecureKeyStorage:
    """安全的API密钥存储"""
    
    def __init__(self, master_key=None):
        """
        初始化安全存储
        :param master_key: 主密钥，如果为None则从环境变量获取
        """
        if master_key:
            self.master_key = generate_key_from_string(master_key)
        else:
            # 从环境变量获取或使用SECRET_KEY派生
            master_secret = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
            self.master_key = generate_key_from_string(master_secret)
    
    def encrypt(self, data):
        """加密数据"""
        return encrypt_data(data, self.master_key)
    
    def decrypt(self, encrypted_data):
        """解密数据"""
        return decrypt_data(encrypted_data, self.master_key)
