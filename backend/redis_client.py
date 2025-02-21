from redis import Redis
from json import dumps, loads
from time import time

# 创建单例 Redis 客户端
redis_client = Redis(host='localhost', port=6379, db=0)

def get_client_tasks(client_id):
    """获取客户端任务"""
    tasks = redis_client.get(f'tasks:{client_id}')
    return loads(tasks) if tasks else {}

def set_client_tasks(client_id, tasks):
    """设置客户端任务"""
    redis_client.set(f'tasks:{client_id}', dumps(tasks))
    redis_client.persist(f'tasks:{client_id}')  # 设置永不过期

def delete_client_tasks(client_id):
    """删除客户端任务"""
    redis_client.delete(f'tasks:{client_id}')

def record_user_activity(client_id: str, activity_type: str):
    """记录用户活动
    activity_type: 'visit' | 'record' | 'download'
    """
    stats_key = f'user_stats:{client_id}'
    current_time = time()
    
    # 获取现有统计数据
    stats = redis_client.get(stats_key)
    if stats:
        stats = loads(stats)
    else:
        stats = {
            'first_visit': current_time,
            'last_visit': current_time,
            'visit_count': 0,
            'record_count': 0,
            'download_count': 0
        }
    
    # 更新统计数据
    stats['last_visit'] = current_time
    
    if activity_type == 'visit':
        stats['visit_count'] += 1
    elif activity_type == 'record':
        stats['record_count'] += 1
    elif activity_type == 'download':
        stats['download_count'] += 1
        
    # 保存更新后的统计数据
    redis_client.set(stats_key, dumps(stats))
    redis_client.persist(stats_key)  # 永不过期

def get_user_stats(client_id: str):
    """获取用户统计数据"""
    stats = redis_client.get(f'user_stats:{client_id}')
    return loads(stats) if stats else None 