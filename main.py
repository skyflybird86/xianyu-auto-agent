#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import asyncio
import time
import os
import websockets
import threading
from loguru import logger
from dotenv import load_dotenv, set_key
from XianyuApis import XianyuApis
import sys
import random
from utils.xianyu_utils import generate_mid, generate_uuid, trans_cookies, generate_device_id, decrypt
from XianyuAgent import XianyuReplyBot
from context_manager import ChatContextManager
from shared_state import update_status, get_status, add_log, log_with_web

# 全局服务状态（如果shared_state不可用）
try:
    from shared_state import service_status, add_log
    USE_SHARED_STATE = True
except ImportError:
    USE_SHARED_STATE = False
    service_status = {
        'connected': False,
        'last_heartbeat': 0,
        'token_valid': False,
        'service_running': False,
        'service_status': 'stopped',
        'message_count': 0,
        'active_conversations': 0,
        'start_time': time.time(),
    }

# 全局变量
websocket_server = None
bot = None
chat_context = None
running = False

def load_env_config():
    """从.env加载配置"""
    required_vars = [
        "API_KEY", "COOKIES_STR", "XIANYU_URL",
        "XIANYU_WS_URL", "MODEL_API_BASE", "MODEL_NAME"
    ]
    
    config = {}
    for var in required_vars:
        config[var] = os.getenv(var, "")
    
    return config

def check_and_complete_env():
    """检查并补全配置"""
    config = load_env_config()
    
    # 需要交互式输入的配置项
    need_input = {}
    
    for key, value in config.items():
        if not value:
            need_input[key] = ""
    
    if not need_input:
        return False  # 不需要更新
    
    print("=========================================")
    print("         配置参数输入")
    print("=========================================")
    print("提示: 输入完成后按回车键确认")
    print("")
    
    updated = False
    max_attempts = 3
    
    for key in need_input.keys():
        attempts = 0
        while attempts < max_attempts:
            try:
                # 提示语
                prompt = {
                    "API_KEY": "请输入API Key: ",
                    "COOKIES_STR": "请输入Cookie字符串: ",
                    "XIANYU_URL": "请输入闲鱼API地址: ",
                    "XIANYU_WS_URL": "请输入WebSocket地址: ",
                    "MODEL_API_BASE": "请输入模型API地址: ",
                    "MODEL_NAME": "请输入模型名称: "
                }.get(key, f"请输入{key}: ")
                
                value = input(prompt).strip()
                
                if value:
                    set_key(".env", key, value)
                    os.environ[key] = value
                    updated = True
                    break
                else:
                    attempts += 1
                    if attempts < max_attempts:
                        print(f"❌ 输入不能为空，请重新输入 (剩余 {max_attempts - attempts} 次机会)")
                    else:
                        print(f"❌ 输入次数已用尽，程序将退出")
                        sys.exit(1)
                        
            except KeyboardInterrupt:
                print("")
                print("❌ 用户中断，程序退出")
                sys.exit(1)
            except Exception as e:
                attempts += 1
                print(f"❌ 输入错误: {e} (剩余 {max_attempts - attempts} 次机会)")

    if updated:
        print("=========================================")
        logger.info("新的配置已保存/更新至 .env 文件中")
        print("")
    
    return updated

async def listen_messages(api):
    """监听消息"""
    global running, bot, chat_context
    
    device_id = generate_device_id()
    device_id_str = device_id.upper().replace("-", "").upper()
    
    ws_url = os.getenv("XIANYU_WS_URL", "wss://112.124.21.187/gateway/api/ws/v2/connect")
    
    # 构建ws连接的headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 DingTalk(2.1.5)',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Sec-WebSocket-Extensions': 'permessage-deflate',
        'Sec-WebSocket-Key': base64.b64encode(os.urandom(16)).decode('utf-8'),
        'Sec-WebSocket-Version': '13'
    }
    
    # 连接WebSocket
    while running:
        try:
            logger.info("正在连接WebSocket...")
            update_status('connected', False)
            async with websockets.connect(ws_url, extra_headers=headers, ping_interval=30, ping_timeout=10) as ws:
                logger.info("✅ WebSocket已连接")
                update_status('connected', True)
                add_log("INFO", "WebSocket已连接")
                
                await send_heartbeat(ws, api)
                
                # 监听消息
                async for message in ws:
                    if not running:
                        break
                    await handle_message(message, api, ws)
                    
        except Exception as e:
            if not running:
                break
            logger.error(f"WebSocket连接错误: {e}")
            add_log("ERROR", f"WebSocket连接错误: {e}")
            update_status('connected', False)
            time.sleep(5)

