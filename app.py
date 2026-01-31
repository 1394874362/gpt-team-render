# -*- coding: utf-8 -*-
import os
import re
import json
import uuid
import threading
from flask import Flask, request, jsonify, send_file, send_from_directory
# from flask_cors import CORS  # 移除此依赖
from curl_cffi import requests as cffi_requests
import telebot


# 导入数据库模块
import database as db
import d1_client  # 导入 D1 客户端

app = Flask(__name__)
# CORS(app)  # 移除此行


# 手动添加CORS支持
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# ================= 🔧 配置区 =================
PORT = int(os.environ.get("PORT", 5000))

# HTTP代理配置（动态IP）
PROXY_HOST = "na.ec39f792e12ce1b7.ipmars.vip"
PROXY_PORT = "4900"
PROXY_USER = "CCCRqQ7zTT-zone-mars-region-US-session-8zHiWYyc-sessTime-2"
PROXY_PASS = "98514780"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

# Telegram Bot 配置
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8153657926:AAFs1MjKEEXrVIOrjn7H6a_DDgmcWMSBT3k")
ADMIN_IDS = [8519872697]  # 管理员用户ID列表
WHITELIST_FILE = "whitelist.json"

# Cloudflare Worker API（用于获取账号token）
WORKER_API = os.environ.get("WORKER_API", "https://gpt-team-api.2804402637.workers.dev")
# ============================================

# 初始化 Telegram Bot
bot = telebot.TeleBot(BOT_TOKEN)

# ================= 白名单管理 =================
def load_whitelist():
    """从文件加载白名单"""
    try:
        if os.path.exists(WHITELIST_FILE):
            with open(WHITELIST_FILE, 'r') as f:
                return set(json.load(f))
    except:
        pass
    return set()

def save_whitelist(whitelist):
    """保存白名单到文件"""
    try:
        with open(WHITELIST_FILE, 'w') as f:
            json.dump(list(whitelist), f)
    except Exception as e:
        print(f"保存白名单失败: {e}")

def is_admin(user_id):
    """检查是否是管理员"""
    return user_id in ADMIN_IDS

def is_whitelisted(user_id):
    """检查用户是否在白名单"""
    return user_id in load_whitelist() or is_admin(user_id)

# 邮箱正则
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# ================= 邀请发送逻辑 =================
def get_team_id_and_send_invite(token, user_email):
    """获取Team ID并发送邀请（和您本地代码一样的逻辑）"""
    print(f"🔄 发送邀请到: {user_email}")
    
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    fake_device_id = str(uuid.uuid4())
    
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "oai-device-id": fake_device_id,
        "oai-language": "en-US",
        "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com"
    }

    try:
        # 步骤1: 获取正确的Team ID
        check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
        check_resp = session.get(check_url, headers=headers, timeout=15)
        
        if check_resp.status_code == 401:
            print(f"❌ Token失效，自动禁用账号...")
            d1_client.query_d1("UPDATE accounts SET is_active = 0, last_check_status = '失效' WHERE authorization_token = ?", [token])
            return False, "Token失效", 401
        if check_resp.status_code == 403:
            # 403 可能是 IP 问题，但也可能是账号问题，保险起见也可以标记，或者只记录
            print(f"❌ IP被封/权限不足 (403)...")
            return False, "IP被封或权限不足", 403
        if check_resp.status_code != 200:
            return False, f"获取Team ID失败: HTTP {check_resp.status_code}", check_resp.status_code
        
        data = check_resp.json()
        accounts_dict = data.get("accounts", {})
        
        # 找Team ID
        team_id = None
        for acc_id, info in accounts_dict.items():
            if acc_id.startswith("org-") or info.get("plan_type") == "team":
                team_id = acc_id
                break
        
        if not team_id and accounts_dict:
            team_id = list(accounts_dict.keys())[0]
        
        if not team_id:
            return False, "该账号没有Team权限", 400
        
        print(f"✅ 获取到Team ID: {team_id}")
        
        # 步骤2: 发送邀请
        headers["chatgpt-account-id"] = team_id
        invite_url = f"https://chatgpt.com/backend-api/accounts/{team_id}/invites"
        payload = {
            "email_addresses": [user_email],
            "role": "standard-user",
            "resend_emails": True
        }
        
        invite_resp = session.post(invite_url, headers=headers, json=payload, timeout=15)
        
        if invite_resp.status_code == 200:
            res_json = invite_resp.json()
            if "account_invites" in res_json or "invites" in res_json:
                d1_client.query_d1("UPDATE accounts SET used_invites = used_invites + 1, last_check_status = '成功', last_check_time = datetime('now') WHERE authorization_token = ?", [token])
                return True, "邀请发送成功", None
            
            err_msg = str(res_json)
            if "max" in err_msg or "limit" in err_msg:
                return False, "Team已满员", 400
            if res_json.get("errored_emails"):
                return False, "邮箱无效或已在Team中", 400
            
            return False, f"API返回异常: {err_msg[:100]}", 400
        else:
            try:
                error_data = invite_resp.json()
                error_msg = error_data.get("detail") or str(error_data)[:100]
            except:
                error_msg = invite_resp.text[:100]
            
            if invite_resp.status_code == 401:
                 print(f"❌ 邀请时Token失效，自动禁用账号...")
                 d1_client.query_d1("UPDATE accounts SET is_active = 0, last_check_status = '失效' WHERE authorization_token = ?", [token])

            return False, f"HTTP {invite_resp.status_code}: {error_msg}", invite_resp.status_code

    except Exception as e:
        return False, f"请求异常: {str(e)}", None

