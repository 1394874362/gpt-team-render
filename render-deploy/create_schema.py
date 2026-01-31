import d1_client
import time

def init_schema():
    print("🚀 开始初始化数据库 Schema...")
    
    queries = [
        # 1. Accounts 表
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            password TEXT,
            session_token TEXT,
            authorization_token TEXT,
            account_id TEXT,
            is_active INTEGER DEFAULT 1,
            is_team INTEGER DEFAULT 0,
            plan_type TEXT,
            expires_at TEXT,
            used_invites INTEGER DEFAULT 0,
            max_invites INTEGER DEFAULT 100,
            check_fail_count INTEGER DEFAULT 0,
            last_check_status TEXT,
            last_check_time TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """,
        
        # 2. Invitations 表
        """
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            account_id TEXT,
            link_code TEXT,
            card_key TEXT,
            promoter_id INTEGER,
            referral_code TEXT,
            validity_type TEXT,
            status TEXT DEFAULT 'active',
            expires_at TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """,
        
        # 3. Sessions 表 (用于安全邀请)
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            account_id INTEGER,
            team_id TEXT,
            token TEXT,
            email TEXT,
            validity_type TEXT,
            promoter_id INTEGER,
            referral_code TEXT,
            link_code TEXT,
            card_key TEXT,
            is_used INTEGER DEFAULT 0,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """,
        
         # 4. Invite Links 表
        """
        CREATE TABLE IF NOT EXISTS invite_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            link_code TEXT UNIQUE NOT NULL,
            validity_type TEXT,
            max_uses INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            tg_check_required INTEGER DEFAULT 0,
            tg_group_id TEXT,
            tg_bot_username TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """,

        # 5. Cards 表
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_key TEXT UNIQUE NOT NULL,
            validity_type TEXT,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            used_by_email TEXT,
            used_account TEXT,
            used_at TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """,
        
        # 6. Promoters 表
        """
        CREATE TABLE IF NOT EXISTS promoters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            total_invites INTEGER DEFAULT 0,
            active_invites INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    ]
    
    for i, sql in enumerate(queries):
        print(f"Executing query {i+1}/{len(queries)}...")
        # 简单的去除换行和多余空格，避免 potential issue
        clean_sql = " ".join(sql.split())
        result = d1_client.query_d1(clean_sql)
        if result is None:
             print(f"⚠️ Query {i+1} failed (Result is None, might be error or just no rows returned for CREATE)")
        time.sleep(1)

    print("✅ Schema 初始化完成 (请检查是否有错误日志)")

if __name__ == "__main__":
    init_schema()
