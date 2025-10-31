#!/bin/bash
# YouTube 代理快速配置脚本

echo "🚀 YouTube 代理快速配置"
echo "======================================"
echo ""

# 检查配置文件
if [ ! -f "/www/wwwroot/v/proxy_config.txt" ]; then
    echo "❌ 错误: 找不到 proxy_config.txt"
    exit 1
fi

echo "✅ 找到配置文件"
echo ""

# 加载配置
echo "📋 加载代理配置..."
source /www/wwwroot/v/proxy_config.txt

# 检查环境变量
if [ -n "$YOUTUBE_PROXY" ]; then
    proxy_count=$(echo "$YOUTUBE_PROXY" | tr ',' '\n' | wc -l)
    echo "✅ YOUTUBE_PROXY 已配置 ($proxy_count 个代理)"
elif [ -n "$WEBSHARE_API_TOKEN" ]; then
    echo "✅ WEBSHARE_API_TOKEN 已配置 (API 自动同步模式)"
else
    echo "❌ 错误: 未配置代理"
    echo ""
    echo "请编辑 /www/wwwroot/v/proxy_config.txt 并配置："
    echo "  - YOUTUBE_PROXY (手动配置)"
    echo "  - 或 WEBSHARE_API_TOKEN (API 自动同步)"
    exit 1
fi

echo ""
echo "🧪 运行测试..."
echo ""

# 运行测试
/www/server/pyporject_evn/v/bin/python /www/wwwroot/v/test_youtube_proxy.py

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "🎉 配置成功！"
    echo "======================================"
    echo ""
    echo "下一步："
    echo "1. 将以下行添加到您的应用启动脚本："
    echo "   source /www/wwwroot/v/proxy_config.txt"
    echo ""
    echo "2. 重启您的应用"
    echo ""
    echo "3. YouTube 视频将自动通过代理解析"
    echo ""
else
    echo ""
    echo "======================================"
    echo "⚠️  测试失败"
    echo "======================================"
    echo ""
    echo "请检查："
    echo "1. 代理配置是否正确"
    echo "2. Webshare 账号状态"
    echo "3. 网络连接是否正常"
    echo ""
    echo "详细说明请查看: /www/wwwroot/v/PROXY_README.md"
fi