async def handle_message(message, api, ws):
    """处理收到的消息"""
    try:
        if isinstance(message, bytes):
            message = message.decode('utf-8')
        
        logger.debug(f"收到消息: {message[:200]}...")
        
        # 心跳响应
        if 'heartbeat' in message.lower():
            await handle_heartbeat_response(message)
            return
        
        # 解析消息
        try:
            data = json.loads(message)
        except:
            # 可能是base64编码的
            try:
                decoded = base64.b64decode(message)
                data = json.loads(decoded.decode('utf-8'))
            except:
                return
        
        # 处理消息
        if 'data' in data and isinstance(data['data'], list):
            for item in data['data']:
                await process_single_message(item, api)
                
    except Exception as e:
        logger.error(f"处理消息时发生错误: {e}")
        import traceback
        logger.debug(traceback.format_exc())

async def process_single_message(item, api):
    """处理单条消息"""
    global bot, chat_context
    
    try:
        biz_type = item.get('bizType', '')
        
        if biz_type == 40:  # 聊天消息
            content = item.get('data', '')
            
            if not content:
                return
            
            # 解码消息内容
            try:
                decoded_content = base64.b64decode(content)
                message_data = json.loads(decoded_content.decode('utf-8'))
            except:
                return
            
            # 提取消息信息
            sender_id = message_data.get('senderUserId', '')
            conversation_id = message_data.get('conversationId', '')
            text = message_data.get('text', {}).get('text', '')
            item_id = message_data.get('itemId', '')
            
            if not text:
                return
            
            # 更新统计
            update_status('message_count', service_status.get('message_count', 0) + 1)
            update_status('active_conversations', len(chat_context.get_active_conversations()))
            
            logger.info(f"用户: {sender_id}, 商品: {item_id}, 会话: {conversation_id}, 消息: {text}")
            add_log("INFO", f"收到消息: {text}")
            
            # 保存上下文
            chat_context.add_user_message(conversation_id, text)
            
            # 获取商品信息
            if item_id:
                try:
                    item_info = api.get_item_info(item_id)
                    if item_info:
                        chat_context.set_item_info(conversation_id, item_info)
                        logger.debug(f"商品信息已保存: {item_id}")
                except Exception as e:
                    logger.error(f"获取商品信息失败: {e}")
            
            # 生成回复
            try:
                reply = bot.generate_reply(conversation_id, text, item_id)
                if reply:
                    await send_reply(api, conversation_id, sender_id, reply)
                    chat_context.add_bot_message(conversation_id, reply)
                    logger.info(f"回复: {reply}")
                    add_log("INFO", f"发送回复: {reply}")
            except Exception as e:
                logger.error(f"生成回复失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                
    except Exception as e:
        logger.error(f"处理单条消息时发生错误: {e}")

async def send_reply(api, conversation_id, receiver_id, text):
    """发送回复"""
    try:
        # 调用API发送消息
        result = api.send_message(receiver_id, conversation_id, text)
        
        if result.get('success', False):
            logger.debug(f"消息发送成功: {text}")
        else:
            logger.error(f"消息发送失败: {result.get('message', '未知错误')}")
            
    except Exception as e:
        logger.error(f"发送回复时发生错误: {e}")

async def send_heartbeat(ws, api):
    """发送心跳"""
    global running
    
    while running:
        try:
            device_id = generate_device_id()
            heartbeat_data = {
                "type": "heartbeat",
                "deviceId": device_id,
                "timestamp": int(time.time() * 1000)
            }
            
            await ws.send(json.dumps(heartbeat_data))
            logger.debug("心跳包已发送")
            update_status('last_heartbeat', time.time())
            
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
            
        await asyncio.sleep(30)

async def handle_heartbeat_response(response):
    """处理心跳响应"""
    try:
        logger.debug(f"收到心跳响应: {response[:100]}")
        update_status('last_heartbeat', time.time())
    except Exception as e:
        logger.error(f"处理心跳响应失败: {e}")

def start_service():
    """启动服务"""
    global running, bot, chat_context, websocket_server
    
    try:
        if running:
            return False, "服务已在运行中"
        
        config = load_env_config()
        
        # 检查必要配置
        if not config.get('COOKIES_STR'):
            return False, "请先配置Cookie"
        if not config.get('API_KEY'):
            return False, "请先配置API Key"
        
        # 解析Cookie
        cookies = trans_cookies(config['COOKIES_STR'])
        
        # 验证Cookie
        if not cookies or 'unb' not in cookies:
            return False, "Cookie中缺少必要的'unb'字段，请检查Cookie是否正确获取"
        
        # 初始化组件
        api = XianyuApis(config['XIANYU_URL'], cookies)
        bot = XianyuReplyBot(config['API_KEY'], config['MODEL_NAME'], config['MODEL_API_BASE'])
        chat_context = ChatContextManager()
        
        # 验证Token
        logger.info("正在验证Token...")
        token_valid = api.check_token_validity()
        update_status('token_valid', token_valid)
        
        if not token_valid:
            logger.warning("Token验证失败，请检查API Key或Cookie")
            add_log("WARNING", "Token验证失败，请检查API Key或Cookie")
        else:
            logger.info("✅ Token验证成功")
            add_log("INFO", "Token验证成功")
        
        # 启动服务
        running = True
        update_status('service_running', True)
        update_status('service_status', 'running')
        update_status('message_count', 0)
        
        # 在后台线程运行WebSocket
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(listen_messages(api))
            except Exception as e:
                logger.error(f"Async loop error: {e}")
                loop.close()
        
        websocket_server = threading.Thread(target=run_async, daemon=True)
        websocket_server.start()
        
        add_log("INFO", "服务已启动")
        return True, "服务启动成功"
        
    except Exception as e:
        logger.error(f"启动服务失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        add_log("ERROR", f"启动服务失败: {e}")
        return False, f"启动服务失败: {e}"

def stop_service():
    """停止服务"""
    global running, websocket_server
    
    try:
        if not running:
            return False, "服务未在运行"
        
        running = False
        update_status('service_running', False)
        update_status('service_status', 'stopped')
        update_status('connected', False)
        add_log("INFO", "服务已停止")
        
        return True, "服务停止成功"
        
    except Exception as e:
        logger.error(f"停止服务失败: {e}")
        add_log("ERROR", f"停止服务失败: {e}")
        return False, f"停止服务失败: {e}"

def restart_service():
    """重启服务"""
    try:
        success, message = stop_service()
        if not success:
            return False, message
            
        time.sleep(1)
        
        return start_service()
        
    except Exception as e:
        logger.error(f"重启服务失败: {e}")
        add_log("ERROR", f"重启服务失败: {e}")
        return False, f"重启服务失败: {e}"

def start_web_server():
    """启动Web服务器"""
    from web_server import run_web_server, update_status as web_update_status, get_status as web_get_status
    
    def sync_status():
        """同步状态到web_server"""
        while True:
            try:
                for key, value in service_status.items():
                    web_update_status(key, value)
            except Exception as e:
                pass
            time.sleep(1)
    
    # 启动状态同步线程
    sync_thread = threading.Thread(target=sync_status, daemon=True)
    sync_thread.start()
    
    # 启动Web服务器
    run_web_server(port=8080)


if __name__ == '__main__':
    if os.path.exists(".env"):
        load_dotenv()
        logger.info("已加载 .env 配置")
    
    if os.path.exists(".env.example"):
        load_dotenv(".env.example")
        logger.info("已加载 .env.example 默认配置")
    
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.info(f"日志级别设置为: {log_level}")

    # 初始化服务状态
    update_status('start_time', time.time())
    update_status('service_running', False)
    update_status('service_status', 'stopped')

    # 启动Web服务器线程
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    logger.info("Web服务器已启动，访问 http://localhost:8080")

    # 保持主进程运行（服务通过Web页面启动）
    while True:
        time.sleep(1)
