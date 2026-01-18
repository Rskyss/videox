#!/bin/bash
# 视频解析服务 - 每周自动重启脚本
# 建议配置 cron 定时任务: 0 4 * * 1 /www/wwwroot/vd/restart_service.sh
# 每周一凌晨4点自动重启服务

cd /www/wwwroot/vd

# 记录重启时间
echo "[$(date +%Y-%m-%d\ %H:%M:%S)] 执行每周定时重启" >> /www/wwwroot/vd/restart.log

# 找到并杀掉旧的 app.py 进程
pkill -f "python3 app.py" 2>/dev/null
sleep 2

# 启动新的服务
source venv/bin/activate
nohup python3 app.py >> backend.log 2>&1 &

echo "[$(date +%Y-%m-%d\ %H:%M:%S)] 服务重启完成, 新进程 PID: $!" >> /www/wwwroot/vd/restart.log
