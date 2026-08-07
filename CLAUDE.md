# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 Flask 和 yt-dlp 的云端视频解析下载工具,支持抖音、YouTube、B站、小红书、TikTok、Twitter/X。下载阶段使用统一后台任务：服务器临时下载/合并并报告进度，文件传输结束后删除，未领取文件一小时自动过期。

## 常用命令

### 开发与运行

```bash
# 启动应用(macOS/Linux)
bash start.sh

# 启动应用(Windows)
start.bat

# 生产环境部署(使用Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5001 --threads 4 --timeout 60 app:app

# 安装依赖
pip3 install -r requirements.txt

# 手动启动(调试模式)
python3 app.py
```

### 端口配置

- 默认端口: 5001 (在 app.py:614 中配置)
- start.sh 中配置的端口: 5009 (line 33)
- 部署时请统一端口配置

## 核心架构

### 1. 模块分层

```
┌─────────────────────────────────────┐
│     Flask Web 层 (app.py)           │  ← 路由、API接口、代理服务
├─────────────────────────────────────┤
│  视频解析层                          │
│  ├─ VideoDownloader (downloader.py) │  ← 主下载器,协调yt-dlp和平台服务
│  ├─ DouyinService (douyin_service.py)│  ← 抖音专用API服务(无需登录)
│  └─ DouyinParser (douyin_parser.py) │  ← 抖音URL解析工具
├─────────────────────────────────────┤
│  工具层 (utils.py)                  │  ← URL验证、路径验证、平台识别
├─────────────────────────────────────┤
│  外部依赖                            │
│  ├─ yt-dlp                          │  ← 通用视频下载工具
│  ├─ browser-cookie3                │  ← 浏览器Cookie读取
│  └─ requests                       │  ← HTTP请求
└─────────────────────────────────────┘
```

### 2. 视频解析流程

**通用流程** (parse_video_info):
```
用户提交URL
    ↓
URL提取和验证 (utils.extract_url_from_text)
    ↓
判断平台类型
    ├─ 抖音 → DouyinService._parse_douyin_video (API直接获取)
    └─ 其他 → VideoDownloader._parse_video_with_ytdlp
        ↓
    返回视频元信息 (标题、大小、时长、媒体/页面链接)
        ↓
    POST /download-jobs 创建统一后台任务
        ↓
    前端轮询进度,完成后从 /download-jobs/<id>/file 下载
```

**关键设计**:
- 服务器仅使用临时任务目录,文件传输后删除,未领取文件一小时过期
- 普通媒体直链按字节报告进度,DASH/HLS 由 yt-dlp 下载并合并
- YouTube 支持 360p、720p、1080p,其他平台选择最佳可用格式
- 下载并发上限为2,待处理任务上限为12

### 3. 平台特殊处理

#### 抖音 (Douyin)
- **优先级**: DouyinService (iesdouyin API) → yt-dlp 备用
- **无需登录**: 使用移动端API和自动生成的ttwid
- **无水印链接**: 通过 `play_addr.url_list` 获取原始视频
- **关键文件**:
  - `douyin_service.py:33-100` - API端点和UA配置
  - `douyin_parser.py` - URL和视频ID提取

#### YouTube
- **403错误处理**: 使用 Android 客户端 (`--extractor-args youtube:player_client=android`)
- **代理支持**:
  - 自动从 Webshare API 获取代理列表 (downloader.py:59-130)
  - 环境变量备用: `YOUTUBE_PROXY` (逗号分隔的代理列表)
  - API Token: `WEBSHARE_API_TOKEN` (默认硬编码在 ProxyManager)
- **代理轮换**: ProxyManager.get_next_proxy() 循环使用代理池

#### B站 (Bilibili)
- **DASH格式**: 视频音频分离,需要合并
- **防盗链**: 必须设置正确的 Referer 和 Origin
- **Cookies要求**: 某些视频需要 cookies.txt (会员内容)
- **代理处理**: `/proxy-download?is_dash=true` 使用 yt-dlp 自动合并
- **关键配置**:
  ```python
  '--user-agent', 'Mozilla/5.0...',
  '--referer', 'https://www.bilibili.com/',
  '--add-header', 'Origin:https://www.bilibili.com'
  ```

#### Twitter/X
- **多视频处理**: `--extractor-args twitter:multiple_video=1`
- **Cookies**: TikTok视频需要从 cookies.txt 读取 (app.py:398-412)

### 4. Cookies 管理策略

**自动检测顺序** (downloader.py:565-610):
1. 本地 `cookies.txt` 文件 (优先级最高)
2. 浏览器 cookies (仅本地环境,服务器环境自动禁用)
   - 默认顺序: chrome → edge → firefox → safari → brave → chromium
   - 环境变量覆盖: `VIDEO_DL_COOKIE_BROWSERS`

**平台需求** (AUTO_COOKIE_DOMAINS):
- 需要cookies: 抖音、TikTok、快手、小红书、YouTube会员、B站会员
- 无需cookies: YouTube公开视频、Twitter

### 5. 代理服务端点

**目的**: 解决跨域下载和防盗链问题

