"""
下载服务模块
负责调用 yt-dlp 下载视频
"""

import subprocess
import os
import re
import json
import requests
import sys
from pathlib import Path
from typing import Dict, Generator, Optional, List
from urllib.parse import urlparse
from datetime import datetime, timedelta

import browser_cookie3

# 获取 yt-dlp 命令路径
def get_ytdlp_command():
    """获取 yt-dlp 命令的完整路径"""
    # 优先使用当前Python解释器对应的yt-dlp
    python_bin_dir = os.path.dirname(sys.executable)
    current_ytdlp = os.path.join(python_bin_dir, 'yt-dlp')
    if os.path.exists(current_ytdlp):
        return current_ytdlp
    # 其次使用虚拟环境中的 yt-dlp
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        venv_ytdlp = os.path.join(sys.prefix, 'bin', 'yt-dlp')
        if os.path.exists(venv_ytdlp):
            return venv_ytdlp
    # 使用系统的 yt-dlp
    return 'yt-dlp'

YTDLP_CMD = get_ytdlp_command()

from utils import (
    is_twitter_url,
    validate_url,
    validate_path,
    extract_url_from_text,
)
from douyin_service import DouyinService, DouyinDownloadError
from douyin_parser import DouyinParser

AUTO_COOKIE_DOMAINS = (
    'douyin.com',
    'tiktok.com',
    'kuaishou.com',
    'xiaohongshu.com',
    'xhslink.com',
    'youtube.com',
    'youtu.be',
    'bilibili.com',
    'b23.tv'
)

DEFAULT_COOKIE_BROWSERS = ['chrome', 'edge', 'firefox', 'safari', 'brave', 'chromium']

BROWSER_COOKIE_LOADERS = {
    name: getattr(browser_cookie3, name, None)
    for name in DEFAULT_COOKIE_BROWSERS
}

LOCAL_COOKIES_FILE = Path(__file__).resolve().parent / "cookies.txt"

DOUYIN_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
)


class ProxyManager:
    """代理管理器 - 从环境变量读取代理配置"""

    def get_residential_proxy(self) -> str:
        """获取住宅代理 (YouTube专用)，从环境变量 IPROYAL_PROXY 读取"""
        return os.environ.get('IPROYAL_PROXY', '')

    def get_proxies(self) -> List[str]:
        """获取代理列表，从环境变量 YOUTUBE_PROXY 读取（逗号分隔）"""
        proxy_env = os.environ.get('YOUTUBE_PROXY', '')
        if proxy_env:
            return [p.strip() for p in proxy_env.split(',') if p.strip()]
        return []

    def get_next_proxy(self) -> Optional[str]:
        """获取第一个可用代理"""
        proxies = self.get_proxies()
        return proxies[0] if proxies else None


