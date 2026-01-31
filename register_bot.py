# -*- coding: utf-8 -*-
"""
ChatGPT 自动注册模块 - Render 优化版
纯 HTTP 请求，无需浏览器，内存占用低
"""
import httpx
import time
import re
import uuid
import random
import string
from typing import Optional, Dict, Any

# ================= 配置 =================
CF_WORKER_DOMAIN = "apimail.xigege.me"
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
MAX_RETRIES = 10
RETRY_INTERVAL = 1

# 代理配置（Render 环境）
PROXY_HOST = "na.ec39f792e12ce1b7.ipmars.vip"
PROXY_PORT = "4900"
PROXY_USER = "CCCRqQ7zTT-zone-mars-region-US-session-8zHiWYyc-sessTime-2"
PROXY_PASS = "98514780"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"


class EmailVerifier:
    """邮件验证器"""
    
    def __init__(self, email: str, proxy: str = None):
        self.email = email
        
        mounts = {}
        if proxy:
            mounts = {
                "http://": httpx.HTTPTransport(proxy=proxy),
                "https://": httpx.HTTPTransport(proxy=proxy, verify=False),
            }
        
        self.client = httpx.Client(
            timeout=30.0,
            verify=False, 
            mounts=mounts if proxy else None
        )
    
    def wait_for_verification_email(self) -> Optional[str]:
        """等待验证邮件并提取验证码"""
        print(f"[*] 等待验证邮件（{self.email}）...")
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                url = f"{TM_API_BASE_URL}?limit=20&offset=0&address={self.email}"
                headers = {'x-admin-auth': TM_API_AUTH_TOKEN}
                
                response = self.client.get(url, headers=headers)
                
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
                
                # 提取验证码
                code_match = re.search(r'(\d{6})', mail_subject + mail_html)
                if code_match:
                    code = code_match.group(1)
                    print(f"[✓] 找到验证码: {code}")
                    return code
                
                time.sleep(RETRY_INTERVAL)
                
            except Exception as e:
                print(f"[!] 获取邮件失败: {e}")
                time.sleep(RETRY_INTERVAL)
        
        print("[✗] 超时未收到验证邮件")
        return None
    
    def close(self):
        """关闭客户端"""
        self.client.close()


class ChatGPTRegister:
    """ChatGPT 注册器"""
    
    def __init__(self, proxy: str = PROXY_URL):
        self.proxy = proxy
        self.session = httpx.Client(
            timeout=30.0,
            verify=False,
            mounts={
                "http://": httpx.HTTPTransport(proxy=proxy),
                "https://": httpx.HTTPTransport(proxy=proxy, verify=False),
            } if proxy else None
        )
        
        self.device_id = str(uuid.uuid4())
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "oai-device-id": self.device_id,
            "oai-language": "en-US",
            "Referer": "https://chatgpt.com/",
            "Origin": "https://chatgpt.com"
        }
    
    def generate_email(self) -> str:
        """生成随机邮箱"""
        domain = random.choice(CF_EMAIL_DOMAINS)
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        return f"{username}@{domain}"
    
    def generate_password(self) -> str:
        """生成强密码"""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choices(chars, k=16))
        return password
    
    def register_account(self, email: str, password: str) -> Dict[str, Any]:
        """注册账号"""
        print(f"\n[1/3] 发送注册请求...")
        print(f"  邮箱: {email}")
        
        try:
            response = self.session.post(
                "https://chatgpt.com/backend-api/v1/signup",
                json={
                    "email": email,
                    "password": password
                },
                headers=self.headers
            )
            
            if response.status_code == 200:
                print("[✓] 注册请求成功")
                return {"success": True}
            else:
                error_msg = response.text
                print(f"[✗] 注册失败: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            print(f"[✗] 注册异常: {e}")
            return {"success": False, "error": str(e)}
    
    def verify_email(self, email: str, code: str) -> Dict[str, Any]:
        """验证邮箱"""
        print(f"\n[3/3] 提交验证码...")
        
        try:
            response = self.session.post(
                "https://chatgpt.com/backend-api/v1/verify-email",
                json={
                    "email": email,
                    "code": code
                },
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    print("[✓] 验证成功，获取到 Token")
                    return {"success": True, "token": token}
                else:
                    print("[✗] 验证成功但未获取到 Token")
                    return {"success": False, "error": "No token"}
            else:
                error_msg = response.text
                print(f"[✗] 验证失败: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            print(f"[✗] 验证异常: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self):
        """关闭会话"""
        self.session.close()


def register_chatgpt_account() -> Dict[str, Any]:
    """
    注册一个 ChatGPT 账号
    
    Returns:
        {
            "success": bool,
            "email": str,
            "password": str,
            "token": str,
            "error": str (if failed)
        }
    """
    register = ChatGPTRegister()
    
    try:
        # 生成账号信息
        email = register.generate_email()
        password = register.generate_password()
        
        print(f"\n{'='*50}")
        print(f"开始注册 ChatGPT 账号")
        print(f"{'='*50}")
        
        # 1. 发送注册请求
        result = register.register_account(email, password)
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "注册失败")
            }
        
        # 2. 等待验证邮件
        print(f"\n[2/3] 等待验证邮件...")
        verifier = EmailVerifier(email, PROXY_URL)
        code = verifier.wait_for_verification_email()
        verifier.close()
        
        if not code:
            return {
                "success": False,
                "error": "未收到验证邮件"
            }
        
        # 3. 验证邮箱
        result = register.verify_email(email, code)
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "验证失败")
            }
        
        print(f"\n{'='*50}")
        print(f"✅ 注册成功！")
        print(f"{'='*50}")
        
        return {
            "success": True,
            "email": email,
            "password": password,
            "token": result["token"]
        }
        
    except Exception as e:
        print(f"\n[✗] 注册过程异常: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        register.close()


if __name__ == "__main__":
    # 测试
    result = register_chatgpt_account()
    print(f"\n最终结果: {result}")
