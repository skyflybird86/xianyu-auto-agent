#!/bin/bash

# 闲鱼自动回复机器人打包脚本

echo "========================================="
echo "   闲鱼自动回复机器人 - 打包脚本"
echo "========================================="
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 正在创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

# 检查PyInstaller
echo ""
echo "🔧 检查PyInstaller..."
if ! command -v pyinstaller &> /dev/null; then
    echo "📦 正在安装PyInstaller..."
    pip install pyinstaller
fi

# 安装项目依赖
echo ""
echo "📦 安装项目依赖..."
pip install -r requirements.txt

echo ""
echo "🔧 开始打包..."
echo ""

# 使用spec文件打包（--noconfirm避免交互式确认）
pyinstaller --clean --noconfirm build.spec

echo ""
echo "✅ 打包完成！"
echo "📁 可执行文件位置: dist/"
echo ""
echo "========================================="
