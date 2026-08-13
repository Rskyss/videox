"""
Flask主应用
提供Web界面和API接口
"""

# 标准库导入
import os
import sys
import json
import glob
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import http.cookiejar

# 第三方库导入
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
import requests
from urllib.parse import unquote, quote, urlparse

from simple_tracker import tracker
# 本地模块导入
from downloader import (
    VideoDownloader,
    YTDLP_CMD,
    sanitize_sensitive_output,
    ytdlp_subprocess_env,
)
from utils import check_ytdlp, install_ytdlp, validate_url


app = Flask(__name__)
downloader = VideoDownloader()

DOWNLOAD_JOB_ROOT = os.path.join(tempfile.gettempdir(), 'videox_download_jobs')
DOWNLOAD_JOB_TTL_SECONDS = 60 * 60
DOWNLOAD_JOB_TIMEOUT_SECONDS = 15 * 60
DOWNLOAD_JOB_MAX_CONCURRENT = 2
DOWNLOAD_JOB_MAX_PENDING = 12
DIRECT_DOWNLOAD_CHUNK_SIZE = 1024 * 512
DIRECT_DOWNLOAD_RECONNECT_ATTEMPTS = 4
DIRECT_DOWNLOAD_LOW_SPEED_WINDOW_SECONDS = 8
DIRECT_DOWNLOAD_LOW_SPEED_BYTES_PER_SECOND = 192 * 1024
YOUTUBE_QUALITY_SELECTORS = {
    '360': '18/b[height<=360][ext=mp4]/bv[height<=360][vcodec^=avc1]+ba[ext=m4a]/bv[height<=360]+ba/b[height<=360]',
    '720': 'bv[height<=720][vcodec^=avc1]+ba[ext=m4a]/bv[height<=720]+ba/b[height<=720]',
    '1080': 'bv[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]',
}
# B站按高度封顶；不强制 AVC，便于选到更小的 HEVC 档
BILIBILI_QUALITY_SELECTORS = {
    '360': 'bv*[height<=360]+ba/b[height<=360]/bv*+ba/b',
    '720': 'bv*[height<=720]+ba/b[height<=720]/bv*+ba/b',
    '1080': 'bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b',
}
SUPPORTED_DOWNLOAD_PLATFORMS = {
    'douyin', 'bilibili', 'xiaohongshu', 'youtube', 'tiktok', 'twitter',
}
PLATFORM_MEDIA_DOMAINS = {
    'douyin': ('douyin.com', 'douyinvod.com', 'snssdk.com', 'bytecdn.cn', 'zijieapi.com'),
    'bilibili': ('bilibili.com', 'bilivideo.com', 'hdslb.com'),
    'xiaohongshu': ('xiaohongshu.com', 'xhscdn.com'),
    'youtube': ('youtube.com', 'youtu.be', 'googlevideo.com'),
    'tiktok': ('tiktok.com', 'tiktokv.com', 'tiktokcdn.com', 'byteoversea.com', 'ibytedtos.com'),
    'twitter': ('twitter.com', 'x.com', 'twimg.com'),
}
download_jobs = {}
download_jobs_lock = threading.Lock()
download_job_slots = threading.BoundedSemaphore(DOWNLOAD_JOB_MAX_CONCURRENT)

# 强制 stdout 和 stderr 不缓冲
sys.stdout.flush()
sys.stderr.flush()


def _safe_job_filename(filename: str) -> str:
    """生成只用于 Content-Disposition 的安全文件名。"""
    filename = os.path.basename((filename or 'video.mp4').strip())
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', stem).strip(' ._')
    return f"{(stem or 'video')[:180]}.mp4"


def _normalize_download_platform(source_url: str, platform_hint: str = ''):
    """把解析器展示名称收敛为下载任务使用的平台键。"""
    detected = detect_platform(source_url)
    if detected in SUPPORTED_DOWNLOAD_PLATFORMS:
        return detected
    normalized_hint = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', platform_hint.lower())
    aliases = {
        '抖音': 'douyin',
        'douyin': 'douyin',
        'b站': 'bilibili',
        'bilibili': 'bilibili',
        '小红书': 'xiaohongshu',
        'xiaohongshu': 'xiaohongshu',
        'youtube': 'youtube',
        'tiktok': 'tiktok',
        'twitter': 'twitter',
        'twitterx': 'twitter',
    }
    return aliases.get(normalized_hint)


