"""
Flask主应用
提供Web界面和API接口
"""

# 标准库导入
import os
import sys
import json
import subprocess
import tempfile
import time
import http.cookiejar

# 第三方库导入
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import requests
from urllib.parse import unquote, quote

from simple_tracker import tracker
# 本地模块导入
from downloader import VideoDownloader, YTDLP_CMD
from utils import check_ytdlp, install_ytdlp


app = Flask(__name__)
downloader = VideoDownloader()

# 强制 stdout 和 stderr 不缓冲
sys.stdout.flush()
sys.stderr.flush()


@app.route('/icon/<path:filename>')
def serve_icon(filename):
    """提供icon文件夹中的静态文件"""
    icon_dir = os.path.join(os.path.dirname(__file__), 'icon')
    return send_from_directory(icon_dir, filename)


def get_platform_referer(url: str) -> str:
    """
    根据URL判断平台并返回对应的Referer
    
    Args:
        url: 视频或缩略图URL
        
    Returns:
        平台对应的Referer URL
    """
    if "douyin.com" in url or "douyinvod.com" in url or "aweme.snssdk.com" in url or "zjcdn.com" in url or "douyinpic.com" in url:
        return 'https://www.douyin.com/'
    elif 'xhscdn.com' in url or 'xiaohongshu.com' in url:
        return 'https://www.xiaohongshu.com/'
    elif 'bilibili.com' in url or 'bilivideo.com' in url:
        return 'https://www.bilibili.com/'
    elif 'ixigua.com' in url or 'ixiguavideo.com' in url:
        return 'https://www.ixigua.com/'
    elif 'kuaishou.com' in url or 'kuaishoucdn.com' in url:
        return 'https://www.kuaishou.com/'
    elif 'twimg.com' in url or 'twitter.com' in url or 'x.com' in url:
        return 'https://twitter.com/'
    elif 'tiktok' in url.lower():
        return 'https://www.tiktok.com/'
    else:
        return 'https://www.bilibili.com/'  # 默认B站

def detect_platform(url):
    """从URL识别平台"""
    url_lower = url.lower()
    if "bilibili.com" in url_lower or "b23.tv" in url_lower:
        return "bilibili"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "douyin.com" in url_lower:
        return "douyin"
    elif "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower:
        return "xiaohongshu"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    elif "tiktok.com" in url_lower:
        return "tiktok"
    return None



@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/check-env', methods=['GET'])
def check_env():
    """
    检查环境依赖

    Returns:
        JSON: {
            'ytdlp_installed': bool,
            'message': str
        }
    """
    ytdlp_installed = check_ytdlp()

    if ytdlp_installed:
        return jsonify({
            'ytdlp_installed': True,
            'message': 'Environment check passed'
        })
    else:
        return jsonify({
            'ytdlp_installed': False,
            'message': 'yt-dlp not installed, need to install'
        })


@app.route('/install-ytdlp', methods=['POST'])
def install_ytdlp_endpoint():
    """
    安装 yt-dlp

    Returns:
        JSON: {
            'success': bool,
            'message': str,
            'error': str (可选)
        }
    """
    success, error = install_ytdlp()

    if success:
        return jsonify({
            'success': True,
            'message': 'yt-dlp installed successfully'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'yt-dlp installation failed',
            'error': error
        }), 500


