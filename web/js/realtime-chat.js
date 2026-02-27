// 实时对话页面逻辑 - 基于豆包实时对话API

// Debug 模式检测
const DEBUG_MODE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

let conversationId = null;
let isProfileCollectionMode = false;  // 是否是信息收集模式
let autoEndTriggered = false;  // 防止自动结束重复触发

// WebSocket 相关
let ws = null;
let isConnected = false;

// 音频相关
let audioContext = null;
let mediaStream = null;
let audioWorklet = null;
let scriptProcessor = null;

// 音频播放相关
let playbackContext = null;
let audioQueue = [];
let isPlaying = false;
let nextPlayTime = 0;  // 下一个音频块的播放时间
let gainNode = null;   // 音量控制节点

// 状态
let isRecording = false;
let currentAIResponse = '';  // 累积AI回复文本
let isAISpeaking = false;    // AI是否正在说话
let isFirstTTS = true;       // 是否是第一次 TTS（开场白），用于去重

// 配置
const SAMPLE_RATE_INPUT = 16000;   // 输入采样率
const SAMPLE_RATE_OUTPUT = 24000; // 输出采样率（豆包TTS输出）
const CHUNK_SIZE = 3200;          // 每次发送的音频块大小

// 页面加载
window.onload = async function() {
    conversationId = storage.get('currentConversationId');

    if (!conversationId) {
        alert('未找到对话');
        goHome();
        return;
    }

    // 检查是否是信息收集模式
    // 注意：如果有 profileJustCompleted 标记，说明信息收集刚完成，不要再进入收集模式
    const userId = storage.get('userId');
    if (userId && !storage.get('profileJustCompleted')) {
        try {
            const profile = await api.user.getProfile(userId);
            isProfileCollectionMode = !profile.profile_completed;
            if (isProfileCollectionMode) {
                console.log('进入信息收集模式');
            }
        } catch (error) {
            console.error('获取用户信息失败:', error);
        }
    }

    showLoading('正在连接');

    // 初始化音频播放
    initPlayback();

    // 连接 WebSocket
    await connectWebSocket();
};

// ========== WebSocket 连接 ==========

// 记录师信息
const RECORDER_INFO = {
    female: { name: '小安', speaker: 'zh_female_vv_jupiter_bigtts' },
    male: { name: '小川', speaker: 'zh_male_xiaotian_jupiter_bigtts' }
};

async function connectWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';

    // 获取选中的记录师
    const selectedRecorder = storage.get('selectedRecorder') || 'female';
    const recorderInfo = RECORDER_INFO[selectedRecorder] || RECORDER_INFO.female;

    // 获取用户ID
    const userId = storage.get('userId');

    // 获取选择的话题信息
    const selectedTopic = storage.get('selectedTopic');
    const selectedGreeting = storage.get('selectedTopicGreeting');
    const selectedContext = storage.get('selectedTopicContext');
    // 使用后清除，避免下次对话重复使用
    storage.remove('selectedTopic');
    storage.remove('selectedTopicGreeting');
    storage.remove('selectedTopicContext');

    // 构建 WebSocket URL，带上音色、记录师名字、对话ID和用户ID参数
    const params = new URLSearchParams({
        speaker: recorderInfo.speaker,
        recorder_name: recorderInfo.name,
        conversation_id: conversationId,
        user_id: userId
    });

    // 如果有选择的话题，添加到参数中
    if (selectedTopic) {
        params.set('topic', selectedTopic);
    }
    if (selectedGreeting) {
        params.set('greeting', selectedGreeting);
    }
    if (selectedContext) {
        params.set('context', selectedContext);
    }

    const wsUrl = `${wsProtocol}://${window.location.host}/api/realtime/dialog?${params.toString()}`;

    console.log('连接 WebSocket:', wsUrl, '记录师:', recorderInfo.name, '用户:', userId, '开场白:', selectedGreeting ? '自定义' : '默认');

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket 已连接');
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleServerMessage(message);
        };

        ws.onerror = (error) => {
            console.error('WebSocket 错误:', error);
            showError('连接失败，请刷新重试');
        };

        ws.onclose = () => {
            console.log('WebSocket 已关闭');
            isConnected = false;
            stopRecording();
        };

    } catch (error) {
        console.error('WebSocket 连接失败:', error);
        showError('连接失败，请刷新重试');
    }
}

