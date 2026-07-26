// 翻译字典
const translations = {
    zh: {
        'page-title': '视频解析神器 - 免费无水印视频解析下载工具',
        'title': '视频解析神器',
        'subtitle': '粘贴视频链接即可轻松解析和下载',
        'input-placeholder': '在此粘贴视频链接...',
        'parse-btn': '解析',
        'duration': '时长',
        'size': '大小',
        'download-btn': '下载视频',
        'platforms-support': '支持以下平台的视频解析，类型不断增加中',
        'footer-info': '基于 yt-dlp 构建 | 仅供学习使用',
        'footer-disclaimer': '本网站不存储或缓存任何视频内容。所有视频和图片均属于其各自所有者和源网站。',
        'parsing': '解析中...',
        'env-check-passed': '✅ 环境检查通过，可以开始使用',
        'env-check-installing': '检测到 yt-dlp 未安装，正在自动安装...',
        'env-check-failed': '❌ 环境检查失败',
        'install-success': '✅ yt-dlp 安装成功',
        'install-failed': '❌ yt-dlp 安装失败',
        'install-request-failed': '❌ 安装请求失败',
        'enter-link': '请输入视频链接',
        'parse-failed': '解析失败',
        'unknown-error': '发生未知错误',
        'no-video-info': '没有可下载的视频信息',
        'download-started': '✅ 下载已开始',
        'download-merging': '🎬 下载已开始（服务器正在合并视频和音频流）',
        'download-processing': '服务器处理中',
        'download-processing-hint': '正在下载并合并音视频流，请耐心等待...',
        'download-btn-retry': '重新下载',
        'faq-heading': '常见问题',
        'faq-q1': '视频解析神器是免费的吗？',
        'faq-a1': '完全免费。无需注册、无需安装软件，也不收取任何费用。',
        'faq-q2': '下载的视频有水印吗？',
        'faq-a2': '没有。抖音、TikTok、B站、小红书解析后的视频均为无水印，并保留原始清晰度。',
        'faq-q3': '支持哪些平台？',
        'faq-a3': '抖音、B站、小红书、YouTube、TikTok、Twitter/X。其中 YouTube 因官方将高清视频与音频分离，目前仅支持 360p。',
        'faq-q4': '为什么链接解析失败？',
        'faq-a4': '可能是链接不正确，或视频已被删除、设为私密、仍在审核中。请重新复制分享链接后再试一次。',
        'faq-q5': '会保存我下载的视频吗？',
        'faq-a5': '不会。我们不存储也不缓存任何视频内容，文件直接传输到你的设备，所有权利仍归原作者所有。'
    },
    en: {
        'page-title': 'Free Video Downloader – TikTok, Douyin, Bilibili | VideoX',
        'title': 'Video Parsing Prodigy',
        'subtitle': 'Paste video link to easily parse and download',
        'input-placeholder': 'Paste video link here...',
        'parse-btn': 'Parse',
        'duration': 'Duration',
        'size': 'Size',
        'download-btn': 'Download Video',
        'platforms-support': 'Support video analysis for the following platforms, The types are constantly increasing.',
        'footer-info': 'Built with yt-dlp | For educational use only',
        'footer-disclaimer': 'We do not store or cache any video content on this website. All videos and images belong to their respective owners and source websites.',
        'parsing': 'Parsing...',
        'env-check-passed': '✅ Environment check passed, ready to use',
        'env-check-installing': 'Detected yt-dlp not installed, installing automatically...',
        'env-check-failed': '❌ Environment check failed',
        'install-success': '✅ yt-dlp installed successfully',
        'install-failed': '❌ yt-dlp installation failed',
        'install-request-failed': '❌ Installation request failed',
        'enter-link': 'Please enter video link',
        'parse-failed': 'Parse failed',
        'unknown-error': 'Unknown error occurred',
        'no-video-info': 'No video information available for download',
        'download-started': '✅ Download started',
        'download-merging': '🎬 Download started (Server is merging video and audio streams)',
        'download-processing': 'Server processing',
        'download-processing-hint': 'Downloading and merging audio/video streams, please wait...',
        'download-btn-retry': 'Re-download',
        'faq-heading': 'Frequently Asked Questions',
        'faq-q1': 'Is VideoX free to use?',
        'faq-a1': 'Yes. VideoX is completely free. No registration, no software installation and no payment is required.',
        'faq-q2': 'Do downloaded videos have a watermark?',
        'faq-a2': 'No. Videos parsed from Douyin, TikTok, Bilibili and Xiaohongshu are saved without watermarks and keep their original resolution.',
        'faq-q3': 'Which platforms are supported?',
        'faq-a3': 'Douyin, Bilibili, Xiaohongshu, YouTube, TikTok and Twitter/X. YouTube currently supports 360p only, because it serves high-definition video and audio as separate streams.',
        'faq-q4': 'Why did my link fail to parse?',
        'faq-a4': 'The link may be incorrect, or the video has been deleted, set to private or is still under review. Copy the share link again and retry.',
        'faq-q5': 'Do you store the videos I download?',
        'faq-a5': 'No. We do not store or cache any video content. Files are streamed directly to your device and all rights remain with the original owners.'
    }
};

