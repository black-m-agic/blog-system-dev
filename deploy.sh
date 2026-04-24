#!/bin/bash

# 部署脚本 - 个人博客系统

echo "开始部署个人博客系统..."

# 更新系统
echo "更新系统..."
sudo apt update && sudo apt upgrade -y

# 安装必要的软件
echo "安装必要的软件..."
sudo apt install -y python3-pip python3-venv nginx
echo "安装依赖..."

# 创建并激活虚拟环境
echo "创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 创建日志目录
echo "创建日志目录..."
mkdir -p logs

# 配置Nginx
echo "配置Nginx..."
sudo cat > /etc/nginx/sites-available/blog << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    location /static {
        alias /home/ubuntu/blog-system/static;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    location /favicon.ico {
        alias /home/ubuntu/blog-system/static/favicon.ico;
        expires 30d;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/blog /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 启动应用
echo "启动应用..."
# 先停止可能存在的进程
pkill -f gunicorn || true
# 启动Gunicorn
gunicorn -c gunicorn.conf.py app:app --daemon

echo "部署完成！应用已启动在 http://localhost:8000"
echo "您可以通过服务器的公网IP访问应用"
