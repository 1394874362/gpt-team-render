# -*- coding: utf-8 -*-
"""
使用 Playwright 绕过 Cloudflare 调用 ChatGPT API
"""
import json
import uuid
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def chat_with_playwright(token, messages, model='gpt-4', stream=False, team_id=None):
    """
    使用 Playwright 调用 ChatGPT API
    
    Args:
        token: ChatGPT access token
        messages: 消息列表 [{"role": "user", "content": "..."}]
        model: 模型名称
        stream: 是否流式输出
        team_id: Team ID (可选)
    
    Returns:
        dict: {"success": bool, "data": dict, "error": str}
    """
    with sync_playwright() as p:
        try:
            # 启动浏览器（使用 chromium）
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            
            # 创建上下文和页面
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = context.new_page()
            
            # 设置 localStorage 和 cookies
            page.goto('https://chatgpt.com')
            
            # 注入 token
            page.evaluate(f'''() => {{
                localStorage.setItem('access_token', '{token}');
            }}''')
            
            device_id = str(uuid.uuid4())
            
            # 如果没有 team_id，先获取
            if not team_id:
                print("[Playwright] 获取 Team ID...")
                response = page.request.get(
                    'https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27',
                    headers={
                        'Authorization': f'Bearer {token}',
                        'oai-device-id': device_id,
                        'oai-language': 'en-US'
                    }
                )
                
                if response.status == 401:
                    browser.close()
                    return {"success": False, "error": "Token失效"}
                
                if response.status != 200:
                    browser.close()
                    return {"success": False, "error": f"获取账号信息失败: {response.status}"}
                
                accounts_data = response.json()
                accounts_dict = accounts_data.get('accounts', {})
                
                for acc_id, info in accounts_dict.items():
                    if acc_id.startswith('org-') or 'team' in info.get('account', {}).get('plan_type', '').lower():
                        team_id = acc_id
                        break
                
                if not team_id and accounts_dict:
                    team_id = list(accounts_dict.keys())[0]
                
                if not team_id:
                    browser.close()
                    return {"success": False, "error": "该账号没有可用的workspace"}
                
                print(f"[Playwright] 使用 Team ID: {team_id}")
            
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
            print("[Playwright] 发送聊天请求...")
            response = page.request.post(
                'https://chatgpt.com/backend-api/conversation',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'chatgpt-account-id': team_id,
                    'oai-device-id': device_id,
                    'oai-language': 'en-US'
                },
                data=json.dumps(payload)
            )
            
            if response.status == 401:
                browser.close()
                return {"success": False, "error": "Token失效"}
            
            if response.status == 403:
                browser.close()
                return {"success": False, "error": "请求被拒绝"}
            
            if response.status != 200:
                browser.close()
                return {"success": False, "error": f"聊天请求失败: {response.status}"}
            
            # 解析响应
            response_text = response.text()
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
            
            browser.close()
            
            # 返回 OpenAI 兼容格式
            return {
                "success": True,
                "data": {
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
                }
            }
            
        except PlaywrightTimeout as e:
            if 'browser' in locals():
                browser.close()
            return {"success": False, "error": f"请求超时: {str(e)}"}
        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return {"success": False, "error": f"发生错误: {str(e)}"}
