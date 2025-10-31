// 应用状态
const appState = {
    isDownloading: false
};

// DOM元素
const elements = {
    videoUrl: document.getElementById('video-url'),
    downloadBtn: document.getElementById('download-btn'),
    message: document.getElementById('message'),
    envStatus: document.getElementById('env-status'),
    progressContainer: null,  // 动态创建
    progressBar: null,         // 动态创建
    progressText: null         // 动态创建
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    checkEnvironment();
    bindEvents();
});

// 绑定事件
function bindEvents() {
    elements.downloadBtn.addEventListener('click', startDownload);
    elements.videoUrl.addEventListener('input', validateForm);
}

// 检查环境
async function checkEnvironment() {
    try {
        const response = await fetch('/check-env');
        const data = await response.json();

        if (!data.ytdlp_installed) {
            showEnvWarning('检测到 yt-dlp 未安装，正在自动安装...');
            await installYtdlp();
        } else {
            showEnvSuccess('环境检查通过，可以开始使用');
            setTimeout(() => {
                elements.envStatus.style.display = 'none';
            }, 3000);
        }
    } catch (error) {
        showEnvError('环境检查失败: ' + error.message);
    }
}

// 安装 yt-dlp
async function installYtdlp() {
    try {
        const response = await fetch('/install-ytdlp', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showEnvSuccess('yt-dlp 安装成功');
            setTimeout(() => {
                elements.envStatus.style.display = 'none';
            }, 3000);
        } else {
            showEnvError('yt-dlp 安装失败: ' + data.error);
        }
    } catch (error) {
        showEnvError('安装请求失败: ' + error.message);
    }
}

// 表单验证
function validateForm() {
    const url = elements.videoUrl.value.trim();
    elements.downloadBtn.disabled = !url || appState.isDownloading;
}

// 开始下载流程
async function startDownload() {
    const url = elements.videoUrl.value.trim();

    if (!url) {
        showMessage('请输入视频链接', 'error');
        return;
    }

    // 禁用按钮，显示加载状态
    appState.isDownloading = true;
    elements.downloadBtn.disabled = true;
    elements.downloadBtn.classList.add('loading');

    // 在按钮内显示进度
    updateButtonProgress('正在解析...', 10);

    try {
        // 构建请求体
        const requestBody = { url };

        // 调用后端解析API
        const response = await fetch('/parse-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || data.message);
        }

        // 解析成功，显示视频信息
        const videoInfo = data.video_info;
        updateButtonProgress('解析完成 ✓', 100);

        // 显示视频信息
        showVideoInfo(videoInfo);

        // 自动触发下载
        const isDash = videoInfo.is_dash || false;
        
        // 短暂延迟后开始下载
        setTimeout(() => {
            if (isDash) {
                updateButtonProgress('准备下载 (DASH合并中)', 100);
            } else {
                updateButtonProgress('准备下载...', 100);
            }
            
            const filename = `${videoInfo.title}.${videoInfo.ext}`;
            const proxyUrl = `/proxy-download?video_url=${encodeURIComponent(videoInfo.url)}&filename=${encodeURIComponent(filename)}&is_dash=${isDash}`;
            
            // 触发下载
            const link = document.createElement('a');
            link.href = proxyUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // 显示下载状态
            setTimeout(() => {
                if (isDash) {
                    updateButtonProgress('下载已开始 (服务器合并中)', 100);
                } else {
                    updateButtonProgress('✅ 下载已开始', 100);
                }
                
                // 延迟后恢复按钮
                setTimeout(() => {
                    restoreDownloadButton();
                    // 清空输入框
                    elements.videoUrl.value = '';
                }, isDash ? 2000 : 1500);
            }, 300);
        }, 600);

    } catch (error) {
        showMessage('❌ 解析失败: ' + error.message, 'error');
        restoreDownloadButton();
    }
}

