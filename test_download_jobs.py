"""后台高清下载任务的本地接口与状态机测试。"""

import json
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


class _SSLDropThenSucceedPopen:
    """模拟 B站等平台常见的连接中途 SSL 断开：前两次尝试失败，第三次成功。"""

    attempts = 0

    def __init__(self, cmd, **kwargs):
        type(self).attempts += 1
        self.cmd = cmd
        if type(self).attempts < 3:
            self.stdout = _FakeStdout([
                '[download]  47.3% of 60.69MiB\n',
                'ERROR: [download] Got error: [SSL: UNEXPECTED_EOF_WHILE_READING] '
                'EOF occurred in violation of protocol (_ssl.c:1010). Giving up after 3 retries\n',
            ])
        else:
            output_template = cmd[cmd.index('-o') + 1]
            output_file = output_template.replace('%(ext)s', 'mp4')
            with open(output_file, 'wb') as handle:
                handle.write(b'recovered-video')
            self.stdout = _FakeStdout([
                '[download] 100.0% of 60.69MiB\n',
                '[Merger] Merging formats into video.mp4\n',
            ])

    def wait(self, timeout=None):
        return 0 if type(self).attempts >= 3 else 1


class _DirectResponse:
    headers = {'Content-Length': '10'}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=None):
        return iter((b'12345', b'67890'))


class _RangeResponse:
    def __init__(self, content_range, chunks, status_code=206):
        self.headers = {'Content-Range': content_range}
        self.status_code = status_code
        self._chunks = chunks
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=None):
        return iter(self._chunks)

    def close(self):
        self.closed = True


