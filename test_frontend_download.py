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

    def test_progress_ui_prefers_server_status_message(self):
        """后端的重试/音频阶段文案不能被笼统的 Downloading video 盖掉。"""
        self.assertIn("let localizedStatus = (message || '').trim();", self.script)
        self.assertNotIn(
            "if (status === 'downloading') localizedStatus = translations[appState.currentLang]['download-downloading'];\n"
            "    if (status === 'merging')",
            self.script,
        )

    def test_direct_links_still_use_browser_download(self):
        self.assertIn('/proxy-download?', self.script)
        self.assertIn('startBrowserDownload(', self.script)

    def test_bilibili_shows_quality_picker_like_youtube(self):
        self.assertIn('isBilibili', self.script)
        self.assertIn('(isYouTube || isBilibili)', self.script)

    def test_size_display_updates_when_quality_changes(self):
        self.assertIn("qualitySelect.addEventListener('change', updateSizeForSelectedQuality)", self.script)
        self.assertIn('function updateSizeForSelectedQuality', self.script)
        self.assertIn('quality_sizes_readable', self.script)

    def test_bilibili_hides_unavailable_quality_options(self):
        self.assertIn('function applyQualityOptions', self.script)
        self.assertIn('available_qualities', self.script)
        self.assertIn('quality_labels', self.script)
        self.assertIn('option.hidden = !isAvailable', self.script)

    def test_non_json_parse_errors_are_handled(self):
        self.assertIn("contentType.includes('application/json')", self.script)
        self.assertIn('parseApiResponse(', self.script)

    def test_old_360_only_claim_is_removed(self):
        combined = f'{self.html}\n{self.script}'.lower()
        self.assertNotIn('currently supports 360p only', combined)
        self.assertNotIn('目前仅支持 360p', combined)


if __name__ == '__main__':
    unittest.main(verbosity=2)
