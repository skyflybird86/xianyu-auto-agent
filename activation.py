#!/usr/bin/env python3
"""
激活码验证模块
用于验证用户购买时获得的激活码
"""

import os
import hashlib
import json
from datetime import datetime, timedelta

# 激活码存储文件
ACTIVATION_FILE = "data/activation.json"

# 预定义的有效激活码（示例，实际使用时应从后端验证）
VALID_ACTIVATION_CODES = [
    "XY2026-AAAA-BBBB-CCCC",
    "XY2026-DDDD-EEEE-FFFF",
    "XY2026-GGGG-HHHH-IIII",
    "XY2026-JJJJ-KKKK-LLLL",
    "XY2026-MMMM-NNNN-OOOO",
]

def generate_activation_code(prefix="XY2026"):
    """生成新的激活码"""
    import random
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    part1 = "".join(random.choice(chars) for _ in range(4))
    part2 = "".join(random.choice(chars) for _ in range(4))
    part3 = "".join(random.choice(chars) for _ in range(4))
    return f"{prefix}-{part1}-{part2}-{part3}"

def is_activated():
    """检查是否已经激活"""
    if not os.path.exists(ACTIVATION_FILE):
        return False
    
    try:
        with open(ACTIVATION_FILE, "r") as f:
            data = json.load(f)
            if data.get("activated", False) and data.get("expire_date"):
                expire_date = datetime.fromisoformat(data["expire_date"])
                if expire_date > datetime.now():
                    return True
    except Exception:
        pass
    
    return False

def activate(code):
    """验证激活码并激活"""
    # 去除空格并转大写
    code = code.strip().upper()
    
    # 验证激活码
    if code in VALID_ACTIVATION_CODES:
        # 生成唯一的机器标识（基于MAC地址或其他硬件信息）
        machine_id = get_machine_id()
        
        # 创建激活记录
        data = {
            "activated": True,
            "activation_code": code,
            "machine_id": machine_id,
            "activate_date": datetime.now().isoformat(),
            "expire_date": (datetime.now() + timedelta(days=365)).isoformat()  # 有效期1年
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(ACTIVATION_FILE), exist_ok=True)
        
        # 保存激活信息
        with open(ACTIVATION_FILE, "w") as f:
            json.dump(data, f, indent=2)
        
        return True, "激活成功！"
    
    return False, "无效的激活码，请联系客服获取"

def get_machine_id():
    """获取机器唯一标识"""
    try:
        import uuid
        return str(uuid.getnode())
    except:
        # 如果无法获取硬件信息，使用随机生成的唯一ID
        return hashlib.md5(os.urandom(16)).hexdigest()

def show_activation_prompt(code=None):
    """显示激活码输入提示"""
    print("=========================================")
    print("       闲鱼自动回复机器人 - 激活验证")
    print("=========================================")
    print("")
    print("请输入您的激活码：")
    print("格式：XY2026-XXXX-XXXX-XXXX")
    print("")
    
    max_attempts = 3
    for attempt in range(max_attempts):
        # 如果已经提供了激活码，直接使用
        if code:
            input_code = code
        else:
            input_code = input(f"激活码 ({attempt + 1}/{max_attempts}): ").strip()
        
        if input_code:
            success, message = activate(input_code)
            if success:
                print("")
                print("✅ " + message)
                print("")
                return True
            else:
                print("❌ " + message)
                print("")
                code = None  # 重置，让用户重新输入
    
    print("💔 激活失败，程序将退出")
    print("请联系客服获取有效的激活码")
    return False

def main():
    """命令行工具入口"""
    import argparse
    parser = argparse.ArgumentParser(description="激活码管理工具")
    parser.add_argument("--check", action="store_true", help="检查激活状态")
    parser.add_argument("--generate", action="store_true", help="生成新激活码")
    parser.add_argument("--reset", action="store_true", help="重置激活状态")
    parser.add_argument("--code", type=str, help="直接提供激活码")
    
    args = parser.parse_args()
    
    if args.check:
        if is_activated():
            print("✅ 已激活")
        else:
            print("❌ 未激活")
    elif args.generate:
        code = generate_activation_code()
        print(f"生成的激活码: {code}")
    elif args.reset:
        if os.path.exists(ACTIVATION_FILE):
            os.remove(ACTIVATION_FILE)
            print("✅ 已重置激活状态")
        else:
            print("⚠️  没有激活记录")
    elif args.code:
        success, message = activate(args.code)
        if success:
            print(f"✅ {message}")
            exit(0)
        else:
            print(f"❌ {message}")
            exit(1)
    else:
        # 尝试从标准输入读取激活码（用于管道输入）
        import sys
        if not sys.stdin.isatty():
            code = sys.stdin.read().strip()
            if code:
                success, message = activate(code)
                if success:
                    print(f"✅ {message}")
                    exit(0)
                else:
                    print(f"❌ {message}")
                    exit(1)
        # 显示交互式输入提示
        if not show_activation_prompt():
            exit(1)

if __name__ == "__main__":
    main()
