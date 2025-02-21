from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import threading
import sys
import os
from typing import Dict
import logging
import glob
import time
from redis import Redis
from json import dumps, loads
import shutil
import requests
import json  # 添加json模块导入
from datetime import datetime, timedelta
from redis_client import redis_client, get_client_tasks, set_client_tasks, delete_client_tasks, record_user_activity, get_user_stats
from logger import error_logger, info_logger

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入main.py的所有功能
from main import (
    init_config, start_record_thread, url_init, get_task_info, stop_record,restart_stopped_record,clean_name,stop_all_record,find_thread_by_name,clear_exit_flag,clear_ffmpeg_process,clear_error_url,stop_thread_by_name
)

app = Flask(__name__)
CORS(app)

# 初始化配置
init_config()

logger = logging.getLogger(__name__)

# 单独维护一个线程字典
# thread_dict = {}
MAX_RECORDINGS_PER_USER = 1

# 存储用户最后心跳时间
user_heartbeats = {}

@app.route('/api/start_record', methods=['POST'])
def api_start_record():
    """启动录制任务"""
    try:
        client_id = request.headers.get('X-Client-ID')
        info_logger.info(f"Client {client_id} starting new recording")
        # 记录录制
        record_user_activity(client_id, 'record')
        print(f"-------当前client_id: {client_id}, time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
        # 更新心跳时间
        user_heartbeats[client_id] = datetime.now()
        
        # 检查Redis中是否存在该客户数据
        recording_tasks = get_client_tasks(client_id)
        
        # 检查是否超过最大录制数量
        if len(recording_tasks) >= MAX_RECORDINGS_PER_USER:
            return jsonify({'error': '已达到最大录制数量限制'}), 400
            
        data = request.json
        url = data.get('url')
        quality = data.get('quality', '标清')
        format = data.get('format', 'mp4')  # 获取视频格式
        
        # 处理URL
        url_tuple = url_init(url, quality) # (quality, url, '')
        
        if not url_tuple:
            return jsonify({'error': '无效的URL'}), 400
        url = url_tuple[1]
        print(f"url:{url}_{time.strftime('%Y-%m-%d %H:%M:%S')}")
        
            
        # 检查是否已经在录制
        if url in recording_tasks:
            print("url in recording_tasks",recording_tasks)
            print("直播已在列表中")
            return jsonify({'error': '直播已在列表中'}), 400
            
        # 启动录制线程
        thread = start_record_thread(url_tuple, client_id, format, 0)
        
        if not thread:
            print("启动录制失败",e)
            return jsonify({'error': '启动录制失败'}), 500
            
        # 更新任务列表
        if url not in recording_tasks:
            recording_tasks[url] = {
                        'url_data': url_tuple,
                        'status': '',
                        'anchor_name': '',
                        'format': format,
                        'start_time': time.time(),
                        'platform': ''
                    }
            set_client_tasks(client_id, recording_tasks)
        return jsonify({'message': url})
    except Exception as e:
        error_logger.error(f"Start record failed for client {client_id}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/start_re_record/<path:url>', methods=['POST'])
def api_start_re_record(url):
    """启动重新录制任务"""
    try:
        client_id = request.headers.get('X-Client-ID')
        if not client_id:
            return jsonify({'error': '未找到客户端ID'}), 400
        recording_tasks = get_client_tasks(client_id)
        if url not in recording_tasks:
            return jsonify({'error': '该直播已不在录制中'})
        # 处理URL
        clear_error_url(client_id, url)
        restart_stopped_record(recording_tasks[url]['url_data'],client_id)
        # 删除下载数据
        anchor_name = recording_tasks[url]['anchor_name']
        platform = recording_tasks[url]['platform']
        pattern = f'{default_path}/{client_id}/{platform}/{anchor_name}'# 或其他格式
        if not os.path.exists(pattern):
            anchor_name = clean_name(anchor_name)
            pattern = f'{default_path}/{client_id}/{platform}/{anchor_name}'# 或其他格式
        if os.path.exists(pattern):
            try:
                shutil.rmtree(pattern)
            except Exception as e:
                logger.error(f"删除用户目录失败: {e}")
        # 重新录制
        monitoring = len(recording_tasks)+1
        format =  recording_tasks[url]['format']
        # thread = find_thread_by_name(f'{client_id}_{url}')
        # if thread:
        #     print(f"{client_id}_{url}_{anchor_name}线程仍在运行")
        start_record_thread(recording_tasks[url]['url_data'], client_id, format, monitoring)
        recording_tasks[url]['start_time'] = time.time()
        set_client_tasks(client_id, recording_tasks)
        return jsonify({'message': '重新开始录制'})
    except Exception as e:
        print("api_start_re_record错误",e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop_record/<path:url>', methods=['POST'])
def api_stop_record(url):
    """停止单个录制任务"""
    try:
        client_id = request.headers.get('X-Client-ID')
        if not client_id:
            return jsonify({'error': '未找到客户端ID'}), 400
            
        recording_tasks = get_client_tasks(client_id)
        if url not in recording_tasks:
            return jsonify({'error': '未找到该录制任务'})
        try:
            stop_record(recording_tasks[url]['url_data'], client_id)
        except Exception as e:
            print(e)
        return jsonify({'message': '停止录制'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_record/<path:url>', methods=['DELETE'])
def api_delete_record(url):
    """删除单个录制任务"""
    try:
        client_id = request.headers.get('X-Client-ID')
        info_logger.info(f"Client {client_id} deleting record: {url}")
        recording_tasks = get_client_tasks(client_id)
        
        if url not in recording_tasks:
            return jsonify({'error': '未找到该录制任务'})

        task = recording_tasks[url]
        
        # 启动异步线程处理耗时操作
        cleanup_thread = threading.Thread(
            target=cleanup_record,
            args=(client_id, url, task),
            daemon=True
        )
        cleanup_thread.start()
        
        # 立即从任务列表中移除
        del recording_tasks[url]
        set_client_tasks(client_id, recording_tasks)
        
        return jsonify({'message': '删除成功'})
    except Exception as e:
        error_logger.error(f"Delete record failed for client {client_id}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def cleanup_record(client_id, url, task):
    """异步清理录制任务"""
    try:
        # 停止录制进程
        clear_ffmpeg_process(client_id, url)
        clear_error_url(client_id, url)
        
        # 停止监控线程
        threading.Thread(
            target=stop_thread_by_name, 
            args=(f'{client_id}_{task["url_data"][1]}', client_id, task)
        ).start()
        
        # 清理文件
        anchor_name = task['anchor_name']
        platform = task['platform']
        pattern = f'{default_path}/{client_id}/{platform}/{anchor_name}'
        if os.path.exists(pattern):
            shutil.rmtree(pattern)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取指定客户的所有录制任务"""
    try:
        client_id = request.headers.get('X-Client-ID')
        # 记录访问
        record_user_activity(client_id, 'visit')
        if not client_id:
            return jsonify({'error': '未找到客户端ID'}), 400
            
        # 获取该客户的任务
        recording_tasks = get_client_tasks(client_id)
        # print(f"get_tasks:{len(recording_tasks)}____{time.strftime('%Y-%m-%d %H:%M:%S')}")
        tasks = []
        if recording_tasks:
            for task in recording_tasks.values():
                try:
                    info_dict = get_task_info(task, client_id)
                    quality, record_url, _ = task['url_data']
                    recording_tasks[record_url]['anchor_name'] = info_dict['anchor_name']
                            # 更新任务列表
                    if info_dict['status'] != recording_tasks[record_url]['status']:
                        recording_tasks[record_url] = {
                            'url_data': task['url_data'],
                            'status': info_dict['status'],
                            'anchor_name': info_dict['anchor_name'],
                            'format': task['format'],
                            'start_time': info_dict['start_time'],
                            'platform': info_dict['platform']
                            # 记录开始时间
                        }
                        set_client_tasks(client_id, recording_tasks)
                        # print(f"set_client_tasks0")
                    if info_dict['platform'] != recording_tasks[record_url]['platform']:
                        recording_tasks[record_url]['platform'] = info_dict['platform']
                        set_client_tasks(client_id, recording_tasks)
                        print(f"set_client_tasks1:{recording_tasks}_{time.strftime('%Y-%m-%d %H:%M:%S')}")
                    tasks.append({
                        'url': record_url,
                        'quality': quality,
                        'anchor': info_dict['anchor_name'],
                        'status': info_dict['status'],
                        'start_time': info_dict['start_time']
                    })
                except Exception as e:
                    print(f"处理任务信息错误: {str(e)}")
        return jsonify(tasks)
    except Exception as e:
        print("get_tasks错误",e)
        return jsonify({'error': str(e)}), 500


script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
default_path = f'{script_path}/downloads'
@app.route('/api/download/<path:url>', methods=['GET'])
def download_record(url):
    """下载录制文件"""
    try:
        # 同时检查header和query参数
        client_id = request.headers.get('X-Client-ID') or request.args.get('client_id')
        # 记录下载
        record_user_activity(client_id, 'download')
        if not client_id:
            print(f"未找到客户端ID")
            return jsonify({'error': '未找到客户端ID'}), 400
            
        recording_tasks = get_client_tasks(client_id)
        if url not in recording_tasks:
            print(f"未找到该录制任务")
            return jsonify({'error': '未找到该录制任务'}), 404
            
        # 获取录制文件路径
        anchor_name = recording_tasks[url]['anchor_name']
        platform = recording_tasks[url]['platform']
        # 在downloads目录下查找该主播的最新文件
        pattern = f'{default_path}/{client_id}/{platform}/{anchor_name}/*'# 或其他格式
        files = glob.glob(pattern, recursive=True)
        
        
        if not files:
            anchor_name = clean_name(anchor_name)
            pattern = f'{default_path}/{client_id}/{platform}/{anchor_name}/*'# 或其他格式
            # print(f"pattern: {pattern}")
            files = glob.glob(pattern, recursive=True)
        if not files:
            print(f"未找到录制文件")
            return jsonify({'error': '未找到录制文件'}), 404
            
        # 按修改时间排序，获取最新文件
        latest_file = max(files, key=os.path.getmtime)
        
        # 发送文件
        return send_file(
            latest_file,
            as_attachment=True,
            download_name=os.path.basename(latest_file)
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup_close', methods=['POST'])
def cleanup_close():
    """清理客户端任务"""
    try:
        # 从请求头获取client_id
        client_id = request.headers.get('X-Client-ID')
        
        # 如果请求头没有，则尝试从请求体获取
        if not client_id:
            try:
                # 读取原始数据并解析JSON
                raw_data = request.data.decode('utf-8')
                data = json.loads(raw_data)
                client_id = data.get('clientId')
            except Exception as e:
                print(f"解析JSON数据失败: {e}")
                
        if not client_id:
            return jsonify({'message': 'No client ID provided'})
            
        print(f"-------------close：{client_id} {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 停止所有录制任务
        all_record_tasks = []
        recording_tasks = get_client_tasks(client_id)
        # for task in recording_tasks.values():
        #     all_record_tasks.append(task['url_data'])
        # try:
        #     stop_all_record(all_record_tasks, client_id)
        #     time.sleep(1)
            
        # except Exception as e:
        #     logger.error(f"停止录制失败: {e}")
                
        for task in recording_tasks.values():
            clear_ffmpeg_process(client_id, task['url_data'][1])
            clear_error_url(client_id, task['url_data'][1])
            thread = find_thread_by_name(f'{client_id}_{task["url_data"][1]}')
            if thread:
                clear_exit_flag(client_id,task['url_data'][1])
                thread.join()
        
        # 清除Redis中的所有相关数据
        redis_client.delete(f'tasks:{client_id}')  # 删除任务数据
        redis_client.delete(f'comments:{client_id}')  # 删除评论数据
        redis_client.delete(f'error8:{client_id}')  # 删除错误数据
        
        # 删除下载目录中的该用户文件夹
        user_dir = f'{default_path}/{client_id}'
        if os.path.exists(user_dir):
            try:
                shutil.rmtree(user_dir)
            except Exception as e:
                logger.error(f"删除用户目录失败: {e}")
                
        return jsonify({'message': 'OK'})
    except Exception as e:
         return jsonify({'error': str(e)}), 500



@app.route('/api/cleanup', methods=['DELETE'])
def cleanup():
    """清理客户端任务"""
    try:
        client_id = request.headers.get('X-Client-ID')
        if not client_id:
            return jsonify({'message': 'OK'})
            
        # 停止所有录制任务
        recording_tasks = get_client_tasks(client_id)
        if recording_tasks:
            print(f"-------------清理客户端任务：{request.headers.get('X-Client-ID')} {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"-------------recording_tasks: {recording_tasks}")
        # all_record_tasks = []
        # for task in recording_tasks.values():
        #     all_record_tasks.append(task['url_data'])
        # try:
        #     stop_all_record(all_record_tasks, client_id)
        #     time.sleep(1)
        # except Exception as e:
        #     logger.error(f"停止录制失败: {e}")
                
        # recording_tasks = get_client_tasks(client_id)
            for task in recording_tasks.values():
                clear_ffmpeg_process(client_id, task['url_data'][1])
                clear_error_url(client_id, task['url_data'][1])
                thread = find_thread_by_name(f'{client_id}_{task["url_data"][1]}')
                if thread:
                    print(f"cleanup: {client_id}_{task['url_data'][1]}_{task['anchor_name']}线程仍在运行")
                    clear_exit_flag(client_id,task['url_data'][1])
                    thread.join()
                    print(f"---cleanup: {client_id}_{task['url_data'][1]}_{task['anchor_name']}线程已停止")
            
            # 清除Redis中的所有相关数据
            redis_client.delete(f'tasks:{client_id}')  # 删除任务数据
            redis_client.delete(f'comments:{client_id}')  # 删除评论数据
            redis_client.delete(f'error8:{client_id}')  # 删除错误数据
            recording_tasks = get_client_tasks(client_id)
            print("cleanup_recording_tasks",recording_tasks)
        # 删除下载目录中的该用户文件夹
        user_dir = f'{default_path}/{client_id}'
        if os.path.exists(user_dir):
            try:
                shutil.rmtree(user_dir)
            except Exception as e:
                logger.error(f"删除用户目录失败: {e}")
                
        return jsonify({'message': 'OK'})
    except Exception as e:
        print(f"-------------清理客户端任务失败：{e}")
        return jsonify({'error': str(e)}), 500

# @app.route('/api/threads', methods=['GET'])
# def get_threads():
#     """获取当前所有活动线程信息"""
#     try:
#         active_threads = []
#         for thread in threading.enumerate():
#             active_threads.append({
#                 'name': thread.name,
#                 'id': thread.ident,
#                 'alive': thread.is_alive(),
#                 'daemon': thread.daemon
#             })
#         return jsonify(active_threads)
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

@app.route('/api/get-language', methods=['GET'])
def get_language():
    """基于IP获取用户所在地区的语言"""
    try:
        # 获取客户端IP
        ip = request.headers.get('X-Real-IP') or request.remote_addr
        
        # 使用IP-API获取地区信息
        response = requests.get(f'http://ip-api.com/json/{ip}')
        data = response.json()
        
        # 根据国家代码返回语言设置
        country_code = data.get('countryCode', 'US')
        
        # 定义国家代码到语言的映射
        language_map = {
            'CN': 'zh',  # 中国
            'TW': 'zh',  # 台湾
            'HK': 'zh',  # 香港
            'JP': 'ja',  # 日本
            'KR': 'ko',  # 韩国
            'US': 'en',  # 美国
            'GB': 'en',  # 英国
            # ... 可以添加更多国家
        }
        
        language = language_map.get(country_code, 'en')  # 默认英语
        return jsonify({'language': language})
        
    except Exception as e:
        return jsonify({'language': 'en', 'error': str(e)})

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """处理用户心跳"""
    try:
        client_id = request.headers.get('X-Client-ID')
        if client_id:
            # 更新用户最后心跳时间
            user_heartbeats[client_id] = datetime.now()
            # print(f"Heartbeat received from {client_id} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 添加检查离线用户的函数
def check_offline_users():
    """检查离线用户并清理"""
    while True:
        try:    
            for client_id, last_heartbeat in list(user_heartbeats.items()):
                current_time = datetime.now()
                offline_threshold = timedelta(minutes=1440)  # 1440分钟/24小时没有心跳就认为离线
                if current_time - last_heartbeat > offline_threshold:
                    print(f"User {client_id} went offline, cleaning up...")
                    
                    # 停止所有录制任务
                    recording_tasks = get_client_tasks(client_id)
                    # all_record_tasks = []
                    # for task in recording_tasks.values():
                    #     print(f"task: {task}")
                    #     all_record_tasks.append(task['url_data'])
                    # try:
                    #     stop_all_record(all_record_tasks, client_id)
                    #     time.sleep(1)
                    # except Exception as e:
                    #     logger.error(f"停止录制失败: {e}")
                    
                    # recording_tasks = get_client_tasks(client_id)
                    print(f"---offline recording_tasks: {recording_tasks}")
                    for task in recording_tasks.values():
                        clear_ffmpeg_process(client_id,task['url_data'][1]) 
                        clear_error_url(client_id, task['url_data'][1])
                        thread = find_thread_by_name(f'{client_id}_{task["url_data"][1]}')
                        if thread:
                            print(f"offline: {client_id}_{task['url_data'][1]}_{task['anchor_name']}线程仍在运行")
                            clear_exit_flag(client_id,task['url_data'][1])
                            thread.join()
                            print(f"---offline: {client_id}_{task['url_data'][1]}_{task['anchor_name']}线程已停止")
                    
                    # 清除Redis中的数据
                    redis_client.delete(f'tasks:{client_id}')
                    redis_client.delete(f'comments:{client_id}')
                    redis_client.delete(f'error8:{client_id}')
                    
                    # 删除用户目录
                    user_dir = f'{default_path}/{client_id}'
                    if os.path.exists(user_dir):
                        try:
                            shutil.rmtree(user_dir)
                        except Exception as e:
                            logger.error(f"删除用户目录失败: {e}")
                    
                    # 删除心跳记录
                    del user_heartbeats[client_id]
                    
        except Exception as e:
            print(f"Error checking offline users: {e}")
            
        time.sleep(60)  # 每分钟检查一次

# 启动检查线程
check_thread = threading.Thread(target=check_offline_users, daemon=True)
check_thread.start()

@app.route('/api/admin/stats', methods=['GET'])
def get_all_stats():
    """获取所有用户统计数据（需要管理员权限）"""
    try:
        # TODO: 添加管理员验证
        all_stats = []
        for key in redis_client.keys('user_stats:*'):
            client_id = key.decode('utf-8').split(':')[1]
            stats = get_user_stats(client_id)
            if stats:
                stats['client_id'] = client_id
                all_stats.append(stats)
        return jsonify(all_stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 添加全局错误处理
@app.errorhandler(Exception)
def handle_exception(e):
    error_logger.error("Unhandled exception:", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5002) 