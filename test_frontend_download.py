"""下载页面前后端契约的静态测试（web 分支：浏览器原生下载）。"""

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

    def test_browser_native_download_via_proxy(self):
        self.assertIn('/proxy-download?', self.script)
        self.assertIn('startBrowserDownload(', self.script)
        self.assertIn("link.download = filename", self.script)
        self.assertNotIn("fetch('/download-jobs'", self.script)
        self.assertNotIn('download-progress', self.html)
        self.assertNotIn('role="progressbar"', self.html)

    def test_non_json_parse_errors_are_handled(self):
        self.assertIn("contentType.includes('application/json')", self.script)
        self.assertIn('parseApiResponse(', self.script)

    def test_old_360_only_claim_is_removed(self):
        combined = f'{self.html}\n{self.script}'.lower()
        self.assertNotIn('currently supports 360p only', combined)
        self.assertNotIn('目前仅支持 360p', combined)


if __name__ == '__main__':
    unittest.main(verbosity=2)
