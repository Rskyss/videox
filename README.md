# VideoX · 视频解析神器

开源的网页版视频解析下载工具。粘贴链接即可解析，支持抖音、B站、小红书、YouTube、TikTok、Twitter/X。

在线体验（可选）：[https://vd.aisoup.ai](https://vd.aisoup.ai)

---

## 你下载本仓库后怎么用

### 1. 环境要求

- Python 3.8+
- 建议安装 [ffmpeg](https://ffmpeg.org/)（B站 / YouTube 等高清合并需要）

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 2. 安装并启动

```bash
git clone https://github.com/Rskyss/videox.git
cd videox

# 安装依赖
python3 -m pip install -r requirements.txt

# 一键启动（macOS / Linux）
bash start.sh
```

浏览器打开：**http://127.0.0.1:5001**

也可以手动启动：

```bash
python3 app.py
```

### 3. 页面上怎么操作

1. 把视频分享链接粘贴到输入框  
2. 点击「解析」  
3. 确认标题、时长、大小后点击「下载」  
4. 等待进度完成后，浏览器会保存视频文件  

说明：下载任务会先在**本机服务进程**里处理（含音视频合并），完成后再交给浏览器保存；临时文件传完会删除，未领取大约一小时后自动清理。

---

## 支持平台

| 平台 | 说明 |
|------|------|
| 抖音 | 优先无水印解析 |
| B站 | 公开视频；部分情况需要登录 cookies |
| 小红书 | 通常需要 cookies |
| YouTube | 支持 360p / 720p / 1080p 合并 |
| TikTok | 公开视频 |
| Twitter/X | 公开视频 |

### 可选：登录态 cookies

若解析提示需要登录，或会员/私密内容失败：

1. 浏览器登录对应平台  
2. 用扩展 **Get cookies.txt LOCALLY** 导出  
3. 保存为项目根目录的 `cookies.txt`（此文件已加入 `.gitignore`，请勿提交）

---

## 可选配置

复制环境变量示例：

```bash
cp .env.example .env
```

如需 YouTube 代理，可在启动前设置：

```bash
export YOUTUBE_PROXY='socks5://user:pass@host:port'
# 或
export IPROYAL_PROXY='socks5://user:pass@host:port'
```

生产环境可用：

```bash
bash start_backend.sh
# 或
gunicorn -w 1 -b 0.0.0.0:5001 --threads 8 --timeout 1200 app:app
```

并发默认：最多 2 个下载任务处理中，最多 12 个排队。

---

## 常见问题

**解析失败？**  
检查链接是否有效、是否需要登录、网络是否正常；需要登录时补充 `cookies.txt`；并升级解析组件：

```bash
python3 -m pip install -U yt-dlp
```

**下载一直 0% / 很慢？**  
大视频（例如数 GB）会占用本机带宽与磁盘，请耐心等待，或换较短视频测试。

**找不到 ffmpeg？**  
先安装 ffmpeg，否则部分平台无法合并音视频。

**可以商用吗？**  
本项目仅供学习与个人使用，请遵守各平台服务条款与版权规定。

---

## 项目结构（精简）

```
videox/
├── app.py              # Web 服务与下载任务
├── downloader.py       # 解析 / 下载核心
├── douyin_service.py   # 抖音解析
├── templates/          # 页面
├── static/             # 前端脚本与样式
├── requirements.txt
├── start.sh            # 本地一键启动
└── .env.example        # 环境变量示例
```

---

## 隐私

- 不收集用户账号密码  
- 视频仅临时处理，传输后删除  
- **不要**把 `cookies.txt`、真实 `.env` 上传到 GitHub  

---

## 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [Flask](https://flask.palletsprojects.com/)

## 版本

**v0.7.1** · 2026-08-07 · 开源清理与使用说明完善
