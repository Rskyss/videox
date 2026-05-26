from datetime import datetime
import os

class SimpleTracker:
    def __init__(self, stats_file='/www/wwwroot/vd/daily_stats.txt'):
        self.stats_file = stats_file
        self.platforms = ['YouTube', '抖音', '小红书', 'B站', 'Twitter', 'TikTok']
    
    def _get_today_stats(self):
        """读取今天的统计数据"""
        today = datetime.now().strftime('%Y-%m-%d')
        stats = {platform: 0 for platform in self.platforms}
        
        if not os.path.exists(self.stats_file):
            return today, stats
        
        # 读取文件，查找今天的数据
        with open(self.stats_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找今天的日期行
        for i, line in enumerate(lines):
            if line.strip() == today:
                # 找到了,读取下一行的数据
                if i + 1 < len(lines):
                    data_line = lines[i + 1].strip()
                    # 解析数据：YouTube：5  抖音：3 ...
                    parts = data_line.split('  ')
                    for part in parts:
                        if '：' in part:
                            platform, count = part.split('：')
                            if platform in stats:
                                stats[platform] = int(count)
                break
        
        return today, stats
    
    def track(self, platform):
        """
        记录一次下载
        platform: 'youtube', 'douyin', 'xiaohongshu', 'bilibili', 'twitter', 'tiktok'
        """
        # 平台名称映射
        platform_map = {
            'youtube': 'YouTube',
            'douyin': '抖音',
            'xiaohongshu': '小红书',
            'bilibili': 'B站',
            'twitter': 'Twitter',
            'tiktok': 'TikTok'
        }
        
        platform_name = platform_map.get(platform.lower(), platform)
        if platform_name not in self.platforms:
            return
        
        today, stats = self._get_today_stats()
        stats[platform_name] += 1
        
        # 更新文件
        self._update_file(today, stats)
    
    def _update_file(self, today, stats):
        """更新统计文件"""
        # 读取现有内容
        if os.path.exists(self.stats_file):
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # 查找今天的记录并更新
        today_found = False
        new_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line == today:
                today_found = True
                new_lines.append(today + '\n')
                # 跳过旧的数据行
                if i + 1 < len(lines):
                    i += 1
                # 写入新的数据行
                data_line = '  '.join([f'{p}：{stats[p]}' for p in self.platforms])
                new_lines.append(data_line + '\n\n')
            else:
                new_lines.append(lines[i])
            i += 1
        
        # 如果今天的记录不存在,添加到开头
        if not today_found:
            data_line = '  '.join([f'{p}：{stats[p]}' for p in self.platforms])
            new_lines.insert(0, today + '\n')
            new_lines.insert(1, data_line + '\n\n')
        
        # 写入文件
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

# 全局实例
tracker = SimpleTracker()
