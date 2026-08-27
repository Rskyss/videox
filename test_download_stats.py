"""网页版下载统计的记账测试：解析 / 下载成功 / 下载失败 三类分开记。"""

import os
import tempfile
import unittest

from simple_tracker import SimpleTracker


class SimpleTrackerTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.stats_file = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        os.remove(self.stats_file)
        self.tracker = SimpleTracker(stats_file=self.stats_file)

    def tearDown(self):
        if os.path.exists(self.stats_file):
            os.remove(self.stats_file)

    def _read(self):
        with open(self.stats_file, 'r', encoding='utf-8') as handle:
            return handle.read()

    def test_default_track_records_parse_line(self):
        """不带事件的 track() 仍然记在第一行（解析计数），保持旧行为。"""
        self.tracker.track('youtube')
        content = self._read()
        self.assertIn('YouTube：1', content.splitlines()[1])

    def test_success_event_records_download_success_line(self):
        self.tracker.track('youtube', 'success')
        content = self._read()
        self.assertIn('下载成功 YouTube：1', content)

    def test_fail_event_records_download_fail_line(self):
        self.tracker.track('bilibili', 'fail')
        content = self._read()
        self.assertIn('下载失败', content)
        self.assertIn('B站：1', content)

    def test_events_accumulate_independently(self):
        """同一天里解析、成功、失败互不串账。"""
        self.tracker.track('douyin')
        self.tracker.track('douyin')
        self.tracker.track('douyin', 'success')
        self.tracker.track('douyin', 'fail')
        content = self._read()
        lines = [line for line in content.splitlines() if '抖音' in line]
        parse_line = [l for l in lines if not l.startswith('下载')][0]
        success_line = [l for l in lines if l.startswith('下载成功')][0]
        fail_line = [l for l in lines if l.startswith('下载失败')][0]
        self.assertIn('抖音：2', parse_line)
        self.assertIn('抖音：1', success_line)
        self.assertIn('抖音：1', fail_line)

    def test_reads_legacy_single_line_format(self):
        """老文件里只有解析行的日期块，追加下载事件时不能丢老数据。"""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        with open(self.stats_file, 'w', encoding='utf-8') as handle:
            handle.write(
                f'{today}\n'
                'YouTube：5  抖音：3  小红书：0  B站：0  Twitter：0  TikTok：0\n\n'
                '2026-01-01\n'
                'YouTube：9  抖音：0  小红书：0  B站：0  Twitter：0  TikTok：0\n\n'
            )
        self.tracker.track('youtube', 'success')
        content = self._read()
        self.assertIn('YouTube：5', content)          # 今天的解析计数保留
        self.assertIn('下载成功 YouTube：1', content)  # 新事件写入
        self.assertIn('YouTube：9', content)          # 历史日期块原样保留

    def test_unknown_platform_is_ignored(self):
        self.tracker.track('unknown-platform', 'success')
        self.assertFalse(os.path.exists(self.stats_file))

    def test_first_line_stays_parse_only_for_admin_compat(self):
        """日期行后的第一行必须是解析计数（不带前缀），旧后台按第一行解析。"""
        self.tracker.track('youtube', 'success')
        self.tracker.track('youtube')
        lines = self._read().splitlines()
        self.assertNotIn('下载', lines[1])
        self.assertIn('YouTube：1', lines[1])


class DownloadJobStatsTestCase(unittest.TestCase):
    """下载任务结束后应按最终状态记一笔成功/失败。"""

    def setUp(self):
        import app as app_module
        self.app_module = app_module
        os.makedirs(app_module.DOWNLOAD_JOB_ROOT, exist_ok=True)
        with app_module.download_jobs_lock:
            app_module.download_jobs.clear()

    def tearDown(self):
        with self.app_module.download_jobs_lock:
            jobs = list(self.app_module.download_jobs.values())
            self.app_module.download_jobs.clear()
        for job in jobs:
            self.app_module._remove_download_job_files(job)

    def _make_job(self, job_id, status):
        import time as time_module
        job_dir = tempfile.mkdtemp(prefix='job-', dir=self.app_module.DOWNLOAD_JOB_ROOT)
        now = time_module.time()
        with self.app_module.download_jobs_lock:
            self.app_module.download_jobs[job_id] = {
                'status': status,
                'progress': 0,
                'message': '',
                'error': '',
                'url': 'https://www.youtube.com/watch?v=test',
                'platform': 'youtube',
                'quality': '720',
                'filename': 'test.mp4',
                'job_dir': job_dir,
                'created_at': now,
                'updated_at': now,
            }

    def test_ready_job_tracks_success(self):
        from unittest import mock
        job_id = 's' * 32
        self._make_job(job_id, 'queued')
        with mock.patch.object(self.app_module, '_run_download_job') as run, \
                mock.patch.object(self.app_module.tracker, 'track') as track:
            run.side_effect = lambda jid: self.app_module._set_download_job(jid, status='ready')
            self.app_module._run_download_job_with_stats(job_id)
        track.assert_called_once_with('youtube', 'success')

    def test_error_job_tracks_fail(self):
        from unittest import mock
        job_id = 'f' * 32
        self._make_job(job_id, 'queued')
        with mock.patch.object(self.app_module, '_run_download_job') as run, \
                mock.patch.object(self.app_module.tracker, 'track') as track:
            run.side_effect = lambda jid: self.app_module._set_download_job(jid, status='error')
            self.app_module._run_download_job_with_stats(job_id)
        track.assert_called_once_with('youtube', 'fail')


