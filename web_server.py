import os
import json
import threading
import time
import hashlib
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from dotenv import set_key, load_dotenv
from io import StringIO

app = Flask(__name__)

def get_machine_id():
    """获取机器ID"""
    try:
        import uuid
        return hashlib.md5(str(uuid.getnode()).encode()).hexdigest()[:16]
    except:
        return "unknown"

def check_activation():
    """检查激活状态"""
    try:
        from activation_client import is_activated as client_is_activated
        return client_is_activated()
    except ImportError:
        return True

def verify_activation_code(code):
    """验证并激活"""
    try:
        from activation_client import activate
        return activate(code)
    except ImportError:
        return {"success": False, "message": "激活模块不可用"}
CORS(app)

# 尝试导入共享状态，如果失败则使用本地状态
try:
    from shared_state import (
        service_status, log_buffer, update_status, get_status,
        add_log, get_logs, clear_logs
    )
    USE_SHARED_STATE = True
except ImportError:
    USE_SHARED_STATE = False
    # 本地状态管理（备用）
    service_status = {
        'connected': False,
        'last_heartbeat': 0,
        'token_valid': False,
        'start_time': 0,
        'message_count': 0,
        'active_conversations': 0,
        'manual_mode_conversations': []
    }
    log_buffer = []
    MAX_LOG_ENTRIES = 1000

# 配置项定义
CONFIG_FIELDS = [
    {'key': 'API_KEY', 'label': 'API Key', 'description': '通义千问API密钥，从百炼平台获取', 'type': 'password'},
    {'key': 'COOKIES_STR', 'label': 'Cookie字符串', 'description': '闲鱼网站Cookie，用于建立连接', 'type': 'textarea'},
    {'key': 'MODEL_BASE_URL', 'label': '模型接口地址', 'description': '默认使用阿里云通义千问', 'type': 'text', 'default': 'https://dashscope.aliyuncs.com/compatible-mode/v1'},
    {'key': 'MODEL_NAME', 'label': '模型名称', 'description': '使用的模型名称', 'type': 'text', 'default': 'qwen-max'},
    {'key': 'TOGGLE_KEYWORDS', 'label': '人工接管关键词', 'description': '发送此关键词切换人工/自动模式', 'type': 'text', 'default': '。'},
    {'key': 'SIMULATE_HUMAN_TYPING', 'label': '模拟人工输入', 'description': '是否模拟人工打字延迟', 'type': 'boolean', 'default': 'False'},
    {'key': 'HEARTBEAT_INTERVAL', 'label': '心跳间隔(秒)', 'description': 'WebSocket心跳发送间隔', 'type': 'number', 'default': '15'},
    {'key': 'TOKEN_REFRESH_INTERVAL', 'label': 'Token刷新间隔(秒)', 'description': 'Access Token刷新周期', 'type': 'number', 'default': '3600'}
]

def get_current_config():
    """获取当前配置"""
    config = {}
    for field in CONFIG_FIELDS:
        value = os.getenv(field['key'], field.get('default', ''))
        # 密码字段不显示实际值
        if field['type'] == 'password' and value:
            config[field['key']] = '******'
        else:
            config[field['key']] = value
    return config

def save_config(config_data):
    """保存配置到.env文件"""
    env_path = '.env'
    
    # 确保.env文件存在
    if not os.path.exists(env_path):
        with open(env_path, 'w', encoding='utf-8') as f:
            pass
    
    for field in CONFIG_FIELDS:
        key = field['key']
        if key in config_data:
            value = config_data[key]
            # 密码字段如果是******则不更新
            if field['type'] == 'password' and value == '******':
                continue
            os.environ[key] = value
            set_key(env_path, key, value)
    
    return True

@app.route('/api/activation/check', methods=['GET'])
def api_check_activation():
    """检查激活状态"""
    is_activated = check_activation()
    return jsonify({
        'activated': is_activated,
        'machine_id': get_machine_id()
    })

