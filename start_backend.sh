#!/bin/bash
cd /www/wwwroot/v
source venv/bin/activate
export FLASK_ENV=production
export WEBSHARE_API_TOKEN='${WEBSHARE_API_TOKEN}'
python3 app.py