// 应用状态
const appState = {
    isLoading: false,
    isDownloading: false,
    downloadTimer: null,
    downloadSeconds: 0,
    videoInfo: null,
    error: null,
    currentLang: 'en'
};

// DOM元素
const elements = {
    videoUrl: document.getElementById('video-url'),
    parseBtn: document.getElementById('parse-btn'),
    clearBtn: document.getElementById('clear-btn'),
    btnText: document.querySelector('.btn-text'),
    spinner: document.querySelector('.spinner'),
    errorMessage: document.getElementById('error-message'),
    videoResult: document.getElementById('video-result'),
    videoThumbnail: document.getElementById('video-thumbnail'),
    videoPlatform: document.getElementById('video-platform'),
    videoTitle: document.getElementById('video-title'),
    videoDuration: document.getElementById('video-duration'),
    videoSize: document.getElementById('video-size'),
    downloadBtn: document.getElementById('download-btn'),
    envStatus: document.getElementById('env-status'),
    urlForm: document.getElementById('url-form')
};

// 翻译函数
function translate(lang) {
    appState.currentLang = lang;

    // 同步浏览器标签标题和页面语言标记,保证搜索引擎读到的语言与实际显示一致
    if (translations[lang] && translations[lang]['page-title']) {
        document.title = translations[lang]['page-title'];
    }
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';

    // 翻译所有带data-i18n属性的元素
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            element.textContent = translations[lang][key];
        }
    });

    // 翻译placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        if (translations[lang] && translations[lang][key]) {
            element.placeholder = translations[lang][key];
        }
    });

    // 更新按钮激活状态
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-lang="${lang}"]`).classList.add('active');

    // 保存语言设置到localStorage
    localStorage.setItem('preferred-lang', lang);
}

// 检测是否为移动设备
function isMobileDevice() {
    // 检测 userAgent
    const userAgent = navigator.userAgent || navigator.vendor || window.opera;
    const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i;

    // 检测触摸屏和屏幕宽度
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const isSmallScreen = window.innerWidth <= 768;

    return mobileRegex.test(userAgent) || (isTouchDevice && isSmallScreen);
}

// 显示移动端限制提示
function showMobileRestriction() {
    const lang = localStorage.getItem('preferred-lang') || 'en';
    const message = lang === 'zh'
        ? '目前不支持移动端H5访问，请访问PC/Mac页面'
        : 'Mobile H5 access is not currently supported. Please visit PC/Mac page';

    // 创建遮罩层
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.95);
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
    `;

    // 创建提示框
    const messageBox = document.createElement('div');
    messageBox.style.cssText = `
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 1rem;
        padding: 2rem;
        max-width: 400px;
        width: 100%;
        text-align: center;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    `;

    // 添加图标
    const icon = document.createElement('div');
    icon.innerHTML = `
        <svg style="width: 64px; height: 64px; margin: 0 auto 1rem; color: #fff;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" style="stroke-width: 2;" />
        </svg>
    `;

    // 添加文字
    const text = document.createElement('p');
    text.textContent = message;
    text.style.cssText = `
        color: #fff;
        font-size: 1.125rem;
        line-height: 1.6;
        margin: 0;
        font-weight: 500;
    `;

    messageBox.appendChild(icon);
    messageBox.appendChild(text);
    overlay.appendChild(messageBox);
    document.body.appendChild(overlay);

    // 禁用页面滚动
    document.body.style.overflow = 'hidden';
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 检测移动设备
    if (isMobileDevice()) {
        showMobileRestriction();
        return; // 不继续执行其他初始化
    }

    // 从localStorage获取语言设置
    const savedLang = localStorage.getItem('preferred-lang') || 'en';
    translate(savedLang);

    // 检查侧边通知
    checkSideNotification();

    checkEnvironment();
    bindEvents();
});