function handleServerMessage(message) {
    console.log('收到消息:', message.type, message);

    switch (message.type) {
        case 'status':
            if (message.status === 'connected') {
                isConnected = true;
                updateAIText('');  // 清空，等待 AI 开始说话后再显示
                updateVoiceStatus('请稍候');
            } else if (message.status === 'error') {
                showError(message.message);
            }
            break;

        case 'audio':
            // 收到音频数据，加入播放队列
            const audioData = base64ToArrayBuffer(message.data);
            queueAudio(audioData);
            break;

        case 'text':
            // 收到文本
            if (message.text_type === 'asr') {
                // 用户说的话 - 不显示，只打印日志
                console.log('用户说:', message.content);
            } else if (message.text_type === 'response') {
                // AI 回复文字 - 累积并显示
                if (isAISpeaking && message.content) {
                    currentAIResponse += message.content;  // 累积文本
                    // 检查是否包含结束标记
                    const displayText = currentAIResponse.replace('【信息收集完成】', '').trim();
                    updateAIText(displayText);

                    // 检测信息收集完成标记
                    if (isProfileCollectionMode && !autoEndTriggered && currentAIResponse.includes('【信息收集完成】')) {
                        autoEndTriggered = true;  // 防止重复触发
                        console.log('检测到信息收集完成标记，准备自动结束对话');
                        // 延迟一点时间让用户听完AI说的话
                        setTimeout(() => {
                            autoEndProfileCollection();
                        }, 3000);
                    }
                }
            }
            break;

        case 'event':
            handleEvent(message.event, message.payload);
            break;

        case 'debug':
            // Debug 模式下显示调试信息
            if (DEBUG_MODE && message.message) {
                showToast(message.message);
            }
            break;
    }
}

function handleEvent(event, payload) {
    console.log('事件:', event, payload);

    switch (event) {
        case 350:
            // TTS 开始 - AI 开始说话
            isAISpeaking = true;
            currentAIResponse = '';  // 清空，准备接收新回复
            updateVoiceStatus('记录师正在说话');
            setVoiceActive(false);
            break;

        case 359:
            // TTS 结束 - AI 说完了，可以开始录音
            isAISpeaking = false;
            // 第一次 TTS 结束后，标记已完成开场白
            if (isFirstTTS) {
                isFirstTTS = false;
            }
            updateVoiceStatus('请开始说话');
            setTimeout(() => {
                startRecording();
            }, 500);
            break;

        case 450:
            // 用户开始说话 - 清空音频队列，音波动起来
            // 不更新上方文字，保持显示AI之前的问题
            clearAudioQueue();
            updateVoiceStatus('正在聆听...');
            setVoiceActive(true);
            break;

        case 459:
            // 用户说完 - AI 开始处理
            updateVoiceStatus('正在思考...');
            setVoiceActive(false);
            break;

        case 152:
        case 153:
            // 会话结束
            isAISpeaking = false;
            updateAIText('对话已结束');
            updateVoiceStatus('已结束');
            setVoiceActive(false);
            stopRecording();
            break;
    }
}

// ========== 音频录制 ==========

async function startRecording() {
    if (isRecording || !isConnected) return;

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE_INPUT,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        audioContext = new AudioContext({ sampleRate: SAMPLE_RATE_INPUT });
        const source = audioContext.createMediaStreamSource(mediaStream);

        // 使用 ScriptProcessor 获取音频数据
        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        scriptProcessor.onaudioprocess = (e) => {
            if (!isRecording || !isConnected) return;

            const inputData = e.inputBuffer.getChannelData(0);
            // 转换为 16bit PCM
            const pcmData = float32ToPCM16(inputData);
            // 发送到服务器
            sendAudio(pcmData);
        };

        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        isRecording = true;
        updateVoiceStatus('请开始说话');

    } catch (error) {
        console.error('无法访问麦克风:', error);
        updateAIText('无法访问麦克风，请检查权限');
        updateVoiceStatus('麦克风错误');
    }
}

function stopRecording() {
    isRecording = false;

    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }

    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }

    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
}

function sendAudio(pcmData) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const base64Data = arrayBufferToBase64(pcmData.buffer);
    ws.send(JSON.stringify({
        type: 'audio',
        data: base64Data
    }));
}

// ========== 音频播放 ==========

function initPlayback() {
    // 创建音频上下文，指定采样率
    playbackContext = new AudioContext({ sampleRate: SAMPLE_RATE_OUTPUT });

    // 创建音量控制节点
    gainNode = playbackContext.createGain();
    gainNode.gain.value = 1.0;
    gainNode.connect(playbackContext.destination);

    console.log('播放上下文采样率:', playbackContext.sampleRate);
}

async function queueAudio(audioData) {
    // 确保 AudioContext 处于运行状态
    if (playbackContext.state === 'suspended') {
        await playbackContext.resume();
    }

    audioQueue.push(audioData);
    if (!isPlaying) {
        playNextAudio();
    }
}

function clearAudioQueue() {
    audioQueue = [];
    isPlaying = false;
    nextPlayTime = 0;  // 重置播放时间
}

async function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }

    isPlaying = true;

    // 批量处理队列中的音频，使用精确的时间调度
    while (audioQueue.length > 0) {
        const audioData = audioQueue.shift();

        try {
            const floatData = pcm16LEToFloat32(audioData);

            if (floatData.length === 0) {
                continue;
            }

            // 应用淡入淡出来减少 click 声
            applyFade(floatData);

            const audioBuffer = playbackContext.createBuffer(1, floatData.length, SAMPLE_RATE_OUTPUT);
            audioBuffer.getChannelData(0).set(floatData);

            const source = playbackContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(gainNode);

            // 计算播放时间，确保音频连续
            const currentTime = playbackContext.currentTime;
            if (nextPlayTime < currentTime) {
                // 如果落后了，稍微往后推一点避免立即播放产生的 click
                nextPlayTime = currentTime + 0.01;
            }

            source.start(nextPlayTime);
            nextPlayTime += audioBuffer.duration;

        } catch (error) {
            console.error('播放音频失败:', error);
        }
    }

    isPlaying = false;
}

