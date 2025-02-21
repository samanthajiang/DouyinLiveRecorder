# Gunicorn 配置
bind = '0.0.0.0:5000'
workers = 4  # 建议设置为 CPU 核心数 * 2 + 1
worker_class = 'gevent'  # 使用 gevent 处理异步请求
timeout = 120
keepalive = 60

# 日志配置
accesslog = 'logs/access.log'
errorlog = 'logs/error.log'
loglevel = 'info' 