// 绑定事件
function bindEvents() {
    elements.urlForm.addEventListener('submit', handleExtract);
    elements.videoUrl.addEventListener('input', handleInput);
    elements.clearBtn.addEventListener('click', handleClear);
    elements.downloadBtn.addEventListener('click', handleDownload);

    // 语言切换事件
    document.getElementById('lang-zh').addEventListener('click', () => translate('zh'));
    document.getElementById('lang-en').addEventListener('click', () => translate('en'));

    // 侧边通知关闭按钮事件
    const closeSideBtn = document.getElementById('close-side-btn');
    if (closeSideBtn) {
        closeSideBtn.addEventListener('click', handleCloseSideNotification);
    }
}

// 检查环境
async function checkEnvironment() {
    try {
        const response = await fetch('/check-env');
        const data = await response.json();

        if (!data.ytdlp_installed) {
            showEnvAlert(translations[appState.currentLang]['env-check-installing'], 'warning');
            await installYtdlp();
        } else {
            // 检查是否已经显示过环境检查成功的提示
            const hasSeenEnvCheck = localStorage.getItem('env-check-seen');

            // 只有第一次访问时才显示提示
            if (!hasSeenEnvCheck) {
                showEnvAlert(translations[appState.currentLang]['env-check-passed'], 'success');

                // 标记用户已经看过提示
                localStorage.setItem('env-check-seen', 'true');

                setTimeout(() => {
                    hideEnvAlert();
                }, 3000);
            }
        }
    } catch (error) {
        showEnvAlert(translations[appState.currentLang]['env-check-failed'] + ': ' + error.message, 'error');
    }
}

// 安装 yt-dlp
async function installYtdlp() {
    try {
        const response = await fetch('/install-ytdlp', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showEnvAlert(translations[appState.currentLang]['install-success'], 'success');

            // 标记用户已经看过提示（安装成功后也算看过）
            localStorage.setItem('env-check-seen', 'true');

            setTimeout(() => {
                hideEnvAlert();
            }, 3000);
        } else {
            showEnvAlert(translations[appState.currentLang]['install-failed'] + ': ' + data.error, 'error');
        }
    } catch (error) {
        showEnvAlert(translations[appState.currentLang]['install-request-failed'] + ': ' + error.message, 'error');
    }
}

// 显示环境警告
function showEnvAlert(message, type = 'warning') {
    elements.envStatus.textContent = message;
    elements.envStatus.className = `alert-box ${type}`;
    elements.envStatus.style.display = 'block';
}

// 隐藏环境警告
function hideEnvAlert() {
    // 添加hiding类触发动画
    elements.envStatus.classList.add('hiding');

    // 动画结束后真正隐藏元素
    setTimeout(() => {
        elements.envStatus.style.display = 'none';
        elements.envStatus.classList.remove('hiding');
    }, 250); // 与CSS transition时间一致
}

// 处理输入
function handleInput() {
    const url = elements.videoUrl.value.trim();

    // 更新按钮状态
    elements.parseBtn.disabled = !url || appState.isLoading;
}

// 处理清空
function handleClear() {
    elements.videoUrl.value = '';
    elements.videoUrl.focus();
    handleInput();
    // 只隐藏清空按钮，不清除结果和错误
    elements.clearBtn.style.display = 'none';
}

// 处理解析
async function handleExtract(e) {
    e.preventDefault();

    const url = elements.videoUrl.value.trim();

    if (!url) {
        showError(translations[appState.currentLang]['enter-link']);
        return;
    }

    // 重置状态
    setLoading(true);
    clearError();
    hideVideoResult();

    try {
        // 调用后端解析API
        const response = await fetch('/parse-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || data.message || translations[appState.currentLang]['parse-failed']);
        }

        // 保存视频信息
        appState.videoInfo = data.video_info;

        // 显示视频信息
        displayVideoInfo(data.video_info);

    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : translations[appState.currentLang]['unknown-error'];
        showError(errorMessage);
        hideVideoResult();
    } finally {
        setLoading(false);
    }
}

