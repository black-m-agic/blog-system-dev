import multiprocessing

# Gunicorn配置文件

# 监听地址和端口
bind = '0.0.0.0:8000'

# 工作进程数量（推荐：CPU核心数 × 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1

# 工作进程类型（使用gevent提高并发性能）
worker_class = 'gevent'

# 每个工作进程的最大连接数
worker_connections = 1000

# 超时时间（秒）
timeout = 30

# 启动时的进程数
transaction_timeout = 30

# 日志配置
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'info'

# 进程名称
proc_name = 'blog-system'

# 最大请求数（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 100
