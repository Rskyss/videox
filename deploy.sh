#!/bin/bash
set -e

# 部署配置
PROJECT_NAME="v"
PORT_BACKEND="5009"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 开始部署项目: $PROJECT_NAME"
echo "📁 当前目录: $CURRENT_DIR"

# 已经在项目目录中，直接配置环境


# 配置后端
echo "🐍 配置Python应用..."

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# ========================================
# 环境检测和自动修复（本地已分析）
# ========================================
echo ""
echo "🔍 检测项目运行环境..."

# 检测并安装 ffmpeg（本地分析检测到使用）
echo "  ▶ 检查 ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "    ⚠️  ffmpeg 未安装，正在自动安装..."
    
    # 尝试使用包管理器安装
    if command -v apt &> /dev/null; then
        sudo apt install -y ffmpeg 2>/dev/null || true
    elif command -v yum &> /dev/null; then
        sudo yum install -y ffmpeg 2>/dev/null || true
    fi
    
    # 如果包管理器安装失败，使用静态编译版本
    if ! command -v ffmpeg &> /dev/null; then
        echo "    → 使用静态编译版本安装..."
        (
            cd /tmp
            wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz 2>/dev/null || curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg-release-amd64-static.tar.xz
            if [ -f ffmpeg-release-amd64-static.tar.xz ]; then
                tar xf ffmpeg-release-amd64-static.tar.xz 2>/dev/null
                cd ffmpeg-*-static 2>/dev/null
                sudo cp ffmpeg ffprobe /usr/local/bin/ 2>/dev/null || cp ffmpeg ffprobe ~/bin/
                cd /tmp
                rm -rf ffmpeg-* 2>/dev/null
            fi
        )
    fi
    
    # 验证安装
    if command -v ffmpeg &> /dev/null; then
        echo "    ✓ ffmpeg 安装成功 ($(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3))"
    else
        echo "    ✗ ffmpeg 安装失败，相关功能可能不可用"
    fi
else
    echo "    ✓ ffmpeg 已就绪 ($(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3))"
fi

# 检测并安装 yt-dlp（本地分析检测到使用）
echo "  ▶ 检查 yt-dlp..."
if ! command -v yt-dlp &> /dev/null; then
    echo "    ⚠️  yt-dlp 未安装，正在尝试自动安装..."
    
    # 尝试使用包管理器安装
    if command -v apt &> /dev/null; then
        sudo apt install -y yt-dlp 2>/dev/null && echo "    ✓ yt-dlp 安装成功" || echo "    ✗ yt-dlp 安装失败，请手动安装"
    elif command -v yum &> /dev/null; then
        sudo yum install -y yt-dlp 2>/dev/null && echo "    ✓ yt-dlp 安装成功" || echo "    ✗ yt-dlp 安装失败，请手动安装"
    else
        echo "    ✗ 无法自动安装 yt-dlp，请手动安装"
    fi
else
    echo "    ✓ yt-dlp 已就绪"
fi

# 检测 cookies.txt（用于需要认证的项目）
if [ -f "cookies.txt" ]; then
    echo "  ▶ 检查 cookies.txt..."
    COOKIE_SIZE=$(wc -c < cookies.txt 2>/dev/null || echo "0")
    if [ "$COOKIE_SIZE" -gt 1000 ]; then
        echo "    ✓ cookies.txt 文件正常 ($(numfmt --to=iec-i --suffix=B $COOKIE_SIZE 2>/dev/null || echo ${COOKIE_SIZE}B))"
    else
        echo "    ⚠️  cookies.txt 文件可能不完整或为空 (${COOKIE_SIZE} bytes)"
    fi
fi

echo "✓ 环境检测完成"
echo ""

# 安装Playwright浏览器（用于页面解析）
echo "📦 安装Playwright浏览器..."
playwright install chromium 2>/dev/null || echo "Playwright安装可选，跳过"

# 端口已在本地从 5003 修改为 $PORT_BACKEND
echo "✓ 应用端口已配置为 $PORT_BACKEND"

# 创建后端启动脚本
cat > start_backend.sh << 'EOF'
#!/bin/bash
cd $CURRENT_DIR
source venv/bin/activate
export FLASK_ENV=production
python3 app.py
EOF

chmod +x start_backend.sh

# 创建Nginx配置提示
cat > nginx_config.txt << 'EOF'
宝塔面板配置说明：

1. 这是一个Flask应用（纯后端）
   - 域名: video.aisoup.cn
   - 根目录: $CURRENT_DIR
   - 运行目录: $CURRENT_DIR

2. 配置反向代理
   - 代理名称: v
   - 目标URL: http://127.0.0.1:$PORT_BACKEND
   - 代理目录: /
   - 发送域名: $host

3. 启动应用
   cd $CURRENT_DIR
   pm2 start start_backend.sh --name v --interpreter bash
   
4. 查看日志
   pm2 logs v
   
5. 停止/重启
   pm2 stop v
   pm2 restart v
EOF

echo "✅ 部署完成！"
echo "📁 项目位置: $CURRENT_DIR"
echo ""
echo "📌 下一步操作："
echo "1. 在宝塔面板配置网站和反向代理"
echo "2. 使用 pm2 启动应用"
echo "3. 查看 nginx_config.txt 获取详细配置说明"
