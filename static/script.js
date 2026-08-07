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
        'footer-disclaimer': '下载处理文件仅临时保存并自动过期。所有视频和图片均属于其各自所有者和源网站。',
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
        'download-started': '✅ 下载已开始，请在浏览器下载栏查看',
        'download-merging': '🎬 服务器正在合并视频和音频流',
        'download-processing': '服务器处理中',
        'download-btn-retry': '重新下载',
        'quality-label': '清晰度',
        'quality-360': '360p · 快速',
        'quality-720': '720p · 推荐',
        'quality-1080': '1080p · 高清',
        'download-queued': '任务排队中',
        'download-downloading': '正在下载视频',
        'download-merging-status': '正在合并音视频',
        'download-ready': '处理完成，正在保存到本地',
        'download-timeout': '下载任务超时，请稍后重试',
        'server-timeout': '服务器处理超时，请稍后重试',
        'faq-heading': '常见问题',
        'faq-q1': '视频解析神器是免费的吗？',
        'faq-a1': '完全免费。无需注册、无需安装软件，也不收取任何费用。',
        'faq-q2': '下载的视频有水印吗？',
        'faq-a2': '没有。抖音、TikTok、B站、小红书解析后的视频均为无水印，并保留原始清晰度。',
        'faq-q3': '支持哪些平台？',
        'faq-a3': '支持抖音、B站、小红书、YouTube、TikTok、Twitter/X。YouTube 与 B站 支持选择 360p、720p、1080p。',
        'faq-q4': '为什么链接解析失败？',
        'faq-a4': '可能是链接不正确，或视频已被删除、设为私密、仍在审核中。请重新复制分享链接后再试一次。',
        'faq-q5': '会保存我下载的视频吗？',
        'faq-a5': '普通直链由浏览器直接下载；需要合并的视频在服务器临时处理后自动保存到你的电脑，传完即删。'
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
        'footer-disclaimer': 'Download processing files are temporary and expire automatically. All videos and images belong to their respective owners and source websites.',
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
        'download-started': '✅ Download started — check your browser download bar',
        'download-merging': '🎬 Server is merging video and audio streams',
        'download-processing': 'Server processing',
        'download-btn-retry': 'Re-download',
        'quality-label': 'Quality',
        'quality-360': '360p · Fast',
        'quality-720': '720p · Recommended',
        'quality-1080': '1080p · HD',
        'download-queued': 'Waiting in queue',
        'download-downloading': 'Downloading video',
        'download-merging-status': 'Merging audio and video',
        'download-ready': 'Ready — saving to your device',
        'download-timeout': 'Download task timed out. Please try again later.',
        'server-timeout': 'Server processing timed out. Please try again later.',
        'faq-heading': 'Frequently Asked Questions',
        'faq-q1': 'Is VideoX free to use?',
        'faq-a1': 'Yes. VideoX is completely free. No registration, no software installation and no payment is required.',
        'faq-q2': 'Do downloaded videos have a watermark?',
        'faq-a2': 'No. Videos parsed from Douyin, TikTok, Bilibili and Xiaohongshu are saved without watermarks and keep their original resolution.',
        'faq-q3': 'Which platforms are supported?',
        'faq-a3': 'Douyin, Bilibili, Xiaohongshu, YouTube, TikTok and Twitter/X are supported. YouTube and Bilibili support 360p, 720p and 1080p.',
        'faq-q4': 'Why did my link fail to parse?',
        'faq-a4': 'The link may be incorrect, or the video has been deleted, set to private or is still under review. Copy the share link again and retry.',
        'faq-q5': 'Do you store the videos I download?',
        'faq-a5': 'Direct links go to your browser. Videos that need merging are processed temporarily on the server, then automatically saved to your device and deleted afterward.'
    }
};