// 显示视频信息
function showVideoInfo(videoInfo) {
    const isDash = videoInfo.is_dash || false;
    
    let infoHtml = `
        <div class="video-info" style="padding: 20px; background: white; border-radius: 8px;">
            <h3 style="margin: 0 0 15px 0; color: #1e293b; font-size: 18px;">📹 视频信息</h3>
            <p style="margin: 8px 0; color: #475569;"><strong>标题:</strong> ${videoInfo.title}</p>
            <p style="margin: 8px 0; color: #475569;"><strong>平台:</strong> ${videoInfo.platform}</p>
    `;

    if (videoInfo.duration_readable && videoInfo.duration_readable !== '未知') {
        infoHtml += `<p style="margin: 8px 0; color: #475569;"><strong>时长:</strong> ${videoInfo.duration_readable}</p>`;
    }

    if (videoInfo.size_readable && videoInfo.size_readable !== '未知') {
        infoHtml += `<p style="margin: 8px 0; color: #475569;"><strong>大小:</strong> ${videoInfo.size_readable}</p>`;
    }

    // 如果是DASH格式，显示特殊提示
    if (isDash) {
        infoHtml += `
            <div style="margin-top: 15px; padding: 12px; background: #fef3c7; border-radius: 6px; border-left: 3px solid #f59e0b;">
                <p style="margin: 0; font-size: 13px; color: #92400e;">
                    🎬 <strong>DASH格式</strong> - 服务器将自动合并视频和音频流
                </p>
            </div>
        `;
    }

    infoHtml += `</div>`;

    // 在消息区域显示
    const messageDiv = elements.message;
    messageDiv.innerHTML = infoHtml;
    messageDiv.className = 'message info';
    messageDiv.style.display = 'block';
}


// 在按钮上更新进度
function updateButtonProgress(text, percent) {
    const btn = elements.downloadBtn;
    
    // 更新按钮文本和进度
    btn.innerHTML = `
        <span style="position: relative; z-index: 1;">${text}</span>
        <div style="
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: ${percent}%;
            background: rgba(255, 255, 255, 0.2);
            transition: width 0.3s ease;
            border-radius: 8px;
        "></div>
    `;
    
    // 确保按钮有相对定位
    btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
}

// 恢复下载按钮
function restoreDownloadButton() {
    appState.isDownloading = false;
    elements.downloadBtn.disabled = false;
    elements.downloadBtn.classList.remove('loading');
    elements.downloadBtn.innerHTML = '解析视频';
    elements.downloadBtn.style.position = '';
    elements.downloadBtn.style.overflow = '';
    validateForm();
}

// 显示消息
function showMessage(text, type = 'info') {
    const messageDiv = elements.message;
    
    // 如果当前显示的是视频信息（HTML内容），保存它
    const hasVideoInfo = messageDiv.querySelector('.video-info');
    
    if (hasVideoInfo) {
        // 在视频信息上方添加提示消息
        const alertDiv = document.createElement('div');
        alertDiv.className = `message ${type}`;
        alertDiv.textContent = text;
        alertDiv.style.marginBottom = '15px';
        messageDiv.insertBefore(alertDiv, messageDiv.firstChild);
        
        // 5秒后移除提示消息
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    } else {
        // 没有视频信息，直接显示消息
        messageDiv.textContent = text;
        messageDiv.className = `message ${type}`;
        messageDiv.style.display = 'block';

        // 5秒后自动隐藏
        setTimeout(() => {
            if (messageDiv.textContent === text) {
                messageDiv.style.display = 'none';
            }
        }, 5000);
    }
}

// 显示环境状态
function showEnvSuccess(text) {
    elements.envStatus.textContent = '✅ ' + text;
    elements.envStatus.className = 'status-box success';
    elements.envStatus.style.display = 'block';
}

function showEnvWarning(text) {
    elements.envStatus.textContent = '⚠️ ' + text;
    elements.envStatus.className = 'status-box warning';
    elements.envStatus.style.display = 'block';
}

function showEnvError(text) {
    elements.envStatus.textContent = '❌ ' + text;
    elements.envStatus.className = 'status-box error';
    elements.envStatus.style.display = 'block';
}
