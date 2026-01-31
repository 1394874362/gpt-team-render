# -*- coding: utf-8 -*-
"""
简化版聊天实现 - 使用 curl-cffi + 会话保持
比 Playwright 轻量，适合 Render 免费套餐
"""
import json
import uuid
import time
from curl_cffi import requests as cffi_requests

# 全局会话缓存（按 token 缓存）
_session_cache = {}
_cache_timeout = 3600  # 1小时过期

def get_or_create_session(token):
    """获取或创建会话"""
    current_time = time.time()
    
    # 清理过期会话
    expired_tokens = [t for t, (sess, ts) in _session_cache.items() if current_time - ts > _cache_timeout]
    for t in expired_tokens:
        try:
            _session_cache[t][0].close()
        except:
            pass
        del _session_cache[t]
    
    # 返回现有会话或创建新会话
    if token in _session_cache:
        session, _ = _session_cache[token]
        _session_cache[token] = (session, current_time)  # 更新时间戳
        return session
    
    # 创建新会话
    session = cffi_requests.Session(impersonate="chrome120")
    _session_cache[token] = (session, current_time)
    return session

def chat_simple(token, messages, model='gpt-4', stream=False, team_id=None, proxy_url=None):
    """
    简化版聊天实现
    
    Args:
        token: ChatGPT access token
        messages: 消息列表 [{"role": "user", "content": "..."}]
        model: 模型名称
        stream: 是否流式输出
        team_id: Team ID (可选)
        proxy_url: 代理 URL (可选)
    
    Returns:
        dict: {"success": bool, "data": dict, "error": str}
    """
    try:
        # 使用会话缓存
        session = get_or_create_session(token)
        
        # 设置代理
        if proxy_url:
            session.proxies = {"http": proxy_url, "https": proxy_url}
        
        device_id = str(uuid.uuid4())
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/event-stream" if stream else "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "oai-device-id": device_id,
            "oai-language": "en-US",
            "Referer": "https://chatgpt.com/",
            "Origin": "https://chatgpt.com",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        
        # 如果没有 team_id，先获取
        if not team_id:
            print("[Simple] 获取 Team ID...")
            check_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27"
            
            try:
                check_resp = session.get(check_url, headers=headers, timeout=15)
                
                if check_resp.status_code == 401:
                    return {"success": False, "error": "Token失效"}
                
                if check_resp.status_code != 200:
                    return {"success": False, "error": f"获取账号信息失败: {check_resp.status_code}"}
                
                accounts_data = check_resp.json()
                accounts_dict = accounts_data.get('accounts', {})
                
                for acc_id, info in accounts_dict.items():
                    if acc_id.startswith('org-') or 'team' in info.get('account', {}).get('plan_type', '').lower():
                        team_id = acc_id
                        break
                
                if not team_id and accounts_dict:
                    team_id = list(accounts_dict.keys())[0]
                
                if not team_id:
                    return {"success": False, "error": "该账号没有可用的workspace"}
                
                print(f"[Simple] 使用 Team ID: {team_id}")
            except Exception as e:
                return {"success": False, "error": f"获取Team ID失败: {str(e)}"}
        
        # 添加 team_id 到请求头
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
        
        # 发送聊天请求
        print("[Simple] 发送聊天请求...")
        chat_url = "https://chatgpt.com/backend-api/conversation"
        
        try:
            chat_resp = session.post(chat_url, headers=headers, json=payload, timeout=120)
            
            if chat_resp.status_code == 401:
                return {"success": False, "error": "Token失效"}
            
            if chat_resp.status_code == 403:
                return {"success": False, "error": "请求被拒绝（Cloudflare拦截）"}
            
            if chat_resp.status_code != 200:
                error_text = chat_resp.text[:200] if chat_resp.text else f"HTTP {chat_resp.status_code}"
                return {"success": False, "error": f"聊天请求失败: {error_text}"}
            
            # 解析响应
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
            return {"success": False, "error": f"请求异常: {str(e)}"}
            
    except Exception as e:
        return {"success": False, "error": f"发生错误: {str(e)}"}
