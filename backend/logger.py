import logging
import os
from datetime import datetime

# 创建logs目录
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 配置日志记录器
def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 使用普通的FileHandler
    handler = logging.FileHandler(
        os.path.join(log_dir, log_file),
        encoding='utf-8',
        mode='a'  # 追加模式
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加handler
    if not logger.handlers:
        logger.addHandler(handler)

    return logger

# 创建不同类型的日志记录器
error_logger = setup_logger('error', 'error.log', logging.ERROR)
info_logger = setup_logger('info', 'info.log', logging.INFO) 