// 设置加载状态
function setLoading(loading) {
    appState.isLoading = loading;
    elements.parseBtn.disabled = loading || !elements.videoUrl.value.trim();
    elements.videoUrl.disabled = loading;

    if (loading) {
        elements.btnText.textContent = translations[appState.currentLang]['parsing'];
        elements.spinner.style.display = 'block';
    } else {
        elements.btnText.textContent = translations[appState.currentLang]['parse-btn'];
        elements.spinner.style.display = 'none';
    }
}

// 显示错误
function showError(message) {
    appState.error = message;
    elements.errorMessage.textContent = message;
    elements.errorMessage.style.display = 'block';
}

// 清除错误
function clearError() {
    appState.error = null;
    elements.errorMessage.style.display = 'none';
}

// 显示视频信息
function displayVideoInfo(videoInfo) {
    // 显示清空按钮（只在有解析结果时显示）
    elements.clearBtn.style.display = 'flex';


    // 更新缩略图
    if (videoInfo.thumbnail && videoInfo.thumbnail.trim() !== '') {
        // 判断是否需要代理(只有B站、小红书等需要Referer验证的平台才使用代理)
        const needsProxy = videoInfo.thumbnail.includes('hdslb.com') ||
            videoInfo.thumbnail.includes('bilivideo.com') ||
            videoInfo.thumbnail.includes('xhscdn.com') ||
            videoInfo.thumbnail.includes('xiaohongshu.com');

        if (needsProxy) {
            // B站、小红书等平台使用代理URL,解决Referer防盗链问题
            elements.videoThumbnail.src = `/proxy-thumbnail?url=${encodeURIComponent(videoInfo.thumbnail)}`;
        } else {
            // 其他平台直接使用原始URL(抖音/YouTube/TikTok等)
            elements.videoThumbnail.src = videoInfo.thumbnail;
        }
        elements.videoThumbnail.alt = videoInfo.title || 'Video thumbnail';
    } else {
        // 如果没有缩略图，使用占位图(方形)
        elements.videoThumbnail.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="400"%3E%3Crect fill="%23374151" width="400" height="400"/%3E%3Ctext fill="%239ca3af" font-family="Arial" font-size="24" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3ENo thumbnail%3C/text%3E%3C/svg%3E';
        elements.videoThumbnail.alt = 'No thumbnail';
    }

    // 更新平台
    elements.videoPlatform.textContent = videoInfo.platform || 'Unknown';

    // 更新标题
    elements.videoTitle.textContent = videoInfo.title || 'No title';

    // 更新时长
    if (videoInfo.duration_readable && videoInfo.duration_readable !== 'Unknown') {
        elements.videoDuration.textContent = videoInfo.duration_readable;
    } else if (videoInfo.duration) {
        elements.videoDuration.textContent = videoInfo.duration;
    } else {
        elements.videoDuration.textContent = '--';
    }

    // 更新大小
    if (videoInfo.size_readable && videoInfo.size_readable !== 'Unknown') {
        elements.videoSize.textContent = videoInfo.size_readable;
    } else if (videoInfo.size) {
        elements.videoSize.textContent = videoInfo.size;
    } else {
        elements.videoSize.textContent = '--';
    }

    // 显示视频结果
    showVideoResult();
}

// 显示视频结果
function showVideoResult() {
    elements.videoResult.style.display = 'block';
}

// 隐藏视频结果
function hideVideoResult() {
    elements.videoResult.style.display = 'none';
    elements.clearBtn.style.display = 'none';
}

