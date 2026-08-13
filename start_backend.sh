#!/bin/bash
# 生产环境启动。密钥/代理等服务器专属配置放在同目录 .env 文件（不进仓库），启动时自动注入。
cd "$(dirname "$0")"
source venv/bin/activate
export FLASK_ENV=production
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi
python3 app.py
