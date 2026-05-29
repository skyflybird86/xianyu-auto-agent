#!/usr/bin/env python3
"""
激活码管理工具（商家端）
用于批量生成和管理激活码
"""

import sqlite3
import os
import random
import string
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "merchant_activation.db")

HMAC_KEY = b'XianyuAutoBot2026SecretKeyForActivationVerification'

def get_db_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化数据库"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            expire_date TEXT NOT NULL,
            created_date TEXT NOT NULL,
            batch_id TEXT,
            remark TEXT,
            activated INTEGER DEFAULT 0,
            activated_date TEXT,
            machine_id TEXT,
            customer_info TEXT,
            status INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT UNIQUE NOT NULL,
            count INTEGER NOT NULL,
            expire_years INTEGER NOT NULL,
            created_date TEXT NOT NULL,
            remark TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

def generate_single_code(expire_years: int = 1) -> tuple:
    """生成单个激活码"""
    expire_timestamp = int((datetime.now() + timedelta(days=365 * expire_years)).timestamp())
    
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    
    random_part = ''.join(random.choice(chars) for _ in range(8))
    
    payload = f"{expire_timestamp}:{random_part}"
    payload_bytes = payload.encode('utf-8')
    
    signature = hmac.new(HMAC_KEY, payload_bytes, hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')[:8]
    
    code = f"XY2026-{random_part[:4]}-{random_part[4:8]}-{signature_b64[:4]}-{signature_b64[4:8]}"
    
    expire_date = datetime.fromtimestamp(expire_timestamp).strftime('%Y-%m-%d')
    
    return code, expire_date, payload

def generate_batch_codes(count: int = 10, expire_years: int = 1,
                         batch_id: str = None, remark: str = "") -> List[Dict[str, Any]]:
    """批量生成激活码"""
    if batch_id is None:
        batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    codes = []
    created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for i in range(count):
        code, expire_date, payload = generate_single_code(expire_years)
        
        try:
            cursor.execute("""
                INSERT INTO activation_codes 
                (code, expire_date, created_date, batch_id, remark)
                VALUES (?, ?, ?, ?, ?)
            """, (code, expire_date, created_date, batch_id, remark))
            
            codes.append({
                "code": code,
                "expire_date": expire_date,
                "created_date": created_date,
                "batch_id": batch_id,
                "payload": payload
            })
        except sqlite3.IntegrityError:
            continue

    cursor.execute("""
        INSERT OR IGNORE INTO batches 
        (batch_id, count, expire_years, created_date, remark)
        VALUES (?, ?, ?, ?, ?)
    """, (batch_id, len(codes), expire_years, created_date, remark))

    conn.commit()
    conn.close()

    return codes

def mark_as_activated(code: str, machine_id: str, customer_info: str = "") -> bool:
    """标记激活码已使用"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE activation_codes
        SET activated = 1, activated_date = ?, machine_id = ?, customer_info = ?
        WHERE code = ? AND activated = 0
    """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), machine_id, customer_info, code))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success

def get_all_codes(page: int = 1, page_size: int = 50,
                  activated: int = None, batch_id: str = None) -> Dict[str, Any]:
    """获取激活码列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    where_clause = "WHERE status = 1"
    params = []

    if activated is not None:
        where_clause += " AND activated = ?"
        params.append(activated)

    if batch_id:
        where_clause += " AND batch_id = ?"
        params.append(batch_id)

    cursor.execute(f"SELECT COUNT(*) as count FROM activation_codes {where_clause}", params)
    total = cursor.fetchone()["count"]

    offset = (page - 1) * page_size
    cursor.execute(f"""
        SELECT * FROM activation_codes
        {where_clause}
        ORDER BY created_date DESC
        LIMIT ? OFFSET ?
    """, params + [page_size, offset])

    rows = cursor.fetchall()
    conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "codes": [dict(row) for row in rows]
    }

def get_stats() -> Dict[str, Any]:
    """获取统计信息"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM activation_codes WHERE status = 1")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as used FROM activation_codes WHERE activated = 1 AND status = 1")
    used = cursor.fetchone()["used"]

    cursor.execute("""
        SELECT COUNT(*) as available FROM activation_codes
        WHERE activated = 0 AND status = 1 AND expire_date >= ?
    """, (datetime.now().strftime('%Y-%m-%d'),))
    available = cursor.fetchone()["available"]

    cursor.execute("SELECT COUNT(*) as expired FROM activation_codes WHERE expire_date < ? AND activated = 0", 
                   (datetime.now().strftime('%Y-%m-%d'),))
    expired = cursor.fetchone()["expired"]

    conn.close()

    return {
        "total": total,
        "used": used,
        "available": available,
        "expired": expired,
        "used_rate": round(used / total * 100, 2) if total > 0 else 0
    }

