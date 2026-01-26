import os
import requests
import json

# 配置 (请将在 Cloudflare 获取的 API Token 填入环境变量或直接此处)
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "TBS2n9A0ifOB4X_jek8DCeiSbRpTvu1P7vqvqrzV") 
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "9093a1e8decd33855afb2c1ba429c2ae")

CF_DB_ID = os.environ.get("CF_DB_ID", "4b1f7165-2b4e-473f-984f-415d8693740b")

def query_d1(sql, params=None):
    """
    通过 HTTP API 执行 D1 SQL 查询
    """
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{CF_DB_ID}/query"
    
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "sql": sql,
        "params": params or []
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                # D1 API 返回结构通常包含 result[0].results
                # 取决于查询类型，返回可能略有不同
                if result.get("result") and len(result["result"]) > 0:
                    return result["result"][0].get("results", [])
                return []
            else:
                print(f"D1 API 错误: {result.get('errors')}")
                return None
        else:
            print(f"HTTP 请求失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"执行异常: {e}")
        return None

# 示例: 获取所有账号
def get_all_accounts():
    return query_d1("SELECT * FROM accounts")

# 示例: 你之前逻辑需要的 invite 次数最少的账号
def get_best_account_from_d1():
    sql = """
    SELECT * FROM accounts 
    WHERE is_active = 1 
    ORDER BY used_invites ASC 
    LIMIT 20
    """
    accounts = query_d1(sql)
    if accounts:
        # 二次筛选（虽然 SQL 已经排好序，但可以在这里加更多逻辑）
        # 注意: D1 API 返回的是字典列表
        return accounts[0] # 返回第一个即可
    return None