def get_available_token():
    """从 Cloudflare D1 直接获取可用的账号 token，优先使用 invite 次数最少的"""
    try:
        # 使用 d1_client 直接查询 Workers 数据库
        account = d1_client.get_best_account_from_d1()
        
        if account:
            # 兼容处理：D1返回的可能是 'used_invites' 或 'usedInvites' 取决于你的表定义
            name = account.get("name", "Unknown")
            used = account.get("used_invites", 0)
            max_uses = account.get("max_invites", 8)
            
            print(f"✅ [D1实时] 选中最佳账号: {name} (Used: {used}/{max_uses})")
            
            # 确保返回 token
            return account.get("authorization_token")
        else:
            print("❌ [D1实时] 未找到可用账号")
            
    except Exception as e:
        print(f"❌ [D1实时] 获取token失败: {e}")
    return None

# ================= Telegram Bot 指令 =================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    if is_whitelisted(user_id):
        text = """🎉 *欢迎使用 ChatGPT Team 邀请机器人！*

✅ 您已在白名单中，可以直接使用。

*使用方法*：直接发送邮箱地址即可获取 Team 邀请。

例如：`test@gmail.com`"""
    else:
        text = """👋 *欢迎使用 ChatGPT Team 邀请机器人！*

⚠️ 您暂未获得使用权限，请联系管理员添加白名单。

您的用户ID：`{}`""".format(user_id)
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['add'])
def cmd_add(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ 您没有管理员权限")
        return
    
    try:
        args = message.text.split()[1:]
        if not args:
            bot.reply_to(message, "用法：`/add <用户ID>`\n例如：`/add 123456789`", parse_mode='Markdown')
            return
        
        target_id = int(args[0])
        whitelist = load_whitelist()
        whitelist.add(target_id)
        save_whitelist(whitelist)
        
        bot.reply_to(message, f"✅ 已添加用户 `{target_id}` 到白名单", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ 用户ID必须是数字")
    except Exception as e:
        bot.reply_to(message, f"❌ 操作失败: {e}")

@bot.message_handler(commands=['remove'])
def cmd_remove(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ 您没有管理员权限")
        return
    
    try:
        args = message.text.split()[1:]
        if not args:
            bot.reply_to(message, "用法：`/remove <用户ID>`", parse_mode='Markdown')
            return
        
        target_id = int(args[0])
        whitelist = load_whitelist()
        if target_id in whitelist:
            whitelist.remove(target_id)
            save_whitelist(whitelist)
            bot.reply_to(message, f"✅ 已从白名单移除用户 `{target_id}`", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"⚠️ 用户 `{target_id}` 不在白名单中", parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ 用户ID必须是数字")
    except Exception as e:
        bot.reply_to(message, f"❌ 操作失败: {e}")

@bot.message_handler(commands=['list'])
def cmd_list(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ 您没有管理员权限")
        return
    
    whitelist = load_whitelist()
    if whitelist:
        user_list = '\n'.join([f"• `{uid}`" for uid in sorted(whitelist)])
        bot.reply_to(message, f"📋 *白名单用户*（共 {len(whitelist)} 人）：\n\n{user_list}", parse_mode='Markdown')
    else:
        bot.reply_to(message, "📋 白名单为空")

@bot.message_handler(func=lambda m: EMAIL_REGEX.match(m.text.strip()) if m.text else False)
def handle_email(message):
    user_id = message.from_user.id
    email = message.text.strip().lower()
    
    # 检查白名单
    if not is_whitelisted(user_id):
        bot.reply_to(message, "❌ 您没有使用权限，请联系管理员添加白名单。\n\n您的用户ID：`{}`".format(user_id), parse_mode='Markdown')
        return
    
    # 发送处理中提示
    processing_msg = bot.reply_to(message, f"⏳ 正在发送邀请到 `{email}`...", parse_mode='Markdown')
    
    max_retries = 3
    attempt = 0
    final_result_text = ""
    
    try:
        while attempt < max_retries:
            attempt += 1
            # 获取可用 token
            token = get_available_token()
            if not token:
                bot.edit_message_text("❌ 暂无可用账号，请稍后再试", 
                                    message.chat.id, processing_msg.message_id)
                return
            
            # 发送邀请
            success, msg, status_code = get_team_id_and_send_invite(token, email)
            
            if success:
                final_result_text = f"✅ 邀请发送成功！\n\n📧 邮箱：`{email}`\n\n请查收邮件并点击邀请链接加入 Team。"
                break
            else:
                if status_code == 401:
                    print(f"⚠️ 尝试 {attempt}/{max_retries} 失败: Token失效，已自动禁用账号，重试中...")
                    continue # Token失效，重试，此时旧Token已被禁用，将获取新Token
                else:
                    final_result_text = f"❌ 邀请发送失败\n\n📧 邮箱：`{email}`\n原因：{msg}"
                    break # 其他错误（如Team已满，邮箱无效等），不重试
        
        if not final_result_text:
             final_result_text = f"❌ 连续 {max_retries} 次尝试失败，请检查账号池是否耗尽。"
        
        bot.edit_message_text(final_result_text, message.chat.id, processing_msg.message_id, parse_mode='Markdown')
        
    except Exception as e:
        bot.edit_message_text(f"❌ 发生错误：{e}", message.chat.id, processing_msg.message_id)

@bot.message_handler(func=lambda m: True)
def handle_other(message):
    if message.text and not message.text.startswith('/'):
        user_id = message.from_user.id
        if is_whitelisted(user_id):
            bot.reply_to(message, "❓ 请发送有效的邮箱地址获取邀请\n\n例如：`test@gmail.com`", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ 您没有使用权限\n\n您的用户ID：`{}`".format(user_id), parse_mode='Markdown')

# ================= Flask 路由 =================
@app.route('/')
def index():
    return jsonify({
        "service": "GPT Team Invite + Telegram Bot",
        "status": "running",
        "version": "2.0",
        "proxy": f"{PROXY_HOST}:{PROXY_PORT}",
        "bot": "enabled"
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/send-invite', methods=['POST'])
def send_invite():
    data = request.json
    
    token = data.get('token')
    email = data.get('email')
    
    if not token or not email:
        return jsonify({"code": 400, "message": "参数错误", "data": {"inviteSuccess": False}}), 400
    
    print(f"📨 收到邀请请求: {email}")
    
    success, message, status_code = get_team_id_and_send_invite(token, email)
    
    if success:
        return jsonify({"code": 200, "message": message, "data": {"inviteSuccess": True}})
    else:
        return jsonify({
            "code": status_code or 500, 
            "message": message, 
            "data": {"inviteSuccess": False, "error": message}
        }), status_code or 500

@app.route('/api/check-tg-member', methods=['POST'])
def check_tg_member():
    """检测用户是否在 Telegram 群组中"""
    data = request.json
    tg_user_id = data.get('tg_user_id')
    tg_group_id = data.get('tg_group_id')
    
    if not tg_user_id or not tg_group_id:
        return jsonify({"code": 400, "is_member": False, "message": "Missing parameters"}), 400
    
    try:
        # 获取成员状态
        chat_member = bot.get_chat_member(tg_group_id, tg_user_id)
        status = chat_member.status
        
        # 允许的状态: creator, administrator, member, restricted (如果restricted但还没被踢出)
        # 不允许: left, kicked
        valid_statuses = ['creator', 'administrator', 'member', 'restricted']
        
        if status in valid_statuses:
            return jsonify({
                "code": 200, 
                "is_member": True, 
                "message": "User is a member",
                "status": status
            })
        else:
             return jsonify({
                "code": 200, 
                "is_member": False, 
                "message": "User is not a member",
                "status": status
            })
            
    except Exception as e:
        print(f"❌ TG Membership check failed: {e}")
        return jsonify({
            "code": 500, 
            "is_member": False, 
            "message": str(e)
        }), 500


@app.route('/api/verify-link-pwd', methods=['POST'])
def verify_link_pwd():
    """验证链接密码"""
    import hashlib
    data = request.json
    link_code = data.get('link_code') or data.get('linkCode')
    password = data.get('password')
    
    if not link_code:
        return jsonify({"code": 400, "message": "Missing link code"}), 400
    
    if not password:
        return jsonify({"code": 400, "message": "请输入密码"}), 400

    # 🛡️ 延迟防止爆破
    import time, random
    time.sleep(1 + random.random())
    
    try:
        # 查询链接信息
        link = d1_client.query_d1("SELECT password, password_enabled FROM invite_links WHERE link_code = ? AND is_active = 1", [link_code])
        if not link or len(link) == 0:
            return jsonify({"code": 404, "message": "链接不存在或已过期"}), 404
        
        link_data = link[0]
        db_pwd = link_data.get('password')
        pwd_enabled = link_data.get('password_enabled', 0)
        
        # 如果没有启用密码保护，直接通过
        if not pwd_enabled or not db_pwd:
            return jsonify({"code": 200, "message": "验证成功"})
        
        # 对用户输入进行 SHA-256 哈希
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # 比对哈希值
        if input_hash == db_pwd:
            return jsonify({"code": 200, "message": "密码正确"})
        else:
            return jsonify({"code": 403, "message": "密码错误"}), 403
            
    except Exception as e:
        print(f"❌ Password check failed: {e}")
        return jsonify({"code": 500, "message": "验证服务异常"}), 500

@app.route('/api/check-account', methods=['POST'])
def check_account():
    """检测账号的 ChatGPT Team 空间状态（供 Worker 调用）"""
    data = request.json
    token = data.get('token')
    
    if not token:
        return jsonify({"code": 400, "valid": False, "message": "缺少token参数"}), 400
    
    print(f"🔍 检测账号状态...")
    account_id_db = data.get('account_id')
    
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    fake_device_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "oai-device-id": fake_device_id,
        "oai-language": "en-US",
        "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com"
    }
    
    try:
        check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
        check_resp = session.get(check_url, headers=headers, timeout=15)
        
        if check_resp.status_code == 401:
            return jsonify({
                "code": 401,
                "valid": False,
                "message": "Token失效",
                "teamCount": 0
            })
        
        if check_resp.status_code == 403:
            return jsonify({
                "code": 403,
                "valid": False,
                "message": "IP被封",
                "teamCount": 0
            })
        
        if check_resp.status_code != 200:
            return jsonify({
                "code": check_resp.status_code,
                "valid": False,
                "message": f"HTTP {check_resp.status_code}",
                "teamCount": 0
            })
        
        data = check_resp.json()
        accounts_dict = data.get("accounts", {})
        
        # 🔍 打印完整原始响应用于调试（限制长度避免日志过大）
        print(f"🔍 [check-account] 完整原始响应结构:")
        for acc_id, info in accounts_dict.items():
            print(f"🔍 [check-account] Account ID: {acc_id}")
            print(f"🔍 [check-account] Account Info Keys: {list(info.keys())}")
            account_info = info.get("account", {})
            print(f"🔍 [check-account] Account Sub-Keys: {list(account_info.keys())}")
            # 打印每个可能包含到期时间的字段
            for key in ["entitlement", "subscription", "billing_info", "last_active_subscription", "features", "plan"]:
                if key in info:
                    print(f"🔍 [check-account] {key}: {json.dumps(info[key], default=str)[:300]}")
                if key in account_info:
                    print(f"🔍 [check-account] account.{key}: {json.dumps(account_info[key], default=str)[:300]}")
        
        # 统计 Team 账号
        team_accounts = []
        first_expires_at = None  # 记录第一个Team的到期时间
        
        for acc_id, info in accounts_dict.items():
            account_info = info.get("account", {})
            is_deactivated = account_info.get("is_deactivated", True)
            plan_type = account_info.get("plan_type", "")
            
            # 🔥 尝试从多个位置提取订阅到期时间
            expires_at = None
            
            # 1. 从 entitlement 获取
            entitlement = info.get("entitlement", {})
            if entitlement:
                expires_at = entitlement.get("expires_at") or entitlement.get("subscription_expires_at")
                print(f"🔍 [check-account] entitlement: {entitlement}")
            
            # 2. 从 account.subscription 获取
            if not expires_at:
                subscription = account_info.get("subscription", {})
                if subscription:
                    expires_at = subscription.get("expires_at") or subscription.get("current_period_end") or subscription.get("end_date")
                    print(f"🔍 [check-account] subscription: {subscription}")
            
            # 3. 从 account.billing_info 获取
            if not expires_at:
                billing_info = account_info.get("billing_info", {})
                if billing_info:
                    expires_at = billing_info.get("expires_at") or billing_info.get("current_period_end")
            
            # 4. 从 features 或 last_active_subscription 获取
            if not expires_at:
                features = info.get("features", [])
                last_sub = info.get("last_active_subscription", {})
                if last_sub:
                    expires_at = last_sub.get("expires_at") or last_sub.get("current_period_end")
                    print(f"🔍 [check-account] last_active_subscription: {last_sub}")
            
            # 5. 尝试调用订阅API获取到期时间（只在必要时调用，避免限流）
            if not expires_at and (acc_id.startswith("org-") or "team" in plan_type.lower()):
                sub_headers = headers.copy()
                sub_headers["chatgpt-account-id"] = acc_id
                
                # 只尝试一个API，减少请求次数
                try:
                    sub_url = f"https://chatgpt.com/backend-api/accounts/{acc_id}/subscriptions"
                    sub_resp = session.get(sub_url, headers=sub_headers, timeout=10)
                    if sub_resp.status_code == 200:
                        sub_data = sub_resp.json()
                        print(f"🔍 [check-account] 订阅API响应: {json.dumps(sub_data, default=str)[:500]}")
                        if isinstance(sub_data, dict):
                            expires_at = sub_data.get("expires_at") or sub_data.get("current_period_end") or sub_data.get("billing_cycle_end")
                            if not expires_at and "subscription" in sub_data:
                                sub_info = sub_data["subscription"]
                                expires_at = sub_info.get("expires_at") or sub_info.get("current_period_end")
                        elif isinstance(sub_data, list) and len(sub_data) > 0:
                            first_sub = sub_data[0]
                            expires_at = first_sub.get("expires_at") or first_sub.get("current_period_end")
                except Exception as sub_e:
                    print(f"⚠️ [check-account] 获取订阅信息失败: {sub_e}")
            
            if not is_deactivated:
                if "team" in plan_type.lower() or acc_id.startswith("org-"):
                    team_accounts.append({
                        "id": acc_id,
                        "plan": plan_type,
                        "name": account_info.get("structure", "unknown"),
                        "expires_at": expires_at
                    })
                    # 记录第一个Team的到期时间
                    if expires_at and not first_expires_at:
                        first_expires_at = expires_at
                        print(f"✅ [check-account] 找到到期时间: {expires_at}")
        
        # [修改] 如果提供了 account_id，则更新数据库
        if account_id_db:
             try:
                 # 更新 expires_at
                 # 注意: 这里假设 D1 表中有 expires_at 字段
                 # 如果没有，可能需要 schema migration，但 Worker 代码似乎用了 expires_at
                 if first_expires_at:
                     d1_client.query_d1("UPDATE accounts SET expires_at = ?, updated_at = datetime('now') WHERE id = ?", [first_expires_at, account_id_db])
                     print(f"💾 更新数据库 expires_at: {first_expires_at} (ID: {account_id_db})")
                 else:
                     # 如果没找到 Team, 可能需要标记?
                     d1_client.query_d1("UPDATE accounts SET updated_at = datetime('now') WHERE id = ?", [account_id_db])
             except Exception as db_e:
                 print(f"⚠️ 数据库更新失败: {db_e}")

        if team_accounts:
            return jsonify({
                "code": 200,
                "valid": True,
                "message": "OK",
                "teamCount": len(team_accounts),
                "teams": team_accounts,
                "expiresAt": first_expires_at
            })
        else:
            # 账号有效但没有Team
            return jsonify({
                "code": 200,
                "valid": True,
                "message": "无Team空间",
                "teamCount": 0,
                "totalAccounts": len(accounts_dict)
            })
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "valid": False,
            "message": str(e),
            "teamCount": 0
        }), 500

@app.route('/api/downgrade-owner', methods=['POST'])
def downgrade_owner():
    """将所有 Team workspaces 的 owner 降级为 standard-user（供 Worker 调用）"""
    data = request.json
    token = data.get('token')
    
    if not token:
        return jsonify({"code": 400, "success": False, "message": "缺少token参数"}), 400
    
    print(f"🔄 开始批量降级 owner 权限...")
    
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    fake_device_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "oai-device-id": fake_device_id,
        "oai-language": "zh-CN",
        "Referer": "https://chatgpt.com/admin/members",
        "Origin": "https://chatgpt.com"
    }
    
    try:
        # 步骤1: 获取所有 Team ID
        check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
        check_resp = session.get(check_url, headers=headers, timeout=15)
        
        if check_resp.status_code == 401:
            return jsonify({"code": 401, "success": False, "message": "Token失效"})
        
        if check_resp.status_code != 200:
            return jsonify({"code": check_resp.status_code, "success": False, "message": f"获取账号信息失败: HTTP {check_resp.status_code}"})
        
        data = check_resp.json()
        accounts_dict = data.get("accounts", {})
        
        # 找出所有的 Team account_id
        team_ids = []
        for acc_id, info in accounts_dict.items():
            if acc_id.startswith("org-") or "team" in info.get("account", {}).get("plan_type", "").lower():
                team_ids.append(acc_id)
        
        if not team_ids:
            # 如果没找到明确的team，尝试用默认的第一个（兼容旧逻辑，但可能有风险）
            if accounts_dict:
                first_id = list(accounts_dict.keys())[0]
                team_ids.append(first_id)
            else:
                return jsonify({"code": 400, "success": False, "message": "未找到 Team 账号"})
        
        print(f"🔍 找到 {len(team_ids)} 个 Team 空间需要降级: {team_ids}")
        
        results = []
        success_count = 0
        
        # 步骤2: 遍历所有 Team ID 进行降级
        for account_id in team_ids:
            try:
                # 获取该空间下的 User ID
                me_url = "https://chatgpt.com/backend-api/me"
                headers["chatgpt-account-id"] = account_id
                me_resp = session.get(me_url, headers=headers, timeout=15)
                
                if me_resp.status_code != 200:
                    results.append(f"[{account_id}] 获取User ID失败 ({me_resp.status_code})")
                    continue
                
                me_data = me_resp.json()
                user_id = me_data.get("id")
                
                if not user_id:
                    results.append(f"[{account_id}] 未找到User ID")
                    continue
                    
                # 发送降级请求
                headers["Referer"] = "https://chatgpt.com/"
                patch_url = f"https://chatgpt.com/backend-api/accounts/{account_id}/users/{user_id}"
                
                patch_resp = session.patch(
                    patch_url, 
                    headers=headers, 
                    json={"role": "standard-user"},
                    timeout=15
                )
                
                if patch_resp.status_code == 200:
                    result = patch_resp.json()
                    new_role = result.get("role", "unknown")
                    results.append(f"[{account_id}] 降级成功 ({new_role})")
                    success_count += 1
                else:
                    try:
                        error_data = patch_resp.json()
                        error_text = error_data.get("detail") or error_data.get("message") or str(error_data)
                    except:
                        error_text = patch_resp.text[:100]
                    
                    if patch_resp.status_code == 400 and ("already" in str(error_text).lower() or "standard" in str(error_text).lower()):
                         results.append(f"[{account_id}] 已经是普通用户")
                         success_count += 1
                    else:
                        results.append(f"[{account_id}] 失败: {error_text}")

            except Exception as e:
                results.append(f"[{account_id}] 异常: {str(e)}")
        
        # 汇总结果
        final_message = f"共检测到 {len(team_ids)} 个空间。结果: " + "; ".join(results)
        print(f"✅ 批量降级完成: {final_message}")
        
        return jsonify({
            "code": 200, 
            "success": True, 
            "message": final_message,
            "data": {
                "total": len(team_ids), 
                "success": success_count, 
                "details": results,
                "newRole": "standard-user" # 兼容旧字段
            }
        })
    
    except Exception as e:
        print(f"❌ 降级流程严重错误: {str(e)}")
        return jsonify({
            "code": 500,
            "success": False,
            "message": f"系统错误: {str(e)}"
        }), 500

@app.route('/api/auto-import', methods=['POST'])
def auto_import():
    """自动导入账号到 D1 (替代 Worker 逻辑，解决国内无法连接 Worker 问题)"""
    data = request.json
    secret = data.get('secret')
    email = data.get('email')
    team_id = data.get('team_id')
    token = data.get('token')
    
    # 简单的密钥检查
    if secret != "gpt-auto-import-2024-secret":
        return jsonify({"success": False, "message": "Invalid secret"}), 403
        
    if not email or not team_id or not token:
        return jsonify({"success": False, "message": "Missing parameters"}), 400
        
    print(f"📥 收到自动导入请求: {email} / {team_id}")
    
    try:
        # 1. 检查是否存在
        sql_check = "SELECT id FROM accounts WHERE name = ? AND account_id = ?"
        existing = d1_client.query_d1(sql_check, [email, team_id])
        
        if existing and len(existing) > 0:
            acc_id = existing[0].get('id')
            # 更新
            sql_update = "UPDATE accounts SET authorization_token = ?, is_active = 1, updated_at = datetime('now') WHERE id = ?"
            d1_client.query_d1(sql_update, [token, acc_id])
            print(f"✅ 账号已更新: {acc_id}")
            return jsonify({
                "success": True,
                "action": "updated",
                "message": "账号已更新",
                "account_id": acc_id
            })
        else:
            # 新增
            sql_insert = """
                INSERT INTO accounts (name, account_id, authorization_token, is_active, max_invites, used_invites, rotation_count, current_rotation, created_at, updated_at)
                VALUES (?, ?, ?, 1, 8, 0, 1, 0, datetime('now'), datetime('now'))
            """
            d1_client.query_d1(sql_insert, [email, team_id, token])
            
            # 再查一次获取 ID
            new_acc = d1_client.query_d1(sql_check, [email, team_id])
            if new_acc and len(new_acc) > 0:
                acc_id = new_acc[0].get('id')
                print(f"✅ 新账号已创建: {acc_id}")
                
                # 🔥 立即检测账号状态并获取到期时间
                try:
                    # 调用内部的 check_account 逻辑
                    session = cffi_requests.Session(impersonate="chrome120")
                    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
                    
                    fake_device_id = str(uuid.uuid4())
                    headers = {
                        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "oai-device-id": fake_device_id,
                        "oai-language": "en-US",
                        "Referer": "https://chatgpt.com/",
                        "Origin": "https://chatgpt.com"
                    }
                    
                    check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
                    check_resp = session.get(check_url, headers=headers, timeout=15)
                    
                    if check_resp.status_code == 200:
                        check_data = check_resp.json()
                        accounts_dict = check_data.get("accounts", {})
                        
                        # 查找到期时间
                        expires_at = None
                        for acc_id_key, info in accounts_dict.items():
                            account_info = info.get("account", {})
                            plan_type = account_info.get("plan_type", "")
                            
                            # 尝试从多个位置获取到期时间
                            entitlement = info.get("entitlement", {})
                            if entitlement:
                                expires_at = entitlement.get("expires_at") or entitlement.get("subscription_expires_at")
                            
                            if not expires_at:
                                subscription = account_info.get("subscription", {})
                                if subscription:
                                    expires_at = subscription.get("expires_at") or subscription.get("current_period_end")
                            
                            if not expires_at:
                                last_sub = info.get("last_active_subscription", {})
                                if last_sub:
                                    expires_at = last_sub.get("expires_at") or last_sub.get("current_period_end")
                            
                            if expires_at:
                                break
                        
                        if expires_at:
                            d1_client.query_d1("UPDATE accounts SET expires_at = ? WHERE id = ?", [expires_at, acc_id])
                            print(f"📅 到期时间已更新: {expires_at}")
                        else:
                            print(f"⚠️ 未能获取到期时间")
                except Exception as check_e:
                    print(f"⚠️ 检测到期时间失败: {check_e}")
                
                return jsonify({
                    "success": True,
                    "action": "created",
                    "message": "新账号已创建",
                    "account_id": acc_id
                })
            else:
                return jsonify({"success": False, "message": "插入后获取ID失败"}), 500

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ================= 成员管理 API (补全 Admin 功能) =================

@app.route('/api/members', methods=['POST'])
def get_members():
    """获取成员列表"""
    data = request.json
    token = data.get('token')
    account_id = data.get('account_id')
    
    if not token or not account_id:
        return jsonify({"code": 400, "message": "Missing parameters"}), 400
        
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "oai-device-id": str(uuid.uuid4()),
        "chatgpt-account-id": account_id,
        "Referer": "https://chatgpt.com/admin/members",
        "Origin": "https://chatgpt.com"
    }
    
    try:
        url = f"https://chatgpt.com/backend-api/accounts/{account_id}/users?limit=100"
        resp = session.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            users_data = resp.json()
            members = []
            print(f"🔍 [DEBUG] Member items count: {len(users_data.get('items', []))}")
            if len(users_data.get('items', [])) > 0:
                 print(f"🔍 [DEBUG] First member sample: {users_data.get('items', [])[0]}")

            members = []
            for u in users_data.get('items', []):
                # 处理时间戳: 可能为浮点数(170000.0) 或 整数, 甚至 None
                created_ts = u.get('created')
                # 尝试其他可能的字段名
                if not created_ts:
                    created_ts = u.get('created_at') or u.get('joined_at') or u.get('joined')
                
                if not created_ts:
                     created_ts = 0
                
                members.append({
                    "email": u.get('email'),
                    "name": u.get('name'),
                    "role": u.get('role'),
                    "joinedAt": int(float(created_ts)) # 确保转换为整数, handle float string
                })
            return jsonify({"code": 200, "data": {"members": members}})
        else:
            print(f"❌ Fetch members failed: {resp.status_code} - {resp.text}")
            return jsonify({"code": resp.status_code, "message": f"Fetch members failed: {resp.text[:200]}"})
    except Exception as e:
        print(f"❌ Get members error: {e}")
        return jsonify({"code": 500, "message": f"Server Error: {str(e)}"}), 500

@app.route('/api/pending-invites', methods=['POST'])
def get_pending_invites():
    """获取待处理邀请"""
    data = request.json
    token = data.get('token')
    account_id = data.get('account_id')
    
    if not token or not account_id:
         return jsonify({"code": 400, "message": "Missing parameters"}), 400

    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "oai-device-id": str(uuid.uuid4()),
        "chatgpt-account-id": account_id,
        "Referer": "https://chatgpt.com/admin/members",
        "Origin": "https://chatgpt.com"
    }

    try:
        url = f"https://chatgpt.com/backend-api/accounts/{account_id}/invites?limit=100"
        resp = session.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            invites_data = resp.json()
            invites = []
            if len(invites_data.get('items', [])) > 0:
                print(f"🔍 [DEBUG] First invite sample: {invites_data.get('items', [])[0]}")

            for i in invites_data.get('items', []):
                # 尝试多种可能的字段名
                email = i.get('email') or i.get('email_address')
                if not email and 'user' in i:
                     email = i['user'].get('email')
                
                invites.append({
                    "email": email,
                    "role": i.get('role'),
                    "invitedAt": i.get('created', 0),
                    "expiresAt": i.get('expires_at', 0),
                    "id": i.get('id'), #添加ID以便取消邀请
                    "raw": i # 调试用
                })
            return jsonify({"code": 200, "data": {"invites": invites}})
        else:
             return jsonify({"code": resp.status_code, "message": f"Fetch invites failed: {resp.text[:100]}"})
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)}), 500

