"""
工具函数模块
提供环境检测、路径验证、URL验证等通用功能
"""

import os
import subprocess
import re
from typing import Tuple


def check_ytdlp() -> bool:
    """
    检查 yt-dlp 是否已安装

    Returns:
        bool: True表示已安装，False表示未安装
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_ytdlp() -> Tuple[bool, str]:
    """
    安装 yt-dlp

    Returns:
        Tuple[bool, str]: (是否成功, 错误信息)
    """
    try:
        result = subprocess.run(
            ["pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "安装超时"
    except Exception as e:
        return False, str(e)


def validate_path(path: str) -> Tuple[bool, str]:
    """
    验证路径是否有效且可写

    Args:
        path: 目录路径

    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if not path:
        return False, "路径不能为空"

    # 检查路径是否存在
    if not os.path.exists(path):
        return False, "路径不存在"

    # 检查是否为目录
    if not os.path.isdir(path):
        return False, "路径不是目录"

    # 检查是否可写
    if not os.access(path, os.W_OK):
        return False, "目录不可写"

    return True, ""


def validate_url(url: str) -> Tuple[bool, str]:
    """
    验证URL是否有效

    Args:
        url: 视频链接

    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if not url:
        return False, "链接不能为空"

    # 基本的URL格式验证
    url_pattern = re.compile(
        r'^https?://'  # http:// 或 https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
        r'(?::\d+)?'  # 可选端口
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        return False, "URL格式无效"

    return True, ""


def is_twitter_url(url: str) -> bool:
    """
    判断是否为Twitter/X链接

    Args:
        url: 视频链接

    Returns:
        bool: True表示是Twitter链接
    """
    url_lower = url.lower()
    return (
        'x.com' in url_lower
        or 'twitter.com' in url_lower
        or 'twimg.com' in url_lower
    )


# 已知视频平台列表（用于智能URL提取）
KNOWN_PLATFORMS = [
    'douyin.com',
    'xiaohongshu.com', 'xhslink.com',
    'ixigua.com',
    'tiktok.com',
    'bilibili.com', 'b23.tv',
    'youtube.com', 'youtu.be',
    'x.com', 'twitter.com', 'twimg.com',
    'kuaishou.com',
]


def extract_url_from_text(text: str) -> Tuple[bool, str, str]:
    """
    从混合文本中智能提取URL

    支持从包含标题和URL的混合文本中自动提取URL链接。
    优先选择已知视频平台的URL。

    Args:
        text: 可能包含标题和URL的混合文本

    Returns:
        Tuple[bool, str, str]: (是否成功, 提取的URL, 错误信息)

    Example:
        >>> extract_url_from_text("复制打开抖音 https://v.douyin.com/xxx/")
        (True, "https://v.douyin.com/xxx/", "")

        >>> extract_url_from_text("没有链接的文本")
        (False, "", "未找到有效的URL链接")
    """
    # 1. 基本处理
    text = text.strip()
    if not text:
        return False, "", "文本不能为空"

    # 2. 长度检查（防止过长输入）
    if len(text) > 10000:
        return False, "", "输入文本过长"

    # 3. 检查是否是纯URL（向后兼容）
    url_pattern_full = re.compile(
        r'^https?://[^\s\u4e00-\u9fff]+$',
        re.IGNORECASE
    )
    if url_pattern_full.match(text):
        return True, text, ""

    # 4. 提取所有URL
    url_pattern = re.compile(
        r'https?://[^\s\u4e00-\u9fff]+',
        re.IGNORECASE
    )
    urls = url_pattern.findall(text)

    if not urls:
        return False, "", "未找到有效的URL链接"

    # 5. 优先选择已知平台的URL
    for url in urls:
        url_lower = url.lower()
        for platform in KNOWN_PLATFORMS:
            if platform in url_lower:
                # 去除URL末尾的标点符号
                cleaned_url = url.rstrip(',.;!?。，、；！？')
                return True, cleaned_url, ""

    # 6. 没有已知平台，返回第一个URL
    cleaned_url = urls[0].rstrip(',.;!?。，、；！？')
    return True, cleaned_url, ""


def get_platform_name(url: str) -> str:
    """
    识别URL所属的视频平台

    Args:
        url: 视频URL

    Returns:
        str: 平台名称（中文）

    Example:
        >>> get_platform_name("https://v.douyin.com/xxx/")
        "抖音"

        >>> get_platform_name("https://www.youtube.com/watch?v=xxx")
        "YouTube"
    """
    url_lower = url.lower()

    if 'douyin.com' in url_lower:
        return '抖音'
    elif 'xiaohongshu.com' in url_lower or 'xhslink.com' in url_lower:
        return '小红书'
    elif 'ixigua.com' in url_lower:
        return '西瓜视频'
    elif 'tiktok.com' in url_lower:
        return 'TikTok'
    elif 'bilibili.com' in url_lower or 'b23.tv' in url_lower:
        return 'B站'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YouTube'
    elif (
        'x.com' in url_lower
        or 'twitter.com' in url_lower
        or 'twimg.com' in url_lower
    ):
        return 'Twitter/X'
    elif 'kuaishou.com' in url_lower:
        return '快手'
    else:
        return 'Unknown'


def get_safe_subpaths(base_path: str) -> list:
    """
    获取目录下的子目录列表（用于目录浏览）

    Args:
        base_path: 基础路径

    Returns:
        list: 子目录信息列表，每项包含 {name, path, is_dir}
    """
    try:
        # 安全检查：防止访问系统敏感目录
        dangerous_paths = ['/etc', '/System', '/private', '/boot', 'C:\\Windows', 'C:\\System']
        abs_path = os.path.abspath(base_path)

        for dangerous in dangerous_paths:
            if abs_path.startswith(dangerous):
                return []

        items = []

        # 添加父目录选项（如果不是根目录）
        parent = os.path.dirname(abs_path)
        if parent != abs_path:  # 不是根目录
            items.append({
                'name': '..',
                'path': parent,
                'is_dir': True
            })

        # 列出所有子目录
        try:
            for entry in os.scandir(base_path):
                if entry.is_dir() and not entry.name.startswith('.'):
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'is_dir': True
                    })
        except PermissionError:
            pass

        return items

    except Exception:
        return []