def _host_matches_domains(hostname: str, domains) -> bool:
    hostname = (hostname or '').lower().rstrip('.')
    return any(hostname == domain or hostname.endswith(f'.{domain}') for domain in domains)


def _safe_direct_media_url(media_url: str, platform: str):
    """仅允许解析结果指向该平台的已知媒体域名，避免任务接口成为任意代理。"""
    valid, _ = validate_url(media_url)
    if not valid:
        return None
    hostname = urlparse(media_url).hostname or ''
    if _host_matches_domains(hostname, PLATFORM_MEDIA_DOMAINS.get(platform, ())):
        return media_url
    return None


def _set_download_job(job_id: str, **updates) -> None:
    with download_jobs_lock:
        job = download_jobs.get(job_id)
        if job is not None:
            job.update(updates)
            job['updated_at'] = time.time()


def _download_job_snapshot(job_id: str):
    with download_jobs_lock:
        job = download_jobs.get(job_id)
        if job is None:
            return None
        return {
            'job_id': job_id,
            'status': job['status'],
            'progress': job.get('progress', 0),
            'progress_known': job.get('progress_known', True),
            'message': job.get('message', ''),
            'error': job.get('error', ''),
            'filename': job.get('filename', ''),
            'quality': job.get('quality', ''),
            'platform': job.get('platform', ''),
        }


def _remove_download_job_files(job) -> None:
    job_dir = job.get('job_dir') if job else None
    if job_dir and os.path.commonpath((DOWNLOAD_JOB_ROOT, job_dir)) == DOWNLOAD_JOB_ROOT:
        shutil.rmtree(job_dir, ignore_errors=True)


def _cleanup_expired_download_jobs() -> None:
    cutoff = time.time() - DOWNLOAD_JOB_TTL_SECONDS
    expired = []
    with download_jobs_lock:
        for job_id, job in list(download_jobs.items()):
            if job.get('status') not in ('queued', 'downloading', 'merging', 'serving') and job.get('updated_at', 0) < cutoff:
                expired.append(download_jobs.pop(job_id))
    for job in expired:
        _remove_download_job_files(job)


def _download_job_cleanup_loop() -> None:
    while True:
        time.sleep(5 * 60)
        _cleanup_expired_download_jobs()


# 分片/连接中途被平台掐断（如 B站常见的 SSL EOF）时的抗断线参数：
# 提高重试次数并加上退避等待，给瞬时网络问题留出恢复时间。
RESILIENT_RETRY_ARGS = [
    '--retries', '10',
    '--fragment-retries', '15',
    '--retry-sleep', 'linear=1:10:2',
    '--retry-sleep', 'fragment:linear=1:10:2',
    '--socket-timeout', '30',
]