class _RangeSession:
    def __init__(self, response):
        self.response = response
        self.trust_env = True
        self.requests = []
        self.closed = False

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response

    def close(self):
        self.closed = True


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

    def test_download_commands_use_resilient_retry_settings(self):
        """B站等平台常见的连接中途 SSL 断开，需要更多重试次数和退避等待。"""
        youtube_cmd = app_module._youtube_download_command(
            'https://www.youtube.com/watch?v=test', '/tmp/test-video', '720',
        )
        bilibili_cmd = app_module._platform_download_command(
            {
                'url': 'https://www.bilibili.com/video/BV1c7GA6kEqN/',
                'platform': 'bilibili',
                'quality': '1080',
            },
            '/tmp/test-bili',
        )
        for cmd in (youtube_cmd, bilibili_cmd):
            self.assertEqual(cmd[cmd.index('--retries') + 1], '10')
            self.assertEqual(cmd[cmd.index('--fragment-retries') + 1], '15')
            self.assertIn('--retry-sleep', cmd)
        # B站音频流对多连接更敏感，并发分片降到 1；YouTube 仍保持 4
        self.assertEqual(bilibili_cmd[bilibili_cmd.index('--concurrent-fragments') + 1], '1')
        self.assertEqual(youtube_cmd[youtube_cmd.index('--concurrent-fragments') + 1], '4')
        self.assertIn('--force-ipv4', bilibili_cmd)
        self.assertNotIn('--force-ipv4', youtube_cmd)

    def test_download_failure_summary_prefers_error_over_progress(self):
        summary = app_module._download_failure_summary([
            '[download]  14.5% of 13.82MiB at 7.84MiB/s ETA 00:01',
            '[download]  28.9% of 13.82MiB at 8.01MiB/s ETA 00:01',
            'ERROR: [download] Got error: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF. Giving up after 3 retries',
        ])
        self.assertIn('SSL', summary)
        self.assertNotIn('14.5%', summary)

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    @mock.patch.object(app_module.subprocess, 'Popen', _SSLDropThenSucceedPopen)
    def test_bilibili_job_retries_after_ssl_drop_and_succeeds(self, _get_proxies):
        """B站下载中途 SSL 断开时，任务应自动整体重试，而不是直接判失败。"""
        _SSLDropThenSucceedPopen.attempts = 0
        job_id = 'b' * 32
        job_dir = tempfile.mkdtemp(prefix='job-', dir=app_module.DOWNLOAD_JOB_ROOT)
        now = time.time()
        with app_module.download_jobs_lock:
            app_module.download_jobs[job_id] = {
                'status': 'queued',
                'progress': 0,
                'message': '',
                'error': '',
                'url': 'https://www.bilibili.com/video/BV1c7GA6kEqN/',
                'platform': 'bilibili',
                'quality': '1080',
                'filename': 'test.mp4',
                'job_dir': job_dir,
                'created_at': now,
                'updated_at': now,
            }

        app_module._run_download_job(job_id)

        snapshot = app_module._download_job_snapshot(job_id)
        self.assertEqual(snapshot['status'], 'ready')
        self.assertEqual(_SSLDropThenSucceedPopen.attempts, 3)

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    def test_bilibili_ssl_drop_error_message_is_friendly(self, _get_proxies):
        """重试仍失败时,不应把整段技术日志原样丢给用户。"""

        class _AlwaysSSLDropPopen(_SSLDropThenSucceedPopen):
            def __init__(self, cmd, **kwargs):
                type(self).attempts += 1
                self.cmd = cmd
                self.stdout = _FakeStdout([
                    '[download]  47.3% of 60.69MiB\n',
                    'ERROR: [download] Got error: [SSL: UNEXPECTED_EOF_WHILE_READING] '
                    'EOF occurred in violation of protocol (_ssl.c:1010). Giving up after 3 retries\n',
                ])

            def wait(self, timeout=None):
                return 1

        _AlwaysSSLDropPopen.attempts = 0
        job_id = 'c' * 32
        job_dir = tempfile.mkdtemp(prefix='job-', dir=app_module.DOWNLOAD_JOB_ROOT)
        now = time.time()
        with app_module.download_jobs_lock:
            app_module.download_jobs[job_id] = {
                'status': 'queued',
                'progress': 0,
                'message': '',
                'error': '',
                'url': 'https://www.bilibili.com/video/BV1c7GA6kEqN/',
                'platform': 'bilibili',
                'quality': '1080',
                'filename': 'test.mp4',
                'job_dir': job_dir,
                'created_at': now,
                'updated_at': now,
            }

        with mock.patch.object(app_module.subprocess, 'Popen', _AlwaysSSLDropPopen):
            app_module._run_download_job(job_id)

        snapshot = app_module._download_job_snapshot(job_id)
        self.assertEqual(snapshot['status'], 'error')
        self.assertEqual(_AlwaysSSLDropPopen.attempts, 3)
        self.assertNotIn('_ssl.c:1010', snapshot['error'])
        self.assertIn('网络连接不稳定', snapshot['error'])

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    def test_bilibili_progress_message_switches_to_audio_and_retry(self, _get_proxies):
        """两段下载时，进度文案应区分画面/音频，并在 SSL 重试时提示网络不稳。"""

        class _TwoStreamWithRetryPopen:
            def __init__(self, cmd, **kwargs):
                output_template = cmd[cmd.index('-o') + 1]
                output_file = output_template.replace('%(ext)s', 'mp4')
                with open(output_file, 'wb') as handle:
                    handle.write(b'merged-video')
                self.stdout = _FakeStdout([
                    '[info] Downloading 2 format(s): 100023+30280\n',
                    '[download] 100.0% of 30.00MiB\n',
                    '[download] Got error: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF. Retrying (1/10)...\n',
                    '[download]  50.0% of 10.00MiB\n',
                    '[download] 100.0% of 10.00MiB\n',
                    '[Merger] Merging formats into video.mp4\n',
                ])
                self.env = kwargs.get('env') or {}

            def wait(self, timeout=None):
                return 0

        job_id = 'd' * 32
        job_dir = tempfile.mkdtemp(prefix='job-', dir=app_module.DOWNLOAD_JOB_ROOT)
        now = time.time()
        messages = []

        original_set = app_module._set_download_job

        def tracking_set(job_id_arg, **updates):
            if 'message' in updates:
                messages.append(updates['message'])
            return original_set(job_id_arg, **updates)

        with app_module.download_jobs_lock:
            app_module.download_jobs[job_id] = {
                'status': 'queued',
                'progress': 0,
                'message': '',
                'error': '',
                'url': 'https://www.bilibili.com/video/BV1c7GA6kEqN/',
                'platform': 'bilibili',
                'quality': '720',
                'filename': 'test.mp4',
                'job_dir': job_dir,
                'created_at': now,
                'updated_at': now,
            }

        with mock.patch.object(app_module.subprocess, 'Popen', _TwoStreamWithRetryPopen), \
                mock.patch.object(app_module, '_set_download_job', side_effect=tracking_set):
            app_module._run_download_job(job_id)

        snapshot = app_module._download_job_snapshot(job_id)
        self.assertEqual(snapshot['status'], 'ready')
        self.assertTrue(any('正在下载视频画面' in m for m in messages))
        self.assertTrue(any('网络不稳，正在重试音频下载' in m for m in messages))
        self.assertTrue(any('正在下载音频' in m for m in messages))

    def test_bilibili_quality_selectors_cap_resolution(self):
        for quality in ('360', '720', '1080'):
            command = app_module._platform_download_command(
                {
                    'url': 'https://www.bilibili.com/video/BV1c7GA6kEqN/',
                    'platform': 'bilibili',
                    'quality': quality,
                },
                '/tmp/test-bili',
            )
            selector = command[command.index('-f') + 1]
            self.assertIn(f'height<={quality}', selector)
            self.assertEqual(selector, app_module.BILIBILI_QUALITY_SELECTORS[quality])

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

    def test_bilibili_quality_options_hide_missing_tiers(self):
        """没有真正 720/1080 时不应继续展示会误导的更高档。"""
        only_low = [
            {'height': 360, 'vcodec': 'avc1', 'acodec': 'none'},
            {'height': 480, 'vcodec': 'av1', 'acodec': 'none'},
        ]
        options = app_module.downloader._bilibili_quality_options(only_low)
        self.assertEqual(options['available_qualities'], ['360', '720'])
        self.assertEqual(options['default_quality'], '720')
        self.assertEqual(options['quality_labels']['720'], '480p · 最高')
        self.assertNotIn('1080', options['available_qualities'])

        full = [
            {'height': 360, 'vcodec': 'avc1', 'acodec': 'none'},
            {'height': 720, 'vcodec': 'avc1', 'acodec': 'none'},
            {'height': 1080, 'vcodec': 'avc1', 'acodec': 'none'},
        ]
        full_options = app_module.downloader._bilibili_quality_options(full)
        self.assertEqual(full_options['available_qualities'], ['360', '720', '1080'])
        self.assertEqual(full_options['quality_labels'], {})

    def test_bilibili_quality_size_estimator_matches_selector_choice(self):
        """估算逻辑要和实际下载选择器 bv*[height<=X]+ba 选中的流一致（数据取自真实解析样本）。"""
        formats = [
            {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize_approx': 12213108},
            {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize_approx': 32964013},
            {'height': 360, 'vcodec': 'hvc1', 'acodec': 'none', 'filesize_approx': 50391998},
            {'height': 360, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 100633183},
            {'height': 480, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 147089339},
            {'height': 720, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 292071379},
            {'height': 1080, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 664787474},
            {'height': 2160, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 3198775691},
        ]
        sizes = app_module.downloader._estimate_bilibili_quality_sizes(formats)

        self.assertEqual(sizes['360'], 100633183 + 32964013)
        self.assertEqual(sizes['720'], 292071379 + 32964013)
        self.assertEqual(sizes['1080'], 664787474 + 32964013)
        # 三档递增，不应该出现"切清晰度但体积不变"的情况
        self.assertLess(sizes['360'], sizes['720'])
        self.assertLess(sizes['720'], sizes['1080'])

    def test_bilibili_quality_size_estimator_falls_back_when_resolution_missing(self):
        """某档没有对应分辨率时，回退到全部视频流里体积最大的那个（对齐选择器 /bv*+ba 回退）。"""
        formats = [
            {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize_approx': 5_000_000},
            {'height': 1080, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 500_000_000},
        ]
        sizes = app_module.downloader._estimate_bilibili_quality_sizes(formats)

        for quality in ('360', '720', '1080'):
            self.assertEqual(sizes[quality], 500_000_000 + 5_000_000)

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    @mock.patch('downloader.subprocess.run')
    def test_bilibili_parse_returns_per_quality_sizes(self, run, _get_proxies):
        formats = [
            {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize_approx': 12213108},
            {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize_approx': 32964013},
            {'height': 360, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 100633183},
            {'height': 720, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 292071379},
            {'height': 1080, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 664787474},
        ]
        run.return_value = mock.Mock(
            returncode=0,
            stdout=json.dumps({
                'id': 'BV1c7GA6kEqN',
                'title': '我们拍到了水下风暴',
                'duration': 1487,
                'extractor_key': 'BiliBili',
                'ext': 'mp4',
                'formats': formats,
                'requested_formats': [formats[3], formats[1]],
                'url': '',
            }),
            stderr='',
        )

        result = app_module.downloader._parse_video_with_ytdlp(
            'https://www.bilibili.com/video/BV1c7GA6kEqN/',
            'https://www.bilibili.com/video/BV1c7GA6kEqN/',
        )

        self.assertTrue(result['success'])
        info = result['video_info']
        self.assertIn('quality_sizes', info)
        self.assertEqual(set(info['quality_sizes'].keys()), {'360', '720', '1080'})
        self.assertEqual(info['available_qualities'], ['360', '720', '1080'])
        self.assertEqual(info['default_quality'], '1080')
        # 三档体积应不同，且默认展示的 size 与默认清晰度档一致
        self.assertEqual(len(set(info['quality_sizes'].values())), 3)
        self.assertEqual(info['size'], info['quality_sizes']['1080'])
        self.assertNotEqual(info['quality_sizes_readable']['360'], info['quality_sizes_readable']['1080'])

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    @mock.patch('downloader.subprocess.run')
    def test_bilibili_parse_hides_unavailable_qualities(self, run, _get_proxies):
        formats = [
            {'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize_approx': 10_000_000},
            {'height': 360, 'vcodec': 'avc1', 'acodec': 'none', 'filesize_approx': 20_000_000},
            {'height': 480, 'vcodec': 'av1', 'acodec': 'none', 'filesize_approx': 40_000_000},
        ]
        run.return_value = mock.Mock(
            returncode=0,
            stdout=json.dumps({
                'id': 'BV1V4Te6MEAu',
                'title': 'AI巨头',
                'duration': 1167,
                'extractor_key': 'BiliBili',
                'ext': 'mp4',
                'formats': formats,
                'requested_formats': [formats[2], formats[0]],
                'url': '',
            }),
            stderr='',
        )

        result = app_module.downloader._parse_video_with_ytdlp(
            'https://www.bilibili.com/video/BV1V4Te6MEAu/',
            'https://www.bilibili.com/video/BV1V4Te6MEAu/',
        )

        info = result['video_info']
        self.assertEqual(info['available_qualities'], ['360', '720'])
        self.assertEqual(info['quality_labels']['720'], '480p · 最高')
        self.assertNotIn('1080', info['quality_sizes'])
        self.assertEqual(info['default_quality'], '720')
        self.assertEqual(info['size'], info['quality_sizes']['720'])

    @mock.patch.object(app_module.downloader.proxy_manager, 'get_proxies', return_value=[])
    @mock.patch('downloader.subprocess.run')
    def test_youtube_parse_has_no_quality_sizes(self, run, _get_proxies):
        """YouTube 走轻量解析，HLS 分片流本身不带总体积，不应假装有三档数据。"""
        run.return_value = mock.Mock(
            returncode=0,
            stdout='{"id":"abc","title":"Test","duration":10,"thumbnail":"thumb","ext":"mp4"}\n',
            stderr='',
        )

        result = app_module.downloader._parse_youtube_lightweight(
            'https://www.youtube.com/watch?v=abc',
            'https://www.youtube.com/watch?v=abc',
        )

        self.assertTrue(result['success'])
        self.assertNotIn('quality_sizes', result['video_info'])
        self.assertEqual(result['video_info']['size_readable'], 'Unknown')

    def test_parse_error_gives_friendly_message_for_ssl_drop(self):
        parsed = app_module.downloader._parse_error(
            "ERROR: [download] Got error: [SSL: UNEXPECTED_EOF_WHILE_READING] "
            "EOF occurred in violation of protocol (_ssl.c:1010). Giving up after 3 retries"
        )
        self.assertIn('网络连接不稳定', parsed)
        self.assertNotIn('_ssl.c:1010', parsed)

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
                self.assertEqual(
                    job['quality'],
                    '720' if platform in ('youtube', 'bilibili') else 'best',
                )

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

    def test_content_range_total_uses_complete_file_size(self):
        response = _RangeResponse('bytes 524288-1048575/3158344', [])
        self.assertEqual(app_module._content_range_total(response), 3158344)

    def test_douyin_slow_stream_resumes_without_duplicate_bytes(self):
        first_response = _RangeResponse('bytes 0-9/10', [b'12345'])
        second_response = _RangeResponse('bytes 5-9/10', [b'67890'])
        first_session = _RangeSession(first_response)
        second_session = _RangeSession(second_response)

        with mock.patch.object(
            app_module.requests,
            'Session',
            side_effect=[first_session, second_session],
        ), mock.patch.object(
            app_module.time,
            'monotonic',
            side_effect=[0, 9, 10],
        ):
            with app_module.app.test_request_context('/'):
                response = app_module.proxy_direct_download(
                    'https://aweme.snssdk.com/aweme/v1/play/?video_id=test',
                    'test.mp4',
                )
                body = b''.join(response.response)
                response.close()

        self.assertEqual(body, b'1234567890')
        self.assertEqual(response.headers['Content-Length'], '10')
        self.assertEqual(first_session.requests[0][1]['headers']['Range'], 'bytes=0-')
        self.assertEqual(second_session.requests[0][1]['headers']['Range'], 'bytes=5-')
        self.assertTrue(first_session.trust_env)
        self.assertFalse(second_session.trust_env)
        self.assertTrue(first_response.closed)
        self.assertTrue(second_response.closed)
        self.assertTrue(first_session.closed)
        self.assertTrue(second_session.closed)

if __name__ == '__main__':
    unittest.main(verbosity=2)
