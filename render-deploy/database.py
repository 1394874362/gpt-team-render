# -*- coding: utf-8 -*-
"""
SQLite数据库管理模块
替代Cloudflare D1
"""
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager

DATABASE_FILE = "gpt_team.db"

@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """初始化数据库表结构"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 管理员表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 账号表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            account_id TEXT NOT NULL,
            authorization_token TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            max_invites INTEGER DEFAULT 8,
            used_invites INTEGER DEFAULT 0,
            rotation_count INTEGER DEFAULT 1,
            current_rotation INTEGER DEFAULT 0,
            check_fail_count INTEGER DEFAULT 0,
            last_check_status TEXT,
            last_check_time TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 邀请链接表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS invite_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            validity_type TEXT NOT NULL,
            max_uses INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 会话表（用于安全邀请）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            account_id INTEGER NOT NULL,
            team_id TEXT NOT NULL,
            token TEXT NOT NULL,
            email TEXT NOT NULL,
            validity_type TEXT NOT NULL,
            promoter_id INTEGER,
            referral_code TEXT,
            link_code TEXT,
            card_key TEXT,
            is_used INTEGER DEFAULT 0,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 邀请记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            account_id INTEGER NOT NULL,
            link_code TEXT,
            card_key TEXT,
            promoter_id INTEGER,
            referral_code TEXT,
            validity_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            expires_at TIMESTAMP,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 推广员表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS promoters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            contact_info TEXT,
            total_invites INTEGER DEFAULT 0,
            active_invites INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 卡密表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_key TEXT UNIQUE NOT NULL,
            validity_type TEXT NOT NULL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            expires_at TIMESTAMP,
            used_by_email TEXT,
            used_account TEXT,
            used_at TIMESTAMP,
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        
        # 创建默认管理员（密码: admin123）
        try:
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                ("admin", password_hash)
            )
            conn.commit()
            print("✅ 创建默认管理员: admin / admin123")
        except sqlite3.IntegrityError:
            print("⚠️ 管理员已存在")
        
        print("✅ 数据库初始化完成")

def generate_random_string(length=8):
    """生成随机字符串"""
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(secrets.choice(chars) for _ in range(length))

def generate_session_id():
    """生成会话ID"""
    return secrets.token_hex(32)

def get_expiry_date(validity_type):
    """计算过期时间"""
    now = datetime.now()
    if validity_type == 'month':
        return now + timedelta(days=30)
    elif validity_type == 'quarter':
        return now + timedelta(days=90)
    elif validity_type == 'year':
        return now + timedelta(days=365)
    elif validity_type == 'permanent':
        return now + timedelta(days=36500)  # 100年
    else:
        return now + timedelta(days=30)

# 数据库操作函数

def get_link_by_code(link_code):
    """根据代码获取链接信息"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM invite_links WHERE link_code = ? AND is_active = 1",
            (link_code,)
        )
        return cursor.fetchone()

def get_available_account():
    """获取可用账号"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts 
            WHERE is_active = 1 AND check_fail_count < 3
            ORDER BY used_invites ASC, RANDOM() 
            LIMIT 1
        """)
        return cursor.fetchone()

def create_session(account_id, team_id, token, email, validity_type, link_code=None, promoter_id=None, referral_code=None):
    """创建会话"""
    session_id = generate_session_id()
    expires_at = datetime.now() + timedelta(minutes=5)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions 
            (session_id, account_id, team_id, token, email, validity_type, 
             link_code, promoter_id, referral_code, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, account_id, team_id, token, email, validity_type,
              link_code, promoter_id, referral_code, expires_at))
        conn.commit()
    
    return session_id

def get_session(session_id):
    """获取会话信息"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()

def mark_session_used(session_id):
    """标记会话已使用"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET is_used = 1 WHERE session_id = ?",
            (session_id,)
        )
        conn.commit()

def update_link_usage(link_code):
    """更新链接使用次数"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE invite_links SET used_count = used_count + 1 WHERE link_code = ?",
            (link_code,)
        )
        conn.commit()

def create_invitation_record(email, account_id, validity_type, link_code=None, 
                            promoter_id=None, referral_code=None, ip_address=None):
    """创建邀请记录"""
    expires_at = get_expiry_date(validity_type)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invitations 
            (email, account_id, link_code, promoter_id, referral_code, 
             validity_type, expires_at, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, account_id, link_code, promoter_id, referral_code,
              validity_type, expires_at, ip_address))
        conn.commit()

def update_account_usage(account_id):
    """更新账号使用次数"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts 
            SET used_invites = used_invites + 1,
                last_check_status = '成功',
                last_check_time = CURRENT_TIMESTAMP,
                check_fail_count = 0
            WHERE id = ?
        """, (account_id,))
        conn.commit()

def cleanup_expired_sessions():
    """清理过期会话"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP")
        conn.commit()

if __name__ == "__main__":
    # 初始化数据库
    init_database()
