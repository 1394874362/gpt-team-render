# Render 完整部署指南

## 🎯 目标
将整个邀请系统迁移到Render，完全脱离Cloudflare，避免被检测。

## 📦 文件结构
```
railway-deploy/
├── app.py              # Flask后端（已扩展）
├── database.py         # SQLite数据库管理
├── requirements.txt    # Python依赖
├── static/            # 静态文件
│   └── link.html      # 邀请页面
└── README_RENDER.md   # 本文件
```

## 🚀 部署步骤

### 步骤1：更新依赖文件
确保`requirements.txt`包含所有必要的依赖。

### 步骤2：准备数据

#### 方案A：手动创建测试数据
服务启动后，数据库会自动初始化。您需要：
1. 访问Python终端
2. 手动插入邀请链接和账号数据

#### 方案B：从Cloudflare D1 导出数据
1. 导出D1数据（如果有）
2. 导入到SQLite

### 步骤3：配置环境变量
在Render服务中配置以下环境变量：
```
PORT=5000
BOT_TOKEN=您的Telegram Bot Token
```

### 步骤4：部署到Render

1. **登录Render Dashboard**
   - 访问 https://dashboard.render.com/

2. **选择现有服务**
   - 找到您现有的Python服务

3. **上传新代码**
   - 方式1：通过Git推送
   - 方式2：手动上传文件

4. **等待部署完成**
   - Render会自动安装依赖并启动服务

### 步骤5：添加初始数据

#### 创建测试邀请链接
通过Python shell创建：

```python
import database as db
import sqlite3

# 初始化数据库
db.init_database()

# 创建测试邀请链接
with db.get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invite_links (link_code, name, validity_type, max_uses, is_active)
        VALUES ('test2024', '测试链接', 'month', 100, 1)
    """)
    conn.commit()

print("✅ 创建测试链接: test2024")
```

#### 添加账号
您需要先从Telegram bot或其他渠道获取Team账号，然后：

```python
with db.get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO accounts (name, account_id, authorization_token, is_active, max_invites)
        VALUES (?, ?, ?, 1, 8)
    """, ('test@example.com', 'org-xxx', 'Bearer your-token-here'))
    conn.commit()

print("✅ 添加账号成功")
```

### 步骤6：测试系统

测试邀请链接：
```
https://your-app.onrender.com/link/test2024
```

测试API：
```bash
# 测试获取链接信息
curl https://your-app.onrender.com/api/link-info?code=test2024

# 测试兑换链接
curl -X POST https://your-app.onrender.com/api/redeem-link \
  -H "Content-Type: application/json" \
  -d '{"linkCode":"test2024","email":"user@example.com"}'
```

## 🔧 常见问题

### Q1: 如何访问SQLite数据库？
Render提供SSH访问（付费版）。免费版可以通过API查询或使用Python shell。

### Q2: 如何备份数据库？
可以添加一个API端点来导出数据：

```python
@app.route('/admin/export-db')
def export_db():
    # 需要添加权限验证
    import json
    with db.get_db() as conn:
        cursor = conn.cursor()
        # 导出所有表...
```

### Q3: 数据库文件会丢失吗？
Render的免费服务在重启时可能会丢失文件。建议：
1. 使用Render PostgreSQL（免费）
2. 定期备份到外部存储
3. 使用环境变量存储关键配置

### Q4: 如何从Cloudflare D1迁移数据？
1. 使用Wrangler CLI导出D1数据
2. 转换为SQLite格式
3. 上传到Render

## 📊 系统架构

```
用户浏览器
    ↓
Render服务器 (Flask)
    ├── 前端 (link.html)
    ├── API (链接兑换、邀请)
    └── 数据库 (SQLite)
         ↓
    通过curl_cffi发送邀请
         ↓
    ChatGPT API
```

**优势**：
- ✅ 完全脱离Cloudflare
- ✅ 所有服务在一个地方
- ✅ 避免检测风险

## 🎨 自定义

### 修改前端样式
编辑 `static/link.html`

### 添加管理后台
您可以将`admin.html`也迁移过来

### 添加更多API
在`app.py`中添加更多路由

## 🛡️ 安全建议

1. **添加API认证**
   - 对管理接口添加密码保护
   - 使用JWT令牌

2. **限制访问频率**
   - 添加速率限制（Flask-Limiter）

3. **环境变量**
   - 不要在代码中硬编码敏感信息

## 📝 下一步

1. 从Cloudflare D1导出数据（如果需要）
2. 部署到Render
3. 添加初始数据
4. 测试功能
5. 从旧系统切换到新系统

## 🆘 需要帮助？

如果遇到问题，请检查：
1. Render服务日志
2. 环境变量配置
3. 数据库是否初始化成功
