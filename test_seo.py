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
        body = resp.get_data(as_text=True)
        self.assertIn('Sitemap:', body)
        self.assertIn('https://vd.aisoup.ai/sitemap.xml', body)
        self.assertNotIn('aifun.store', body)

    def test_robots_blocks_api_in_every_group(self):
        # 特定 User-agent 分组会完全覆盖通用组,每组都必须重复 API 屏蔽规则
        body = self.client.get('/robots.txt').get_data(as_text=True)
        groups = [g for g in body.split('User-agent:')[1:] if g.strip()]
        self.assertGreaterEqual(len(groups), 3)
        for group in groups:
            self.assertIn('Disallow: /download-jobs', group)
            self.assertIn('Disallow: /parse-video', group)

    def test_llms_txt_accessible(self):
        resp = self.client.get('/llms.txt')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('VideoX', body)
        self.assertIn('VideoX for Mac', body)
        self.assertIn('vd.aisoup.ai', body)

    def test_sitemap_lastmod_fresh(self):
        body = self.client.get('/sitemap.xml').get_data(as_text=True)
        self.assertIn('<lastmod>2026-08-13</lastmod>', body)

    def test_share_card_uses_real_image(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('og:image" content="https://vd.aisoup.ai/static/mac-screenshot.png"', html)
        self.assertNotIn('og:image" content="https://vd.aisoup.ai/static/favicon.png"', html)

    def test_mac_app_structured_data_valid(self):
        html = self.client.get('/').get_data(as_text=True)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        app_schema = None
        for block in blocks:
            data = json.loads(block)
            if data.get('@type') == 'SoftwareApplication':
                app_schema = data
                break
        self.assertIsNotNone(app_schema, '缺少 Mac 客户端的 SoftwareApplication 结构化数据')
        self.assertEqual(app_schema.get('name'), 'VideoX for Mac')
        self.assertIn('macOS', app_schema.get('operatingSystem', ''))
        self.assertIn('myqcloud.com', app_schema.get('downloadUrl', ''))
        self.assertEqual(app_schema.get('offers', {}).get('price'), '0')

    def test_faq_structured_data_matches_page_language(self):
        # FAQ 标注必须与页面默认中文一致,语言不一致会降低搜索引擎采信
        html = self.client.get('/').get_data(as_text=True)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        for block in blocks:
            data = json.loads(block)
            if data.get('@type') == 'FAQPage':
                first_q = data['mainEntity'][0]['name']
                self.assertIn('网页版', first_q)
                return
        self.fail('缺少 FAQPage 结构化数据')

    def test_sitemap_accessible(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('xml', resp.headers.get('Content-Type', ''))
        body = resp.get_data(as_text=True)
        self.assertIn('<loc>https://vd.aisoup.ai/</loc>', body)
        self.assertNotIn('aifun.store', body)

    def test_canonical_uses_primary_domain(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('rel="canonical" href="https://vd.aisoup.ai/"', html)
        self.assertIn('og:url" content="https://vd.aisoup.ai"', html)
        self.assertNotIn('aifun.store', html)

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

    def test_terms_and_privacy_pages_accessible(self):
        terms = self.client.get('/terms')
        privacy = self.client.get('/privacy')
        self.assertEqual(terms.status_code, 200)
        self.assertEqual(privacy.status_code, 200)
        self.assertIn('服务条款', terms.get_data(as_text=True))
        self.assertIn('隐私政策', privacy.get_data(as_text=True))

    def test_homepage_promotes_mac_client(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('VideoX for Mac', html)
        self.assertIn('https://videox-1304948377.cos.ap-guangzhou.myqcloud.com/VideoX_0.2.0.dmg', html)
        self.assertIn('brand-mark.png', html)
        self.assertIn('mac-screenshot.png', html)
        self.assertIn('mac-screenshot-tasks.png', html)
        self.assertIn('id="mac-shots"', html)

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
