"""
下载服务模块
负责调用 yt-dlp 下载视频
"""

import subprocess
import os
import re
import json
import requests
from pathlib import Path
from typing import Dict, Generator, Optional, List
from urllib.parse import urlparse
from datetime import datetime, timedelta

import browser_cookie3

from utils import (
    is_twitter_url,
    validate_url,
    validate_path,
    extract_url_from_text,
)
from douyin_service import DouyinService, DouyinDownloadError
from douyin_parser import DouyinParser

# 需要携带登录状态的平台
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

# yt-dlp 支持的常见浏览器名称（可通过环境变量覆盖顺序）
DEFAULT_COOKIE_BROWSERS = ['chrome', 'edge', 'firefox', 'safari', 'brave', 'chromium']

# browser-cookie3 函数映射（某些浏览器在当前平台可能不可用，运行时兜底为 None）
BROWSER_COOKIE_LOADERS = {
    name: getattr(browser_cookie3, name, None)
    for name in DEFAULT_COOKIE_BROWSERS
}

# 本地 cookies 文件（便于用户从浏览器/手机手动导出）
LOCAL_COOKIES_FILE = Path(__file__).resolve().parent / "cookies.txt"

# 针对部分平台设置更接近真实设备的UA
DOUYIN_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
)


class ProxyManager:
    """代理管理器 - 自动从 Webshare API 获取代理列表"""
    
    def __init__(self):
        # 优先从环境变量获取，如果没有则使用硬编码的token
        self.api_token = os.environ.get('WEBSHARE_API_TOKEN', 'YOUR_WEBSHARE_API_TOKEN')
        self.proxies: List[str] = []
        self.last_update: Optional[datetime] = None
        self.cache_duration = timedelta(hours=1)
        self.current_index = 0
    
    def _fetch_proxies_from_api(self) -> List[str]:
        """从 Webshare API 获取代理列表"""
        if not self.api_token:
            return []
        
        try:
            response = requests.get(
                'https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=25',
                headers={'Authorization': f'Token {self.api_token}'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                proxies = [
                    f"http://{p['username']}:{p['password']}@{p['proxy_address']}:{p['port']}"
                    for p in data.get('results', [])
                    if p.get('valid', True)
                ]
                return proxies
        except Exception:
            pass
        return []
    
    def _load_proxies_from_env(self) -> List[str]:
        """从环境变量加载代理（逗号分隔）"""
        proxy_env = os.environ.get('YOUTUBE_PROXY', '')
        if proxy_env:
            return [p.strip() for p in proxy_env.split(',') if p.strip()]
        return []
    
    def get_proxies(self) -> List[str]:
        """获取代理列表（优先 API，其次环境变量）"""
        # 如果缓存有效，直接返回
        if self.proxies and self.last_update and \
           datetime.now() - self.last_update < self.cache_duration:
            return self.proxies
        
        # 优先从 API 获取
        proxies = self._fetch_proxies_from_api()
        
        # API 失败时从环境变量获取
        if not proxies:
            proxies = self._load_proxies_from_env()
        
        # 如果都失败，保留旧缓存
        if proxies:
            self.proxies = proxies
            self.last_update = datetime.now()
            self.current_index = 0
        
        return self.proxies
    
    def get_next_proxy(self) -> Optional[str]:
        """获取下一个可用的代理（轮换）"""
        proxies = self.get_proxies()
        if not proxies:
            return None
        
        proxy = proxies[self.current_index % len(proxies)]
        self.current_index += 1
        return proxy


class VideoDownloader:
    """视频下载服务类"""

    def __init__(self):
        """初始化下载器"""
        self.cookie_browser_order = self._load_cookie_browser_order()
        self.douyin_headers = [
            "--user-agent", DOUYIN_UA,
            "--referer", "https://www.douyin.com/"
        ]
        self.douyin_service = DouyinService()
        self.douyin_parser = DouyinParser()
        self.local_cookie_file = LOCAL_COOKIES_FILE
        self.proxy_manager = ProxyManager()

        # 注: Playwright已移除(需要浏览器界面,不适合服务器部署)

    def download(self, url: str, directory: str, cookies_from_browser: str = None) -> Dict:
        """
        下载视频

        Args:
            url: 视频链接（可以是纯URL或包含标题的混合文本）
            directory: 下载目录
            cookies_from_browser: 使用指定浏览器的cookies (chrome/firefox/safari/edge)

        Returns:
            Dict: {
                'success': bool,
                'message': str,
                'error': str (可选)
            }
        """
        # 1. 智能提取URL
        url_extracted, extracted_url, extract_error = extract_url_from_text(url)
        if not url_extracted:
            return {
                'success': False,
                'message': '链接提取失败',
                'error': extract_error
            }
        url = extracted_url  # 使用提取出的URL

        # 2. 验证URL
        url_valid, url_error = validate_url(url)
        if not url_valid:
            return {
                'success': False,
                'message': '链接验证失败',
                'error': url_error
            }

        # 3. 验证路径
        path_valid, path_error = validate_path(directory)
        if not path_valid:
            return {
                'success': False,
                'message': '目录验证失败',
                'error': path_error
            }

        # 抖音优先走内置无水印通道
        douyin_error_hint = None
        is_douyin = self.douyin_parser.is_douyin_url(url)

        if is_douyin:
            # 抖音视频: 使用优化的DouyinService(纯后端,无需登录)
            douyin_result = self.douyin_service.download(url, directory)
            if douyin_result['success']:
                return douyin_result

            # DouyinService失败时,记录错误信息用于后续提示
            douyin_error_hint = douyin_result.get('error') or douyin_result.get('message')

            # 注: 已移除第三方API和Playwright备用方案(不适合服务器部署)
            # 继续尝试 yt-dlp 作为最后的备用选项

        # 4. 自动选择Cookies来源
        resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)

        # 5. 构建yt-dlp命令
        output_template = os.path.join(directory, "%(title)s.%(ext)s")
        cmd = ["yt-dlp", url, "-o", output_template]

        # 6. 添加平台特定参数
        cmd.extend(self._platform_specific_args(url))

        # 7. 添加cookies支持
        if resolved_browser:
            cmd.extend(["--cookies-from-browser", resolved_browser])
        local_cookie = self._resolve_cookie_file(url)
        if local_cookie:
            cmd.extend(["--cookies", local_cookie])

        # 8. 特殊处理Twitter链接
        if is_twitter_url(url):
            cmd.extend(["--extractor-args", "twitter:multiple_video=1"])

        # 9. 执行下载
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                return {
                    'success': True,
                    'message': '视频下载成功'
                }
            else:
                # 下载失败
                error_msg = result.stderr if result.stderr else result.stdout
                error_parsed = self._parse_error(error_msg)

                # 抖音链接: 提供友好的错误提示
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

    def _parse_error(self, error_output: str) -> str:
        """
        解析yt-dlp错误输出，提取关键信息

        Args:
            error_output: yt-dlp的错误输出

        Returns:
            str: 简化的错误信息
        """
        if not error_output:
            return "Unknown error"

        error_lower = error_output.lower()

        # 依赖缺失或Cookies读取失败
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

        # DNS 解析 / 网络层错误
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

        # 登录/权限相关
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

        # 常见错误模式匹配
        error_patterns = {
            'cookies': '该平台需要登录凭证，请尝试其他视频',
            'login': '该平台需要登录凭证，请尝试其他视频',
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

        # 如果没有匹配到已知模式，返回原始错误的前200个字符
        return error_output[:200]

    def download_with_progress(self, url: str, directory: str, cookies_from_browser: str = None) -> Generator[Dict, None, None]:
        """
        下载视频并实时返回进度信息

        Args:
            url: 视频链接（可以是纯URL或包含标题的混合文本）
            directory: 下载目录
            cookies_from_browser: 使用指定浏览器的cookies (chrome/firefox/safari/edge)

        Yields:
            Dict: {
                'status': 'progress' | 'complete' | 'error',
                'percent': float,  # 下载百分比
                'speed': str,      # 下载速度
                'eta': str,        # 预计剩余时间
                'downloaded': str, # 已下载大小
                'total': str,      # 总大小
                'message': str     # 状态消息
            }
        """
        # 1. 智能提取URL
        url_extracted, extracted_url, extract_error = extract_url_from_text(url)
        if not url_extracted:
            yield {
                'status': 'error',
                'message': '链接提取失败',
                'error': extract_error
            }
            return
        url = extracted_url  # 使用提取出的URL

        # 2. 验证URL
        url_valid, url_error = validate_url(url)
        if not url_valid:
            yield {
                'status': 'error',
                'message': '链接验证失败',
                'error': url_error
            }
            return

        # 3. 验证路径
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

        # 抖音链接走专用下载（策略1-3）
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

        # 4. 自动选择Cookies来源
        resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)

        # 5. 构建yt-dlp命令
        output_template = os.path.join(directory, "%(title)s.%(ext)s")
        cmd = ["yt-dlp", url, "-o", output_template, "--newline"]

        # 6. 添加平台特定参数
        cmd.extend(self._platform_specific_args(url))

        # 7. 添加cookies支持
        if resolved_browser:
            cmd.extend(["--cookies-from-browser", resolved_browser])
        local_cookie = self._resolve_cookie_file(url)
        if local_cookie:
            cmd.extend(["--cookies", local_cookie])

        # 8. 特殊处理Twitter链接
        if is_twitter_url(url):
            cmd.extend(["--extractor-args", "twitter:multiple_video=1"])

        # 9. 执行下载并实时读取输出
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 收集所有输出用于错误解析
            all_output = []

            # 实时读取输出
            for line in process.stdout:
                all_output.append(line)
                progress_data = self._parse_progress(line)
                if progress_data:
                    yield progress_data

            # 等待进程结束
            process.wait()

            if process.returncode == 0:
                yield {
                    'status': 'complete',
                    'percent': 100,
                    'message': '视频下载成功'
                }
            else:
                # 下载失败
                error_output = ''.join(all_output)
                parsed_error = self._parse_error(error_output)

                # 抖音链接: 提供友好的错误提示
                if is_douyin:
                    suggestions = self._get_douyin_download_suggestions(url)
                    parsed_error = f"{parsed_error}\n\n💡 抖音下载建议:\n{suggestions}"

                yield {
                    'status': 'error',
                    'message': '下载失败',
                    'error': parsed_error
                }

        except FileNotFoundError:
            yield {
                'status': 'error',
                'message': 'yt-dlp 未安装',
                'error': '请先安装 yt-dlp 工具'
            }
        except Exception as e:
            yield {
                'status': 'error',
                'message': '下载发生异常',
                'error': str(e)
            }

    def _parse_progress(self, line: str) -> Dict:
        """
        解析yt-dlp输出行，提取进度信息

        Args:
            line: yt-dlp输出的一行文本

        Returns:
            Dict: 进度信息字典，如果不是进度行则返回None
        """
        # yt-dlp 进度输出格式示例:
        # [download]   45.2% of 120.00MiB at 2.50MiB/s ETA 00:35
        # [download] 100% of 120.00MiB in 01:20

        if '[download]' not in line:
            return None

        # 提取百分比
        percent_match = re.search(r'(\d+\.?\d*)%', line)
        if not percent_match:
            return None

        percent = float(percent_match.group(1))

        # 提取速度
        speed_match = re.search(r'at\s+([\d.]+\w+/s)', line)
        speed = speed_match.group(1) if speed_match else 'N/A'

        # 提取ETA
        eta_match = re.search(r'ETA\s+([\d:]+)', line)
        eta = eta_match.group(1) if eta_match else 'N/A'

        # 提取已下载和总大小
        size_match = re.search(r'of\s+([\d.]+\w+)', line)
        total_size = size_match.group(1) if size_match else 'N/A'

        # 计算已下载大小
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
        """
        从环境变量加载浏览器优先级（可选），否则使用默认顺序
        """
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
        """
        决定本次下载应使用的浏览器 cookies 来源

        注: 服务器环境下,浏览器cookie不可用,将自动返回None
        """
        pref = (preference or '').strip().lower()

        if pref == '':
            return None  # 用户明确选择不使用

        if pref and pref != 'auto':
            return pref

        # 自动模式：仅对需要登录的平台启用
        # 注: 抖音已由DouyinService处理,不需要浏览器cookie
        if self._platform_requires_cookies(url):
            domain_hint = self._cookie_domain_hint(url)

            # 尝试检测浏览器登录信息(服务器环境下会失败,返回None)
            try:
                detected = self._detect_browser_with_domain(domain_hint)
                if detected:
                    return detected
            except Exception:
                # 服务器环境或无浏览器时,静默失败
                pass

            # 未检测到登录信息时,返回None(不使用cookie)
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
        针对特定平台追加额外参数（UA、Referer等）
        """
        args = []

        if self._is_douyin_url(url):
            args.extend(self.douyin_headers)

        if self._is_youtube_url(url):
            # 使用 Android 客户端避免 403 错误
            args.extend(['--extractor-args', 'youtube:player_client=android'])
            
            # YouTube 使用代理（自动从 Webshare API 或环境变量获取）
            proxy = self.proxy_manager.get_next_proxy()
            if proxy:
                args.extend(['--proxy', proxy])
        
        if self._is_bilibili_url(url):
            # B站需要特定的 User-Agent、Referer 和 cookies 避免 412 错误
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
        """
        如果用户提供了 cookies.txt，则为需要登录的平台自动附加 --cookies
        """
        if not self._platform_requires_cookies(url):
            return None

        path = self.local_cookie_file
        if not path:
            return None
        try:
            if path.exists() and path.stat().st_size > 0:
                return str(path)
        except OSError:
            return None
        return None

    def _get_douyin_download_suggestions(self, url: str) -> str:
        """
        为抖音下载失败提供友好的建议

        Args:
            url: 抖音视频链接

        Returns:
            建议文本
        """
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
        """
        解析视频信息并返回直接下载链接(不实际下载文件)

        Args:
            url: 视频链接
            cookies_from_browser: 使用指定浏览器的cookies

        Returns:
            Dict: {
                'success': bool,
                'video_info': {
                    'title': str,          # 视频标题
                    'url': str,            # 直接下载链接（DASH格式返回页面URL）
                    'page_url': str,       # 原始页面URL
                    'size': int,           # 文件大小(字节)
                    'size_readable': str,  # 可读的文件大小
                    'duration': int,       # 时长(秒)
                    'duration_readable': str,  # 可读的时长
                    'thumbnail': str,      # 缩略图URL
                    'platform': str,       # 平台名称
                    'ext': str,            # 文件扩展名
                    'is_dash': bool        # 是否为DASH格式（需要yt-dlp处理）
                },
                'message': str,
                'error': str (可选)
            }
        """
        # 1. 智能提取URL
        url_extracted, extracted_url, extract_error = extract_url_from_text(url)
        if not url_extracted:
            return {
                'success': False,
                'message': '链接提取失败',
                'error': extract_error
            }
        url = extracted_url
        original_page_url = url  # 保存原始页面URL

        # 2. 验证URL
        url_valid, url_error = validate_url(url)
        if not url_valid:
            return {
                'success': False,
                'message': '链接验证失败',
                'error': url_error
            }

        # 3. 抖音视频优先使用专用服务
        is_douyin = self.douyin_parser.is_douyin_url(url)

        if is_douyin:
            try:
                return self._parse_douyin_video(url, original_page_url)
            except Exception as e:
                # 抖音解析失败,尝试 yt-dlp
                pass

        # 4. 使用 yt-dlp 解析其他平台
        return self._parse_video_with_ytdlp(url, original_page_url, cookies_from_browser)

    def _parse_douyin_video(self, url: str, page_url: str) -> Dict:
        """解析抖音视频信息"""
        try:
            # 提取视频ID
            video_id = self.douyin_parser.extract_video_id(url)
            if not video_id:
                raise Exception("无法提取视频ID")

            # 获取视频信息
            aweme = self.douyin_service._get_aweme_detail(url)
            if not aweme:
                raise Exception("无法获取视频信息")

            # 提取下载链接
            download_url = self.douyin_service._build_download_url(aweme)
            if not download_url:
                raise Exception("无法提取下载链接")

            # 提取视频信息
            title = aweme.get('desc', '抖音视频')
            # 清理标题中的特殊字符
            title = self._sanitize_filename(title)

            # 获取视频统计信息
            statistics = aweme.get('statistics', {})
            duration = aweme.get('video', {}).get('duration', 0) // 1000  # 毫秒转秒

            # 构建缩略图URL
            cover_list = aweme.get('video', {}).get('cover', {}).get('url_list', [])
            thumbnail = cover_list[0] if cover_list else ''

            # 获取文件大小 - 发送HEAD请求到下载URL(跟随重定向)
            filesize = 0
            try:
                head_response = requests.head(download_url, timeout=10, allow_redirects=True)
                if head_response.status_code == 200:
                    filesize = int(head_response.headers.get('Content-Length', 0))
            except Exception as e:
                # HEAD请求失败,大小保持为0
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
                    'is_dash': False  # 抖音不是DASH格式
                }
            }
        except Exception as e:
            return {
                'success': False,
                'message': '抖音视频解析失败',
                'error': str(e)
            }

    def _parse_video_with_ytdlp(self, url: str, page_url: str, cookies_from_browser: str = None) -> Dict:
        """使用 yt-dlp 解析视频信息"""
        try:
            # 构建命令
            cmd = ["yt-dlp", "-j", "--no-playlist", url]

            # 添加平台特定参数
            cmd.extend(self._platform_specific_args(url))

            # 添加 cookies 支持
            resolved_browser = self._resolve_cookie_browser(url, cookies_from_browser)
            if resolved_browser:
                cmd.extend(["--cookies-from-browser", resolved_browser])

            local_cookie = self._resolve_cookie_file(url)
            if local_cookie:
                cmd.extend(["--cookies", local_cookie])

            # Twitter特殊处理
            if is_twitter_url(url):
                cmd.extend(["--extractor-args", "twitter:multiple_video=1"])

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return {
                    'success': False,
                    'message': '视频解析失败',
                    'error': self._parse_error(error_msg)
                }

            # 解析JSON输出
            video_data = json.loads(result.stdout)

            # 提取信息
            title = video_data.get('title', '未命名视频')
            title = self._sanitize_filename(title)

            # 检测是否为DASH格式（视频音频分离）
            is_dash = False
            download_url = video_data.get('url', '')
            
            # B站等平台的URL可能在requested_formats中（DASH格式）
            if not download_url:
                requested_formats = video_data.get('requested_formats', [])
                if requested_formats and len(requested_formats) >= 2:
                    # DASH格式：有多个流（视频+音频）
                    is_dash = True
                    # 对于DASH格式，返回页面URL，让yt-dlp处理合并
                    download_url = page_url
                elif requested_formats:
                    # 只有一个流，使用该流的URL
                    download_url = requested_formats[0].get('url', '')
            
            # 如果还是没有，尝试从formats中获取最佳质量的
            if not download_url or download_url == page_url:
                # 已经标记为DASH格式，使用页面URL
                if not is_dash:
                    formats = video_data.get('formats', [])
                    if formats:
                        # 优先选择视频格式
                        for fmt in formats:
                            if fmt.get('vcodec') != 'none' and fmt.get('url'):
                                download_url = fmt.get('url', '')
                                break
                        # 如果没有视频格式，使用第一个有URL的format
                        if not download_url:
                            for fmt in formats:
                                if fmt.get('url'):
                                    download_url = fmt.get('url', '')
                                    break

            # 文件大小 - 优先使用精确值,然后尝试近似值
            filesize = video_data.get('filesize') or video_data.get('filesize_approx', 0)

            # 如果DASH格式,合并所有流的大小
            if is_dash:
                requested_formats = video_data.get('requested_formats', [])
                total_size = 0
                for fmt in requested_formats:
                    fmt_size = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                    if fmt_size:
                        total_size += fmt_size
                if total_size > 0:
                    filesize = total_size

            # 如果仍然没有大小信息,尝试从formats中估算(X/Twitter等m3u8流式视频)
            if not filesize or filesize <= 0:
                formats = video_data.get('formats', [])
                # 寻找包含filesize_approx的http格式(通常是最高画质)
                max_filesize = 0
                for fmt in formats:
                    if fmt.get('protocol') == 'https' and fmt.get('vcodec') != 'none':
                        fmt_size = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                        if fmt_size and fmt_size > max_filesize:
                            max_filesize = fmt_size
                if max_filesize > 0:
                    filesize = max_filesize

            # 时长
            duration = video_data.get('duration', 0)

            # 缩略图 - 多重备用策略
            thumbnail = self._extract_best_thumbnail(video_data)

            # 平台
            extractor = video_data.get('extractor_key', '')
            platform = self._get_platform_display_name(extractor)

            # 文件扩展名
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
                    'is_dash': is_dash  # 标记是否为DASH格式
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
        """清理文件名中的非法字符"""
        # 移除或替换Windows/Unix不允许的字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')

        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]

        # 移除首尾空格
        filename = filename.strip()

        return filename or '未命名视频'

    def _format_filesize(self, size: int) -> str:
        """格式化文件大小"""
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
        """格式化时长"""
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
        """获取平台显示名称"""
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
        """
        智能提取最佳缩略图

        处理多种情况:
        1. 标准的 thumbnail 字段
        2. thumbnails 列表中的最高质量图片
        3. 过滤无效的占位图(如B站的transparent.gif)
        4. 从formats中提取缩略图
        """
        # 无效缩略图模式(需要过滤)
        invalid_patterns = [
            'transparent.gif',  # B站占位图
            'default.jpg',      # 默认占位图
            'placeholder',      # 占位符
            '1x1',              # 1x1像素图
        ]

        def is_valid_thumbnail(url: str) -> bool:
            """检查是否为有效的缩略图URL"""
            if not url:
                return False
            url_lower = url.lower()
            return not any(pattern in url_lower for pattern in invalid_patterns)

        # 策略1: 使用 thumbnail 字段
        thumbnail = video_data.get('thumbnail', '')
        if is_valid_thumbnail(thumbnail):
            return self._ensure_https_thumbnail(thumbnail)

        # 策略2: 从 thumbnails 列表中选择最佳
        thumbnails = video_data.get('thumbnails', [])
        if thumbnails:
            # 优先选择高分辨率的缩略图
            valid_thumbnails = [t for t in thumbnails if is_valid_thumbnail(t.get('url', ''))]

            if valid_thumbnails:
                # 按优先级排序: preference > width > height
                best_thumbnail = max(
                    valid_thumbnails,
                    key=lambda t: (
                        t.get('preference', 0),
                        t.get('width', 0),
                        t.get('height', 0)
                    )
                )
                return self._ensure_https_thumbnail(best_thumbnail.get('url', ''))

        # 策略3: 从 formats 中提取(某些平台会在这里放缩略图信息)
        formats = video_data.get('formats', [])
        for fmt in formats:
            fmt_thumbnail = fmt.get('thumbnail', '')
            if is_valid_thumbnail(fmt_thumbnail):
                return self._ensure_https_thumbnail(fmt_thumbnail)

        # 策略4: 尝试其他可能的字段
        alternative_fields = ['cover', 'preview_url', 'poster', 'image']
        for field in alternative_fields:
            alt_thumbnail = video_data.get(field, '')
            if is_valid_thumbnail(alt_thumbnail):
                return self._ensure_https_thumbnail(alt_thumbnail)

        # 如果所有策略都失败,返回空字符串
        return ''

    def _ensure_https_thumbnail(self, thumbnail_url: str) -> str:
        """
        确保缩略图URL使用HTTPS协议

        很多平台(如B站)返回的缩略图URL是HTTP协议,
        但现代浏览器在HTTPS网站上会阻止加载HTTP资源(混合内容阻止),
        所以需要将HTTP转换为HTTPS

        Args:
            thumbnail_url: 原始缩略图URL

        Returns:
            转换为HTTPS的缩略图URL
        """
        if not thumbnail_url:
            return ''

        # 将HTTP转换为HTTPS
        if thumbnail_url.startswith('http://'):
            return thumbnail_url.replace('http://', 'https://', 1)

        return thumbnail_url
