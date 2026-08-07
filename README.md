# 视频下载工具

简洁易用的**云端视频解析下载工具**,基于 yt-dlp 构建,提供友好的 Web 界面。

## ✨ 核心特性

- ✅ **临时处理**: 下载任务完成传输后立即删除,未领取文件一小时自动过期
- ✅ **统一进度**: 所有平台均显示服务器下载、合并和就绪进度
- ✅ **多平台支持**: 支持抖音、YouTube、B站、小红书、TikTok、Twitter/X
- ✅ **高清合并**: YouTube 支持 360p、720p、1080p并自动合并音视频
- ✅ **无水印下载**: 抖音视频自动获取无水印链接
- ✅ **快速解析**: 平均解析时间 1-3 秒
- ✅ **跨平台**: 支持 Windows、macOS、Linux

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- 稳定的网络连接

### 启动应用

**macOS/Linux:**
```bash
bash start.sh
```

**Windows:**
```bash
start.bat
```

启动后访问: `http://127.0.0.1:5001`

## 📖 使用说明

### 基本流程

1. **输入视频链接** - 支持抖音、YouTube、B站、Twitter 等平台
2. **点击解析** - 系统获取标题、时长、大小等信息
3. **点击下载** - 服务器创建临时后台任务并显示实时进度
4. **保存文件** - 处理完成后浏览器自动开始下载

### 工作原理

```
用户输入链接
   ↓
服务器解析视频并创建后台下载任务
   ↓
下载/合并音视频并报告进度
   ↓
用户浏览器下载处理完成的文件
   ↓
服务器删除临时文件
```

**优势:**
- 🎯 六个平台使用一致的进度和错误反馈
- ⚡ 大文件不再由浏览器先完整载入内存
- 💾 临时文件传输后删除,未领取文件一小时自动过期
- 🌐 下载队列有并发和待处理数量限制

## 🎬 支持的平台

### 完美支持(无需登录)
- ✅ **抖音** - 无水印下载,无需登录
- ✅ **YouTube** - 360p、720p、1080p,自动合并音视频
- ✅ **Bilibili** - 公开视频支持
- ✅ **TikTok** - 公开视频支持浏览器模拟解析
- ✅ **Twitter/X** - 自动下载视频

### 需要登录(可选)
- ⚠️ **小红书** - 需 cookies.txt
- ⚠️ **快手** - 需 cookies.txt
- ⚠️ **YouTube会员视频** - 需 cookies.txt

## 🔧 高级功能

### Cookies 文件

如需下载会员/私密内容,可在项目目录放置 `cookies.txt`:

```bash
# 从浏览器导出 cookies
# 使用浏览器插件: "Get cookies.txt"
# 保存为: /path/to/project/cookies.txt
```

## 🌐 服务器部署

### 部署优势

- ✅ 临时文件自动清理
- ✅ 下载任务实时进度
- ✅ 最多 2 个并发处理任务、12 个待处理任务
- ⚠️ 需预留临时磁盘空间并安装 ffmpeg

### 必需文件清单

```
app.py                  # Flask 主程序
downloader.py           # 下载服务
douyin_service.py       # 抖音解析
douyin_parser.py        # 抖音工具
utils.py                # 工具函数
requirements.txt        # 依赖声明
start.sh                # Linux 启动
templates/              # 前端模板
  └── index.html
static/                 # 静态资源
  ├── script.js
  └── style.css
```

**总大小:** ~140KB (不含 cookies.txt)

### 快速部署

```bash
# 1. 上传文件到服务器
scp -r ./* server:/path/to/video/

# 2. 服务器安装依赖
ssh server
cd /path/to/video
bash start.sh
```

### 生产环境配置

当前任务状态保存在进程内存中，生产环境应使用单进程多线程模式：

```bash
# 安装 Gunicorn
pip install gunicorn

# 后台任务最长允许 15 分钟
gunicorn -w 1 -b 0.0.0.0:5001 --threads 8 --timeout 1200 app:app
```

## 📊 并发能力

| 运行模式 | 并发解析 | 适用场景 |
|---------|---------|---------|
| Flask开发服务器 | 最多2个下载任务 | 本地测试 |
| Gunicorn (1进程x8线程) | 最多2个下载任务、12个待处理 | 生产环境 |

## ⚠️ 注意事项

### 下载链接时效性

不同平台的视频链接有效期:
- YouTube: 约 6 小时
- 抖音: 约 2-4 小时
- B站: 约 1-2 小时

**建议:** 解析后立即下载

### 跨域问题

某些平台可能有 CORS 限制:
- 浏览器会自动处理
- 如遇问题,可使用浏览器扩展(如 CORS Unblock)

## 🐛 常见问题

### Q: 解析失败怎么办?

**A:** 可能原因:
1. 视频链接无效/已删除
2. 视频需要登录查看
3. 网络连接问题
4. 平台反爬限制

**解决方案:**
- 确认链接有效
- 需要登录的平台请使用 cookies.txt
- 检查网络连接
- 更新 yt-dlp: `pip install -U yt-dlp`

### Q: 自动下载失败?

**A:** 可能是浏览器阻止了自动下载

**解决方案:**
1. 允许网站弹窗/下载
2. 检查浏览器下载设置
3. 手动点击提供的下载链接

### Q: 可以批量下载吗?

**A:** 当前版本不支持批量下载

**原因:** 每个链接需要独立解析,避免服务器压力过大

## 📁 项目结构

```
video/
├── app.py                      # Flask Web服务
├── downloader.py               # 视频解析核心
├── douyin_service.py           # 抖音专用服务
├── douyin_parser.py            # 抖音URL解析
├── utils.py                    # 工具函数
├── requirements.txt            # Python依赖
├── start.sh                    # 启动脚本
├── templates/
│   └── index.html             # Web界面
├── static/
│   ├── script.js              # 前端逻辑
│   └── style.css              # 样式表
└── docs/                       # 文档
```

## 🔒 隐私与安全

- ✅ 不收集用户数据
- ✅ 视频仅在下载处理期间临时保存
- ✅ 文件传输结束后删除,未领取文件一小时自动过期
- ✅ 不保存浏览记录
- ⚠️ 请勿上传 cookies.txt 到公开仓库

## 📜 许可证

本项目仅供学习和个人使用,请遵守:
- 视频平台服务条款
- 版权法相关规定
- 不得用于商业用途

## 🙏 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
- [Flask](https://flask.palletsprojects.com/) - 轻量级 Web 框架

## 🆘 获取帮助

遇到问题?
1. 查看 [常见问题](#常见问题)
2. 检查 [GitHub Issues](https://github.com/yt-dlp/yt-dlp/issues)
3. 更新到最新版本

---

**版本:** v0.7 - 全平台统一下载进度
**更新日期:** 2026-08-07
