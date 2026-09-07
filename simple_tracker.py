from datetime import datetime
import os

class SimpleTracker:
    """网页版使用统计：按天记三类事件——解析、下载成功、下载失败。

    文件格式（每个日期块最多三行，第一行必须是解析计数，旧后台按第一行解析）：
        2026-08-27
        YouTube：2  抖音：0  小红书：1  B站：0  Twitter：0  TikTok：0
        下载成功 YouTube：1  抖音：0  小红书：0  B站：0  Twitter：0  TikTok：0
        下载失败 YouTube：0  抖音：0  小红书：0  B站：0  Twitter：0  TikTok：0
    """

    EVENTS = ('parse', 'success', 'fail')
    EVENT_PREFIX = {'parse': '', 'success': '下载成功 ', 'fail': '下载失败 '}

    def __init__(self, stats_file='/www/wwwroot/vd/daily_stats.txt'):
        self.stats_file = stats_file
        self.platforms = ['YouTube', '抖音', '小红书', 'B站', 'Twitter', 'TikTok']

    def _empty_stats(self):
        return {event: {platform: 0 for platform in self.platforms} for event in self.EVENTS}

    def _parse_data_line(self, line):
        """解析一行计数，返回 (事件类型, {平台: 数量})；不是计数行返回 (None, None)。"""
        event = 'parse'
        for key, prefix in self.EVENT_PREFIX.items():
            if prefix and line.startswith(prefix.strip()):
                event = key
                line = line[len(prefix.strip()):].strip()
                break
        counts = {}
        for part in line.split('  '):
            part = part.strip()
            if '：' in part:
                platform, _, count = part.partition('：')
                if platform in self.platforms and count.isdigit():
                    counts[platform] = int(count)
        if not counts:
            return None, None
        return event, counts

    def _get_today_stats(self):
        """读取今天的统计数据"""
        today = datetime.now().strftime('%Y-%m-%d')
        stats = self._empty_stats()

        if not os.path.exists(self.stats_file):
            return today, stats

        with open(self.stats_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if line.strip() == today:
                # 读取该日期块内的所有计数行，直到遇到下一个日期
                for cursor in range(i + 1, len(lines)):
                    text = lines[cursor].strip()
                    if not text:
                        continue
                    if self._looks_like_date(text):
                        break
                    event, counts = self._parse_data_line(text)
                    if event:
                        for platform, count in counts.items():
                            stats[event][platform] = count
                break

        return today, stats

    @staticmethod
    def _looks_like_date(text):
        return len(text) == 10 and text[4] == '-' and text[7] == '-' and text[:4].isdigit()

    def track(self, platform, event='parse'):
        """
        记录一次事件
        platform: 'youtube', 'douyin', 'xiaohongshu', 'bilibili', 'twitter', 'tiktok'
        event: 'parse'（解析成功） / 'success'（下载完成） / 'fail'（下载失败）
        """
        platform_map = {
            'youtube': 'YouTube',
            'douyin': '抖音',
            'xiaohongshu': '小红书',
            'bilibili': 'B站',
            'twitter': 'Twitter',
            'tiktok': 'TikTok'
        }

        platform_name = platform_map.get(str(platform).lower(), platform)
        if platform_name not in self.platforms or event not in self.EVENTS:
            return

        today, stats = self._get_today_stats()
        stats[event][platform_name] += 1

        self._update_file(today, stats)

    def _format_block(self, today, stats):
        """生成一天的记录块：解析行永远在第一行，下载行只在有数据时写。"""
        block = [today + '\n']
        block.append(self._format_data_line('parse', stats) + '\n')
        for event in ('success', 'fail'):
            if any(stats[event].values()):
                block.append(self._format_data_line(event, stats) + '\n')
        block.append('\n')
        return block

    def _format_data_line(self, event, stats):
        prefix = self.EVENT_PREFIX[event]
        return prefix + '  '.join(f'{p}：{stats[event][p]}' for p in self.platforms)

    def _update_file(self, today, stats):
        """更新统计文件：替换今天的整个日期块，其余内容原样保留。"""
        if os.path.exists(self.stats_file):
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []

        new_lines = []
        today_found = False
        i = 0
        while i < len(lines):
            text = lines[i].strip()
            if text == today:
                today_found = True
                new_lines.extend(self._format_block(today, stats))
                # 跳过旧日期块（计数行与空行），直到下一个日期行
                i += 1
                while i < len(lines):
                    nxt = lines[i].strip()
                    if self._looks_like_date(nxt):
                        break
                    i += 1
                continue
            new_lines.append(lines[i])
            i += 1

        if not today_found:
            new_lines = self._format_block(today, stats) + new_lines

        with open(self.stats_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

# 全局实例
tracker = SimpleTracker()
