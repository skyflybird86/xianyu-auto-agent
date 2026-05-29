#!/bin/bash

# 闲鱼自动回复机器人启动脚本

echo "========================================="
echo "   闲鱼自动回复机器人"
echo "========================================="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python"
    exit 1
fi

echo "✅ Python3已安装"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 正在创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖
echo ""
echo "📦 正在检查依赖..."
pip install -q -r requirements.txt

# 检查激活状态
echo ""
echo "🔐 正在检查激活状态..."
python3 -c "from activation import is_activated; exit(0 if is_activated() else 1)"
if [ $? -ne 0 ]; then
    echo "❌ 未激活"
    python3 activation.py
    if [ $? -ne 0 ]; then
        exit 1
    fi
    echo "✅ 激活成功"
else
    echo "✅ 已激活"
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo ""
    echo "📝 正在创建配置文件..."
    cp .env.example .env
    echo ""
    echo "⚠️  请先在Web界面配置必要的参数！"
fi

echo ""
echo "🚀 正在启动服务..."
echo ""
echo "📱 Web管理界面: http://localhost:8080"
echo "💡 提示: 首次使用请打开Web界面配置Cookie和API Key"
echo ""
echo "按 Ctrl+C 停止服务"
echo "========================================="
echo ""

python3 main.py