@app.route('/api/batch-invite', methods=['POST'])
def batch_invite():
    """批量邀请"""
    data = request.json
    token = data.get('token')
    account_id = data.get('account_id')
    emails = data.get('emails', [])
    
    if not token or not account_id or not emails:
        return jsonify({"code": 400, "message": "Missing parameters"}), 400

    print(f"📧 开始批量邀请 {len(emails)} 个邮箱到 {account_id}")

    success_count = 0
    failed_count = 0
    
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "oai-device-id": str(uuid.uuid4()),
        "chatgpt-account-id": account_id,
        "Referer": "https://chatgpt.com/admin/members",
        "Origin": "https://chatgpt.com"
    }
    
    invite_url = f"https://chatgpt.com/backend-api/accounts/{account_id}/invites"
    
    for email in emails:
        try:
            payload = {
                "email": email,
                "role": "standard-user"
            }
            resp = session.post(invite_url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                 success_count += 1
            else:
                 failed_count += 1
                 print(f"❌ 邀请 {email} 失败: {resp.status_code} {resp.text}")
        except Exception as e:
            failed_count += 1
            print(f"❌ 邀请 {email} 异常: {e}")
            
    return jsonify({
        "code": 200, 
        "data": {
            "success": success_count,
            "failed": failed_count
        },
        "message": f"处理完成: 成功 {success_count}, 失败 {failed_count}"
    })

# ================= 链接兑换API =================
@app.route('/api/link-info', methods=['GET'])
def get_link_info():
    """获取链接信息"""
    link_code = request.args.get('code')
    if not link_code:
        return jsonify({"code": 400, "message": "缺少链接代码"}), 400
    
    link = db.get_link_by_code(link_code)
    if not link:
        return jsonify({"code": 404, "message": "链接不存在或已失效"}), 404
    
    max_uses = link['max_uses'] or 100
    used_count = link['used_count'] or 0
    remaining_uses = max_uses - used_count
    
    if remaining_uses <= 0:
        return jsonify({"code": 400, "message": "链接使用次数已达上限"}), 400
    
    # 检查过期
    if link['expires_at']:
        from datetime import datetime
        if datetime.fromisoformat(link['expires_at'].replace(' ', 'T')) < datetime.now():
            return jsonify({"code": 400, "message": "链接已过期"}), 400
    
    return jsonify({
        "code": 200,
        "data": {
            "name": link['name'],
            "linkCode": link['link_code'],
            "validityType": link['validity_type'],
            "maxUses": max_uses,
            "usedCount": used_count,
            "remainingUses": remaining_uses
        }
    })

@app.route('/api/redeem-link', methods=['POST'])
def redeem_link():
    """兑换链接，创建会话"""
    data = request.json
    link_code = data.get('linkCode')
    email = data.get('email')
    referral_code = data.get('referralCode')
    
    if not link_code or not email:
        return jsonify({"code": 400, "message": "参数错误"}), 400
    
    # 验证链接
    link = db.get_link_by_code(link_code)
    if not link:
        return jsonify({"code": 404, "message": "链接不存在或已失效"}), 404
    
    if (link['used_count'] or 0) >= (link['max_uses'] or 100):
        return jsonify({"code": 400, "message": "链接使用次数已达上限"}), 400
    
    # 获取可用账号
    account = db.get_available_account()
    if not account:
        return jsonify({"code": 500, "message": "暂无可用账号"}), 500
    
    # 从账号token获取Team ID
    try:
        token = account['authorization_token']
        session = cffi_requests.Session(impersonate="chrome120")
        session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
        
        headers = {
            "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "oai-device-id": str(uuid.uuid4()),
            "oai-language": "en-US"
        }
        
        check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
        check_resp = session.get(check_url, headers=headers, timeout=15)
        
        if check_resp.status_code != 200:
            return jsonify({"code": 500, "message": f"账号验证失败: HTTP {check_resp.status_code}"}), 500
        
        accounts_dict = check_resp.json().get("accounts", {})
        
        # 找Team ID
        team_id = None
        for acc_id, info in accounts_dict.items():
            if acc_id.startswith("org-") or info.get("account", {}).get("plan_type") == "team":
                team_id = acc_id
                break
        
        if not team_id and accounts_dict:
            team_id = list(accounts_dict.keys())[0]
        
        if not team_id:
            return jsonify({"code": 500, "message": "该账号没有Team权限"}), 500
        
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取Team信息失败: {str(e)}"}), 500
    
    # 创建会话
    try:
        db.cleanup_expired_sessions()
        session_id = db.create_session(
            account_id=account['id'],
            team_id=team_id,
            token=account['authorization_token'],
            email=email,
            validity_type=link['validity_type'],
            link_code=link_code,
            referral_code=referral_code
        )
        
        return jsonify({
            "code": 200,
            "data": {
                "sessionId": session_id,
                "message": "验证成功，请继续发送邀请"
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"会话创建失败: {str(e)}"}), 500

@app.route('/api/send-invite-secure', methods=['POST'])
def send_invite_secure():
    """安全发送邀请（使用sessionId）"""
    data = request.json
    session_id = data.get('sessionId')
    email = data.get('email')
    
    if not session_id or not email:
        return jsonify({"code": 400, "message": "参数错误"}), 400
    
    # 验证会话
    session = db.get_session(session_id)
    if not session:
        return jsonify({"code": 404, "message": "会话不存在或已失效"}), 404
    
    # 检查会话是否过期
    from datetime import datetime
    if datetime.fromisoformat(session['expires_at'].replace(' ', 'T')) < datetime.now():
        return jsonify({"code": 400, "message": "会话已过期，请重新验证"}), 400
    
    # 检查会话是否已使用
    if session['is_used']:
        return jsonify({"code": 400, "message": "会话已使用，请勿重复提交"}), 400
    
    # 发送邀请
    try:
        success, message, _ = get_team_id_and_send_invite(session['token'], email)
        
        # 标记会话已使用
        db.mark_session_used(session_id)
        
        if success:
            # 更新数据库
            if session['link_code']:
                db.update_link_usage(session['link_code'])
                db.update_account_usage(session['account_id'])
                
                # 创建邀请记录
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
                db.create_invitation_record(
                    email=email,
                    account_id=session['account_id'],
                    validity_type=session['validity_type'],
                    link_code=session['link_code'],
                    referral_code=session['referral_code'],
                    ip_address=ip_address
                )
            
            return jsonify({
                "code": 200,
                "message": "邀请发送成功",
                "data": {"inviteSuccess": True}
            })
        else:
            return jsonify({
                "code": 500,
                "message": message,
                "data": {"inviteSuccess": False, "error": message}
            })
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"发送失败: {str(e)}",
            "data": {"inviteSuccess": False, "error": str(e)}
        }), 500