// 应用状态
const appState = {
    isLoading: false,
    isDownloading: false,
    downloadJobId: null,
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
    qualityControl: document.getElementById('quality-control'),
    qualitySelect: document.getElementById('quality-select'),
    downloadProgress: document.getElementById('download-progress'),
    downloadStatus: document.getElementById('download-status'),
    downloadPercent: document.getElementById('download-percent'),
    downloadProgressBar: document.getElementById('download-progress-bar'),
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
    elements.qualitySelect.addEventListener('change', updateSizeForSelectedQuality);

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

        const data = await parseApiResponse(response);

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

async function parseApiResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error(`Invalid server response (HTTP ${response.status})`);
        }
        if (!response.ok) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }
        return data;
    }

    if (response.status === 504) {
        throw new Error(t('server-timeout'));
    }

    throw new Error(`Server returned HTTP ${response.status}`);
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

    const isYouTube = videoInfo.platform === 'YouTube' ||
        (videoInfo.page_url && /(?:youtube\.com|youtu\.be)/i.test(videoInfo.page_url));
    const isBilibili = videoInfo.platform === 'B站' ||
        (videoInfo.page_url && /(?:bilibili\.com|b23\.tv)/i.test(videoInfo.page_url));
    elements.qualityControl.style.display = (isYouTube || isBilibili) ? 'flex' : 'none';
    elements.qualitySelect.value = '720';
    updateSizeForSelectedQuality();
    resetDownloadProgress();

    // 显示视频结果
    showVideoResult();
}

// 根据当前选中的清晰度，刷新页面上显示的体积
// 目前只有 B站 在解析阶段拿到了每档清晰度的准确体积，
// YouTube 因该档清晰度不提供体积数据（HLS 分片流协议本身不带总大小），保持 "--"
function updateSizeForSelectedQuality() {
    const videoInfo = appState.videoInfo;
    if (!videoInfo) return;

    const sizesReadable = videoInfo.quality_sizes_readable;
    if (!sizesReadable) return;

    const quality = elements.qualitySelect.value || '720';
    const readable = sizesReadable[quality];
    elements.videoSize.textContent = (readable && readable !== 'Unknown') ? readable : '--';
}

// 显示视频结果
function showVideoResult() {
    elements.videoResult.style.display = 'block';
}

// 隐藏视频结果
function hideVideoResult() {
    elements.videoResult.style.display = 'none';
    elements.clearBtn.style.display = 'none';
    elements.qualityControl.style.display = 'none';
    stopDownloadTimer();
    resetDownloadProgress();
}

