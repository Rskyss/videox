"""
抖音视频解析器 - 多策略备用方案
提供多种解析策略,提高下载成功率
"""

import re
import requests
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, quote
import json


class DouyinParser:
    """抖音视频解析器,提供多种解析策略"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
                         "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.douyin.com/",
        })

    def is_douyin_url(self, url: str) -> bool:
        """判断是否为抖音链接"""
        return 'douyin.com' in url.lower()

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        从抖音链接中提取视频ID

        Args:
            url: 抖音视频链接

        Returns:
            视频ID,提取失败返回None
        """
        # 方式1: 从完整URL中提取 (支持 /video/ 和 /note/ 格式)
        match = re.search(r'/(?:video|note)/(\d+)', url)
        if match:
            return match.group(1)

        # 方式2: 从分享参数中提取
        match = re.search(r'item_ids?=(\d+)', url, re.IGNORECASE)
        if match:
            return match.group(1)

        # 方式3: 短链跳转提取
        if 'v.douyin.com' in url.lower():
            try:
                resp = self.session.get(url, timeout=10, allow_redirects=True)
                return self.extract_video_id(resp.url)
            except:
                pass

        return None

    def parse_share_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析抖音分享文本,提取标题和链接

        Args:
            text: 抖音分享的文本内容

        Returns:
            (标题, URL) 元组
        """
        # 提取标题 (通常在引号中)
        title_match = re.search(r'["""](.*?)["""]', text)
        title = title_match.group(1) if title_match else None

        # 提取URL
        url_patterns = [
            r'(https?://v\.douyin\.com/[A-Za-z0-9]+/?)',
            r'(https?://www\.douyin\.com/video/\d+)',
            r'(https?://www\.iesdouyin\.com/share/video/\d+)',
        ]

        url = None
        for pattern in url_patterns:
            match = re.search(pattern, text)
            if match:
                url = match.group(1)
                break

        return title, url

    def get_video_info(self, url: str) -> Dict:
        """
        获取视频信息 (尝试无需cookies的公开API)

        Args:
            url: 抖音视频链接

        Returns:
            包含视频信息的字典
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            return {
                'success': False,
                'error': '无法提取视频ID'
            }

        # 尝试公开API (可能需要cookies)
        try:
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"
            params = {'item_ids': video_id}

            resp = self.session.get(api_url, params=params, timeout=10)

            if resp.status_code == 200 and len(resp.text) > 0:
                try:
                    data = resp.json()
                    item_list = data.get('item_list', [])

                    if item_list:
                        aweme = item_list[0]
                        return {
                            'success': True,
                            'video_id': video_id,
                            'title': aweme.get('desc', ''),
                            'author': aweme.get('author', {}).get('nickname', ''),
                            'video_data': aweme.get('video', {}),
                        }
                except json.JSONDecodeError:
                    pass
        except:
            pass

        return {
            'success': False,
            'video_id': video_id,
            'error': '无法获取视频信息,可能需要登录'
        }

    def get_download_suggestion(self, url: str) -> str:
        """
        为抖音链接生成下载建议

        Args:
            url: 抖音视频链接

        Returns:
            给用户的建议文本
        """
        video_id = self.extract_video_id(url)

        suggestions = [
            "抖音视频下载建议:",
            "",
            "1. 确保已在浏览器(Chrome/Safari)登录抖音账号",
            "2. 在工具界面选择'自动检测'浏览器登录状态",
            "3. 如果仍然失败,可以尝试:",
            f"   - 在浏览器中打开: https://www.douyin.com/video/{video_id}",
            "   - 确认视频可以正常播放",
            "   - 检查视频是否为私密视频或已删除",
            "",
            "4. 替代方案:",
            "   - 使用浏览器扩展插件下载",
            "   - 在抖音App中保存到相册(但会有水印)",
        ]

        return "\n".join(suggestions)


def test_parser():
    """测试解析器功能"""
    parser = DouyinParser()

    # 测试文本解析
    share_text = '2.03 02/16 i@v.bC "有了孩子后的每一天"  https://v.douyin.com/iFscbgoU/ 复制此链接，打开Dou音搜索，直接观看视频！'
    title, url = parser.parse_share_text(share_text)
    print(f"标题: {title}")
    print(f"链接: {url}")

    if url:
        video_id = parser.extract_video_id(url)
        print(f"视频ID: {video_id}")


if __name__ == '__main__':
    test_parser()
