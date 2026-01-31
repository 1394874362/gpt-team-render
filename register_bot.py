# -*- coding: utf-8 -*-
"""
ChatGPT 自动注册模块 - Render 版本
完整移植本地脚本逻辑，使用 curl_cffi 模拟浏览器
"""
from curl_cffi import requests as curl_requests
import httpx
import time
import re
import uuid
import random
import string
from typing import Optional, Dict, Any
from urllib.parse import unquote

# ================= 配置 =================
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
TM_API_AUTH_TOKEN = "xigege666"

MAX_RETRIES = 15
RETRY_INTERVAL = 2

# 代理配置
PROXY_HOST = "na.ec39f792e12ce1b7.ipmars.vip"
PROXY_PORT = "4900"
PROXY_USER = "CCCRqQ7zTT-zone-mars-region-US-session-8zHiWYyc-sessTime-2"
PROXY_PASS = "98514780"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"


def request_with_retry(func, *args, max_retries=3, **kwargs):
    """带重试的请求函数"""
    for attempt in range(max_retries):
        try:
            response = func(*args, **kwargs)
            return response
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
            else:
                raise
    return None


class EmailVerifier:
    """邮件验证器 - 不使用代理直连邮件API"""
    
    def __init__(self, email: str):
        self.email = email
        # 邮件API不需要代理，直连更稳定
        self.client = httpx.Client(timeout=30.0, verify=False)
    
    def wait_for_verification_email(self) -> Optional[str]:
        """等待验证邮件并提取验证码"""
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
                raw_content = mail.get('raw', '')
                
                if not raw_content:
                    time.sleep(RETRY_INTERVAL)
                    continue
                
                # 提取验证码
                code = self.extract_verification_code(raw_content)
                if code:
                    return code
                
                time.sleep(RETRY_INTERVAL)
                
            except Exception:
                time.sleep(RETRY_INTERVAL)
        
        return None
    
    def extract_verification_code(self, raw_content: str) -> Optional[str]:
        """从邮件内容提取验证码"""
        processed = raw_content.replace('=\r\n', '').replace('=\n', '')
        
        patterns = [
            r'(?:verification code|code|otp)[\s\:\-]*([0-9]{6,8})',
            r'\b([0-9]{6,8})\b',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, processed, re.IGNORECASE)
            if matches:
                for match in matches:
                    code = match.strip()
                    if code.isdigit() and 6 <= len(code) <= 8:
                        return code
        
        all_numbers = re.findall(r'\b\d{6,8}\b', processed)
        if all_numbers:
            return all_numbers[0]
        
        return None
    
    def close(self):
        self.client.close()


