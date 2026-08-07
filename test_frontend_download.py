"""下载页面前后端契约的静态测试。"""

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

    def test_all_platforms_use_background_job_api(self):
        self.assertIn("fetch('/download-jobs'", self.script)
        self.assertIn('created.status_url', self.script)
        self.assertIn('job.download_url', self.script)
        self.assertIn('media_url: videoInfo.url', self.script)
        self.assertIn('is_dash: Boolean(videoInfo.is_dash)', self.script)
        self.assertNotIn('startDashDownload(', self.script)
        self.assertNotIn('/proxy-download?', self.script)

    def test_non_json_gateway_errors_are_handled(self):
        self.assertIn("response.status === 504", self.script)
        self.assertIn("contentType.includes('application/json')", self.script)
        self.assertNotIn('response.json().then', self.script)

    def test_progress_bar_is_accessible(self):
        self.assertIn('role="progressbar"', self.html)
        self.assertIn("setAttribute('aria-valuenow'", self.script)

    def test_old_360_only_claim_is_removed(self):
        combined = f'{self.html}\n{self.script}'.lower()
        self.assertNotIn('currently supports 360p only', combined)
        self.assertNotIn('目前仅支持 360p', combined)


if __name__ == '__main__':
    unittest.main(verbosity=2)
