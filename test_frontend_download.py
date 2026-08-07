"""下载页面前后端契约的静态测试（web：合并走进度条，直链走浏览器）。"""

import re
import unittest


class FrontendDownloadContractTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('templates/index.html', encoding='utf-8') as handle:
            cls.html = handle.read()
        with open('static/script.js', encoding='utf-8') as handle:
            cls.script = handle.read()

    def test_quality_picker_has_supported_values(self):
        values = set(re.findall(r'<option value="(\d+)"', self.html))
        self.assertEqual(values, {'360', '720', '1080'})
        self.assertIn('<option value="720" data-i18n="quality-720" selected>', self.html)

    def test_merge_platforms_use_job_progress_then_auto_save(self):
        self.assertIn("fetch('/download-jobs'", self.script)
        self.assertIn('startDownloadJob(', self.script)
        self.assertIn('job.download_url', self.script)
        self.assertIn('role="progressbar"', self.html)
        self.assertIn('download-progress', self.html)
        self.assertIn("updateJobProgress('ready', 100", self.script)

    def test_direct_links_still_use_browser_download(self):
        self.assertIn('/proxy-download?', self.script)
        self.assertIn('startBrowserDownload(', self.script)

    def test_bilibili_shows_quality_picker_like_youtube(self):
        self.assertIn('isBilibili', self.script)
        self.assertIn('(isYouTube || isBilibili)', self.script)

    def test_non_json_parse_errors_are_handled(self):
        self.assertIn("contentType.includes('application/json')", self.script)
        self.assertIn('parseApiResponse(', self.script)

    def test_old_360_only_claim_is_removed(self):
        combined = f'{self.html}\n{self.script}'.lower()
        self.assertNotIn('currently supports 360p only', combined)
        self.assertNotIn('目前仅支持 360p', combined)


if __name__ == '__main__':
    unittest.main(verbosity=2)
