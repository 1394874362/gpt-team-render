#!/bin/bash
# Render 部署脚本

echo "📦 安装 Python 依赖..."
pip install -r requirements.txt

echo "🎭 安装 Playwright 浏览器..."
playwright install chromium

echo "✅ 部署完成！"
