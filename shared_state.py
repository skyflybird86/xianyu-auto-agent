"""共享状态管理模块"""
import threading
import time
import os

# 全局状态锁
state_lock = threading.Lock()

# 共享的服务状态
service_status = {
    'connected': False,
    'last_heartbeat': 0,
    'token_valid': False,
    'start_time': 0,
    'message_count': 0,
    'active_conversations': 0,
    'manual_mode_conversations': []
}

# 日志缓冲区（最多保存1000条日志）
log_buffer = []
MAX_LOG_ENTRIES = 1000
log_lock = threading.Lock()

def update_status(key, value):
    """线程安全地更新状态"""
    with state_lock:
        service_status[key] = value

def get_status():
    """获取当前状态快照"""
    with state_lock:
        return service_status.copy()

def add_log(level, message):
    """线程安全地添加日志"""
    with log_lock:
        log_entry = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'level': level,
            'message': message
        }
        log_buffer.append(log_entry)

        # 保持缓冲区大小限制
        if len(log_buffer) > MAX_LOG_ENTRIES:
            del log_buffer[:len(log_buffer) - MAX_LOG_ENTRIES]

def get_logs(level='all', limit=100):
    """获取日志"""
    with log_lock:
        if level == 'all':
            logs = log_buffer[-limit:]
        else:
            logs = [log for log in log_buffer if log['level'].lower() == level.lower()][-limit:]

        return {
            'logs': logs,
            'total': len(log_buffer),
            'displayed': len(logs)
        }

def clear_logs():
    """清空日志"""
    with log_lock:
        log_buffer.clear()

def log_with_web(level, message):
    """同时记录到loguru和web日志"""
    add_log(level, message)
    from loguru import logger
    if level == 'DEBUG':
        logger.debug(message)
    elif level == 'INFO':
        logger.info(message)
    elif level == 'WARNING':
        logger.warning(message)
    elif level == 'ERROR':
        logger.error(message)
