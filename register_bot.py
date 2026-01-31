# -*- coding: utf-8 -*-
"""
ChatGPT 自动注册模块 - curl_cffi 版本
使用 curl_cffi 模拟浏览器指纹，绕过 Cloudflare 检测
"""
from curl_cffi import requests as cffi_requests
import time
import re
import uuid
import random
import string
from typing import Optional, Dict, Any

# ================= 配置 =================
CF_ADMIN_PASSWORD = "xigege666"
CF_EMAIL_DOMAINS = [
    "xigege.me", 
    "sssid.me",
    "a.xigegee.me",
    "aj.xigegee.me",
    "an.xigegee.me",
    "f.xigegee.me",
    "k.xigegee.me",
    "m.xigegee.me"
]

TM_API_BASE_URL = "https://apimail.xigege.me/admin/mails"
TM_API_AUTH_TOKEN = CF_ADMIN_PASSWORD

# 邮件等待配置
MAX_RETRIES = 15
RETRY_INTERVAL = 2

# 代理配置
PROXY_HOST = "na.ec39f792e12ce1b7.ipmars.vip"
PROXY_PORT = "4900"
PROXY_USER = "CCCRqQ7zTT-zone-mars-region-US-session-8zHiWYyc-sessTime-2"
PROXY_PASS = "98514780"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"


def get_verification_code(email: str) -> Optional[str]:
    """从邮件 API 获取验证码"""
    session = cffi_requests.Session(impersonate="chrome120")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            url = f"{TM_API_BASE_URL}?limit=20&offset=0&address={email}"
            headers = {'x-admin-auth': TM_API_AUTH_TOKEN}
            
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                time.sleep(RETRY_INTERVAL)
                continue
            
            data = response.json()
            
            if data.get('count', 0) == 0 or not data.get('results'):
                time.sleep(RETRY_INTERVAL)
                continue
            
            mail = data['results'][0]
            mail_subject = mail.get('subject', '')
            mail_html = mail.get('html', '')
            
            # 提取6位验证码
            code_match = re.search(r'(\d{6})', mail_subject + mail_html)
            if code_match:
                return code_match.group(1)
            
            time.sleep(RETRY_INTERVAL)
            
        except Exception as e:
            time.sleep(RETRY_INTERVAL)
    
    return None


def register_chatgpt_account() -> Dict[str, Any]:
    """
    注册一个 ChatGPT 账号
    使用 curl_cffi 模拟 Chrome 浏览器
    """
    # 创建模拟 Chrome 的会话
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    
    # 生成账号信息
    domain = random.choice(CF_EMAIL_DOMAINS)
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    email = f"{username}@{domain}"
    
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choices(chars, k=16))
    
    device_id = str(uuid.uuid4())
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "oai-device-id": device_id,
        "oai-language": "en-US",
        "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }
    
    try:
        # 步骤1: 发送注册请求
        signup_url = "https://chatgpt.com/backend-api/signups"
        signup_payload = {"email": email}
        
        resp = session.post(signup_url, json=signup_payload, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            # 检查是否是 HTML 响应
            text = resp.text[:100]
            if "<html" in text.lower():
                return {"success": False, "error": "被CF拦截"}
            return {"success": False, "error": f"注册请求失败({resp.status_code})"}
        
        # 步骤2: 等待验证码
        time.sleep(3)
        code = get_verification_code(email)
        
        if not code:
            return {"success": False, "error": "未收到验证码"}
        
        # 步骤3: 验证邮箱并设置密码
        verify_url = "https://chatgpt.com/backend-api/signups/verify"
        verify_payload = {
            "email": email,
            "code": code,
            "password": password
        }
        
        resp = session.post(verify_url, json=verify_payload, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            text = resp.text[:100]
            if "<html" in text.lower():
                return {"success": False, "error": "验证被CF拦截"}
            return {"success": False, "error": f"验证失败({resp.status_code})"}
        
        data = resp.json()
        token = data.get("access_token") or data.get("token")
        
        if not token:
            return {"success": False, "error": "未获取到Token"}
        
        return {
            "success": True,
            "email": email,
            "password": password,
            "token": token
        }
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 50:
            error_msg = error_msg[:50]
        return {"success": False, "error": error_msg}


if __name__ == "__main__":
    result = register_chatgpt_account()
    print(f"结果: {result}")