// 处理下载：
// - 需要合并的（YouTube / B站 / DASH）走后台任务 + 进度条，满了自动保存
// - 普通直链直接走浏览器下载栏
function handleDownload() {
    if (!appState.videoInfo) {
        showError(translations[appState.currentLang]['no-video-info']);
        return;
    }

    if (appState.isDownloading) {
        return;
    }

    const videoInfo = appState.videoInfo;
    const isDash = Boolean(videoInfo.is_dash);
    const filename = `${videoInfo.title}.${videoInfo.ext || 'mp4'}`;
    const isYouTube = videoInfo.platform === 'YouTube' ||
        (videoInfo.page_url && /(?:youtube\.com|youtu\.be)/i.test(videoInfo.page_url));
    const isBilibili = videoInfo.platform === 'B站' ||
        (videoInfo.page_url && /(?:bilibili\.com|b23\.tv)/i.test(videoInfo.page_url));
    const quality = (isYouTube || isBilibili) ? (elements.qualitySelect.value || '720') : 'best';
    const needsMerge = isYouTube || isBilibili || isDash;

    if (needsMerge) {
        startDownloadJob(videoInfo, filename, quality);
        return;
    }

    const proxyUrl = `/proxy-download?video_url=${encodeURIComponent(videoInfo.url)}&filename=${encodeURIComponent(filename)}&is_dash=false`;
    startBrowserDownload(proxyUrl, filename, false);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function updateJobProgress(status, progress, message, progressKnown = true) {
    const percent = Math.min(100, Math.max(0, Number(progress) || 0));
    let localizedStatus = message || translations[appState.currentLang]['download-processing'];
    if (status === 'queued') localizedStatus = translations[appState.currentLang]['download-queued'];
    if (status === 'downloading') localizedStatus = translations[appState.currentLang]['download-downloading'];
    if (status === 'merging') localizedStatus = translations[appState.currentLang]['download-merging-status'];
    if (status === 'ready') localizedStatus = translations[appState.currentLang]['download-ready'];

    elements.downloadProgress.style.display = 'block';
    elements.downloadStatus.textContent = localizedStatus;
    elements.downloadProgressBar.classList.toggle('indeterminate', progressKnown === false);
    elements.downloadPercent.textContent = progressKnown === false ? '…' : `${Math.round(percent)}%`;
    elements.downloadProgressBar.style.width = progressKnown === false ? '35%' : `${percent}%`;
    if (progressKnown === false) {
        elements.downloadProgress.removeAttribute('aria-valuenow');
        elements.downloadProgress.setAttribute('aria-valuetext', localizedStatus);
    } else {
        elements.downloadProgress.setAttribute('aria-valuenow', String(Math.round(percent)));
        elements.downloadProgress.removeAttribute('aria-valuetext');
    }
    updateDownloadBtnText(localizedStatus, progressKnown === false ? '…' : `${Math.round(percent)}%`);
}

function resetDownloadProgress() {
    if (!elements.downloadProgress) return;
    elements.downloadProgress.style.display = 'none';
    elements.downloadStatus.textContent = '';
    elements.downloadPercent.textContent = '0%';
    elements.downloadProgressBar.style.width = '0%';
    elements.downloadProgressBar.classList.remove('indeterminate');
    elements.downloadProgress.setAttribute('aria-valuenow', '0');
    elements.downloadProgress.removeAttribute('aria-valuetext');
}

async function startDownloadJob(videoInfo, filename, quality) {
    setDownloadingState(true);
    clearError();
    updateJobProgress('queued', 0, translations[appState.currentLang]['download-queued']);

    try {
        const createResponse = await fetch('/download-jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: videoInfo.page_url || videoInfo.url,
                media_url: videoInfo.url,
                platform: videoInfo.platform,
                is_dash: Boolean(videoInfo.is_dash) || videoInfo.platform === 'YouTube' || videoInfo.platform === 'B站',
                expected_size: Number(videoInfo.size) || 0,
                filename,
                quality
            })
        });
        const created = await parseApiResponse(createResponse);
        appState.downloadJobId = created.job_id;

        const startedAt = Date.now();
        while (appState.isDownloading && appState.downloadJobId === created.job_id) {
            if (Date.now() - startedAt > 20 * 60 * 1000) {
                throw new Error(translations[appState.currentLang]['download-timeout']);
            }

            await sleep(1000);
            const statusResponse = await fetch(created.status_url, { cache: 'no-store' });
            const job = await parseApiResponse(statusResponse);

            if (job.status === 'error') {
                throw new Error(job.error || job.message || 'Download failed');
            }

            updateJobProgress(job.status, job.progress, job.message, job.progress_known !== false);
            if (job.status === 'ready' && job.download_url) {
                // 进度满后自动触发浏览器保存
                updateJobProgress('ready', 100, translations[appState.currentLang]['download-ready'], true);
                const link = document.createElement('a');
                link.href = job.download_url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                appState.downloadJobId = null;
                setDownloadingState(false);
                showEnvAlert(translations[appState.currentLang]['download-started'], 'success');
                setTimeout(() => {
                    hideEnvAlert();
                    resetDownloadProgress();
                }, 3000);
                return;
            }
        }
    } catch (error) {
        appState.downloadJobId = null;
        setDownloadingState(false);
        resetDownloadProgress();
        showError(error instanceof Error ? error.message : translations[appState.currentLang]['unknown-error']);
    }
}

function startBrowserDownload(proxyUrl, filename, needsServerPrepare) {
    setDownloadingState(true);
    clearError();

    if (needsServerPrepare) {
        startDownloadTimer();
        showEnvAlert(translations[appState.currentLang]['download-merging'], 'success');
    }

    const link = document.createElement('a');
    link.href = proxyUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    if (!needsServerPrepare) {
        showEnvAlert(translations[appState.currentLang]['download-started'], 'success');
    }

    setTimeout(() => {
        stopDownloadTimer();
        setDownloadingState(false);
        hideEnvAlert();
    }, needsServerPrepare ? 8000 : 3000);
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
    if (appState.downloadTimer) {
        clearInterval(appState.downloadTimer);
    }
    appState.downloadTimer = setInterval(() => {
        appState.downloadSeconds += 1;
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