def _youtube_download_command(
    url: str,
    output_base: str,
    quality: str,
    proxy=None,
    client: str = 'web_safari',
):
    cmd = [
        YTDLP_CMD,
        url,
        '--no-playlist',
        '--no-update',
        '--newline',
        '--progress',
        '--concurrent-fragments', '4',
        *RESILIENT_RETRY_ARGS,
        '-f', YOUTUBE_QUALITY_SELECTORS[quality],
        '-o', f'{output_base}.%(ext)s',
        '--merge-output-format', 'mp4',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    cmd.extend(downloader.youtube_args(proxy, client))
    cookie_file = downloader.local_cookie_file
    if cookie_file and os.path.exists(str(cookie_file)):
        cmd.extend(['--cookies', str(cookie_file)])
    return cmd


def _platform_download_command(job, output_base: str, proxy=None, client=None):
    """构造所有需要 yt-dlp 处理/合并的平台下载命令。"""
    source_url = job['url']
    platform = job['platform']
    quality = job['quality']
    if platform == 'youtube':
        return _youtube_download_command(
            source_url,
            output_base,
            quality,
            proxy,
            client or 'web_safari',
        )

    # B站 CDN 对多连接更敏感，并发分片容易在音频流阶段触发 SSL 中断；降到 1 更稳。
    # 部分网络环境下 IPv6 握手会长时间卡住，进度一直停在 0%，强制 IPv4。
    concurrent_fragments = '1' if platform == 'bilibili' else '4'
    cmd = [
        YTDLP_CMD,
        source_url,
        '--no-playlist',
        '--no-update',
        '--newline',
        '--progress',
        '--concurrent-fragments', concurrent_fragments,
        *RESILIENT_RETRY_ARGS,
        '-f', (
            BILIBILI_QUALITY_SELECTORS.get(quality, BILIBILI_QUALITY_SELECTORS['720'])
            if platform == 'bilibili'
            else 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b'
        ),
        '-o', f'{output_base}.%(ext)s',
        '--merge-output-format', 'mp4',
    ]
    if platform == 'bilibili':
        cmd.append('--force-ipv4')
    cmd.extend(downloader._platform_specific_args(source_url))
    if platform == 'twitter':
        cmd.extend(['--extractor-args', 'twitter:multiple_video=1'])
    cookie_file = downloader._resolve_cookie_file(source_url)
    if cookie_file:
        cmd.extend(['--cookies', cookie_file])
    return cmd


def _direct_download_cookies(platform: str):
    """读取直链下载确实需要的站点 Cookie。"""
    if platform != 'tiktok':
        return None
    cookie_file = downloader.local_cookie_file
    if not cookie_file or not os.path.exists(str(cookie_file)):
        return None
    cookies = {}
    try:
        jar = http.cookiejar.MozillaCookieJar(str(cookie_file))
        jar.load(ignore_discard=True, ignore_expires=True)
        for cookie in jar:
            if 'tiktok.com' in cookie.domain:
                cookies[cookie.name] = cookie.value
    except OSError:
        return None
    return cookies or None


def _run_direct_download_job(job_id: str, job, output_base: str) -> bool:
    """流式保存平台媒体直链，并按字节更新任务进度。"""
    media_url = job.get('media_url')
    if not media_url:
        return False
    platform = job['platform']
    expected_size = max(0, int(job.get('expected_size') or 0))
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'Referer': get_platform_referer(media_url),
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    _set_download_job(job_id, status='downloading', progress=0, message='正在下载视频', error='')
    response = requests.get(
        media_url,
        headers=headers,
        cookies=_direct_download_cookies(platform),
        stream=True,
        allow_redirects=True,
        timeout=(15, 60),
    )
    response.raise_for_status()
    total_size = int(response.headers.get('Content-Length') or expected_size or 0)
    _set_download_job(job_id, progress_known=total_size > 0)
    output_file = f'{output_base}.mp4'
    downloaded = 0
    last_progress = -1
    with open(output_file, 'wb') as handle:
        for chunk in response.iter_content(chunk_size=1024 * 512):
            if not chunk:
                continue
            handle.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                progress = min(95, int(downloaded * 95 / total_size))
                if progress != last_progress:
                    _set_download_job(
                        job_id,
                        status='downloading',
                        progress=progress,
                        message='正在下载视频',
                    )
                    last_progress = progress
            else:
                _set_download_job(
                    job_id,
                    status='downloading',
                    progress=0,
                    progress_known=False,
                    message=f'正在下载视频（{downloaded / 1024 / 1024:.1f} MB）',
                )
    if downloaded <= 0:
        raise RuntimeError('Downloaded file is empty')
    _set_download_job(
        job_id,
        status='ready',
        progress=100,
        message='处理完成，可以下载',
        file_path=output_file,
        file_size=downloaded,
    )
    return True


def _run_download_job(job_id: str) -> None:
    with download_job_slots:
        with download_jobs_lock:
            job = download_jobs.get(job_id)
            if job is None:
                return
            job = dict(job)
            job.setdefault('platform', _normalize_download_platform(job.get('url', '')) or 'youtube')
            job.setdefault('media_url', None)
            job.setdefault('expected_size', 0)
            quality = job['quality']
            job_dir = job['job_dir']

        os.makedirs(job_dir, mode=0o700, exist_ok=True)
        output_base = os.path.join(job_dir, 'video')
        try:
            if _run_direct_download_job(job_id, job, output_base):
                return
        except Exception as exc:
            _set_download_job(
                job_id,
                status='downloading',
                progress=0,
                message='直链下载失败，正在切换解析线路',
                error='',
            )
            app.logger.warning('直链下载失败，回退 yt-dlp: %s', sanitize_sensitive_output(str(exc)))

        # 非 YouTube 平台此前只有一次机会：一旦这次遇到瞬时网络问题（如 B站常见的
        # SSL EOF 中断），整个任务直接判定失败。这里给普通平台也留几次完整重试。
        routes = [(None, None)] * 3
        if job['platform'] == 'youtube':
            routes = []
            for proxy in downloader.proxy_manager.get_proxies()[:3]:
                routes.extend(((proxy, 'web_safari'), (proxy, 'android_vr')))
            routes.extend(((None, 'web_safari'), (None, 'android_vr'), (None, 'tv')))
        last_error = 'Download failed'

        for attempt, (proxy, client) in enumerate(routes, start=1):
            for path in glob.glob(f'{output_base}.*'):
                try:
                    os.remove(path)
                except OSError:
                    pass

            _set_download_job(
                job_id,
                status='downloading',
                progress=0,
                message=(
                    f'正在准备 {quality}p 下载线路（{attempt}/{len(routes)}）'
                    if job['platform'] == 'youtube'
                    else '正在准备下载'
                ),
                error='',
            )
            cmd = _platform_download_command(job, output_base, proxy, client)
            output_tail = []
            started_at = time.time()
            expected_streams = 1
            completed_streams = 0
            previous_stream_percent = 0.0
            current_progress = 0

            try:
                process_env = ytdlp_subprocess_env()
                # B站走国内 CDN，继承本机系统代理（Clash 等）反而容易在音频流阶段 SSL 断开。
                # YouTube 有单独的显式代理线路，不受这里影响。
                if job['platform'] == 'bilibili':
                    for key in (
                        'http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
                        'all_proxy', 'ALL_PROXY',
                    ):
                        process_env.pop(key, None)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=process_env,
                )
                for raw_line in iter(process.stdout.readline, ''):
                    line = sanitize_sensitive_output(raw_line.strip())
                    if not line:
                        continue
                    output_tail.append(line)
                    output_tail = output_tail[-40:]

                    format_match = re.search(r'Downloading \d+ format\(s\):\s*(\S+)', line)
                    if format_match:
                        expected_streams = 2 if '+' in format_match.group(1) else 1

                    retry_match = re.search(r'Retrying\s*\((\d+)/(\d+)\)', line, re.IGNORECASE)
                    if retry_match or (
                        'got error' in line.lower() and 'ssl' in line.lower()
                    ):
                        retry_label = (
                            f'{retry_match.group(1)}/{retry_match.group(2)}'
                            if retry_match else ''
                        )
                        stage = '音频' if completed_streams >= 1 or (
                            expected_streams > 1 and previous_stream_percent >= 99
                        ) else '视频'
                        _set_download_job(
                            job_id,
                            status='downloading',
                            progress_known=current_progress > 0,
                            message=(
                                f'网络不稳，正在重试{stage}下载'
                                + (f'（{retry_label}）' if retry_label else '')
                            ),
                        )
                        continue

                    percent_match = re.search(r'\[download\]\s+([0-9.]+)%', line)
                    if percent_match:
                        stream_percent = float(percent_match.group(1))
                        if previous_stream_percent >= 99 and stream_percent < previous_stream_percent:
                            completed_streams = min(expected_streams - 1, completed_streams + 1)
                        overall_fraction = (completed_streams + stream_percent / 100) / expected_streams
                        current_progress = min(95, max(0, int(overall_fraction * 95)))
                        previous_stream_percent = stream_percent
                        if job['platform'] == 'youtube':
                            progress_message = f'正在下载 {quality}p 音视频'
                        elif expected_streams > 1 and completed_streams >= 1:
                            progress_message = '正在下载音频'
                        elif expected_streams > 1:
                            progress_message = '正在下载视频画面'
                        else:
                            progress_message = '正在下载视频'
                        _set_download_job(
                            job_id,
                            status='downloading',
                            progress=current_progress,
                            progress_known=True,
                            message=progress_message,
                        )
                    elif '[Merger]' in line or '[VideoRemuxer]' in line or '[Fixup' in line:
                        _set_download_job(job_id, status='merging', progress=99, message='正在合并音视频')

                    if time.time() - started_at > DOWNLOAD_JOB_TIMEOUT_SECONDS:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        raise TimeoutError('Download time exceeded 15 minutes')

                return_code = process.wait(timeout=10)
            except Exception as exc:
                return_code = -1
                output_tail.append(sanitize_sensitive_output(str(exc)))

            if return_code == 0:
                candidates = [
                    path for path in glob.glob(f'{output_base}.*')
                    if not path.endswith(('.part', '.ytdl')) and os.path.isfile(path)
                ]
                if candidates:
                    output_file = max(candidates, key=os.path.getsize)
                    _set_download_job(
                        job_id,
                        status='ready',
                        progress=100,
                        message='处理完成，可以下载',
                        file_path=output_file,
                        file_size=os.path.getsize(output_file),
                    )
                    return
                output_tail.append('Downloaded file does not exist')

            last_error = _download_failure_summary(output_tail) or 'Download failed'
            retryable = any(token in last_error.lower() for token in (
                'bot', 'sign in', 'challenge', 'proxy', 'timeout', 'timed out',
                'connection', 'network', 'http error 403', 'http error 429',
                'requested format is not available', 'only images are available',
                'no video formats found',
                # B站等平台常见的连接中途被掐断，属于可重试的瞬时网络问题
                'ssl', 'eof', 'reset by peer', 'broken pipe',
            ))
            if attempt < len(routes) and retryable:
                continue
            break

        _set_download_job(
            job_id,
            status='error',
            message='下载失败',
            error=downloader._parse_error(last_error),
        )