class ChatGPTReg:
    """ChatGPT 注册器 - 完整 OAuth 流程"""
    
    def __init__(self, proxy: str = PROXY_URL):
        # 尝试创建带代理的会话，如果失败则不用代理
        try:
            self.session = curl_requests.Session(
                impersonate="chrome120",
                verify=False,
                proxies={"http": proxy, "https": proxy} if proxy else {},
                timeout=30
            )
        except Exception as e:
            # 代理失败，尝试不用代理
            self.session = curl_requests.Session(
                impersonate="chrome120",
                verify=False,
                timeout=30
            )
        
        self.auth_session_logging_id = str(uuid.uuid4())
        self.oai_did = ""
        self.csrf_token = ""
        self.authorize_url = ""

    def init_session(self) -> bool:
        """初始化会话，获取 csrf token"""
        try:
            resp = self.session.get("https://chatgpt.com", timeout=30)
            if resp.status_code != 200:
                return False

            self.oai_did = self.session.cookies.get("oai-did")
            if not self.oai_did:
                return False

            csrf_cookie = self.session.cookies.get("__Host-next-auth.csrf-token")
            if csrf_cookie:
                self.csrf_token = unquote(csrf_cookie).split("|")[0]
            else:
                return False

            self.session.get(
                f"https://chatgpt.com/auth/login?openaicom-did={self.oai_did}",
                timeout=30
            )
            return True
        except Exception as e:
            return False

    def get_authorize_url(self, email: str) -> bool:
        """获取授权 URL"""
        try:
            url = f"https://chatgpt.com/api/auth/signin/openai?prompt=login&ext-oai-did={self.oai_did}&auth_session_logging_id={self.auth_session_logging_id}&screen_hint=login_or_signup&login_hint={email}"
            payload = {
                "callbackUrl": "https://chatgpt.com/", 
                "csrfToken": self.csrf_token, 
                "json": "true"
            }
            resp = request_with_retry(
                self.session.post, url, 
                data=payload, 
                headers={"Origin": "https://chatgpt.com"}
            )
            data = resp.json()
            if data.get("url") and "auth.openai.com" in data["url"]:
                self.authorize_url = data["url"]
                return True
            return False
        except:
            return False

    def start_authorize(self) -> bool:
        """开始授权流程"""
        try:
            resp = request_with_retry(
                self.session.get, 
                self.authorize_url, 
                allow_redirects=True
            )
            if "create-account" in resp.url or "log-in" in resp.url:
                return True
            return False
        except:
            return False

    def register(self, email: str, password: str) -> bool:
        """注册账户"""
        try:
            resp = request_with_retry(
                self.session.post,
                "https://auth.openai.com/api/accounts/user/register",
                json={"password": password, "username": email},
                headers={
                    "Content-Type": "application/json", 
                    "Origin": "https://auth.openai.com"
                }
            )
            return resp.status_code == 200
        except:
            return False

    def send_verification_email(self) -> bool:
        """发送验证邮件"""
        try:
            resp = request_with_retry(
                self.session.get, 
                "https://auth.openai.com/api/accounts/email-otp/send", 
                allow_redirects=True
            )
            return resp.status_code == 200
        except:
            return False

    def validate_otp(self, otp_code: str) -> bool:
        """验证 OTP"""
        try:
            resp = request_with_retry(
                self.session.post,
                "https://auth.openai.com/api/accounts/email-otp/validate",
                json={"code": otp_code},
                headers={
                    "Content-Type": "application/json", 
                    "Origin": "https://auth.openai.com"
                }
            )
            return resp.status_code == 200
        except:
            return False

    def create_account(self, name: str, birthdate: str) -> bool:
        """创建账户"""
        try:
            resp = request_with_retry(
                self.session.post,
                "https://auth.openai.com/api/accounts/create_account",
                json={"name": name, "birthdate": birthdate},
                headers={
                    "Content-Type": "application/json", 
                    "Origin": "https://auth.openai.com"
                }
            )
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    continue_url = data.get("continue_url")
                    if continue_url:
                        request_with_retry(
                            self.session.get, 
                            continue_url, 
                            allow_redirects=True
                        )
                except:
                    pass
                return True
            return False
        except:
            return False

    def get_session(self) -> Optional[Dict]:
        """获取会话信息"""
        try:
            resp = request_with_retry(
                self.session.get, 
                "https://chatgpt.com/api/auth/session"
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except:
            return None

    def close(self):
        pass


def generate_random_email() -> str:
    domain = random.choice(CF_EMAIL_DOMAINS)
    length = random.randint(10, 15)
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{username}@{domain}"


def generate_random_password() -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=16))


def generate_random_name() -> str:
    first = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana", "Eva", "Frank"]
    last = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
    return f"{random.choice(first)} {random.choice(last)}"


def generate_random_birthdate() -> str:
    year = random.randint(1974, 2006)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


def register_chatgpt_account() -> Dict[str, Any]:
    """
    完整的 ChatGPT 注册流程
    """
    email = generate_random_email()
    password = generate_random_password()
    name = generate_random_name()
    birthdate = generate_random_birthdate()
    
    try:
        reg = ChatGPTReg(proxy=PROXY_URL)
        
        # 1. 初始化会话
        if not reg.init_session():
            return {"success": False, "error": "初始化失败"}
        
        time.sleep(0.5)
        
        # 2. 获取授权 URL
        if not reg.get_authorize_url(email):
            return {"success": False, "error": "获取授权URL失败"}
        
        time.sleep(1)
        
        # 3. 开始授权流程
        if not reg.start_authorize():
            return {"success": False, "error": "授权流程失败"}
        
        time.sleep(1)
        
        # 4. 注册账户
        if not reg.register(email, password):
            return {"success": False, "error": "注册失败"}
        
        time.sleep(1)
        
        # 5. 发送验证邮件
        if not reg.send_verification_email():
            return {"success": False, "error": "发送验证邮件失败"}
        
        # 6. 等待验证码
        time.sleep(3)
        verifier = EmailVerifier(email)
        code = verifier.wait_for_verification_email()
        verifier.close()
        
        if not code:
            return {"success": False, "error": "未收到验证码"}
        
        # 7. 验证 OTP
        if not reg.validate_otp(code):
            return {"success": False, "error": "OTP验证失败"}
        
        time.sleep(1)
        
        # 8. 创建账户
        reg.create_account(name, birthdate)
        
        # 9. 获取 session
        session_info = reg.get_session()
        access_token = None
        
        if session_info:
            access_token = session_info.get('accessToken')
        
        if access_token:
            return {
                "success": True,
                "email": email,
                "password": password,
                "token": access_token
            }
        else:
            return {"success": False, "error": "未获取到Token"}
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 50:
            error_msg = error_msg[:50]
        return {"success": False, "error": error_msg}


if __name__ == "__main__":
    result = register_chatgpt_account()
    print(f"结果: {result}")