class ProxyDownloadStatsTestCase(unittest.TestCase):
    """代理直传与前端上报通道的记账测试。"""

    def setUp(self):
        import app as app_module
        self.app_module = app_module
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()

    def test_platform_from_media_url(self):
        cases = {
            'https://v3.douyinvod.com/abc/video.mp4': 'douyin',
            'https://upos-sz.bilivideo.com/xyz.m4s': 'bilibili',
            'https://sns-video.xhscdn.com/clip.mp4': 'xiaohongshu',
            'https://video.twimg.com/ext_tw_video/1.mp4': 'twitter',
            'https://example.com/video.mp4': '',
        }
        for url, expected in cases.items():
            self.assertEqual(self.app_module._platform_from_media_url(url), expected, url)

    def test_track_download_endpoint_accepts_whitelisted_payload(self):
        from unittest import mock
        with mock.patch.object(self.app_module.tracker, 'track') as track:
            resp = self.client.post('/track-download', json={'platform': 'xiaohongshu', 'event': 'success'})
        self.assertEqual(resp.status_code, 204)
        track.assert_called_once_with('xiaohongshu', 'success')

    def test_track_download_endpoint_rejects_bad_payload(self):
        from unittest import mock
        with mock.patch.object(self.app_module.tracker, 'track') as track:
            for payload in (
                {'platform': 'evil', 'event': 'success'},
                {'platform': 'youtube', 'event': 'parse'},
                {'platform': 'youtube'},
                {},
            ):
                resp = self.client.post('/track-download', json=payload)
                self.assertEqual(resp.status_code, 400, payload)
        track.assert_not_called()

    def test_proxy_stream_completion_tracks_success(self):
        from unittest import mock

        fake_resp = mock.Mock()
        fake_resp.headers = {'Content-Length': '4'}
        fake_resp.iter_content.return_value = iter([b'ab', b'cd'])
        fake_resp.raise_for_status.return_value = None

        with mock.patch.object(self.app_module.requests, 'get', return_value=fake_resp), \
                mock.patch.object(self.app_module.tracker, 'track') as track:
            with self.app_module.app.test_request_context():
                response = self.app_module.proxy_direct_download(
                    'https://video.twimg.com/ext_tw_video/1.mp4', 'test.mp4')
                body = b''.join(response.response)
        self.assertEqual(body, b'abcd')
        track.assert_called_once_with('twitter', 'success')

    def test_proxy_stream_interruption_tracks_fail(self):
        from unittest import mock

        def broken_iter(chunk_size):
            yield b'ab'
            raise IOError('upstream reset')

        fake_resp = mock.Mock()
        fake_resp.headers = {}
        fake_resp.iter_content.side_effect = broken_iter
        fake_resp.raise_for_status.return_value = None

        with mock.patch.object(self.app_module.requests, 'get', return_value=fake_resp), \
                mock.patch.object(self.app_module.tracker, 'track') as track:
            with self.app_module.app.test_request_context():
                response = self.app_module.proxy_direct_download(
                    'https://video.twimg.com/ext_tw_video/1.mp4', 'test.mp4')
                b''.join(response.response)
        track.assert_called_once_with('twitter', 'fail')

    def test_proxy_client_cancel_tracks_nothing(self):
        """用户自己取消下载（流被提前关闭）不算成功也不算失败。"""
        from unittest import mock

        fake_resp = mock.Mock()
        fake_resp.headers = {}
        fake_resp.iter_content.return_value = iter([b'ab', b'cd', b'ef'])
        fake_resp.raise_for_status.return_value = None

        with mock.patch.object(self.app_module.requests, 'get', return_value=fake_resp), \
                mock.patch.object(self.app_module.tracker, 'track') as track:
            with self.app_module.app.test_request_context():
                response = self.app_module.proxy_direct_download(
                    'https://video.twimg.com/ext_tw_video/1.mp4', 'test.mp4')
                iterator = iter(response.response)
                next(iterator)
                iterator.close()  # 模拟浏览器中断
        track.assert_not_called()

    def test_proxy_connect_failure_tracks_fail(self):
        from unittest import mock
        import requests as requests_module

        with mock.patch.object(
                self.app_module.requests, 'get',
                side_effect=requests_module.ConnectionError('no route')), \
                mock.patch.object(self.app_module.tracker, 'track') as track:
            with self.app_module.app.test_request_context():
                result = self.app_module.proxy_direct_download(
                    'https://video.twimg.com/ext_tw_video/1.mp4', 'test.mp4')
        self.assertEqual(result[1], 500)
        track.assert_called_once_with('twitter', 'fail')


if __name__ == '__main__':
    unittest.main()