class VideoDownloader:
    def __init__(self):
        self.cookie_browser_order = self._load_cookie_browser_order()
        self.douyin_headers = [
            "--user-agent", DOUYIN_UA,
            "--referer", "https://www.douyin.com/"
        ]
        self.douyin_service = DouyinService()
        self.douyin_parser = DouyinParser()
        self.local_cookie_file = LOCAL_COOKIES_FILE
        self.proxy_manager = ProxyManager()

    def download(self, url: str, directory: str, cookies_from_browser: str = None) -> Dict:
        url_extracted, extracted_url, extract_error = extract_url_from_text(url)
        if not url_extracted:
            return {
                'success': False,
                'message': '链接提取失败',
                'error': extract_error
            }
        url = extracted_url
        url_valid, url_error = validate_url(url)
        if not url_valid:
            return {
                'success': False,
                'message': '链接验证失败',
                'error': url_error
            }
        path_valid, path_error = validate_path(directory)
        if not path_valid:
            return {
                'success': False,
                'message': '目录验证失败',
                'error': path_error
            }
        douyin_error_hint = None
        is_douyin = self.douyin_parser.is_douyin_url(url)
        if is_douyin:
            douyin_result = self.douyin_service.download(url, directory)
            if douyin_result['success']:
                return douyin_result
            douyin_error_hint = douyin_result.get('error') or douyin_result.get('message')

        # YouTube URL特殊处理：带重试和降级机制
        if self._is_youtube_url(url):
            return self._download_youtube_with_retry(url, directory, cookies_from_browser, is_douyin, douyin_error_hint)

        resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)
        output_template = os.path.join(directory, "%(title)s.%(ext)s")
        cmd = [YTDLP_CMD, url, "-o", output_template]
        cmd.extend(self._platform_specific_args(url))
        if resolved_browser:
            cmd.extend(["--cookies-from-browser", resolved_browser])
        local_cookie = self._resolve_cookie_file(url)
        if local_cookie:
            cmd.extend(["--cookies", local_cookie])
        if is_twitter_url(url):
            cmd.extend(["--extractor-args", "twitter:multiple_video=1"])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': '视频下载成功'
                }
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                error_parsed = self._parse_error(error_msg)
                if is_douyin:
                    suggestions = self._get_douyin_download_suggestions(url)
                    if douyin_error_hint:
                        error_parsed = f"DouyinService: {douyin_error_hint}\nyt-dlp: {error_parsed}\n\n💡 抖音下载建议:\n{suggestions}"
                    else:
                        error_parsed = f"{error_parsed}\n\n{suggestions}"
                return {
                    'success': False,
                    'message': '下载失败',
                    'error': error_parsed
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': '下载超时',
                'error': '下载时间超过5分钟，请检查网络连接或视频大小'
            }
        except FileNotFoundError:
            return {
                'success': False,
                'message': 'yt-dlp 未安装',
                'error': '请先安装 yt-dlp 工具'
            }
        except Exception as e:
            return {
                'success': False,
                'message': '下载发生异常',
                'error': str(e)
            }

    def _download_youtube_with_retry(self, url: str, directory: str, cookies_from_browser: str = None, is_douyin: bool = False, douyin_error_hint: str = None) -> Dict:
        """
        YouTube下载带重试机制
        尝试顺序：
        1. 优先使用住宅代理 (IPRoyal)
        2. 使用数据中心代理池
        3. 降级到直连
        """
        resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)
        output_template = os.path.join(directory, "%(title)s.%(ext)s")
        local_cookie = self._resolve_cookie_file(url)

        # 1. 优先使用住宅代理
        residential_proxy = self.proxy_manager.get_residential_proxy()
        if residential_proxy:
            cmd = [YTDLP_CMD, url, "-o", output_template]
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])
            cmd.extend(['--proxy', residential_proxy])

            if resolved_browser:
                cmd.extend(["--cookies-from-browser", resolved_browser])
            if local_cookie:
                cmd.extend(["--cookies", local_cookie])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    return {'success': True, 'message': '视频下载成功'}
                print(f"住宅代理下载失败: {result.stderr[:100] if result.stderr else 'unknown'}")
            except Exception as e:
                print(f"住宅代理异常: {e}")

        # 2. 尝试数据中心代理池
        proxies = self.proxy_manager.get_proxies()
        max_proxy_attempts = min(3, len(proxies)) if proxies else 0

        for attempt in range(max_proxy_attempts):
            proxy = self.proxy_manager.get_next_proxy()
            if not proxy:
                break

            cmd = [YTDLP_CMD, url, "-o", output_template]
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])
            cmd.extend(['--proxy', proxy])

            if resolved_browser:
                cmd.extend(["--cookies-from-browser", resolved_browser])
            if local_cookie:
                cmd.extend(["--cookies", local_cookie])

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    return {
                        'success': True,
                        'message': '视频下载成功'
                    }
                # 代理失败，尝试下一个
                print(f"代理 {proxy} 下载失败，尝试下一个...")
            except subprocess.TimeoutExpired:
                print(f"代理 {proxy} 超时，尝试下一个...")
                continue
            except Exception as e:
                print(f"代理 {proxy} 异常: {e}，尝试下一个...")
                continue

        # 所有代理都失败，降级到直连
        print("代理下载失败，降级到直连模式...")
        cmd = [YTDLP_CMD, url, "-o", output_template]
        cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        # 不添加 --proxy 参数，使用直连

        if resolved_browser:
            cmd.extend(["--cookies-from-browser", resolved_browser])
        if local_cookie:
            cmd.extend(["--cookies", local_cookie])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': '视频下载成功'
                }
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                error_parsed = self._parse_error(error_msg)
                return {
                    'success': False,
                    'message': '下载失败',
                    'error': error_parsed
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': '下载超时',
                'error': '下载时间超过5分钟，请检查网络连接或视频大小'
            }
        except FileNotFoundError:
            return {
                'success': False,
                'message': 'yt-dlp 未安装',
                'error': '请先安装 yt-dlp 工具'
            }
        except Exception as e:
            return {
                'success': False,
                'message': '下载发生异常',
                'error': str(e)
            }

    def _parse_error(self, error_output: str) -> str:
        if not error_output:
            return "Unknown error"
        error_lower = error_output.lower()
        dependency_errors = {
            'pycryptodome': '缺少 pycryptodome 依赖，运行 start.sh/start.bat 重新安装即可',
            'keyring': '缺少 keyring 依赖，运行 start.sh/start.bat 重新安装即可',
            'browser-cookie3': '缺少 browser-cookie3 依赖，运行 start.sh/start.bat 重新安装即可',
            'could not find the default profile': '未找到浏览器登录信息，请确认已在该浏览器登录目标平台',
            'no such file or directory: cookies-from-browser': '浏览器 cookies 读取失败，请重新选择浏览器或确认已登录',
        }
        for key, message in dependency_errors.items():
            if key in error_lower:
                return message
        dns_tokens = (
            'failed to resolve',
            'name or service not known',
            'nodename nor servname provided',
            'temporary failure in name resolution',
        )
        if any(token in error_lower for token in dns_tokens):
            host_hint = None
            host_match = re.search(r"resolve ['\"]?([a-z0-9.-]+)", error_output, re.IGNORECASE)
            if host_match:
                host_hint = host_match.group(1).lower()
            target = host_hint or '目标域名'
            return f"无法解析 {target}，请检查本机网络/DNS 设置或开启系统代理后重试"
        auth_patterns = [
            'login required',
            'please log in',
            'account is limited',
            'http error 403',
            'access denied',
            'cookie required',
        ]
        if any(token in error_lower for token in auth_patterns):
            return '该平台要求浏览器保持登录，请先在浏览器中登录后重试'
        error_patterns = {
            'private': '视频为私有或已删除',
            'copyright': '视频因版权问题无法下载',
            'geo': '该视频在当前地区不可用',
            'network': '网络连接失败',
            'unavailable': '视频不可用',
            'unsupported': '不支持的网站或视频格式',
        }
        for pattern, message in error_patterns.items():
            if pattern in error_lower:
                return message
        return error_output[:200]

    def download_with_progress(self, url: str, directory: str, cookies_from_browser: str = None) -> Generator[Dict, None, None]:
        url_extracted, extracted_url, extract_error = extract_url_from_text(url)
        if not url_extracted:
            yield {
                'status': 'error',
                'message': '链接提取失败',
                'error': extract_error
            }
            return
        url = extracted_url
        url_valid, url_error = validate_url(url)
        if not url_valid:
            yield {
                'status': 'error',
                'message': '链接验证失败',
                'error': url_error
            }
            return
        path_valid, path_error = validate_path(directory)
        if not path_valid:
            yield {
                'status': 'error',
                'message': '目录验证失败',
                'error': path_error
            }
            return
        douyin_error_hint = None
        is_douyin = self.douyin_parser.is_douyin_url(url)
        if is_douyin:
            try:
                yield from self.douyin_service.download_with_progress(
                    url,
                    directory,
                    raise_on_error=True
                )
                return
            except DouyinDownloadError as exc:
                douyin_error_hint = str(exc)
                yield {
                    'status': 'progress',
                    'percent': 0,
                    'message': '抖音API通道暂不可用，正在切换到 yt-dlp 通道...'
                }
            except Exception as exc:
                douyin_error_hint = str(exc)
                yield {
                    'status': 'progress',
                    'percent': 0,
                    'message': '抖音API通道异常，正在切换到 yt-dlp 通道...'
                }
        # YouTube特殊处理：先尝试直连（不使用代理）
        is_youtube = self._is_youtube_url(url)
        resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)
        output_template = os.path.join(directory, "%(title)s.%(ext)s")
        local_cookie = self._resolve_cookie_file(url)

        # YouTube下载策略：优先直连，失败后尝试代理
        attempts = []
        if is_youtube:
            # 第一次尝试：直连
            attempts.append(('direct', False))
            # 如果有代理，准备第二次尝试
            if self.proxy_manager.get_proxies():
                attempts.append(('proxy', True))
        else:
            # 非YouTube：使用默认策略
            attempts.append(('default', False))

        for attempt_name, use_proxy in attempts:
            if attempt_name == 'proxy':
                yield {
                    'status': 'progress',
                    'percent': 0,
                    'message': '直连失败，尝试使用代理下载...'
                }

            cmd = [YTDLP_CMD, url, "-o", output_template, "--newline"]
            # 根据策略添加YouTube参数
            if is_youtube:
                cmd.extend(['--extractor-args', 'youtube:player_client=android'])
                if use_proxy:
                    proxy = self.proxy_manager.get_next_proxy()
                    if proxy:
                        cmd.extend(['--proxy', proxy])
            else:
                cmd.extend(self._platform_specific_args(url))
            if resolved_browser:
                cmd.extend(["--cookies-from-browser", resolved_browser])
            if local_cookie:
                cmd.extend(["--cookies", local_cookie])
            if is_twitter_url(url):
                cmd.extend(["--extractor-args", "twitter:multiple_video=1"])

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                all_output = []
                for line in process.stdout:
                    all_output.append(line)
                    progress_data = self._parse_progress(line)
                    if progress_data:
                        yield progress_data
                process.wait()
                if process.returncode == 0:
                    yield {
                        'status': 'complete',
                        'percent': 100,
                        'message': '视频下载成功'
                    }
                    return  # 成功后立即返回
                else:
                    # 如果还有其他尝试方式，继续尝试
                    if attempt_name != attempts[-1][0]:
                        continue
                    # 最后一次尝试也失败了
                    error_output = ''.join(all_output)
                    parsed_error = self._parse_error(error_output)
                    if is_douyin:
                        suggestions = self._get_douyin_download_suggestions(url)
                        parsed_error = f"{parsed_error}\n\n💡 抖音下载建议:\n{suggestions}"
                    yield {
                        'status': 'error',
                        'message': '下载失败',
                        'error': parsed_error
                    }
                    return
            except Exception as e:
                # 如果还有其他尝试方式，继续尝试
                if attempt_name != attempts[-1][0]:
                    continue
                # 最后一次尝试也失败了
                yield {
                    'status': 'error',
                    'message': '下载发生异常',
                    'error': str(e)
                }
                return

    def _parse_progress(self, line: str) -> Dict:
        if '[download]' not in line:
            return None
        percent_match = re.search(r'(\d+\.?\d*)%', line)
        if not percent_match:
            return None
        percent = float(percent_match.group(1))
        speed_match = re.search(r'at\s+([\d.]+\w+/s)', line)
        speed = speed_match.group(1) if speed_match else 'N/A'
        eta_match = re.search(r'ETA\s+([\d:]+)', line)
        eta = eta_match.group(1) if eta_match else 'N/A'
        size_match = re.search(r'of\s+([\d.]+\w+)', line)
        total_size = size_match.group(1) if size_match else 'N/A'
        if size_match and percent > 0:
            downloaded = f"{percent:.1f}%"
        else:
            downloaded = 'N/A'
        return {
            'status': 'progress',
            'percent': percent,
            'speed': speed,
            'eta': eta,
            'downloaded': downloaded,
            'total': total_size,
            'message': f'下载中... {percent:.1f}%'
        }

    def _load_cookie_browser_order(self):
        env_value = os.environ.get('VIDEO_DL_COOKIE_BROWSERS')
        if env_value:
            browsers = [
                item.strip().lower()
                for item in env_value.split(',')
                if item.strip()
            ]
            return browsers or DEFAULT_COOKIE_BROWSERS.copy()
        return DEFAULT_COOKIE_BROWSERS.copy()

    def _resolve_cookie_browser(self, url: str, preference: Optional[str]) -> Optional[str]:
        pref = (preference or '').strip().lower()
        if pref == '':
            return None
        if pref and pref != 'auto':
            return pref
        if self._platform_requires_cookies(url):
            domain_hint = self._cookie_domain_hint(url)
            try:
                detected = self._detect_browser_with_domain(domain_hint)
                if detected:
                    return detected
            except Exception:
                pass
            return None
        return None

    def _platform_requires_cookies(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return any(domain in netloc for domain in AUTO_COOKIE_DOMAINS)

    def _is_douyin_url(self, url: str) -> bool:
        return 'douyin.com' in url.lower()

    def _is_youtube_url(self, url: str) -> bool:
        url_lower = url.lower()
        return 'youtube.com' in url_lower or 'youtu.be' in url_lower
    
    def _is_bilibili_url(self, url: str) -> bool:
        url_lower = url.lower()
        return 'bilibili.com' in url_lower or 'b23.tv' in url_lower

    def _platform_specific_args(self, url: str):
        """
        生成平台特定的参数
        注意：此方法用于非下载场景（如解析），保持原有行为
        """
        args = []
        if self._is_douyin_url(url):
            args.extend(self.douyin_headers)
        if self._is_youtube_url(url):
            args.extend([
                '--extractor-args', 'youtube:player_client=android,web',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ])
            # 优先使用住宅代理
            residential_proxy = self.proxy_manager.get_residential_proxy()
            if residential_proxy:
                args.extend(['--proxy', residential_proxy])
            else:
                proxy = self.proxy_manager.get_next_proxy()
                if proxy:
                    args.extend(['--proxy', proxy])
        if self._is_bilibili_url(url):
            args.extend([
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--referer', 'https://www.bilibili.com/',
                '--add-header', 'Origin:https://www.bilibili.com',
                '--add-header', 'Accept:*/*',
                '--add-header', 'Accept-Language:zh-CN,zh;q=0.9,en;q=0.8'
            ])
        return args

    def _cookie_domain_hint(self, url: str) -> Optional[str]:
        netloc = urlparse(url).netloc.lower()
        for domain in AUTO_COOKIE_DOMAINS:
            if domain in netloc:
                return domain
        return netloc or None

    def _detect_browser_with_domain(self, domain: Optional[str]) -> Optional[str]:
        if not domain:
            return None
        for browser in self.cookie_browser_order:
            loader = BROWSER_COOKIE_LOADERS.get(browser)
            if not loader:
                continue
            try:
                jar = loader(domain_name=domain)
                if jar and len(jar):
                    return browser
            except Exception:
                continue
        return None

    def _resolve_cookie_file(self, url: str) -> Optional[str]:
        if not self._platform_requires_cookies(url):
            return None
        path = self.local_cookie_file
        if not path:
            return None
        try:
            if not (path.exists() and path.stat().st_size > 0):
                return None
            domain_hint = self._cookie_domain_hint(url)
            if not domain_hint:
                return None
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookie_domain = parts[0]
                        if cookie_domain == f'.{domain_hint}' or cookie_domain == domain_hint or cookie_domain.endswith(f'.{domain_hint}'):
                            return str(path)
            return None
        except OSError:
            return None
        return None

    def _get_douyin_download_suggestions(self, url: str) -> str:
        video_id = self.douyin_parser.extract_video_id(url)
        suggestions = [
            "抖音视频下载可能需要以下操作:",
            "1. 确保已在浏览器(Chrome/Safari)登录抖音账号",
            "2. 在界面上选择'自动检测'或指定浏览器(如 Chrome)",
            "3. 首次使用可能需要授权读取浏览器 cookies",
        ]
        if video_id:
            suggestions.append(f"4. 或在浏览器中打开视频页面确认可访问:")
            suggestions.append(f"   https://www.douyin.com/video/{video_id}")
        suggestions.append("")
        suggestions.append("💡 提示: 如果视频是私密或需要特殊权限,可能无法下载")
        return "\n".join(suggestions)

    def parse_video_info(self, url: str, cookies_from_browser: str = None) -> Dict:
        url_extracted, extracted_url, extract_error = extract_url_from_text(url)
        if not url_extracted:
            return {
                'success': False,
                'message': '链接提取失败',
                'error': extract_error
            }
        url = extracted_url
        original_page_url = url
        url_valid, url_error = validate_url(url)
        if not url_valid:
            return {
                'success': False,
                'message': '链接验证失败',
                'error': url_error
            }
        is_douyin = self.douyin_parser.is_douyin_url(url)
        if is_douyin:
            try:
                return self._parse_douyin_video(url, original_page_url)
            except Exception as e:
                pass
        return self._parse_video_with_ytdlp(url, original_page_url, cookies_from_browser)

    def _parse_douyin_video(self, url: str, page_url: str) -> Dict:
        try:
            video_id = self.douyin_parser.extract_video_id(url)
            if not video_id:
                raise Exception("无法提取视频ID")
            aweme = self.douyin_service._get_aweme_detail(url)
            if not aweme:
                raise Exception("无法获取视频信息")
            download_url = self.douyin_service._build_download_url(aweme)
            if not download_url:
                raise Exception("无法提取下载链接")
            title = aweme.get('desc', '抖音视频')
            title = self._sanitize_filename(title)
            statistics = aweme.get('statistics', {})
            duration = aweme.get('video', {}).get('duration', 0) // 1000
            cover_list = aweme.get('video', {}).get('cover', {}).get('url_list', [])
            thumbnail = cover_list[0] if cover_list else ''
            filesize = 0
            try:
                head_response = requests.head(download_url, timeout=10, allow_redirects=True)
                if head_response.status_code == 200:
                    filesize = int(head_response.headers.get('Content-Length', 0))
            except Exception as e:
                print(f"获取抖音视频大小失败: {e}")
            return {
                'success': True,
                'message': '解析成功',
                'video_info': {
                    'title': title or f'douyin_{video_id}',
                    'url': download_url,
                    'page_url': page_url,
                    'size': filesize,
                    'size_readable': self._format_filesize(filesize),
                    'duration': duration,
                    'duration_readable': self._format_duration(duration),
                    'thumbnail': thumbnail,
                    'platform': '抖音',
                    'ext': 'mp4',
                    'is_dash': False
                }
            }
        except Exception as e:
            return {
                'success': False,
                'message': '抖音视频解析失败',
                'error': str(e)
            }

    def _parse_video_with_ytdlp(self, url: str, page_url: str, cookies_from_browser: str = None) -> Dict:
        try:
            is_youtube = self._is_youtube_url(url)
            max_retries = 3 if is_youtube else 1

            for attempt in range(max_retries):
                cmd = [YTDLP_CMD, "-j", "--no-playlist", url]
                cmd.extend(self._platform_specific_args(url))
                resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)
                if resolved_browser:
                    cmd.extend(["--cookies-from-browser", resolved_browser])
                local_cookie = self._resolve_cookie_file(url)
                if local_cookie:
                    cmd.extend(["--cookies", local_cookie])
                if is_twitter_url(url):
                    cmd.extend(["--extractor-args", "twitter:multiple_video=1"])
                    # Twitter 优先选 http 直链 mp4，避免 HLS 多分片合并
                    cmd.extend(["-f", "best[protocol^=http][protocol!*=m3u8]/best"])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    break

                # 检查是否是 YouTube 反机器人错误
                error_msg = result.stderr if result.stderr else result.stdout
                is_bot_check = 'bot' in error_msg.lower() or 'sign in' in error_msg.lower()

                # 如果是最后一次尝试或不是反机器人错误,直接返回错误
                if attempt == max_retries - 1 or not is_bot_check:
                    return {
                        'success': False,
                        'message': '视频解析失败',
                        'error': self._parse_error(error_msg)
                    }
                # 否则继续重试(会自动切换到下一个代理)

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return {
                    'success': False,
                    'message': '视频解析失败',
                    'error': self._parse_error(error_msg)
                }
            video_data = json.loads(result.stdout)
            title = video_data.get('title', '未命名视频')
            title = self._sanitize_filename(title)
            is_dash = False
            download_url = video_data.get('url', '')
            if not download_url:
                requested_formats = video_data.get('requested_formats', [])
                if requested_formats and len(requested_formats) >= 2:
                    is_dash = True
                    download_url = page_url
                elif requested_formats:
                    download_url = requested_formats[0].get('url', '')
            if not download_url or download_url == page_url:
                if not is_dash:
                    formats = video_data.get('formats', [])
                    if formats:
                        for fmt in formats:
                            if fmt.get('vcodec') != 'none' and fmt.get('url'):
                                download_url = fmt.get('url', '')
                                break
                        if not download_url:
                            for fmt in formats:
                                if fmt.get('url'):
                                    download_url = fmt.get('url', '')
                                    break
            filesize = video_data.get('filesize') or video_data.get('filesize_approx', 0)
            if is_dash:
                requested_formats = video_data.get('requested_formats', [])
                total_size = 0
                for fmt in requested_formats:
                    fmt_size = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                    if fmt_size:
                        total_size += fmt_size
                if total_size > 0:
                    filesize = total_size
            if not filesize or filesize <= 0:
                formats = video_data.get('formats', [])
                max_filesize = 0
                for fmt in formats:
                    if fmt.get('protocol') == 'https' and fmt.get('vcodec') != 'none':
                        fmt_size = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                        if fmt_size and fmt_size > max_filesize:
                            max_filesize = fmt_size
                if max_filesize > 0:
                    filesize = max_filesize
            duration = video_data.get('duration', 0)
            thumbnail = self._extract_best_thumbnail(video_data)
            extractor = video_data.get('extractor_key', '')
            platform = self._get_platform_display_name(extractor)
            ext = video_data.get('ext', 'mp4')
            return {
                'success': True,
                'message': '解析成功',
                'video_info': {
                    'title': title,
                    'url': download_url,
                    'page_url': page_url,
                    'size': filesize,
                    'size_readable': self._format_filesize(filesize),
                    'duration': int(duration) if duration else 0,
                    'duration_readable': self._format_duration(int(duration) if duration else 0),
                    'thumbnail': thumbnail,
                    'platform': platform,
                    'ext': ext,
                    'is_dash': is_dash
                }
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': '解析超时',
                'error': '视频解析时间超过30秒,请稍后重试'
            }
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'message': '解析响应格式错误',
                'error': str(e)
            }
        except FileNotFoundError:
            return {
                'success': False,
                'message': 'yt-dlp 未安装',
                'error': '请先安装 yt-dlp 工具'
            }
        except Exception as e:
            return {
                'success': False,
                'message': '解析发生异常',
                'error': str(e)
            }

    def _sanitize_filename(self, filename: str) -> str:
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        if len(filename) > 200:
            filename = filename[:200]
        filename = filename.strip()
        return filename or '未命名视频'

    def _format_filesize(self, size: int) -> str:
        if not size or size <= 0:
            return 'Unknown'
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size_float = float(size)
        while size_float >= 1024 and unit_index < len(units) - 1:
            size_float /= 1024
            unit_index += 1
        return f"{size_float:.2f} {units[unit_index]}"

    def _format_duration(self, seconds: int) -> str:
        if not seconds or seconds <= 0:
            return 'Unknown'
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _get_platform_display_name(self, extractor: str) -> str:
        platform_map = {
            'Youtube': 'YouTube',
            'Twitter': 'Twitter/X',
            'BiliBili': 'B站',
            'Tiktok': 'TikTok',
            'Douyin': '抖音',
            'XiaoHongShu': '小红书',
            'Generic': '通用',
        }
        return platform_map.get(extractor, extractor or 'Unknown')

    def _extract_best_thumbnail(self, video_data: Dict) -> str:
        invalid_patterns = [
            'transparent.gif',
            'default.jpg',
            'placeholder',
            '1x1',
        ]
        def is_valid_thumbnail(url: str) -> bool:
            if not url:
                return False
            url_lower = url.lower()
            return not any(pattern in url_lower for pattern in invalid_patterns)
        thumbnail = video_data.get('thumbnail', '')
        if is_valid_thumbnail(thumbnail):
            return self._ensure_https_thumbnail(thumbnail)
        thumbnails = video_data.get('thumbnails', [])
        if thumbnails:
            valid_thumbnails = [t for t in thumbnails if is_valid_thumbnail(t.get('url', ''))]
            if valid_thumbnails:
                best_thumbnail = max(
                    valid_thumbnails,
                    key=lambda t: (
                        t.get('preference', 0),
                        t.get('width', 0),
                        t.get('height', 0)
                    )
                )
                return self._ensure_https_thumbnail(best_thumbnail.get('url', ''))
        formats = video_data.get('formats', [])
        for fmt in formats:
            fmt_thumbnail = fmt.get('thumbnail', '')
            if is_valid_thumbnail(fmt_thumbnail):
                return self._ensure_https_thumbnail(fmt_thumbnail)
        alternative_fields = ['cover', 'preview_url', 'poster', 'image']
        for field in alternative_fields:
            alt_thumbnail = video_data.get(field, '')
            if is_valid_thumbnail(alt_thumbnail):
                return self._ensure_https_thumbnail(alt_thumbnail)
        return ''

    def _ensure_https_thumbnail(self, thumbnail_url: str) -> str:
        if not thumbnail_url:
            return ''
        if thumbnail_url.startswith('http://'):
            return thumbnail_url.replace('http://', 'https://', 1)
        return thumbnail_url