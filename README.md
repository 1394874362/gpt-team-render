# GPT Team Invite - Python邀请服务

## 🎯 用途

这是一个Python Flask服务，用于代替Cloudflare Worker发送ChatGPT Team邀请。

**为什么需要这个？**
- Cloudflare Worker IP被chatgpt.com封禁（403 Forbidden）
- Python + curl_cffi可以完美模拟浏览器特征
- 部署在Railway/Render等平台，IP不被封

## 📦 部署到Railway

### 1. 创建Railway项目

1. 访问：https://railway.app
2. 登录GitHub账号
3. 点击 "New Project" → "Deploy from GitHub repo"
4. 选择这个文件夹（或上传到GitHub）

### 2. 环境变量配置（可选）

在Railway Dashboard设置：

```
PROXY_URL=http://your-proxy-server:port  # 如果需要代理
WORKER_API=https://gpt-team-api.2804402637.workers.dev
```

### 3. 部署

Railway会自动：
- 读取`requirements.txt`安装依赖
- 读取`Procfile`启动服务
- 分配域名：`https://your-app.railway.app`

## 🔧 本地测试

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python app.py

# 测试
curl http://localhost:5000/health
```

## 📡 API端点

### POST /api/send-invite

发送邀请请求

**请求：**
```json
{
  "token": "Bearer ey...",
  "teamId": "org-xxx",
  "email": "user@example.com"
}
```

**响应（成功）：**
```json
{
  "code": 200,
  "message": "邀请发送成功",
  "data": {
    "inviteSuccess": true
  }
}
```

**响应（失败）：**
```json
{
  "code": 403,
  "message": "HTTP 403: Forbidden",
  "data": {
    "inviteSuccess": false,
    "error": "..."
  }
}
```

## 🌐 前端集成

修改`index-configured.html`：

```javascript
// 改为调用Python服务而不是Worker代理
const PYTHON_API = 'https://your-app.railway.app';

// 步骤2：调用Python服务发送邀请
const proxyRes = await fetch(PYTHON_API + '/api/send-invite', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        token: inviteData.token,
        teamId: inviteData.teamId,
        email: inviteData.email
    })
});
```

## 🚀 完整架构

```
用户浏览器
  ↓
Cloudflare Pages (静态前端)
  ↓
Cloudflare Worker (卡密验证、数据库)
  ↓
Python Service (Railway) - 发送邀请
  ↓ (可选代理)
chatgpt.com ✅
```

## 🔒 优势

- ✅ **curl_cffi完美伪装**：TLS指纹、HTTP/2特征
- ✅ **非Cloudflare IP**：Railway服务器IP不在黑名单
- ✅ **可配置代理**：如果直连还是被封，可以加代理
- ✅ **免费额度**：Railway提供免费试用

## ⚠️ 注意事项

1. **代理配置**：如果Railway服务器还是被封，需要配置代理
2. **环境变量**：敏感信息用环境变量，不要硬编码
3. **CORS**：已配置，允许Cloudflare Pages跨域调用