# ================= 前端静态文件服务 =================
@app.route('/link')
@app.route('/link/<code>')
def link_page(code=None):
    """邀请链接页面"""
    return send_file('static/link.html')

@app.route('/admin')
def admin_page():
    """管理后台页面"""
    return send_file('static/admin.html')

@app.route('/index')
def index_page():
    """首页"""
    return send_file('static/index.html')

# ================= Codex Chat API =================
@app.route('/api/chat', methods=['POST'])
def codex_chat():
    """处理 Codex 的聊天请求，转发到 ChatGPT API"""
    data = request.json
    token = data.get('token')
    messages = data.get('messages', [])
    model = data.get('model', 'gpt-4')
    stream = data.get('stream', False)
    use_simple = data.get('use_simple', True)  # 默认使用简化版
    
    if not token:
        return jsonify({"code": 400, "message": "缺少token参数"}), 400
    
    if not messages:
        return jsonify({"code": 400, "message": "缺少messages参数"}), 400
    
    print(f"🤖 [Codex] 收到聊天请求, model={model}, stream={stream}, use_simple={use_simple}")
    
    # 优先使用简化版（curl-cffi + 会话保持）
    if use_simple:
        try:
            from simple_chat import chat_simple
            result = chat_simple(token, messages, model, stream, proxy_url=PROXY_URL)
            
            if result['success']:
                return jsonify(result['data'])
            else:
                return jsonify({"code": 500, "message": result['error']}), 500
        except Exception as e:
            print(f"❌ [Simple] 错误: {e}")
            return jsonify({"code": 500, "message": f"Simple错误: {str(e)}"}), 500
    
    # 使用 Playwright 方案（备用）
    try:
        from playwright_chat import chat_with_playwright
        result = chat_with_playwright(token, messages, model, stream)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({"code": 500, "message": result['error']}), 500
    except Exception as e:
        print(f"❌ [Playwright] 错误: {e}")
        return jsonify({"code": 500, "message": f"Playwright错误: {str(e)}"}), 500
    
    fake_device_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "oai-device-id": fake_device_id,
        "oai-language": "en-US",
        "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com",
        "Accept": "text/event-stream",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }
    
    try:
        # 步骤1: 获取 Team ID
        check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
        check_resp = session.get(check_url, headers=headers, timeout=15)
        
        if check_resp.status_code == 401:
            return jsonify({"code": 401, "message": "Token失效"}), 401
        
        if check_resp.status_code != 200:
            return jsonify({"code": check_resp.status_code, "message": f"获取账号信息失败"}), check_resp.status_code
        
        accounts_data = check_resp.json()
        accounts_dict = accounts_data.get("accounts", {})
        
        # 找 Team ID
        team_id = None
        for acc_id, info in accounts_dict.items():
            if acc_id.startswith("org-") or "team" in info.get("account", {}).get("plan_type", "").lower():
                team_id = acc_id
                break
        
        if not team_id and accounts_dict:
            team_id = list(accounts_dict.keys())[0]
        
        if not team_id:
            return jsonify({"code": 400, "message": "该账号没有可用的workspace"}), 400
        
        print(f"✅ [Codex] 使用 Team ID: {team_id}")
        
        # 步骤2: 发送聊天请求
        headers["chatgpt-account-id"] = team_id
        
        # 构建 ChatGPT 格式的消息
        chat_messages = []
        for msg in messages:
            chat_messages.append({
                "id": str(uuid.uuid4()),
                "author": {"role": msg.get("role", "user")},
                "content": {"content_type": "text", "parts": [msg.get("content", "")]},
                "metadata": {}
            })
        
        payload = {
            "action": "next",
            "messages": chat_messages,
            "parent_message_id": str(uuid.uuid4()),
            "model": model,
            "timezone_offset_min": -480,
            "suggestions": [],
            "history_and_training_disabled": False,
            "conversation_mode": {"kind": "primary_assistant"},
            "force_paragen": False,
            "force_paragen_model_slug": "",
            "force_nulligen": False,
            "force_rate_limit": False
        }
        
        chat_url = "https://chatgpt.com/backend-api/conversation"
        
        if stream:
            # 流式响应
            chat_resp = session.post(chat_url, headers=headers, json=payload, timeout=120, stream=True)
            
            if chat_resp.status_code != 200:
                return jsonify({"code": chat_resp.status_code, "message": "聊天请求失败"}), chat_resp.status_code
            
            def generate():
                for line in chat_resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith('data: '):
                            yield decoded + '\n\n'
            
            from flask import Response
            return Response(generate(), mimetype='text/event-stream')
        else:
            # 非流式响应
            chat_resp = session.post(chat_url, headers=headers, json=payload, timeout=120)
            
            if chat_resp.status_code != 200:
                return jsonify({"code": chat_resp.status_code, "message": "聊天请求失败"}), chat_resp.status_code
            
            # 解析响应，提取最终消息
            response_text = chat_resp.text
            final_message = ""
            
            for line in response_text.split('\n'):
                if line.startswith('data: ') and not line.startswith('data: [DONE]'):
                    try:
                        json_str = line[6:]
                        data = json.loads(json_str)
                        if "message" in data and data["message"]:
                            msg = data["message"]
                            if msg.get("content", {}).get("parts"):
                                final_message = msg["content"]["parts"][0]
                    except:
                        pass
            
            # 返回 OpenAI 兼容格式
            return jsonify({
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(__import__('time').time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": final_message
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            })
    
    except Exception as e:
        print(f"❌ [Codex] 聊天请求异常: {e}")
        return jsonify({"code": 500, "message": str(e)}), 500

# ================= 启动 =================
def run_bot():
    """在后台线程运行 Telegram Bot"""
    print("🤖 Telegram Bot 启动中...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Bot 错误: {e}")

if __name__ == '__main__':
    print("="*60)
    print(f"🚀 GPT Team Invite + Telegram Bot (Render Complete)")
    print(f"🌐 端口: {PORT}")
    print(f"🔌 代理: {PROXY_HOST}:{PROXY_PORT}")
    print(f"🤖 Bot Token: {BOT_TOKEN[:20]}...")
    print(f"👑 管理员: {ADMIN_IDS}")
    print(f"💾 数据库: SQLite ({db.DATABASE_FILE})")
    print("="*60)
    
    # 初始化数据库
    print("\n📦 初始化数据库...")
    db.init_database()
    
    # 启动 Bot（后台线程）
    print("\n🤖 启动 Telegram Bot...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # 启动 Flask
    print(f"\n🌐 启动 Flask 服务器 on 0.0.0.0:{PORT}...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