@app.route('/download', methods=['POST'])
def download_video():
    """
    下载视频接口

    请求体:
        {
            'url': str,
            'directory': str,
            'cookies_from_browser': str (可选, chrome/firefox/safari/edge)
        }

    Returns:
        JSON: {
            'success': bool,
            'message': str,
            'error': str (可选)
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'message': 'Invalid request data'
        }), 400

    url = data.get('url', '').strip()
    directory = data.get('directory', '').strip()
    cookies_from_browser = data.get('cookies_from_browser', '').strip() or None

    if not url:
        return jsonify({
            'success': False,
            'message': 'Please enter video link'
        }), 400

    if not directory:
        return jsonify({
            'success': False,
            'message': 'Please select download directory'
        }), 400

    # 调用下载服务
    result = downloader.download(url, directory, cookies_from_browser)

    if result['success']:
        # 统计下载
        try:
            platform = detect_platform(url)
            if platform:
                tracker.track(platform)
        except:
            pass
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/download-stream', methods=['POST'])
def download_video_stream():
    """
    下载视频接口（支持实时进度推送）

    请求体:
        {
            'url': str,
            'directory': str,
            'cookies_from_browser': str (可选, chrome/firefox/safari/edge)
        }

    Returns:
        Server-Sent Events 流，实时推送下载进度
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'message': 'Invalid request data'
        }), 400

    url = data.get('url', '').strip()
    directory = data.get('directory', '').strip()
    cookies_from_browser = data.get('cookies_from_browser', '').strip() or None

    if not url:
        return jsonify({
            'success': False,
            'message': 'Please enter video link'
        }), 400

    if not directory:
        return jsonify({
            'success': False,
            'message': 'Please select download directory'
        }), 400

    def generate():
        """生成SSE事件流"""
        try:
            for progress in downloader.download_with_progress(url, directory, cookies_from_browser):
                # 将进度数据转换为SSE格式
                event_data = f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
                yield event_data
        except Exception as e:
            error_data = {
                'status': 'error',
                'message': 'Download exception occurred',
                'error': str(e)
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/parse-video', methods=['POST'])
def parse_video():
    """
    解析视频信息并返回直接下载链接

    请求体:
        {
            'url': str  # 视频链接
        }

    Returns:
        JSON: {
            'success': bool,
            'video_info': {
                'title': str,
                'url': str,
                'size': int,
                'size_readable': str,
                'duration': int,
                'duration_readable': str,
                'thumbnail': str,
                'platform': str,
                'ext': str
            },
            'message': str,
            'error': str (可选)
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'message': 'Invalid request data'
        }), 400

    url = data.get('url', '').strip()

    if not url:
        return jsonify({
            'success': False,
            'message': 'Please enter video link'
        }), 400

    # 调用解析服务 (不传递cookies参数,使用cookies.txt文件)
    result = downloader.parse_video_info(url)

    if result['success']:
        # 统计下载
        try:
            platform = detect_platform(url)
            if platform:
                tracker.track(platform)
        except:
            pass
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/proxy-thumbnail', methods=['GET'])
def proxy_thumbnail():
    """
    代理缩略图接口 - 解决B站等平台的Referer防盗链问题

    查询参数:
        url: 缩略图URL (需要URL编码)

    Returns:
        图片文件流
    """
    thumbnail_url = request.args.get('url', '').strip()

    if not thumbnail_url:
        return jsonify({
            'success': False,
            'message': 'Missing thumbnail URL parameter'
        }), 400

    try:
        # 解码URL
        thumbnail_url = unquote(thumbnail_url)

        # 根据URL判断平台并设置对应的Referer
        referer = get_platform_referer(thumbnail_url)

        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': referer,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        }

        # 请求缩略图
        resp = requests.get(thumbnail_url, headers=headers, timeout=10)
        resp.raise_for_status()

        # 返回图片
        return Response(
            resp.content,
            mimetype=resp.headers.get('Content-Type', 'image/jpeg'),
            headers={
                'Cache-Control': 'public, max-age=86400',  # 缓存1天
                'Access-Control-Allow-Origin': '*',
            }
        )

    except Exception as e:
        app.logger.error(f"代理缩略图失败: {e}")
        return jsonify({
            'success': False,
            'message': 'Thumbnail loading failed',
            'error': str(e)
        }), 500


@app.route('/proxy-download', methods=['GET'])
def proxy_download():
    """
    代理下载接口 - 解决跨域下载问题
    
    查询参数:
        video_url: 视频直链URL (需要URL编码)
        filename: 文件名
        is_dash: 是否为DASH格式 (可选，默认false)
    
    Returns:
        视频文件流
    """
    video_url = request.args.get('video_url', '').strip()
    filename = request.args.get('filename', 'video.mp4').strip()
    is_dash = request.args.get('is_dash', 'false').lower() == 'true'
    
    if not video_url:
        return jsonify({
            'success': False,
            'message': 'Missing video URL parameter'
        }), 400
    
    try:
        # 解码URL
        video_url = unquote(video_url)
        
        # 对于DASH格式，使用yt-dlp下载并合并
        if is_dash:
            return download_with_ytdlp(video_url, filename)
        
        # 非DASH格式，直接代理下载
        return proxy_direct_download(video_url, filename)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Server error',
            'error': str(e)
        }), 500


def proxy_direct_download(video_url: str, filename: str):
    """直接代理下载（用于非DASH格式）"""
    try:
        # 根据视频URL选择合适的Referer
        referer = get_platform_referer(video_url)
        cookies_dict = {}
        
        # TikTok需要特殊处理：需要cookies和正确的请求头
        if 'tiktok' in video_url.lower():
            # 从cookies.txt读取TikTok的cookies
            cookie_file = downloader.local_cookie_file
            if cookie_file and os.path.exists(str(cookie_file)):
                try:
                    jar = http.cookiejar.MozillaCookieJar(str(cookie_file))
                    jar.load(ignore_discard=True, ignore_expires=True)
                    # 提取TikTok相关的cookies
                    for cookie in jar:
                        if 'tiktok.com' in cookie.domain:
                            cookies_dict[cookie.name] = cookie.value
                    app.logger.info(f"成功加载 {len(cookies_dict)} 个TikTok cookies")
                except Exception as e:
                    app.logger.warning(f"读取TikTok cookies失败: {e}")
        
        # 设置请求头（模拟浏览器）
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': referer,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # 发起流式请求（TikTok需要cookies）
        resp = requests.get(
            video_url, 
            headers=headers, 
            cookies=cookies_dict if cookies_dict else None,
            stream=True, 
            timeout=60
        )
        resp.raise_for_status()
        
        # 获取文件大小
        content_length = resp.headers.get('Content-Length')
        
        # 生成响应
        def generate():
            """流式传输视频数据"""
            try:
                for chunk in resp.iter_content(chunk_size=1024 * 512):  # 512KB chunks
                    if chunk:
                        yield chunk
            except Exception as e:
                # CDN连接中断时捕获异常，防止Flask进程崩溃
                app.logger.error(f"流式传输中断: {e}")
        
        # 对文件名进行URL编码（解决中文文件名问题）
        encoded_filename = quote(filename)
        
        # 设置响应头（使用RFC 5987格式支持中文文件名）
        response = Response(
            stream_with_context(generate()),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
                'Content-Type': 'video/mp4',
                'Cache-Control': 'no-cache',
            }
        )
        
        if content_length:
            response.headers['Content-Length'] = content_length
        
        return response
        
    except requests.RequestException as e:
        return jsonify({
            'success': False,
            'message': 'Download failed',
            'error': str(e)
        }), 500


def download_with_ytdlp(video_url: str, filename: str):
    """使用yt-dlp下载（用于DASH格式，自动合并视频和音频）"""
    try:
        # 创建临时文件（不带扩展名，让 yt-dlp 自动添加）
        temp_dir = tempfile.gettempdir()
        # 使用简单的文件名避免特殊字符问题
        safe_filename = f"bili_{int(time.time())}_{os.getpid()}"
        temp_file_base = os.path.join(temp_dir, safe_filename)

        is_youtube = 'youtube.com' in video_url.lower() or 'youtu.be' in video_url.lower()
        max_retries = 3 if is_youtube else 1
        result = None

        # 重试循环
        for attempt in range(max_retries):
            # 构建yt-dlp命令
            cmd = [
                YTDLP_CMD,
                video_url,
                "-o", f"{temp_file_base}.%(ext)s",
                "--merge-output-format", "mp4",  # 强制输出mp4格式
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--referer", "https://www.bilibili.com/"
            ]

            # YouTube 视频添加代理支持
            if is_youtube:
                cmd.extend([
                    '--extractor-args', 'youtube:player_client=android,web',
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ])
                proxy = downloader.proxy_manager.get_next_proxy()
                if proxy:
                    cmd.extend(['--proxy', proxy])
                    app.logger.info(f"[尝试 {attempt + 1}/{max_retries}] 使用代理: {proxy[:30]}...")

            # 如果 cookies 文件存在，添加 cookies 参数
            cookie_file = downloader.local_cookie_file
            if cookie_file and os.path.exists(str(cookie_file)):
                cmd.extend(["--cookies", str(cookie_file)])

            # 执行下载
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=300  # 5分钟超时
            )

            # 如果成功,跳出循环
            if result.returncode == 0:
                break

            # 检查是否是反机器人错误
            error_msg = result.stderr if result.stderr else result.stdout
            is_bot_check = 'bot' in error_msg.lower() or 'sign in' in error_msg.lower()

            app.logger.warning(f"[尝试 {attempt + 1}/{max_retries}] 下载失败 - 是否bot错误: {is_bot_check}")

            # 如果是最后一次尝试或不是反机器人错误,抛出异常
            if attempt == max_retries - 1:
                app.logger.error(f"[尝试 {attempt + 1}/{max_retries}] 已达最大重试次数,下载失败")
                raise Exception(f"yt-dlp download failed: {result.stderr[:500]}")

            if not is_bot_check:
                app.logger.error(f"[尝试 {attempt + 1}/{max_retries}] 非bot错误,直接失败: {error_msg[:100]}")
                raise Exception(f"yt-dlp download failed: {result.stderr[:500]}")

            # 否则继续重试(会自动切换到下一个代理)
            app.logger.warning(f"[尝试 {attempt + 1}/{max_retries}] Bot错误,切换代理重试...")

        if result.returncode != 0:
            raise Exception(f"yt-dlp download failed after {max_retries} attempts")
        
        # 找到实际生成的文件（yt-dlp 会添加扩展名）
        temp_file = f"{temp_file_base}.mp4"
        
        # 读取下载的文件并流式传输
        if not os.path.exists(temp_file):
            # 尝试查找其他可能的扩展名
            for ext in ['.mp4', '.mkv', '.webm', '.flv']:
                potential_file = f"{temp_file_base}{ext}"
                if os.path.exists(potential_file):
                    temp_file = potential_file
                    break
            else:
                raise Exception(f"Downloaded file does not exist: {temp_file}")
        
        def generate():
            """流式读取并传输文件"""
            try:
                with open(temp_file, 'rb') as f:
                    while True:
                        chunk = f.read(1024 * 512)  # 512KB chunks
                        if not chunk:
                            break
                        yield chunk
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
        
        # 获取文件大小
        file_size = os.path.getsize(temp_file)
        
        # 对文件名进行URL编码
        encoded_filename = quote(filename)
        
        # 设置响应头
        response = Response(
            stream_with_context(generate()),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
                'Content-Type': 'video/mp4',
                'Content-Length': str(file_size),
                'Cache-Control': 'no-cache',
            }
        )
        
        return response
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': 'Download timeout',
            'error': 'Download time exceeded 5 minutes'
        }), 500
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        app.logger.error(f"DASH下载失败: {error_detail}")
        sys.stderr.write(f"[ERROR] DASH下载失败:\n{error_detail}\n")
        sys.stderr.flush()
        return jsonify({
            'success': False,
            'message': 'Download failed',
            'error': f"{str(e)}"
        }), 500



# SEO路由 - robots.txt和sitemap.xml
@app.route('/robots.txt')
def robots():
    """提供robots.txt文件供搜索引擎爬虫读取"""
    return send_from_directory('.', 'robots.txt', mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    """提供sitemap.xml文件供搜索引擎索引"""
    return send_from_directory('.', 'sitemap.xml', mimetype='application/xml')

if __name__ == '__main__':
    # 生产环境运行
    app.run(
        debug=False,  # 生产环境必须关闭debug
        host='0.0.0.0',  # 监听所有网络接口
        port=5001,  # 端口设置为5003
        threaded=True,   # 启用多线程
        use_reloader=False  # 生产环境关闭自动重载
    )

# Google验证
@app.route('/googlebb599f357f33fc9d.html')
def google_verification():
    return 'google-site-verification: googlebb599f357f33fc9d.html'

# Google验证
@app.route('/googlebb599f357f33fc9d.html')
def google_verification():
    return 'google-site-verification: googlebb599f357f33fc9d.html'
