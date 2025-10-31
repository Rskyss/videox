"""
抖音无水印下载支持 V2 - 优化版
添加移动端解析、改进API调用、无需登录
"""

import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional, List
import html as html_lib

import requests
from urllib.parse import unquote


class DouyinDownloadError(Exception):
    """抖音下载相关异常"""


class DouyinService:
    """
    优化的抖音下载服务
    - 支持iesdouyin分享页解析(无需登录)
    - 自动ttwid生成
    - 多种降级策略
    - 纯后端运行,适合服务器部署
    """

    # API endpoints
    DETAIL_API = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"
    MOBILE_DETAIL_API = "https://m.douyin.com/web/api/v2/aweme/iteminfo/"
    TTPASS_URL = "https://ttwid.bytedance.com/ttwid/union/register/"

    # User-Agents
    DESKTOP_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
        "MicroMessenger/8.0.38(0x18002633) NetType/WIFI Language/zh_CN"
    )

    def __init__(self):
        """初始化服务"""
        self.session = requests.Session()
        
        # 先访问首页获取真实Cookie，提高成功率
        try:
            init_resp = self.session.get(
                "https://www.douyin.com/",
                headers={"User-Agent": self.DESKTOP_UA},
                timeout=10
            )
            # 保留首页返回的Cookie
        except:
            pass
        
        self._setup_session()

        # 缓存目录
        cache_root = Path.home() / ".cache" / "video-downloader-v2"
        cache_root.mkdir(parents=True, exist_ok=True)
        self.ttwid_cache = cache_root / "ttwid.json"

    def _setup_session(self):
        """配置session默认headers"""
        self.session.headers.update({
            "User-Agent": self.DESKTOP_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            # 移除 Accept-Encoding 避免gzip解压问题
            "Referer": "https://www.douyin.com/",
            "Origin": "https://www.douyin.com",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        })
        
        # 添加基础Cookie避免被识别为爬虫
        self.session.cookies.set("__ac_nonce", "0638733a400869e3deb4f", domain=".douyin.com")
        self.session.cookies.set("__ac_signature", "_02B4Z6wo00f01LjBMOgAAIDAh.tfe-gVw", domain=".douyin.com")
        self.session.cookies.set("ttwid", "1%7C-random-ttwid-placeholder%7C0", domain=".douyin.com")

    # ========================= Public API =========================

    def is_supported(self, url: str) -> bool:
        """检查是否支持该URL"""
        return "douyin.com" in url.lower()

    def download(self, url: str, directory: str) -> Dict:
        """
        下载视频(同步方法)

        Args:
            url: 抖音视频链接
            directory: 保存目录

        Returns:
            下载结果字典
        """
        try:
            aweme = self._get_aweme_detail(url)
            filepath = self._save_video(aweme, directory)
            return {
                "success": True,
                "message": f"视频下载成功: {filepath}"
            }
        except DouyinDownloadError as exc:
            return {
                "success": False,
                "message": "抖音下载失败",
                "error": str(exc)
            }
        except Exception as exc:
            return {
                "success": False,
                "message": "抖音下载发生未知错误",
                "error": str(exc)
            }

    def download_with_progress(
        self,
        url: str,
        directory: str,
        raise_on_error: bool = False
    ) -> Generator[Dict, None, None]:
        """下载视频并返回进度"""
        try:
            yield {"status": "progress", "percent": 0, "message": "正在解析抖音链接..."}

            aweme = self._get_aweme_detail(url)
            title = self._sanitize_title(self._extract_title(aweme))
            download_url = self._build_download_url(aweme)
            filepath = os.path.join(directory, f"{title}.mp4")

            yield {"status": "progress", "percent": 5, "message": "正在获取视频数据..."}

            downloaded = 0
            total = 0
            with self.session.get(download_url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                with open(filepath, "wb") as file_obj:
                    for chunk in resp.iter_content(chunk_size=1024 * 512):
                        if not chunk:
                            continue
                        file_obj.write(chunk)
                        downloaded += len(chunk)
                        percent = min(99, (downloaded / total * 100) if total else 50)
                        yield {
                            "status": "progress",
                            "percent": percent,
                            "message": f"下载中... {percent:.1f}%",
                            "downloaded": self._format_bytes(downloaded),
                            "total": self._format_bytes(total) if total else "未知"
                        }

            yield {
                "status": "complete",
                "percent": 100,
                "message": f"下载完成: {filepath}"
            }
        except DouyinDownloadError as exc:
            if raise_on_error:
                raise
            yield {
                "status": "error",
                "message": "抖音下载失败",
                "error": str(exc)
            }
        except Exception as exc:
            if raise_on_error:
                raise DouyinDownloadError(str(exc)) from exc
            yield {
                "status": "error",
                "message": "抖音下载发生未知错误",
                "error": str(exc)
            }

    # ========================= 核心解析逻辑 =========================

    def _get_aweme_detail(self, url: str) -> Dict:
        """
        获取视频详情(多策略降级)

        策略顺序:
        1. 移动端HTML解析 (最简单,无需复杂参数)
        2. PC端HTML解析
        3. API调用 (需要ttwid)
        """
        item_id = self._extract_item_id(url)
        if not item_id:
            raise DouyinDownloadError("未能解析视频ID，请确认链接有效")

        # 策略1: 移动端HTML解析 (优先,最简单)
        try:
            return self._fetch_aweme_from_mobile_page(item_id)
        except DouyinDownloadError as exc:
            print(f"移动端解析失败: {exc}")

        # 策略2: PC端HTML解析
        try:
            return self._fetch_aweme_from_pc_page(item_id)
        except DouyinDownloadError as exc:
            print(f"PC端解析失败: {exc}")

        # 策略3: API调用 (需要ttwid)
        try:
            return self._fetch_aweme_from_api(item_id)
        except DouyinDownloadError as exc:
            print(f"API调用失败: {exc}")

        raise DouyinDownloadError(
            "所有解析策略均失败。"
            "这可能是因为: 1) 视频已删除 2) 视频为私密 3) 需要登录查看"
        )

    def _fetch_aweme_from_mobile_page(self, item_id: str) -> Dict:
        """
        从iesdouyin分享页提取视频信息(无需登录)

        核心原理: iesdouyin页面中包含完整的window._ROUTER_DATA
        """
        # 优先使用iesdouyin分享链接(包含完整数据)
        mobile_url = f"https://www.iesdouyin.com/share/video/{item_id}/"

        # 使用移动端UA - 移除Accept-Encoding避免gzip问题
        headers = {
            "User-Agent": self.MOBILE_UA,
            "Referer": "https://www.douyin.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

        try:
            resp = self.session.get(mobile_url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            html = resp.text

            # 提取JSON数据
            aweme = self._extract_aweme_from_html(html, item_id)

            if aweme:
                return aweme

            raise DouyinDownloadError("iesdouyin页面解析失败:未找到视频数据")

        except requests.RequestException as exc:
            raise DouyinDownloadError(f"iesdouyin页面请求失败: {exc}")

    def _fetch_aweme_from_pc_page(self, item_id: str) -> Dict:
        """从PC端页面提取视频信息"""
        pc_url = f"https://www.douyin.com/video/{item_id}"

        try:
            resp = self.session.get(pc_url, timeout=15)
            resp.raise_for_status()
            html = resp.text

            aweme = self._extract_aweme_from_html(html, item_id)

            if aweme:
                return aweme

            raise DouyinDownloadError("PC端页面解析失败:未找到视频数据")

        except requests.RequestException as exc:
            raise DouyinDownloadError(f"PC端页面请求失败: {exc}")

    def _fetch_aweme_from_api(self, item_id: str) -> Dict:
        """从API获取视频信息(需要ttwid)"""
        ttwid = self._get_ttwid()

        params = {"item_ids": item_id}
        cookies = {"ttwid": ttwid}

        # 尝试桌面端API
        try:
            resp = self.session.get(
                self.DETAIL_API,
                params=params,
                cookies=cookies,
                timeout=10
            )
            resp.raise_for_status()

            data = resp.json()
            item_list = data.get("item_list") or []

            if item_list:
                return item_list[0]

        except Exception as exc:
            print(f"桌面端API失败: {exc}")

        # 尝试移动端API
        try:
            resp = self.session.get(
                self.MOBILE_DETAIL_API,
                params=params,
                cookies=cookies,
                timeout=10
            )
            resp.raise_for_status()

            data = resp.json()
            item_list = data.get("item_list") or []

            if item_list:
                return item_list[0]

        except Exception as exc:
            print(f"移动端API失败: {exc}")

        raise DouyinDownloadError("API调用返回空数据")

    def _extract_aweme_from_html(self, html: str, item_id: str) -> Optional[Dict]:
        """
        从HTML中提取视频数据

        多种提取模式:
        1. window._ROUTER_DATA__
        2. window.__INIT_PROPS__
        3. <script id="RENDER_DATA">
        4. 直接提取视频播放地址
        """
        candidates = self._extract_candidate_data(html)

        # 从候选数据中查找目标视频
        for data in candidates:
            aweme = self._search_aweme_in_data(data, item_id)
            if aweme:
                return aweme

        # 兜底: 直接提取视频播放地址
        play_addr = self._extract_playaddr_from_html(html)
        if play_addr:
            return {
                "desc": f"douyin_{item_id}",
                "statistics": {"aweme_id": item_id},
                "video": {
                    "play_addr": {
                        "url_list": [play_addr],
                        "uri": item_id
                    }
                }
            }

        return None

    def _extract_candidate_data(self, html: str) -> List[Dict[str, Any]]:
        """提取HTML中的所有JSON数据块"""
        data_list: List[Dict[str, Any]] = []

        def try_load(text: str, *, url_decode: bool = False):
            if not text:
                return
            try:
                text = html_lib.unescape(text.strip())
                if url_decode:
                    text = unquote(text)
                data = json.loads(text)
                if isinstance(data, dict):
                    data_list.append(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            data_list.append(item)
            except json.JSONDecodeError:
                return

        # 模式1: window._ROUTER_DATA = {...}; (单下划线,iesdouyin使用)
        for match in re.finditer(
            r'window\._ROUTER_DATA\s*=\s*(\{.+?\});?\s*<',
            html,
            re.S
        ):
            try_load(match.group(1))

        # 模式1b: window._ROUTER_DATA__ = {...}; (双下划线,旧版本)
        for match in re.finditer(
            r'window\._ROUTER_DATA__\s*=\s*(\{.*?\})\s*;</script>',
            html,
            re.S
        ):
            try_load(match.group(1))

        # 模式2: window._ROUTER_DATA__ = JSON.parse("...");
        for match in re.finditer(
            r'window\._ROUTER_DATA__\s*=\s*JSON\.parse\("(.+?)"\)',
            html,
            re.S
        ):
            encoded = match.group(1)
            try:
                decoded = json.loads(f'"{encoded}"')
                try_load(decoded)
            except json.JSONDecodeError:
                continue

        # 模式3: <script id="RENDER_DATA">
        render_match = re.search(
            r'<script id="RENDER_DATA" type="application/json">(.+?)</script>',
            html,
            re.S
        )
        if render_match:
            try_load(render_match.group(1), url_decode=True)

        # 模式4: <script id="SIGI_STATE">
        sigi_match = re.search(
            r'<script id="SIGI_STATE" type="application/json">(.+?)</script>',
            html,
            re.S
        )
        if sigi_match:
            try_load(sigi_match.group(1))

        # 模式5: window.__INIT_PROPS__ = {...}
        for match in re.finditer(
            r'window\.__INIT_PROPS__\s*=\s*(\{.*?\});',
            html,
            re.S
        ):
            try_load(match.group(1))

        return data_list

    def _extract_playaddr_from_html(self, html: str) -> Optional[str]:
        """直接从HTML中提取视频播放地址"""
        patterns = [
            r'playAddr["\']?\s*:\s*["\']([^"\']+)["\']',
            r'"playApi"\s*:\s*"([^"]+)"',
            r'"play_addr"\s*:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = html_lib.unescape(match.group(1))
                url = url.replace("\\u002F", "/").replace("\\/", "/")
                if url.startswith("//"):
                    url = "https:" + url
                # 去除水印
                url = url.replace("playwm", "play")
                return url

        return None

    def _search_aweme_in_data(self, data: Any, target_id: str) -> Optional[Dict]:
        """在数据结构中搜索目标视频"""
        # 特殊处理: iesdouyin的 _ROUTER_DATA 结构
        if "loaderData" in data:
            try:
                for key, value in data["loaderData"].items():
                    if "videoInfoRes" in value:
                        item_list = value["videoInfoRes"].get("item_list", [])
                        if item_list:
                            return item_list[0]
            except (KeyError, TypeError, IndexError):
                pass

        stack: List = [data]
        candidate_keys = (
            "itemStruct", "itemInfo", "item_info", "aweme", "awemeInfo",
            "aweme_info", "item", "detail", "awemeDetail", "aweme_detail",
            "videoData", "video_data", "item_list", "videoInfoRes"
        )

        while stack:
            node = stack.pop()

            if isinstance(node, dict):
                # 检查是否是目标视频
                aweme_id = node.get("aweme_id") or node.get("awemeId") or node.get("id")
                if node.get("video") and (not target_id or str(aweme_id) == str(target_id)):
                    return node

                # 继续搜索候选键
                for key in candidate_keys:
                    if key in node:
                        found = self._coerce_aweme(node[key], target_id)
                        if found:
                            return found

                stack.extend(node.values())

            elif isinstance(node, list):
                stack.extend(node)

        return None

    def _coerce_aweme(self, value: Any, target_id: str) -> Optional[Dict]:
        """将值强制转换为aweme结构"""
        if isinstance(value, dict):
            if value.get("video"):
                aweme_id = value.get("aweme_id") or value.get("awemeId")
                if not target_id or str(aweme_id) == str(target_id):
                    return value

        elif isinstance(value, list):
            for item in value:
                found = self._coerce_aweme(item, target_id)
                if found:
                    return found

        return None

    # ========================= 辅助方法 =========================

    def _extract_item_id(self, url: str) -> Optional[str]:
        """从URL提取视频ID"""
        # 方式1: 从完整URL提取 (支持 /video/ 和 /note/ 格式)
        match = re.search(r'/(?:video|note)/(\d+)', url)
        if match:
            return match.group(1)

        # 方式2: 从参数提取
        match = re.search(r'item_ids?=(\d+)', url, re.IGNORECASE)
        if match:
            return match.group(1)

        # 方式3: 短链跳转
        if 'v.douyin.com' in url.lower():
            try:
                resp = self.session.get(url, timeout=10, allow_redirects=True)
                resp.raise_for_status()

                match = re.search(r'itemId: "(\d+)"', resp.text)
                if match:
                    return match.group(1)

                match = re.search(r'/(?:video|note)/(\d+)', resp.url)
                if match:
                    return match.group(1)

            except Exception:
                pass

        return None

    def _build_download_url(self, aweme: Dict) -> str:
        """构建无水印下载URL"""
        # 检查是否为图文内容
        images = aweme.get("images")
        if images and len(images) > 0:
            raise DouyinDownloadError(
                "这是一个图文作品，不是视频！\n"
                "图文作品包含图片和背景音乐，暂不支持下载。\n"
                "建议在抖音App中直接保存图片。"
            )
        
        video_data = aweme.get("video") or {}

        # 优先使用无水印链接
        for key in ("play_addr", "download_addr", "play_addr_lowbr"):
            addr = video_data.get(key) or {}
            url_list = addr.get("url_list") or []
            if url_list:
                candidate = url_list[0]
                # 去除水印标记
                # 过滤音频链接
                if "ies-music" in candidate or ".mp3" in candidate:
                    continue
                return candidate.replace("playwm", "play")

        raise DouyinDownloadError("未能获取视频播放地址")

    def _save_video(self, aweme: Dict, directory: str) -> str:
        """保存视频到本地"""
        title = self._sanitize_title(self._extract_title(aweme))
        filepath = os.path.join(directory, f"{title}.mp4")
        download_url = self._build_download_url(aweme)

        with self.session.get(download_url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(filepath, "wb") as file_obj:
                for chunk in resp.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        file_obj.write(chunk)

        return filepath

    def _extract_title(self, aweme: Dict) -> str:
        """提取视频标题"""
        fields = [
            aweme.get("desc"),
            aweme.get("share_info", {}).get("share_title"),
            aweme.get("statistics", {}).get("aweme_id"),
        ]
        for field in fields:
            if field:
                return str(field)
        return "douyin_video"

    def _sanitize_title(self, title: str) -> str:
        """清理文件名"""
        safe = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        return safe[:100] or "douyin_video"  # 限制长度

    def _format_bytes(self, num: int) -> str:
        """格式化字节数"""
        if not num:
            return "0B"
        for unit in ["B", "KB", "MB", "GB"]:
            if num < 1024:
                return f"{num:.1f}{unit}"
            num /= 1024
        return f"{num:.1f}TB"

    # ========================= TTwid管理 =========================

    def _get_ttwid(self, force_refresh: bool = False) -> str:
        """获取ttwid (自动缓存)"""
        if not force_refresh:
            cached = self._read_cached_ttwid()
            if cached:
                return cached

        ttwid = self._request_ttwid()
        self._write_cached_ttwid(ttwid)
        return ttwid

    def _read_cached_ttwid(self) -> Optional[str]:
        """读取缓存的ttwid"""
        if not self.ttwid_cache.exists():
            return None
        try:
            with open(self.ttwid_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < 7 * 24 * 3600:  # 7天有效期
                return data.get("ttwid")
        except Exception:
            return None
        return None

    def _write_cached_ttwid(self, ttwid: str) -> None:
        """缓存ttwid"""
        try:
            with open(self.ttwid_cache, "w", encoding="utf-8") as f:
                json.dump({"ttwid": ttwid, "ts": time.time()}, f)
        except Exception:
            pass

    def _request_ttwid(self) -> str:
        """请求ttwid"""
        payload = {"region": "cn", "aid": 1768, "needFid": False, "service": "www.ixigua.com"}
        headers = {
            "User-Agent": self.DESKTOP_UA,
            "Content-Type": "application/json",
        }

        try:
            resp = self.session.post(
                self.TTPASS_URL,
                headers=headers,
                json=payload,
                timeout=10
            )
            if resp.ok and "ttwid" in resp.cookies:
                return resp.cookies["ttwid"]
        except Exception as exc:
            print(f"ttwid请求失败: {exc}")

        # 兜底: 访问首页获取
        try:
            resp = self.session.get("https://www.douyin.com/", timeout=10)
            if "ttwid" in resp.cookies:
                return resp.cookies["ttwid"]
        except Exception:
            pass

        raise DouyinDownloadError("无法获取ttwid")