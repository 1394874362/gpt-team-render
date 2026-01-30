#!/bin/bash
# 腾讯云启动脚本 (Tencent Cloud Start Script)

# 1. 安装依赖 / Install Dependencies
echo "📦 Installing dependencies..."
# 尝试使用 pip3，如果不存在则使用 pip
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
else
    pip install -r requirements.txt
fi

# 2. 设置环境变量 / Set Env Vars
export PORT=5000

# 3. 启动应用 / Start App
echo "🚀 Starting GPT Team Invite Service on port $PORT..."
echo "ℹ️  Ensure your Tencent Cloud Firewall allows TCP port $PORT"

if command -v python3 &> /dev/null; then
    python3 app.py
else
    python app.py
fi