| 端点 | 用途 | 关键场景 |
|------|------|----------|
| `/proxy-thumbnail` | 代理缩略图 | B站/抖音防盗链(Referer验证) |
| `/proxy-download` | 代理视频下载 | B站DASH格式、跨域下载 |
| `POST /download-jobs` | 创建统一下载任务 | 全部支持平台 |
| `GET /download-jobs/<id>` | 查询任务状态和进度 | 全部支持平台 |
| `GET /download-jobs/<id>/file` | 下载完成文件并触发清理 | 全部支持平台 |

**Referer 自动判断** (app.py:40-63 get_platform_referer):
根据URL域名自动设置对应平台的 Referer,避免403错误

### 6. 错误处理

**智能错误解析** (downloader.py:283-354 _parse_error):
- 依赖缺失: pycryptodome、keyring、browser-cookie3
- DNS/网络: 提示检查DNS和系统代理
- 登录要求: HTTP 403、"login required"
- 平台特定: cookies、geo-blocking、copyright

**抖音专用建议** (downloader.py:698-724):
下载失败时提供友好的操作指引(浏览器登录、cookies授权等)

## 开发注意事项

### 部署相关

1. **端口一致性**: 确保 app.py 和 start.sh 的端口配置一致
2. **临时存储边界**: 仅允许任务目录临时保存；必须保留传输后删除和一小时过期清理
3. **代理配置**: YouTube受限地区需配置 WEBSHARE_API_TOKEN 或 YOUTUBE_PROXY
4. **Cookies文件**:
   - 位置: 项目根目录 `cookies.txt`
   - 格式: Netscape cookies.txt (使用浏览器插件 "Get cookies.txt" 导出)
   - 安全: 已在 .gitignore 中排除

### 添加新平台支持

1. 在 `utils.py:KNOWN_PLATFORMS` 添加域名
2. 在 `_platform_specific_args()` 添加UA/Referer等参数
3. 如需特殊处理,参考 DouyinService 创建独立服务类
4. 在 `get_platform_referer()` 添加防盗链处理

### 前端集成

- **主页面**: templates/index.html
- **核心逻辑**: static/script.js
- **API端点**:
  - POST `/parse-video` - 解析视频信息
  - GET `/proxy-thumbnail?url=...` - 加载缩略图
  - GET `/proxy-download?video_url=...&filename=...&is_dash=...` - 下载视频

### 常见问题排查

1. **YouTube 403错误**: 检查代理配置和 Android 客户端参数
2. **B站下载失败**: 确认使用了 `/proxy-download?is_dash=true`
3. **抖音无法解析**: DouyinService失败会自动降级到 yt-dlp
4. **缩略图无法加载**: 使用 `/proxy-thumbnail` 代理端点
5. **文件大小Unknown**: DASH格式需合并多个流,m3u8流式视频可能无精确大小

### SEO相关

- `robots.txt` 和 `sitemap.xml` 位于项目根目录
- 路由: app.py:599-607
- 图标: icon/store_icon.png (通过 `/icon/<filename>` 访问)

## ⚠️ 关键开发原则

### 遇到不明确问题必须中断开发

**重要提醒：开发过程中如果遇到任何不明白、不确定的地方，千万不要自己去开发，必须停住开发过程，跟用户进行确认后才能继续开发。**

**具体执行要求：**
- 技术方案不确定时 → 立即中断，询问用户
- 业务逻辑模糊时 → 立即中断，澄清需求
- 依赖集成方式不明确时 → 立即中断，确认方案
- 数据结构设计有疑问时 → 立即中断，讨论设计
- 任何可能影响项目架构的决策 → 立即中断，获得确认

**绝对禁止：**
- 自行猜测不明确的技术实现
- 凭经验假设业务需求细节
- 跳过不确定的技术环节继续开发
- 使用未经确认的依赖库或框架方案

### 严格按需求开发原则

**重要提醒：只能解决用户明确提出的需求或问题，不得添加需求或问题以外的功能或代码。**

**具体执行要求：**
- 只修复用户报告的具体问题
- 只实现用户明确要求的功能
- 添加任何额外功能前必须征得用户同意
- 优化或重构代码前必须征得用户同意
- 修改用户界面或用户体验前必须征得用户同意

**绝对禁止：**
- 自行添加"优化"或"改进"功能
- 在解决问题时顺便修复其他未报告的问题
- 基于个人判断添加"有用"的功能
- 未经授权修改现有功能的行为逻辑

### MCP工具辅助分析原则

**重要提醒：当遇到不清楚、有疑问或复杂技术问题时，必须主动使用context7和sequential thinking等MCP工具来协助检查和深度思考。**

**具体执行要求：**
- 技术问题分析不清楚时 → 使用sequential thinking工具进行深度分析
- 需要查找最新库文档或API时 → 使用context7工具获取准确信息
- 复杂错误排查时 → 结合thinking工具进行系统性分析
- 架构设计决策时 → 使用MCP工具辅助评估方案
- 遇到持续性问题时 → 主动使用工具而非反复尝试

**工具使用场景：**
- **context7**：获取最新技术文档、API规范、框架使用方法
- **sequential thinking**：复杂问题分解、错误原因分析、方案对比
- **组合使用**：先用context7获取信息，再用thinking进行分析

**绝对禁止：**
- 明明有工具辅助却凭经验盲目尝试
- 遇到复杂问题不使用thinking工具分析
- 不查最新文档就使用过时的技术方案
- 忽略MCP工具提供的准确信息
