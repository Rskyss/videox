#!/bin/bash

echo "========================================"
echo "视频下载工具 - 启动中..."
echo "========================================"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python 环境"
    echo "请先安装 Python 3.8 或更高版本"
    echo "macOS: brew install python3"
    echo "Ubuntu/Debian: sudo apt install python3 python3-pip"
    exit 1
fi

echo "[1/3] Python 环境检测通过"
echo ""

# 检查并安装依赖
echo "[2/3] 正在检查并安装依赖..."
python3 -m pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "[警告] 依赖安装可能未完全成功，但会继续尝试启动"
fi
echo ""

# 启动Flask应用
echo "[3/3] 正在启动 Web 服务..."
echo ""
echo "========================================"
echo "应用启动成功！"
echo "访问地址: http://127.0.0.1:5001"
echo "或访问: http://localhost:5001"
echo "按 Ctrl+C 可停止服务"
echo "========================================"
echo ""

# 等待1秒后打开浏览器
sleep 1

# 根据操作系统打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open http://localhost:5001
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:5001
    fi
fi

# 启动Flask应用
python3 app.py
