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

echo "[1/4] Python 环境检测通过"
echo ""

# 检查并安装依赖
echo "[2/4] 正在检查并安装依赖..."
python3 -m pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "[警告] 依赖安装可能未完全成功，但会继续尝试启动"
fi
echo ""

# 安装Playwright浏览器
echo "[3/4] 正在检查 Playwright 浏览器..."
if command -v playwright &> /dev/null; then
    # 检查chromium是否已安装
    if ! python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.executable_path; p.stop()" &> /dev/null; then
        echo "正在安装 Chromium 浏览器（仅首次需要，约 300MB）..."
        python3 -m playwright install chromium
        if [ $? -ne 0 ]; then
            echo "[警告] Playwright 浏览器安装失败，抖音下载可能受影响"
        fi
    else
        echo "Playwright Chromium 已就绪"
    fi
else
    echo "[警告] Playwright 未安装，抖音下载功能可能受限"
fi
echo ""

# 启动Flask应用
echo "[4/4] 正在启动 Web 服务..."
echo ""
echo "========================================"
echo "应用启动成功！"
echo "访问地址: http://127.0.0.1:5009"
echo "或访问: http://localhost:5009"
echo "按 Ctrl+C 可停止服务"
echo "========================================"
echo ""

# 等待1秒后打开浏览器
sleep 1

# 根据操作系统打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open http://localhost:5009
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:5009
    fi
fi

# 启动Flask应用
python3 app.py
