#!/bin/bash
# 生产环境启动示例。密钥请用环境变量注入，不要写进本文件。
cd "$(dirname "$0")"
source venv/bin/activate
export FLASK_ENV=production
# 可选：YouTube 受限地区代理
# export YOUTUBE_PROXY='socks5://user:pass@host:port'
# export IPROYAL_PROXY='socks5://user:pass@host:port'
python3 app.py
