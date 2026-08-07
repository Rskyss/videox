"""后台高清下载任务的本地接口与状态机测试。"""

import os
import tempfile
import time
import unittest
from unittest import mock

import app as app_module


class _FakeStdout:
    def __init__(self, lines):
        self._lines = iter(lines)

    def readline(self):
        return next(self._lines, '')


class _SuccessfulPopen:
    def __init__(self, cmd, **kwargs):
        output_template = cmd[cmd.index('-o') + 1]
        output_file = output_template.replace('%(ext)s', 'mp4')
        with open(output_file, 'wb') as handle:
            handle.write(b'test-video')
        self.stdout = _FakeStdout([
            '[download]  12.5% of 10.00MiB\n',
            '[download] 100.0% of 10.00MiB\n',
            '[Merger] Merging formats into video.mp4\n',
        ])

    def wait(self, timeout=None):
        return 0


class _DirectResponse:
    headers = {'Content-Length': '10'}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=None):
        return iter((b'12345', b'67890'))


class DownloadJobTestCase(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()
        os.makedirs(app_module.DOWNLOAD_JOB_ROOT, exist_ok=True)
        with app_module.download_jobs_lock:
            app_module.download_jobs.clear()

    def tearDown(self):
        with app_module.download_jobs_lock:
            jobs = list(app_module.download_jobs.values())
            app_module.download_jobs.clear()
        for job in jobs:
            app_module._remove_download_job_files(job)

    def test_quality_selectors_cap_resolution(self):
        for quality in ('360', '720', '1080'):
            command = app_module._youtube_download_command(
                'https://www.youtube.com/watch?v=test',
                '/tmp/test-video',
                quality,
            )
            selector = command[command.index('-f') + 1]
            self.assertIn(f'height<={quality}', selector)
            self.assertIn('--merge-output-format', command)

        fallback_command = app_module._youtube_download_command(
            'https://www.youtube.com/watch?v=test',
            '/tmp/test-video',
            '1080',
            client='android_vr',
        )
        self.assertIn(
            'youtube:player_client=android_vr',
            fallback_command[fallback_command.index('--extractor-args') + 1],
        )

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    @mock.patch('downloader.subprocess.run')
    def test_metadata_parse_survives_missing_download_formats(self, run, _get_proxies):
        run.return_value = mock.Mock(
            returncode=1,
            stdout='{"id":"abc","title":"Test","duration":10,"thumbnail":"thumb"}\n',
            stderr='ERROR: Requested format is not available',
        )

        result = app_module.downloader._parse_youtube_lightweight(
            'https://www.youtube.com/watch?v=abc',
            'https://www.youtube.com/watch?v=abc',
        )

        self.assertTrue(result['success'])
        self.assertIn('--ignore-no-formats-error', run.call_args.args[0])

    def test_impersonate_dependency_error_does_not_expose_traceback(self):
        parsed = app_module.downloader._parse_error(
            'Traceback (most recent call last):\n'
            'YoutubeDLError: Impersonate target "chrome" is not available'
        )
        self.assertIn('浏览器模拟组件', parsed)
        self.assertNotIn('Traceback', parsed)

    def test_job_rejects_unsupported_quality(self):
        response = self.client.post('/download-jobs', json={
            'url': 'https://www.youtube.com/watch?v=test',
            'quality': '2160',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('不支持', response.get_json()['message'])

    def test_job_rejects_unsupported_platform(self):
        response = self.client.post('/download-jobs', json={
            'url': 'https://example.com/video',
            'quality': '720',
        })
        self.assertEqual(response.status_code, 400)

    @mock.patch.object(app_module.threading, 'Thread')
    def test_all_advertised_platforms_create_jobs(self, _thread):
        cases = {
            'douyin': 'https://www.douyin.com/video/123',
            'bilibili': 'https://www.bilibili.com/video/BV123',
            'xiaohongshu': 'https://www.xiaohongshu.com/explore/123',
            'youtube': 'https://www.youtube.com/watch?v=123',
            'tiktok': 'https://www.tiktok.com/@test/video/123',
            'twitter': 'https://x.com/test/status/123',
        }
        for platform, url in cases.items():
            with self.subTest(platform=platform):
                response = self.client.post('/download-jobs', json={
                    'url': url,
                    'platform': platform,
                    'quality': '720',
                })
                self.assertEqual(response.status_code, 202)
                job_id = response.get_json()['job_id']
                with app_module.download_jobs_lock:
                    job = app_module.download_jobs[job_id]
                self.assertEqual(job['platform'], platform)
                self.assertEqual(job['quality'], '720' if platform == 'youtube' else 'best')

    def test_job_queue_is_bounded(self):
        now = time.time()
        with app_module.download_jobs_lock:
            for index in range(app_module.DOWNLOAD_JOB_MAX_PENDING):
                app_module.download_jobs[str(index)] = {
                    'status': 'queued',
                    'job_dir': os.path.join(app_module.DOWNLOAD_JOB_ROOT, str(index)),
                    'updated_at': now,
                }
        response = self.client.post('/download-jobs', json={
            'url': 'https://www.youtube.com/watch?v=test',
            'quality': '720',
        })
        self.assertEqual(response.status_code, 429)

    @mock.patch.object(app_module.threading, 'Thread')
    def test_create_job_returns_immediately(self, thread_class):
        response = self.client.post('/download-jobs', json={
            'url': 'https://www.youtube.com/watch?v=test',
            'filename': '../unsafe:name.mp4',
            'quality': '1080',
        })
        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertTrue(body['success'])
        self.assertRegex(body['job_id'], r'^[a-f0-9]{32}$')
        self.assertEqual(response.headers['Location'], body['status_url'])
        thread_class.return_value.start.assert_called_once()

        with app_module.download_jobs_lock:
            job = app_module.download_jobs[body['job_id']]
        self.assertEqual(job['quality'], '1080')
        self.assertEqual(job['filename'], 'unsafe_name.mp4')

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    @mock.patch.object(app_module.subprocess, 'Popen', _SuccessfulPopen)
    def test_worker_reaches_ready_with_progress(self, _get_proxies):
        job_id = 'a' * 32
        job_dir = tempfile.mkdtemp(prefix='job-', dir=app_module.DOWNLOAD_JOB_ROOT)
        now = time.time()
        with app_module.download_jobs_lock:
            app_module.download_jobs[job_id] = {
                'status': 'queued',
                'progress': 0,
                'message': '',
                'error': '',
                'url': 'https://www.youtube.com/watch?v=test',
                'quality': '720',
                'filename': 'test.mp4',
                'job_dir': job_dir,
                'created_at': now,
                'updated_at': now,
            }

        app_module._run_youtube_download_job(job_id)
        snapshot = app_module._download_job_snapshot(job_id)
        self.assertEqual(snapshot['status'], 'ready')
        self.assertEqual(snapshot['progress'], 100)

        response = self.client.get(f'/download-jobs/{job_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['download_url'], f'/download-jobs/{job_id}/file')

        file_response = self.client.get(f'/download-jobs/{job_id}/file')
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response.get_data(), b'test-video')
        file_response.close()
        self.assertFalse(os.path.exists(job_dir))
        self.assertIsNone(app_module._download_job_snapshot(job_id))

    @mock.patch.object(app_module.requests, 'get', return_value=_DirectResponse())
    def test_direct_media_job_reports_progress_and_reaches_ready(self, _get):
        job_id = 'b' * 32
        job_dir = tempfile.mkdtemp(prefix='job-', dir=app_module.DOWNLOAD_JOB_ROOT)
        now = time.time()
        with app_module.download_jobs_lock:
            app_module.download_jobs[job_id] = {
                'status': 'queued',
                'progress': 0,
                'message': '',
                'error': '',
                'url': 'https://www.xiaohongshu.com/explore/123',
                'media_url': 'https://sns-video-hw.xhscdn.com/test.mp4',
                'platform': 'xiaohongshu',
                'is_dash': False,
                'expected_size': 10,
                'quality': 'best',
                'filename': 'test.mp4',
                'job_dir': job_dir,
                'created_at': now,
                'updated_at': now,
            }

        app_module._run_download_job(job_id)

        snapshot = app_module._download_job_snapshot(job_id)
        self.assertEqual(snapshot['status'], 'ready')
        self.assertEqual(snapshot['progress'], 100)
        with app_module.download_jobs_lock:
            output_file = app_module.download_jobs[job_id]['file_path']
        with open(output_file, 'rb') as handle:
            self.assertEqual(handle.read(), b'1234567890')


if __name__ == '__main__':
    unittest.main(verbosity=2)
