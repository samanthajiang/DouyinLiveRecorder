# 添加生产环境配置
PROD_CONFIG = {
    'HOST': '0.0.0.0',
    'PORT': 5000,
    'DEBUG': False,
    
    # CORS配置
    'CORS_ORIGINS': [
        'https://www.recordtik.live',  # 替换为你的域名
        'http://localhost:3000'     # 开发环境
    ],
    
    # Redis配置
    'REDIS_URL': 'redis://redis:6379/0'  # 使用 Docker 服务名
} 