// 处理下载
function handleDownload() {
    if (!appState.videoInfo) {
        showError(translations[appState.currentLang]['no-video-info']);
        return;
    }

    if (appState.isDownloading) {
        return;
    }

    const videoInfo = appState.videoInfo;
    const isDash = videoInfo.is_dash || false;
    const filename = `${videoInfo.title}.${videoInfo.ext || 'mp4'}`;

    const isYouTube = videoInfo.platform === 'YouTube' ||
                      (videoInfo.url && videoInfo.url.includes('googlevideo.com'));

    if (isYouTube && !isDash) {
        window.open(videoInfo.url, '_blank');
        showEnvAlert(translations[appState.currentLang]['download-started'], 'success');
        setTimeout(() => { hideEnvAlert(); }, 3000);
        return;
    }

    const proxyUrl = `/proxy-download?video_url=${encodeURIComponent(videoInfo.url)}&filename=${encodeURIComponent(filename)}&is_dash=${isDash}`;

    if (isDash) {
        startDashDownload(proxyUrl, filename);
    } else {
        setDownloadingState(true);
        const link = document.createElement('a');
        link.href = proxyUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showEnvAlert(translations[appState.currentLang]['download-started'], 'success');
        setTimeout(() => { hideEnvAlert(); }, 3000);
        setTimeout(() => { setDownloadingState(false); }, 5000);
    }
}

// DASH/HLS下载：使用fetch追踪进度，避免重复点击
function startDashDownload(proxyUrl, filename) {
    setDownloadingState(true);
    startDownloadTimer();

    fetch(proxyUrl)
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || err.message || 'Download failed'); });
            }
            const contentLength = response.headers.get('Content-Length');
            if (contentLength) {
                updateDownloadBtnText(
                    translations[appState.currentLang]['download-processing'],
                    `${formatBytes(parseInt(contentLength))}`
                );
            }
            return response.blob();
        })
        .then(blob => {
            stopDownloadTimer();
            const blobUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
            setDownloadingState(false);
            showEnvAlert(translations[appState.currentLang]['download-started'], 'success');
            setTimeout(() => { hideEnvAlert(); }, 3000);
        })
        .catch(error => {
            stopDownloadTimer();
            setDownloadingState(false);
            showError(error.message);
        });
}

function setDownloadingState(downloading) {
    appState.isDownloading = downloading;
    const btn = elements.downloadBtn;
    const btnTextEl = btn.querySelector('span');

    if (downloading) {
        btn.disabled = true;
        btn.classList.add('downloading');
    } else {
        btn.disabled = false;
        btn.classList.remove('downloading');
        if (btnTextEl) {
            btnTextEl.textContent = translations[appState.currentLang]['download-btn'];
        }
    }
}


function startDownloadTimer() {
    appState.downloadSeconds = 0;
    updateDownloadBtnText(translations[appState.currentLang]['download-processing'], '0s');
    appState.downloadTimer = setInterval(() => {
        appState.downloadSeconds++;
        updateDownloadBtnText(
            translations[appState.currentLang]['download-processing'],
            `${appState.downloadSeconds}s`
        );
    }, 1000);
}

function stopDownloadTimer() {
    if (appState.downloadTimer) {
        clearInterval(appState.downloadTimer);
        appState.downloadTimer = null;
    }
}

function updateDownloadBtnText(label, detail) {
    const btnTextEl = elements.downloadBtn.querySelector('span');
    if (btnTextEl) {
        btnTextEl.textContent = `${label} (${detail})`;
    }
}

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '';
    const mb = bytes / (1024 * 1024);
    return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
}

// 检查侧边通知是否应该显示
function checkSideNotification() {
    // 如果是移动端，不显示侧边栏
    if (window.innerWidth <= 1024) return;

    const sideNotification = document.getElementById('side-notification');
    if (!sideNotification) return;

    // 检查 localStorage 中是否已经设置了关闭标记（版本号变更时重新显示）
    const notificationVersion = 'v2';  // 更新内容时修改此版本号
    const isClosed = localStorage.getItem('side-notification-closed') === notificationVersion;

    if (!isClosed) {
        sideNotification.style.display = 'flex';
    }
}

// 处理关闭侧边通知
function handleCloseSideNotification() {
    const sideNotification = document.getElementById('side-notification');
    if (!sideNotification) return;

    // 添加退出动画类
    sideNotification.classList.add('hiding');

    // 动画结束后隐藏元素
    setTimeout(() => {
        sideNotification.style.display = 'none';
        sideNotification.classList.remove('hiding');

        // 在 localStorage 中标记已关闭（保存版本号）
        const notificationVersion = 'v2';  // 与 checkSideNotification 中保持一致
        localStorage.setItem('side-notification-closed', notificationVersion);
    }, 500); // 与 CSS animation 时间一致
}
