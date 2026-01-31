# -*- coding: utf-8 -*-
"""
使用 undetected-chromedriver 绕过 Cloudflare 调用 ChatGPT API
比 Playwright 更轻量，适合 Render 免费套餐
"""
import json
import uuid
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def chat_with_undetected(token, messages, model='gpt-4', stream=False, team_id=None):
    """
    使用 undetected-chromedriver 调用 ChatGPT API
    
    Args:
        token: ChatGPT access token
        messages: 消息列表 [{"role": "user", "content": "..."}]
        model: 模型名称
        stream: 是否流式输出
        team_id: Team ID (可选)
    
    Returns:
        dict: {"success": bool, "data": dict, "error": str}
    """
    driver = None
    try:
        # 配置 Chrome 选项
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        
        # 创建 driver
        driver = uc.Chrome(options=options, version_main=120)
        
        # 访问 ChatGPT
        driver.get('https://chatgpt.com')
        time.sleep(2)
        
        # 注入 token
        driver.execute_script(f'''
            localStorage.setItem('access_token', '{token}');
        ''')
        
        device_id = str(uuid.uuid4())
        
        # 如果没有 team_id，先获取
        if not team_id:
            print("[Undetected] 获取 Team ID...")
            check_url = 'https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27'
            
            response = driver.execute_async_script(f'''
                const callback = arguments[arguments.length - 1];
                fetch('{check_url}', {{
                    headers: {{
                        'Authorization': 'Bearer {token}',
                        'oai-device-id': '{device_id}',
                        'oai-language': 'en-US'
                    }}
                }})
                .then(r => r.json())
                .then(data => callback({{status: 200, data: data}}))
                .catch(err => callback({{status: 500, error: err.toString()}}));
            ''')
            
            if response.get('status') == 401:
                driver.quit()
                return {"success": False, "error": "Token失效"}
            
            if response.get('status') != 200:
                driver.quit()
                return {"success": False, "error": f"获取账号信息失败: {response.get('status')}"}
            
            accounts_data = response.get('data', {})
            accounts_dict = accounts_data.get('accounts', {})
            
            for acc_id, info in accounts_dict.items():
                if acc_id.startswith('org-') or 'team' in info.get('account', {}).get('plan_type', '').lower():
                    team_id = acc_id
                    break
            
            if not team_id and accounts_dict:
                team_id = list(accounts_dict.keys())[0]
            
            if not team_id:
                driver.quit()
                return {"success": False, "error": "该账号没有可用的workspace"}
            
            print(f"[Undetected] 使用 Team ID: {team_id}")
        
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
        
        # 发送聊天请求
        print("[Undetected] 发送聊天请求...")
        response = driver.execute_async_script(f'''
            const callback = arguments[arguments.length - 1];
            fetch('https://chatgpt.com/backend-api/conversation', {{
                method: 'POST',
                headers: {{
                    'Authorization': 'Bearer {token}',
                    'Content-Type': 'application/json',
                    'chatgpt-account-id': '{team_id}',
                    'oai-device-id': '{device_id}',
                    'oai-language': 'en-US'
                }},
                body: JSON.stringify({json.dumps(payload)})
            }})
            .then(r => r.text().then(text => ({{status: r.status, text: text}})))
            .then(result => callback(result))
            .catch(err => callback({{status: 500, error: err.toString()}}));
        ''')
        
        driver.quit()
        
        if response.get('status') == 401:
            return {"success": False, "error": "Token失效"}
        
        if response.get('status') == 403:
            return {"success": False, "error": "请求被拒绝"}
        
        if response.get('status') != 200:
            return {"success": False, "error": f"聊天请求失败: {response.get('status')}"}
        
        # 解析响应
        response_text = response.get('text', '')
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
        return {
            "success": True,
            "data": {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
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
            }
        }
        
    except Exception as e:
        if driver:
            driver.quit()
        return {"success": False, "error": f"发生错误: {str(e)}"}