// 应用淡入淡出效果减少音频块之间的 click 声
function applyFade(samples) {
    const fadeLength = Math.min(64, Math.floor(samples.length / 10));

    // 淡入
    for (let i = 0; i < fadeLength; i++) {
        samples[i] *= i / fadeLength;
    }

    // 淡出
    for (let i = 0; i < fadeLength; i++) {
        samples[samples.length - 1 - i] *= i / fadeLength;
    }
}

// ========== 界面控制 ==========

// 显示轻量提示
function showToast(message) {
    // 创建 toast 元素
    const toast = document.createElement('div');
    toast.className = 'toast-message';
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        font-size: 16px;
        z-index: 9999;
        animation: fadeIn 0.3s ease;
    `;
    document.body.appendChild(toast);

    // 自动移除
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 1200);
}

// 更新 AI 文字内容
function updateAIText(text) {
    document.getElementById('aiText').textContent = text;
}

// 更新用户语音状态
function updateVoiceStatus(text) {
    document.getElementById('voiceStatus').textContent = text;
}

// 设置音波动画状态
function setVoiceActive(active) {
    const visualizer = document.getElementById('voiceVisualizer');
    if (active) {
        visualizer.classList.add('active');
    } else {
        visualizer.classList.remove('active');
    }
}

// 简化的状态更新函数
function showLoading(text) {
    updateAIText(text + '...');
    updateVoiceStatus('请稍候');
    setVoiceActive(false);
}

function showError(text) {
    updateAIText('错误: ' + text);
    updateVoiceStatus('连接失败');
    setVoiceActive(false);
}

// ========== 工具函数 ==========

function float32ToPCM16(float32Array) {
    const pcm16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm16;
}

function pcm16LEToFloat32(arrayBuffer) {
    // 显式按小端序读取 16bit PCM
    const dataView = new DataView(arrayBuffer);
    const numSamples = arrayBuffer.byteLength / 2;
    const float32 = new Float32Array(numSamples);

    for (let i = 0; i < numSamples; i++) {
        // true = little-endian
        const int16 = dataView.getInt16(i * 2, true);
        float32[i] = int16 / 32768.0;
    }
    return float32;
}

function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

// ========== 页面控制 ==========

// 自动结束信息收集（由AI触发）
async function autoEndProfileCollection() {
    console.log('自动结束信息收集对话');

    stopRecording();

    if (ws) {
        ws.send(JSON.stringify({ type: 'stop' }));
        ws.close();
    }

    updateAIText('正在保存...');
    updateVoiceStatus('请稍候');

    try {
        // 结束对话
        await api.conversation.endQuick(conversationId);
        // 显示欢迎弹窗
        await showWelcomeModal();
    } catch (error) {
        console.error('自动结束对话失败:', error);
        // 出错也显示弹窗，让用户能回到主页
        await showWelcomeModal();
    }
}

async function endChat() {
    if (!confirm('确定要结束这次对话吗？')) {
        return;
    }

    stopRecording();

    if (ws) {
        ws.send(JSON.stringify({ type: 'stop' }));
        ws.close();
    }

    updateAIText('正在保存...');
    updateVoiceStatus('请稍候');

    try {
        // 结束对话（后台会处理摘要生成和开场白刷新）
        await api.conversation.endQuick(conversationId);

        if (isProfileCollectionMode) {
            // 信息收集模式：显示欢迎弹窗
            await showWelcomeModal();
        } else {
            // 正常对话模式：后台生成回忆录，直接跳转
            const userId = storage.get('userId');
            api.memoir.generateAsync(userId, conversationId);
            // 显示简短提示后跳转
            showToast('对话已保存，可在「我的回忆」中查看');
            setTimeout(() => {
                goHome();
            }, 1500);
        }
    } catch (error) {
        console.error('结束对话失败:', error);
        alert('操作失败: ' + error.message);
        goHome();
    }
}

// 显示欢迎弹窗（信息收集完成后）
async function showWelcomeModal() {
    // 直接调用后端标记 profile 完成，不依赖后台异步任务
    const userId = storage.get('userId');
    if (userId) {
        try {
            await api.user.completeProfile(userId);
            console.log('已标记 profile 完成');
        } catch (error) {
            console.error('标记 profile 完成失败:', error);
        }
    }

    // 清除临时标记（因为后端已经同步更新了）
    storage.remove('profileJustCompleted');

    const modal = document.getElementById('welcomeModal');
    if (modal) {
        modal.style.display = 'flex';
    } else {
        // 如果没有弹窗元素，用 alert 兜底
        alert('很高兴认识您！接下来就可以开始记录您的故事了。');
        goHome();
    }
}

function goHome() {
    stopRecording();
    if (ws) {
        ws.close();
    }
    storage.remove('currentConversationId');
    window.location.href = 'index.html';
}

window.onbeforeunload = function() {
    stopRecording();
    if (ws) {
        ws.close();
    }
};
