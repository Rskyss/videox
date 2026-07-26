"""
SEO 相关自动检查

覆盖内容:
- 应用可被正常导入(重复路由会导致导入失败)
- robots.txt / sitemap.xml / Google 验证页可访问
- 首页标题包含搜索用户真正会搜的英文关键词
- 首页包含常见问题内容及供搜索引擎读取的问答结构

运行: python3 test_seo.py
"""

import json
import re
import unittest


class SEOTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def test_robots_accessible(self):
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sitemap:', resp.get_data(as_text=True))

    def test_sitemap_accessible(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('xml', resp.headers.get('Content-Type', ''))
        self.assertIn('<loc>', resp.get_data(as_text=True))

    def test_google_verification_accessible(self):
        resp = self.client.get('/googlebb599f357f33fc9d.html')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('google-site-verification', resp.get_data(as_text=True))

    def test_title_contains_search_keywords(self):
        html = self.client.get('/').get_data(as_text=True)
        match = re.search(r'<title>(.*?)</title>', html, re.S)
        self.assertIsNotNone(match, '首页缺少 title 标签')
        title = match.group(1)

        self.assertIn('Video Downloader', title)
        self.assertIn('VideoX', title)
        self.assertLessEqual(len(title), 65, 'title 过长会被搜索结果截断')

    def test_faq_visible_on_homepage(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('data-i18n="faq-heading"', html)
        self.assertIn('data-i18n="faq-q1"', html)
        self.assertIn('data-i18n="faq-a1"', html)

    def test_faq_structured_data_valid(self):
        html = self.client.get('/').get_data(as_text=True)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        self.assertTrue(blocks, '首页缺少结构化数据')

        faq = None
        for block in blocks:
            data = json.loads(block)
            if data.get('@type') == 'FAQPage':
                faq = data
                break

        self.assertIsNotNone(faq, '缺少 FAQPage 结构化数据,Google 和 AI 无法引用问答')
        questions = faq.get('mainEntity', [])
        self.assertGreaterEqual(len(questions), 4)
        for item in questions:
            self.assertEqual(item.get('@type'), 'Question')
            self.assertTrue(item.get('name'))
            self.assertTrue(item.get('acceptedAnswer', {}).get('text'))

    def test_faq_translations_complete(self):
        with open('static/script.js', encoding='utf-8') as f:
            script = f.read()

        html = self.client.get('/').get_data(as_text=True)
        keys = set(re.findall(r'data-i18n="(faq-[^"]+)"', html))
        self.assertTrue(keys)

        for lang in ('zh', 'en'):
            section = re.search(
                r"    %s: \{(.*?)\n    \}" % lang, script, re.S)
            self.assertIsNotNone(section, f'找不到 {lang} 语言词条')
            for key in keys:
                self.assertIn(
                    f"'{key}'", section.group(1),
                    f'{lang} 缺少词条 {key},切换语言时会显示空白')

    def test_title_switches_with_language(self):
        with open('static/script.js', encoding='utf-8') as f:
            script = f.read()

        self.assertIn('document.title', script,
                      '切换语言时标签标题不会跟着变')
        for lang in ('zh', 'en'):
            section = re.search(
                r"    %s: \{(.*?)\n    \}" % lang, script, re.S)
            self.assertIn("'page-title'", section.group(1),
                          f'{lang} 缺少 page-title 词条')


if __name__ == '__main__':
    unittest.main(verbosity=2)
