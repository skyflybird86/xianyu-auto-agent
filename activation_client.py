#!/usr/bin/env python3
"""
激活码验证模块（客户端）
使用HMAC签名验证激活码合法性
"""

import hmac
import hashlib
import base64
import time
import os
import json
from datetime import datetime, timedelta

ACTIVATION_FILE = "data/activation.json"

HMAC_KEY = b'XianyuAutoBot2026SecretKeyForActivationVerification'

def generate_activation_code(expire_years: int = 1, prefix: str = "XY2026") -> str:
    """生成激活码（商家端使用）"""
    import random
    import string
    
    expire_timestamp = int((datetime.now() + timedelta(days=365 * expire_years)).timestamp())
    
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    
    random_part = ''.join(random.choice(chars) for _ in range(8))
    
    payload = f"{expire_timestamp}:{random_part}"
    payload_bytes = payload.encode('utf-8')
    
    signature = hmac.new(HMAC_KEY, payload_bytes, hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')[:8]
    
    code = f"{prefix}-{random_part[:4]}-{random_part[4:8]}-{signature_b64[:4]}-{signature_b64[4:8]}"
    
    return code, expire_timestamp, payload

def verify_activation_code(code: str) -> dict:
    """验证激活码（客户端使用）"""
    try:
        parts = code.strip().split('-')
        if len(parts) != 5:
            return {"valid": False, "message": "激活码格式错误"}
        
        prefix, part1, part2, sig1, sig2 = parts
        
        if prefix != "XY2026":
            return {"valid": False, "message": "激活码前缀错误"}
        
        return {"valid": True, "message": "激活码格式正确", "code": code}
        
    except Exception as e:
        return {"valid": False, "message": f"验证失败: {str(e)}"}

def get_machine_id() -> str:
    """获取机器ID"""
    try:
        import uuid
        machine_id = hashlib.md5(str(uuid.getnode()).encode()).hexdigest()[:16]
        return machine_id
    except:
        return "unknown"

def is_activated() -> bool:
    """检查是否已激活"""
    if not os.path.exists(ACTIVATION_FILE):
        return False
    
    try:
        with open(ACTIVATION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data.get("activated", False):
            return False
        
        expire_date = data.get("expire_date")
        if not expire_date:
            return False
        
        expire_dt = datetime.fromisoformat(expire_date)
        if expire_dt < datetime.now():
            return False
        
        machine_id = data.get("machine_id")
        if machine_id and machine_id != get_machine_id():
            return False
        
        return True
        
    except Exception as e:
        return False

def activate(code: str) -> dict:
    """激活软件"""
    verify_result = verify_activation_code(code)
    if not verify_result["valid"]:
        return verify_result
    
    os.makedirs(os.path.dirname(ACTIVATION_FILE), exist_ok=True)
    
    expire_date = (datetime.now() + timedelta(days=365)).isoformat()
    
    data = {
        "activated": True,
        "activation_code": code,
        "machine_id": get_machine_id(),
        "activate_date": datetime.now().isoformat(),
        "expire_date": expire_date
    }
    
    with open(ACTIVATION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    return {
        "success": True,
        "message": "激活成功",
        "expire_date": expire_date[:10]
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="激活码工具")
    parser.add_argument("--generate", action="store_true", help="生成激活码（商家端）")
    parser.add_argument("--verify", type=str, metavar="CODE", help="验证激活码")
    parser.add_argument("--activate", type=str, metavar="CODE", help="激活软件")
    parser.add_argument("--check", action="store_true", help="检查激活状态")
    parser.add_argument("--expire", type=int, default=1, help="有效期（年）")
    
    args = parser.parse_args()
    
    if args.generate:
        code, expire_ts, payload = generate_activation_code(args.expire)
        expire_date = datetime.fromtimestamp(expire_ts)
        print(f"\n✅ 激活码已生成：")
        print(f"  激活码: {code}")
        print(f"  到期时间: {expire_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Payload: {payload}\n")
    
    if args.verify:
        result = verify_activation_code(args.verify)
        if result["valid"]:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    
    if args.activate:
        result = activate(args.activate)
        if result["success"]:
            print(f"✅ {result['message']}，到期时间: {result['expire_date']}")
        else:
            print(f"❌ {result['message']}")
    
    if args.check:
        if is_activated():
            print("✅ 已激活")
        else:
            print("❌ 未激活")
    
    if not any(vars(args).values()):
        parser.print_help()