@app.route('/api/activation/activate', methods=['POST'])
def api_activate():
    """激活软件"""
    code = request.json.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '请输入激活码'}), 400

    result = verify_activation_code(code)
    if result.get('success'):
        return jsonify({
            'success': True,
            'message': '激活成功',
            'expire_date': result.get('expire_date')
        })
    else:
        return jsonify({
            'success': False,
            'message': result.get('message', '激活失败')
        }), 400

@app.route('/api/activation/stats', methods=['GET'])
def api_activation_stats():
    """获取激活统计"""
    try:
        from activation_db import get_activation_stats
        return jsonify(get_activation_stats())
    except:
        return jsonify({'total': 0, 'used': 0, 'available': 0, 'used_rate': 0})

@app.route('/')
def index():
    activated = check_activation()
    if not activated:
        return build_activation_html()
    return build_html()

@app.route('/api/config', methods=['GET'])
def api_get_config():
    """获取配置"""
    return jsonify(get_current_config())

@app.route('/api/config', methods=['POST'])
def api_save_config():
    """保存配置"""
    try:
        config_data = request.json
        save_config(config_data)
        return jsonify({'success': True, 'message': '配置保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def api_get_status():
    """获取服务状态"""
    if USE_SHARED_STATE:
        status = get_status()
    else:
        status = service_status.copy()

    # 计算运行时间
    if status.get('start_time', 0) > 0:
        uptime_seconds = int(time.time() - status['start_time'])
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        status['uptime'] = f"{hours}小时{minutes}分钟{seconds}秒"
    else:
        status['uptime'] = '未启动'

    # 检查心跳状态
    if status.get('last_heartbeat', 0) > 0:
        heartbeat_age = int(time.time() - status['last_heartbeat'])
        if heartbeat_age < 30:
            status['heartbeat_status'] = '正常'
        else:
            status['heartbeat_status'] = '警告'
    else:
        status['heartbeat_status'] = '无数据'

    return jsonify(status)

@app.route('/api/restart', methods=['POST'])
def api_restart():
    """触发重启（实际重启需要外部处理）"""
    if USE_SHARED_STATE:
        update_status('connected', False)
        update_status('token_valid', False)
    else:
        global service_status
        service_status['connected'] = False
        service_status['token_valid'] = False
    return jsonify({'success': True, 'message': '已触发重启，请手动重启服务'})

@app.route('/api/logs', methods=['GET'])
def api_get_logs():
    """获取服务日志"""
    limit = request.args.get('limit', 100, type=int)
    level = request.args.get('level', 'all')

    if USE_SHARED_STATE:
        return jsonify(get_logs(level, limit))
    else:
        global log_buffer
        filtered_logs = log_buffer

        if level != 'all':
            filtered_logs = [log for log in filtered_logs if log['level'].lower() == level.lower()]

        recent_logs = filtered_logs[-limit:]

        return jsonify({
            'logs': recent_logs,
            'total': len(filtered_logs),
            'displayed': len(recent_logs)
        })

@app.route('/api/logs/clear', methods=['POST'])
def api_clear_logs():
    """清空日志缓冲区"""
    global log_buffer
    if USE_SHARED_STATE:
        clear_logs()
    else:
        log_buffer = []
    return jsonify({'success': True, 'message': '日志已清空'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """停止服务"""
    if USE_SHARED_STATE:
        update_status('connected', False)
        update_status('token_valid', False)
        update_status('service_running', False)
        update_status('service_status', 'stopped')
    else:
        global service_status
        service_status['connected'] = False
        service_status['token_valid'] = False
    
    return jsonify({'success': True, 'message': '服务已停止'})

# 全局变量用于存储服务线程和实例
xianyu_live_instance = None
xianyu_bot_instance = None
service_thread = None

def start_service():
    """启动自动回复服务"""
    global xianyu_live_instance, xianyu_bot_instance, service_thread
    
    try:
        from main import XianyuReplyBot, XianyuLive
        
        cookies_str = os.getenv("COOKIES_STR")
        
        if not cookies_str:
            raise ValueError("COOKIES_STR 未配置")
        
        bot = XianyuReplyBot()
        xianyuLive = XianyuLive(cookies_str, bot)
        
        xianyu_bot_instance = bot
        xianyu_live_instance = xianyuLive
        
        # 在新线程中运行服务
        service_thread = threading.Thread(target=run_service, args=(xianyuLive,), daemon=True)
        service_thread.start()
        
        if USE_SHARED_STATE:
            update_status('service_running', True)
            update_status('service_status', 'running')
            add_log("INFO", "自动回复服务已启动")
        
        return True, "服务启动成功"
    except Exception as e:
        if USE_SHARED_STATE:
            add_log("ERROR", f"服务启动失败: {str(e)}")
        return False, str(e)

def run_service(xianyuLive):
    """运行服务（在独立线程中）"""
    import asyncio
    try:
        asyncio.run(xianyuLive.main())
    except Exception as e:
        if USE_SHARED_STATE:
            add_log("ERROR", f"服务运行异常: {str(e)}")
            update_status('service_running', False)
            update_status('service_status', 'error')

def stop_service():
    """停止服务"""
    global xianyu_live_instance, xianyu_bot_instance, service_thread
    
    if USE_SHARED_STATE:
        update_status('service_running', False)
        update_status('service_status', 'stopped')
        add_log("INFO", "自动回复服务已停止")
    
    # 可以在这里添加优雅关闭逻辑
    
    xianyu_live_instance = None
    xianyu_bot_instance = None
    service_thread = None
    
    return True, "服务已停止"

@app.route('/api/service/start', methods=['POST'])
def api_start_service():
    """启动自动回复服务"""
    global service_thread
    
    if service_thread and service_thread.is_alive():
        return jsonify({'success': False, 'message': '服务已经在运行中'})
    
    success, message = start_service()
    return jsonify({'success': success, 'message': message})

@app.route('/api/service/stop', methods=['POST'])
def api_stop_service():
    """停止自动回复服务"""
    global service_thread
    
    if not service_thread or not service_thread.is_alive():
        return jsonify({'success': False, 'message': '服务未在运行'})
    
    success, message = stop_service()
    return jsonify({'success': success, 'message': message})

@app.route('/api/service/restart', methods=['POST'])
def api_restart_service():
    """重启自动回复服务"""
    # 先停止
    stop_service()
    time.sleep(1)
    # 再启动
    success, message = start_service()
    return jsonify({'success': success, 'message': message})

def run_web_server(port=5000):
    """启动Web服务器"""
    import socket
    import platform
    
    # 尝试绑定端口，如果失败则尝试其他端口
    host = '127.0.0.1' if platform.system() == 'Windows' else '0.0.0.0'
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    available_port = port
    for p in [port, 8080, 8081, 8082]:
        try:
            sock.bind((host, p))
            available_port = p
            sock.close()
            break
        except:
            continue

    sock.close()

    # 确保templates目录存在
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # 如果模板文件不存在，创建一个
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w', encoding='utf-8') as f:
            f.write(build_html())

    print(f"Web服务器已启动，访问 http://localhost:{available_port}")
    if USE_SHARED_STATE and 'add_log' in dir():
        add_log("INFO", f"Web服务器已启动，访问 http://localhost:{available_port}")
    app.run(host=host, port=available_port, debug=False, use_reloader=False)

def build_activation_html():
    """构建激活页面"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>激活 - 闲鱼自动回复助手</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .activation-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            padding: 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
        }
        .logo {
            font-size: 64px;
            margin-bottom: 20px;
        }
        .title {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 10px;
        }
        .subtitle {
            font-size: 14px;
            color: #666;
            margin-bottom: 30px;
        }
        .machine-id {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 20px;
            font-size: 12px;
            color: #666;
        }
        .machine-id code {
            background: #e5e7eb;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: Monaco, Menlo, monospace;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        .form-group label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: #333;
            margin-bottom: 8px;
        }
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.2s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .btn {
            width: 100%;
            padding: 14px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .alert {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 14px;
        }
        .alert-success {
            background: #dcfce7;
            color: #166534;
        }
        .alert-error {
            background: #fee2e2;
            color: #991b1b;
        }
    </style>
</head>
<body>
    <div class="activation-card">
        <div class="logo">🐟</div>
        <h1 class="title">闲鱼自动回复助手</h1>
        <p class="subtitle">请输入激活码以使用完整功能</p>
        
        <div class="machine-id">
            <strong>机器码：</strong>
            <code id="machine-id"></code>
        </div>
        
        <div id="alert-container"></div>
        
        <div class="form-group">
            <label>激活码</label>
            <input type="text" id="activation-code" placeholder="请输入激活码" maxlength="64">
        </div>
        
        <button class="btn btn-primary" onclick="activate()">激活</button>
    </div>

    <script>
        let machineId = '';
        
        async function checkActivation() {
            try {
                const response = await fetch('/api/activation/check');
                const data = await response.json();
                machineId = data.machine_id;
                document.getElementById('machine-id').textContent = machineId;
                
                if (data.activated) {
                    // 已激活，跳转到主页
                    window.location.href = '/';
                }
            } catch (error) {
                console.error('检查激活状态失败:', error);
            }
        }
        
        function showAlert(message, type = 'error') {
            const container = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            container.appendChild(alert);
            setTimeout(() => alert.remove(), 3000);
        }
        
        async function activate() {
            const code = document.getElementById('activation-code').value.trim();
            if (!code) {
                showAlert('请输入激活码', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/activation/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: code })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showAlert('激活成功！即将跳转到主页面...', 'success');
                    setTimeout(() => window.location.href = '/', 1500);
                } else {
                    showAlert(result.message || '激活失败', 'error');
                }
            } catch (error) {
                showAlert('激活失败: ' + error.message, 'error');
            }
        }
        
        // 页面加载时检查激活状态
        document.addEventListener('DOMContentLoaded', () => {
            checkActivation();
        });
    </script>
</body>
</html>
    '''

def build_html():
    """构建主页面"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>闲鱼自动回复助手</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
        
        .card { background: white; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); padding: 24px; margin-bottom: 24px; }
        .card-title { font-size: 18px; font-weight: 600; color: #1a1a1a; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        .card-title::before { content: ''; width: 4px; height: 20px; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 2px; }
        
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
        .status-item { background: #f8f9fa; border-radius: 12px; padding: 20px; text-align: center; }
        .status-label { font-size: 13px; color: #666; margin-bottom: 8px; }
        .status-value { font-size: 24px; font-weight: 700; }
        .status-connected { color: #10b981; }
        .status-disconnected { color: #ef4444; }
        .status-warning { color: #f59e0b; }
        .status-normal { color: #3b82f6; }
        
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 14px; font-weight: 500; color: #333; margin-bottom: 8px; }
        .form-group label span { color: #ef4444; }
        .form-group input[type="text"],
        .form-group input[type="password"],
        .form-group input[type="number"],
        .form-group textarea,
        .form-group select {
            width: 100%; padding: 12px 16px; border: 2px solid #e5e7eb; border-radius: 8px;
            font-size: 14px; transition: all 0.2s;
        }
        .form-group input[type="text"]:focus,
        .form-group input[type="password"]:focus,
        .form-group input[type="number"]:focus,
        .form-group textarea:focus,
        .form-group select:focus {
            outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .form-group textarea { height: 100px; resize: vertical; }
        .form-group .help-text { font-size: 12px; color: #9ca3af; margin-top: 4px; }
        
        .btn-group { display: flex; gap: 12px; margin-top: 20px; }
        .btn { padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
        .btn-secondary { background: #f3f4f6; color: #374151; }
        .btn-secondary:hover { background: #e5e7eb; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        
        .status-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .status-dot.connected { background: #10b981; box-shadow: 0 0 8px rgba(16, 185, 129, 0.5); animation: pulse 2s infinite; }
        .status-dot.disconnected { background: #ef4444; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
        .alert-success { background: #dcfce7; color: #166534; }
        .alert-error { background: #fee2e2; color: #991b1b; }
        .alert-info { background: #dbeafe; color: #1e40af; }
        
        .stats-row { display: flex; gap: 16px; margin-top: 16px; }
        .stat-box { flex: 1; background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; }
        .stat-number { font-size: 28px; font-weight: 700; color: #667eea; }
        .stat-label { font-size: 13px; color: #666; margin-top: 4px; }
        
        /* 日志样式 */
        .log-container { max-height: 400px; overflow-y: auto; background: #1e1e1e; border-radius: 8px; padding: 16px; font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; }
        .log-entry { padding: 6px 0; border-bottom: 1px solid #333; display: flex; gap: 12px; }
        .log-entry:last-child { border-bottom: none; }
        .log-timestamp { color: #888; min-width: 160px; flex-shrink: 0; }
        .log-level { min-width: 60px; flex-shrink: 0; font-weight: 600; }
        .log-level.DEBUG { color: #8854d0; }
        .log-level.INFO { color: #3b82f6; }
        .log-level.WARNING { color: #f59e0b; }
        .log-level.ERROR { color: #ef4444; }
        .log-message { color: #e0e0e0; flex: 1; word-break: break-all; }
        .log-filters { display: flex; gap: 8px; margin-bottom: 16px; }
        .log-filter-btn { padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; border: 1px solid #e5e7eb; background: white; }
        .log-filter-btn.active { background: #667eea; color: white; border-color: #667eea; }
        .log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .log-clear-btn { padding: 6px 12px; background: #f3f4f6; border: none; border-radius: 4px; font-size: 12px; cursor: pointer; color: #666; }
        .log-clear-btn:hover { background: #e5e7eb; }
        .log-stats { font-size: 12px; color: #666; }
        
        @media (max-width: 768px) {
            .btn-group { flex-direction: column; }
            .btn { width: 100%; }
            .log-timestamp { min-width: 100px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐟 闲鱼自动回复助手</h1>
            <p>智能客服系统 - 自动回复买家消息</p>
        </div>
        
        <div class="card">
            <div class="card-title">服务状态</div>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">连接状态</div>
                    <div class="status-value" id="status-connected">
                        <span class="status-dot" id="status-dot"></span>
                        <span id="status-text">未连接</span>
                    </div>
                </div>
                <div class="status-item">
                    <div class="status-label">Token状态</div>
                    <div class="status-value" id="status-token">未验证</div>
                </div>
                <div class="status-item">
                    <div class="status-label">心跳状态</div>
                    <div class="status-value" id="status-heartbeat">无数据</div>
                </div>
                <div class="status-item">
                    <div class="status-label">运行时间</div>
                    <div class="status-value" id="status-uptime">未启动</div>
                </div>
            </div>
            <div class="stats-row">
                <div class="stat-box">
                    <div class="stat-number" id="stat-messages">0</div>
                    <div class="stat-label">消息处理</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="stat-conversations">0</div>
                    <div class="stat-label">活跃会话</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="stat-manual">0</div>
                    <div class="stat-label">人工接管</div>
                </div>
            </div>
            <div class="btn-group" style="margin-top: 20px;">
                <button class="btn btn-primary" onclick="refreshStatus()">刷新状态</button>
                <button class="btn btn-secondary" onclick="location.reload()">重新加载</button>
                <button class="btn btn-danger" onclick="stopService()">停止服务</button>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">系统配置</div>
            <form id="config-form">
                <div class="form-group">
                    <label>API Key <span>*</span></label>
                    <input type="password" id="API_KEY" placeholder="请输入通义千问API密钥">
                    <div class="help-text">从阿里云百炼平台获取</div>
                </div>
                
                <div class="form-group">
                    <label>Cookie字符串 <span>*</span></label>
                    <textarea id="COOKIES_STR" placeholder="请粘贴闲鱼网站的Cookie"></textarea>
                    <div class="help-text">登录闲鱼后，从浏览器开发者工具获取</div>
                </div>
                
                <div class="form-group">
                    <label>模型接口地址</label>
                    <input type="text" id="MODEL_BASE_URL" placeholder="模型API地址">
                    <div class="help-text">默认: https://dashscope.aliyuncs.com/compatible-mode/v1</div>
                </div>
                
                <div class="form-group">
                    <label>模型名称</label>
                    <input type="text" id="MODEL_NAME" placeholder="模型名称">
                    <div class="help-text">默认: qwen-max</div>
                </div>
                
                <div class="form-group">
                    <label>人工接管关键词</label>
                    <input type="text" id="TOGGLE_KEYWORDS" placeholder="切换关键词">
                    <div class="help-text">发送此关键词可切换人工/自动模式，默认: 。</div>
                </div>
                
                <div class="form-group">
                    <label>模拟人工输入</label>
                    <select id="SIMULATE_HUMAN_TYPING">
                        <option value="False">否</option>
                        <option value="True">是</option>
                    </select>
                    <div class="help-text">是否模拟人工打字延迟</div>
                </div>
                
                <div class="form-group">
                    <label>心跳间隔(秒)</label>
                    <input type="number" id="HEARTBEAT_INTERVAL" min="5" max="60" placeholder="15">
                    <div class="help-text">WebSocket心跳发送间隔，默认15秒</div>
                </div>
                
                <div class="form-group">
                    <label>Token刷新间隔(秒)</label>
                    <input type="number" id="TOKEN_REFRESH_INTERVAL" min="60" max="7200" placeholder="3600">
                    <div class="help-text">Access Token刷新周期，默认3600秒(1小时)</div>
                </div>
                
                <div class="btn-group">
                    <button type="button" class="btn btn-secondary" onclick="loadConfig()">加载配置</button>
                    <button type="button" class="btn btn-primary" onclick="saveConfig()">保存配置</button>
                </div>
            </form>
        </div>
        
        <div class="card">
            <div class="card-title">使用说明</div>
            <ul style="list-style: none; padding-left: 0;">
                <li style="padding: 10px 0; border-bottom: 1px solid #eee;">
                    <strong>1. 配置API Key</strong><br>
                    访问阿里云百炼平台获取API密钥，填入配置表单。
                </li>
                <li style="padding: 10px 0; border-bottom: 1px solid #eee;">
                    <strong>2. 获取Cookie（推荐使用Chrome扩展）</strong><br>
                    <button class="btn btn-primary" onclick="showExtensionGuide()" style="margin-top: 8px; padding: 8px 16px; font-size: 13px;">
                        📦 查看Chrome扩展安装指南
                    </button>
                </li>
                <li style="padding: 10px 0; border-bottom: 1px solid #eee;">
                    <strong>3. 保存配置</strong><br>
                    点击"保存配置"按钮，配置会自动保存到.env文件。
                </li>
                <li style="padding: 10px 0;">
                    <strong>4. 人工接管</strong><br>
                    在闲鱼聊天窗口发送"。"(默认关键词)即可切换人工接管模式，再次发送可恢复自动回复。
                </li>
            </ul>
        </div>
        
        <div class="card" id="extension-guide" style="display: none;">
            <div class="card-title">Chrome扩展安装指南</div>
            <div style="padding: 20px; background: #f8f9fa; border-radius: 12px;">
                <h3 style="color: #667eea; margin-bottom: 16px;">🎯 为什么使用Chrome扩展？</h3>
                <p style="color: #555; line-height: 1.8; margin-bottom: 16px;">
                    Chrome扩展可以一键获取Cookie，无需手动复制粘贴，操作更加简单便捷！
                </p>
                
                <h3 style="color: #667eea; margin-bottom: 16px;">📝 安装步骤：</h3>
                <ol style="color: #555; line-height: 2; padding-left: 20px; margin-bottom: 16px;">
                    <li>打开Chrome浏览器，在地址栏输入 <code style="background: #e5e7eb; padding: 2px 6px; border-radius: 4px;">chrome://extensions/</code></li>
                    <li>在页面右上角打开"开发者模式"开关</li>
                    <li>点击"加载已解压的扩展程序"按钮</li>
                    <li>选择项目中的 <code style="background: #e5e7eb; padding: 2px 6px; border-radius: 4px;">chrome-extension</code> 文件夹</li>
                    <li>扩展图标会出现在Chrome工具栏中</li>
                </ol>
                
                <h3 style="color: #667eea; margin-bottom: 16px;">✨ 使用方法：</h3>
                <ol style="color: #555; line-height: 2; padding-left: 20px; margin-bottom: 16px;">
                    <li>打开闲鱼网站并登录账号</li>
                    <li>点击Chrome工具栏中的扩展图标</li>
                    <li>点击"获取Cookie"按钮</li>
                    <li>点击"打开配置页面"，Cookie会自动填充</li>
                </ol>
                
                <div style="background: #dcfce7; border-left: 4px solid #10b981; padding: 12px; border-radius: 0 8px 8px 0; margin-top: 16px;">
                    <strong style="color: #166534;">💡 提示：</strong>
                    <span style="color: #166534;">扩展会自动复制Cookie到剪贴板，也可以手动复制粘贴到配置页面。</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📋 服务日志</div>
            <div class="log-header">
                <div class="log-filters">
                    <button class="log-filter-btn active" onclick="filterLogs('all')">全部</button>
                    <button class="log-filter-btn" onclick="filterLogs('DEBUG')">DEBUG</button>
                    <button class="log-filter-btn" onclick="filterLogs('INFO')">INFO</button>
                    <button class="log-filter-btn" onclick="filterLogs('WARNING')">WARNING</button>
                    <button class="log-filter-btn" onclick="filterLogs('ERROR')">ERROR</button>
                </div>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <span class="log-stats" id="log-stats">共 0 条日志</span>
                    <button class="log-clear-btn" onclick="clearLogs()">清空日志</button>
                    <button class="log-clear-btn" onclick="refreshLogs()" style="background: #667eea; color: white;">🔄 刷新</button>
                </div>
            </div>
            <div class="log-container" id="log-container">
                <div style="color: #888; text-align: center; padding: 40px;">暂无日志</div>
            </div>
        </div>
        
    </div>

    <script>
        let statusInterval;
        let extensionGuideVisible = false;
        
        function showExtensionGuide() {
            const guide = document.getElementById('extension-guide');
            if (extensionGuideVisible) {
                guide.style.display = 'none';
                extensionGuideVisible = false;
            } else {
                guide.style.display = 'block';
                extensionGuideVisible = true;
                guide.scrollIntoView({ behavior: 'smooth' });
            }
        }
        
        function showAlert(message, type = 'info') {
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            document.querySelector('.container').insertBefore(alert, document.querySelector('.card'));
            setTimeout(() => alert.remove(), 3000);
        }
        
        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                const config = await response.json();
                
                Object.keys(config).forEach(key => {
                    const element = document.getElementById(key);
                    if (element) {
                        element.value = config[key];
                    }
                });
                showAlert('配置加载成功', 'success');
            } catch (error) {
                showAlert('加载配置失败: ' + error.message, 'error');
            }
        }
        
        async function saveConfig() {
            const config = {};
            const fields = ['API_KEY', 'COOKIES_STR', 'MODEL_BASE_URL', 'MODEL_NAME', 
                           'TOGGLE_KEYWORDS', 'SIMULATE_HUMAN_TYPING', 'HEARTBEAT_INTERVAL', 'TOKEN_REFRESH_INTERVAL'];
            
            fields.forEach(key => {
                const element = document.getElementById(key);
                if (element) {
                    config[key] = element.value;
                }
            });
            
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await response.json();
                
                if (result.success) {
                    showAlert('配置保存成功，请重启服务使配置生效', 'success');
                } else {
                    showAlert('保存失败: ' + result.message, 'error');
                }
            } catch (error) {
                showAlert('保存配置失败: ' + error.message, 'error');
            }
        }
        
        async function refreshStatus() {
            await fetchStatus();
        }
        
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                
                // 更新连接状态
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                if (status.connected) {
                    dot.className = 'status-dot connected';
                    text.textContent = '已连接';
                    text.className = 'status-connected';
                } else {
                    dot.className = 'status-dot disconnected';
                    text.textContent = '未连接';
                    text.className = 'status-disconnected';
                }
                
                // 更新Token状态
                document.getElementById('status-token').textContent = status.token_valid ? '有效' : '无效';
                document.getElementById('status-token').className = status.token_valid ? 'status-value status-connected' : 'status-value status-disconnected';
                
                // 更新心跳状态
                document.getElementById('status-heartbeat').textContent = status.heartbeat_status;
                document.getElementById('status-heartbeat').className = 
                    status.heartbeat_status === '正常' ? 'status-value status-connected' :
                    status.heartbeat_status === '警告' ? 'status-value status-warning' : 'status-value';
                
                // 更新运行时间
                document.getElementById('status-uptime').textContent = status.uptime;
                
                // 更新统计数据
                document.getElementById('stat-messages').textContent = status.message_count || 0;
                document.getElementById('stat-conversations').textContent = status.active_conversations || 0;
                document.getElementById('stat-manual').textContent = (status.manual_mode_conversations || []).length;
                
            } catch (error) {
                console.error('获取状态失败:', error);
            }
        }
        
        async function stopService() {
            if (confirm('确定要停止服务吗？')) {
                try {
                    const response = await fetch('/api/stop', { method: 'POST' });
                    const result = await response.json();
                    if (result.success) {
                        showAlert('服务已停止', 'info');
                        fetchStatus();
                    }
                } catch (error) {
                    showAlert('停止服务失败', 'error');
                }
            }
        }
        
        // 日志相关变量
        let currentLogLevel = 'all';
        let logInterval;
        
        async function fetchLogs() {
            try {
                const response = await fetch(`/api/logs?level=${currentLogLevel}&limit=100`);
                const data = await response.json();
                displayLogs(data.logs);
                document.getElementById('log-stats').textContent = `共 ${data.total} 条日志，显示 ${data.displayed} 条`;
            } catch (error) {
                console.error('获取日志失败:', error);
            }
        }
        
        function displayLogs(logs) {
            const container = document.getElementById('log-container');
            
            if (logs.length === 0) {
                container.innerHTML = '<div style="color: #888; text-align: center; padding: 40px;">暂无日志</div>';
                return;
            }
            
            container.innerHTML = logs.map(log => `
                <div class="log-entry">
                    <span class="log-timestamp">${log.timestamp}</span>
                    <span class="log-level ${log.level}">${log.level}</span>
                    <span class="log-message">${escapeHtml(log.message)}</span>
                </div>
            `).join('');
            
            // 自动滚动到底部
            container.scrollTop = container.scrollHeight;
        }
        
        function filterLogs(level) {
            currentLogLevel = level;
            
            // 更新按钮状态
            document.querySelectorAll('.log-filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            fetchLogs();
        }
        
        async function clearLogs() {
            if (confirm('确定要清空所有日志吗？')) {
                try {
                    const response = await fetch('/api/logs/clear', { method: 'POST' });
                    const result = await response.json();
                    if (result.success) {
                        fetchLogs();
                        showAlert('日志已清空', 'success');
                    }
                } catch (error) {
                    showAlert('清空日志失败', 'error');
                }
            }
        }
        
        function refreshLogs() {
            fetchLogs();
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // 页面加载时初始化
        document.addEventListener('DOMContentLoaded', () => {
            loadConfig();
            fetchStatus();
            fetchLogs();
            // 每5秒刷新一次状态和日志
            statusInterval = setInterval(fetchStatus, 5000);
            logInterval = setInterval(fetchLogs, 5000);
        });
        
        // 页面关闭时清除定时器
        window.addEventListener('beforeunload', () => {
            if (statusInterval) clearInterval(statusInterval);
            if (logInterval) clearInterval(logInterval);
        });
    </script>
</body>
</html>
    '''

if __name__ == '__main__':
    run_web_server()