def _download_failure_summary(output_tail) -> str:
    """从 yt-dlp 输出尾部提取真正的失败原因，避免把进度百分比当成错误。"""
    lines = [line for line in (output_tail or []) if line]
    if not lines:
        return ''
    error_lines = [
        line for line in lines
        if line.startswith('ERROR:') or 'Giving up after' in line or 'Got error:' in line
    ]
    if error_lines:
        return '\n'.join(error_lines[-6:])
    # 没有明确 ERROR 时，丢掉纯进度行再取尾部
    meaningful = [
        line for line in lines
        if not re.search(r'\[download\]\s+[0-9.]+%', line)
        and 'ETA' not in line
    ]
    return '\n'.join((meaningful or lines)[-8:])


def _run_youtube_download_job(job_id: str) -> None:
    """兼容旧调用名称；实际所有平台都由统一任务执行。"""
    _run_download_job(job_id)


download_job_cleanup_thread = threading.Thread(
    target=_download_job_cleanup_loop,
    name='videox-download-cleanup',
    daemon=True,
)
download_job_cleanup_thread.start()


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


@app.route('/terms')
@app.route('/terms/')
def terms():
    """用户协议（与客户端官网同一份文案）"""
    return render_template('terms.html')


@app.route('/privacy')
@app.route('/privacy/')
def privacy():
    """隐私政策（与客户端官网同一份文案）"""
    return render_template('privacy.html')


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
        quality: 清晰度 360/720/1080（YouTube / B站可选）
    
    Returns:
        视频文件流
    """
    video_url = request.args.get('video_url', '').strip()
    filename = request.args.get('filename', 'video.mp4').strip()
    is_dash = request.args.get('is_dash', 'false').lower() == 'true'
    quality = request.args.get('quality', '720').strip() or '720'
    
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
            return download_with_ytdlp(video_url, filename, quality=quality)
        
        # 非DASH格式，直接代理下载
        return proxy_direct_download(video_url, filename)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Server error',
            'error': str(e)
        }), 500


@app.route('/download-jobs', methods=['POST'])
def create_download_job():
    """为所有支持的平台创建统一后台下载任务。"""
    _cleanup_expired_download_jobs()
    data = request.get_json(silent=True) or {}
    source_url = (data.get('url') or '').strip()
    platform = _normalize_download_platform(source_url, str(data.get('platform') or ''))
    quality = str(data.get('quality') or ('720' if platform in ('youtube', 'bilibili') else 'best'))
    filename = _safe_job_filename(data.get('filename') or 'video.mp4')
    is_dash = bool(data.get('is_dash'))
    try:
        expected_size = max(0, int(data.get('expected_size') or 0))
    except (TypeError, ValueError):
        expected_size = 0
    expected_size = min(expected_size, 100 * 1024 * 1024 * 1024)
    media_url = (data.get('media_url') or '').strip()

    source_valid, source_error = validate_url(source_url)
    if not source_valid or platform not in SUPPORTED_DOWNLOAD_PLATFORMS:
        return jsonify({
            'success': False,
            'message': '不支持的下载链接',
            'error': source_error or 'Unsupported platform',
        }), 400
    if platform in ('youtube', 'bilibili') and quality not in YOUTUBE_QUALITY_SELECTORS:
        return jsonify({
            'success': False,
            'message': '不支持的清晰度',
            'error': 'quality must be one of: 360, 720, 1080',
        }), 400
    if platform not in ('youtube', 'bilibili'):
        quality = 'best'

    # DASH/HLS 必须交给 yt-dlp 合并；普通媒体直链则可按字节精确计进度。
    safe_media_url = None if is_dash else _safe_direct_media_url(media_url, platform)

    job_id = uuid.uuid4().hex
    job_dir = os.path.join(DOWNLOAD_JOB_ROOT, job_id)
    now = time.time()
    with download_jobs_lock:
        active_jobs = sum(
            1 for job in download_jobs.values()
            if job.get('status') in ('queued', 'downloading', 'merging')
        )
        if active_jobs >= DOWNLOAD_JOB_MAX_PENDING:
            return jsonify({
                'success': False,
                'message': '当前下载任务较多，请稍后重试',
            }), 429
        download_jobs[job_id] = {
            'status': 'queued',
            'progress': 0,
            'progress_known': True,
            'message': '任务已进入队列',
            'error': '',
            'url': source_url,
            'media_url': safe_media_url,
            'platform': platform,
            'is_dash': is_dash,
            'expected_size': expected_size,
            'quality': quality,
            'filename': filename,
            'job_dir': job_dir,
            'created_at': now,
            'updated_at': now,
        }

    worker = threading.Thread(
        target=_run_download_job,
        args=(job_id,),
        name=f'videox-download-{job_id[:8]}',
        daemon=True,
    )
    worker.start()

    response = jsonify({
        'success': True,
        'job_id': job_id,
        'status': 'queued',
        'status_url': f'/download-jobs/{job_id}',
    })
    response.status_code = 202
    response.headers['Location'] = f'/download-jobs/{job_id}'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/download-jobs/<job_id>', methods=['GET'])
def get_download_job(job_id):
    """查询后台下载进度。"""
    _cleanup_expired_download_jobs()
    snapshot = _download_job_snapshot(job_id)
    if snapshot is None:
        return jsonify({'success': False, 'message': '下载任务不存在或已过期'}), 404

    snapshot['success'] = snapshot['status'] != 'error'
    if snapshot['status'] == 'ready':
        snapshot['download_url'] = f'/download-jobs/{job_id}/file'
        with download_jobs_lock:
            job = download_jobs.get(job_id)
            if job:
                snapshot['file_size'] = job.get('file_size', 0)
    response = jsonify(snapshot)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/download-jobs/<job_id>/file', methods=['GET'])
def download_job_file(job_id):
    """流式发送已完成文件；响应结束后清理临时文件。"""
    with download_jobs_lock:
        job = download_jobs.get(job_id)
        if job is None:
            return jsonify({'success': False, 'message': '下载任务不存在或已过期'}), 404
        if job.get('status') != 'ready':
            return jsonify({'success': False, 'message': '文件尚未处理完成'}), 409
        file_path = job.get('file_path')
        filename = job.get('filename') or 'video.mp4'
        job['status'] = 'serving'
        job['updated_at'] = time.time()

    if not file_path or not os.path.isfile(file_path):
        _set_download_job(job_id, status='error', message='下载文件已失效', error='File not found')
        return jsonify({'success': False, 'message': '下载文件已失效，请重新创建任务'}), 410

    file_size = os.path.getsize(file_path)
    encoded_filename = quote(filename)

    def generate_file():
        try:
            with open(file_path, 'rb') as handle:
                while True:
                    chunk = handle.read(1024 * 512)
                    if not chunk:
                        break
                    yield chunk
        finally:
            with download_jobs_lock:
                completed_job = download_jobs.pop(job_id, None)
            _remove_download_job_files(completed_job)

    return Response(
        stream_with_context(generate_file()),
        mimetype='video/mp4',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
            'Content-Length': str(file_size),
            'Cache-Control': 'no-store',
        },
    )


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

        hostname = urlparse(video_url).hostname or ''
        if _host_matches_domains(hostname, PLATFORM_MEDIA_DOMAINS['douyin']):
            return _resumable_douyin_download(
                video_url,
                filename,
                headers,
                cookies_dict or None,
            )
        
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
                for chunk in resp.iter_content(chunk_size=DIRECT_DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        yield chunk
            except Exception as e:
                # CDN连接中断时捕获异常，防止Flask进程崩溃
                app.logger.error(f"流式传输中断: {e}")
            finally:
                resp.close()
        
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


def _content_range_total(response) -> int:
    """从 206 响应中提取完整文件大小。"""
    content_range = response.headers.get('Content-Range', '')
    match = re.match(r'^bytes\s+\d+-\d+/(\d+)$', content_range, re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        return int(response.headers.get('Content-Length') or 0)
    except (TypeError, ValueError):
        return 0


def _open_douyin_range(
    video_url: str,
    headers,
    cookies,
    offset: int,
    trust_env: bool,
    validator: str = '',
):
    """打开抖音 Range 流；续传时拒绝返回整文件，避免拼接出重复内容。"""
    session = requests.Session()
    session.trust_env = trust_env
    request_headers = dict(headers)
    request_headers['Range'] = f'bytes={offset}-'
    if offset > 0 and validator:
        request_headers['If-Range'] = validator

    response = None
    try:
        response = session.get(
            video_url,
            headers=request_headers,
            cookies=cookies,
            stream=True,
            allow_redirects=True,
            timeout=(15, 30),
        )
        response.raise_for_status()
        if offset > 0 and response.status_code != 206:
            raise requests.RequestException(
                f'CDN did not honor Range resume at byte {offset}'
            )
        return session, response
    except Exception:
        if response is not None:
            response.close()
        session.close()
        raise


def _resumable_douyin_download(video_url: str, filename: str, headers, cookies):
    """抖音流低速或中断时透明重连，并从已发送位置继续。"""
    # 保持现有系统代理为首选；只有连接持续低速/中断时才切换直连，再交替重试。
    route_modes = (True, False, True, False)[:DIRECT_DOWNLOAD_RECONNECT_ATTEMPTS]
    route_index = 0
    offset = 0
    session, response = _open_douyin_range(
        video_url,
        headers,
        cookies,
        offset=0,
        trust_env=route_modes[route_index],
    )
    total_size = _content_range_total(response)
    supports_resume = response.status_code == 206 and total_size > 0
    validator = response.headers.get('ETag') or response.headers.get('Last-Modified') or ''

    def generate():
        nonlocal route_index, offset, session, response
        try:
            while True:
                route_started_at = time.monotonic()
                route_bytes = 0
                reconnect_reason = ''
                try:
                    for chunk in response.iter_content(
                        chunk_size=DIRECT_DOWNLOAD_CHUNK_SIZE
                    ):
                        if not chunk:
                            continue
                        yield chunk
                        offset += len(chunk)
                        route_bytes += len(chunk)

                        if total_size and offset >= total_size:
                            return

                        elapsed = time.monotonic() - route_started_at
                        can_reconnect = (
                            supports_resume
                            and route_index + 1 < len(route_modes)
                        )
                        if (
                            can_reconnect
                            and elapsed >= DIRECT_DOWNLOAD_LOW_SPEED_WINDOW_SECONDS
                            and route_bytes / max(elapsed, 0.001)
                            < DIRECT_DOWNLOAD_LOW_SPEED_BYTES_PER_SECOND
                        ):
                            reconnect_reason = '持续低速'
                            break
                    else:
                        if not total_size or offset >= total_size:
                            return
                        reconnect_reason = '连接提前结束'
                except Exception as exc:
                    reconnect_reason = sanitize_sensitive_output(str(exc))

                response.close()
                session.close()
                if not supports_resume or route_index + 1 >= len(route_modes):
                    raise requests.RequestException(
                        reconnect_reason or 'Douyin stream ended before completion'
                    )

                route_index += 1
                app.logger.warning(
                    '抖音下载流重连: offset=%s route=%s reason=%s',
                    offset,
                    'system-proxy' if route_modes[route_index] else 'direct',
                    reconnect_reason,
                )
                session, response = _open_douyin_range(
                    video_url,
                    headers,
                    cookies,
                    offset=offset,
                    trust_env=route_modes[route_index],
                    validator=validator,
                )
                resumed_total = _content_range_total(response)
                if resumed_total and resumed_total != total_size:
                    raise requests.RequestException(
                        'CDN file size changed while resuming download'
                    )
        finally:
            response.close()
            session.close()

    encoded_filename = quote(filename)
    response_headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}",
        'Content-Type': 'video/mp4',
        'Cache-Control': 'no-cache',
    }
    if total_size:
        response_headers['Content-Length'] = str(total_size)

    return Response(
        stream_with_context(generate()),
        mimetype='video/mp4',
        headers=response_headers,
    )


def download_with_ytdlp(video_url: str, filename: str, quality: str = '720'):
    """使用yt-dlp下载（用于DASH/HLS格式，自动合并视频和音频）"""
    try:
        temp_dir = tempfile.gettempdir()
        safe_filename = f"dl_{int(time.time())}_{os.getpid()}"
        temp_file_base = os.path.join(temp_dir, safe_filename)

        url_lower = video_url.lower()
        is_youtube = 'youtube.com' in url_lower or 'youtu.be' in url_lower
        is_bilibili = 'bilibili.com' in url_lower or 'b23.tv' in url_lower
        is_twitter = 'twitter.com' in url_lower or 'x.com' in url_lower
        youtube_attempts = downloader.proxy_manager.get_proxies()[:3] + [None] if is_youtube else [None]
        max_retries = len(youtube_attempts)
        result = None
        if quality not in YOUTUBE_QUALITY_SELECTORS:
            quality = '720'

        for attempt in range(max_retries):
            cmd = [
                YTDLP_CMD,
                video_url,
                "-o", f"{temp_file_base}.%(ext)s",
                "--merge-output-format", "mp4",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]

            if is_bilibili:
                cmd.extend([
                    "--referer", "https://www.bilibili.com/",
                    "--add-header", "Origin:https://www.bilibili.com",
                    '-f', BILIBILI_QUALITY_SELECTORS[quality],
                ])
                app.logger.info(f"使用 B站下载清晰度 quality={quality}")

            if is_youtube:
                proxy = youtube_attempts[attempt]
                cmd.extend(['-f', YOUTUBE_QUALITY_SELECTORS[quality]])
                cmd.extend(downloader.youtube_args(proxy))
                app.logger.info(f"[尝试 {attempt + 1}/{max_retries}] 使用YouTube下载线路 quality={quality}")

            if is_twitter:
                cmd.extend(["--extractor-args", "twitter:multiple_video=1"])

            cookie_file = downloader.local_cookie_file
            if cookie_file and os.path.exists(str(cookie_file)) and not is_twitter:
                cmd.extend(["--cookies", str(cookie_file)])

            dl_timeout = 600 if is_twitter else 300
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=dl_timeout,
                env=ytdlp_subprocess_env(),
            )

            # 如果成功,跳出循环
            if result.returncode == 0:
                break

            # 机器人校验和 EJS 挑战偶尔会瞬时失败，允许自动切换线路。
            error_msg = result.stderr if result.stderr else result.stdout
            error_lower = error_msg.lower()
            is_bot_check = any(token in error_lower for token in (
                'bot', 'sign in', 'nchallengeinput', 'challenge solver',
                'could not solve',
            ))

            app.logger.warning(f"[尝试 {attempt + 1}/{max_retries}] 下载失败 - 是否bot错误: {is_bot_check}")

            # 如果是最后一次尝试或不是反机器人错误,抛出异常
            if attempt == max_retries - 1:
                app.logger.error(f"[尝试 {attempt + 1}/{max_retries}] 已达最大重试次数,下载失败")
                raise Exception(f"yt-dlp download failed: {sanitize_sensitive_output(result.stderr)[:500]}")

            if not is_bot_check:
                app.logger.error(f"[尝试 {attempt + 1}/{max_retries}] 非bot错误,直接失败: {sanitize_sensitive_output(error_msg)[:100]}")
                raise Exception(f"yt-dlp download failed: {sanitize_sensitive_output(result.stderr)[:500]}")

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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route('/robots.txt')
def robots():
    """提供robots.txt文件供搜索引擎爬虫读取"""
    return send_from_directory(BASE_DIR, 'robots.txt', mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    """提供sitemap.xml文件供搜索引擎索引"""
    return send_from_directory(BASE_DIR, 'sitemap.xml', mimetype='application/xml')

@app.route('/googlebb599f357f33fc9d.html')
def google_verification():
    """Google Search Console 站点归属验证文件"""
    return Response('google-site-verification: googlebb599f357f33fc9d.html',
                    mimetype='text/html')

if __name__ == '__main__':
    # 生产环境运行
    app.run(
        debug=False,  # 生产环境必须关闭debug
        host='0.0.0.0',  # 监听所有网络接口
        port=5009,
        threaded=True,   # 启用多线程
        use_reloader=False  # 生产环境关闭自动重载
    )