def export_codes(batch_id: str = None, output_file: str = None) -> str:
    """导出激活码"""
    result = get_all_codes(page=1, page_size=1000, batch_id=batch_id)
    
    if not result["codes"]:
        return "没有可导出的激活码"
    
    if output_file is None:
        output_file = f"activation_codes_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# 激活码导出\n")
        f.write(f"# 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 总数: {len(result['codes'])}\n")
        if batch_id:
            f.write(f"# 批次: {batch_id}\n")
        f.write(f"\n")
        
        for code in result["codes"]:
            status = "已使用" if code["activated"] else "未使用"
            f.write(f"{code['code']} | {code['expire_date']} | {status}\n")
    
    return output_file

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="激活码管理工具（商家端）")
    parser.add_argument("--init", action="store_true", help="初始化数据库")
    parser.add_argument("--generate", type=int, metavar="N", help="生成N个激活码")
    parser.add_argument("--list", action="store_true", help="列出所有激活码")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--export", action="store_true", help="导出激活码")
    parser.add_argument("--batch", type=str, help="批次ID")
    parser.add_argument("--expire", type=int, default=1, help="有效期（年）")
    parser.add_argument("--remark", type=str, default="", help="备注")
    parser.add_argument("--mark-used", type=str, metavar="CODE", help="标记激活码已使用")
    parser.add_argument("--machine-id", type=str, help="机器码")

    args = parser.parse_args()

    if args.init:
        init_database()

    if args.generate:
        codes = generate_batch_codes(
            count=args.generate,
            expire_years=args.expire,
            batch_id=args.batch,
            remark=args.remark
        )
        print(f"\n✅ 成功生成 {len(codes)} 个激活码：")
        print("-" * 60)
        for c in codes:
            print(f"  {c['code']} | 到期: {c['expire_date']}")
        print("-" * 60)
        print(f"批次ID: {codes[0]['batch_id']}\n")

    if args.list:
        result = get_all_codes(page=1, page_size=100, batch_id=args.batch)
        print(f"\n📋 共 {result['total']} 个激活码：")
        print("-" * 80)
        for code in result['codes']:
            status = "✅ 已使用" if code['activated'] else "⭕ 未使用"
            machine = code['machine_id'] or "-"
            print(f"  {code['code']} | {status} | 到期: {code['expire_date']} | 机器码: {machine}")
        print("-" * 80)

    if args.stats:
        stats = get_stats()
        print("\n📊 激活码统计：")
        print(f"  总数: {stats['total']}")
        print(f"  已使用: {stats['used']}")
        print(f"  可用: {stats['available']}")
        print(f"  已过期: {stats['expired']}")
        print(f"  使用率: {stats['used_rate']}%")

    if args.export:
        output = export_codes(batch_id=args.batch)
        print(f"✅ 激活码已导出到: {output}")

    if args.mark_used:
        machine_id = args.machine_id or "unknown"
        success = mark_as_activated(args.mark_used, machine_id)
        if success:
            print(f"✅ 激活码已标记为使用")
        else:
            print(f"❌ 激活码不存在或已使用")

    if not any(vars(args).values()):
        parser.print_help()