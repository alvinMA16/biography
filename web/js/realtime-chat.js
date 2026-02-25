// 实时对话页面逻辑 - 基于豆包实时对话API

let conversationId = null;

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

    showLoading('正在连接');

    // 初始化音频播放
    initPlayback();

    // 连接 WebSocket
    await connectWebSocket();
};

// ========== WebSocket 连接 ==========

// 记录师配置
const RECORDERS = {
    female: { speaker: 'zh_female_vv_jupiter_bigtts' },
    male: { speaker: 'zh_male_xiaotian_jupiter_bigtts' }
};

async function connectWebSocket() {
    const hostname = window.location.hostname || 'localhost';

    // 获取选中的记录师音色
    const selectedRecorder = storage.get('selectedRecorder') || 'female';
    const speaker = RECORDERS[selectedRecorder]?.speaker || RECORDERS.female.speaker;

    // 构建 WebSocket URL，带上音色参数
    const wsUrl = `ws://${hostname}:8001/api/realtime/dialog?speaker=${encodeURIComponent(speaker)}`;

    console.log('连接 WebSocket:', wsUrl, '记录师:', selectedRecorder);

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
                showStatus('已连接，等待开场白...');
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
                // 用户说的话（ASR结果）
                console.log('用户说:', message.content);
            } else if (message.text_type === 'response') {
                // AI 回复
                updateAIText(message.content);
            }
            break;

        case 'event':
            handleEvent(message.event, message.payload);
            break;
    }
}

function handleEvent(event, payload) {
    console.log('事件:', event, payload);

    switch (event) {
        case 350:
            // TTS 开始
            showStatus('AI 正在回复...');
            break;

        case 359:
            // TTS 结束，可以开始录音了
            showStatus('请开始说话');
            setTimeout(() => {
                startRecording();
            }, 500);
            break;

        case 450:
            // 用户开始说话，清空音频队列
            clearAudioQueue();
            showStatus('正在聆听...');
            break;

        case 459:
            // 用户说完，AI 开始处理
            showStatus('正在思考...');
            break;

        case 152:
        case 153:
            // 会话结束
            showStatus('对话已结束');
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
        showVoiceInput();
        updateVoiceHint('正在聆听...');

    } catch (error) {
        console.error('无法访问麦克风:', error);
        showError('无法访问麦克风，请检查权限');
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

function showLoading(text) {
    document.getElementById('aiSection').style.display = 'none';
    document.getElementById('voiceSection').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('loadingText').innerHTML = text + '<span class="loading-dots"></span>';
    document.getElementById('textInputFallback').style.display = 'none';
}

function showStatus(text) {
    document.getElementById('aiSection').style.display = 'flex';
    document.getElementById('voiceSection').style.display = 'none';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('aiQuestion').textContent = text;
    document.getElementById('textInputFallback').style.display = 'none';
}

function showVoiceInput() {
    document.getElementById('aiSection').style.display = 'flex';
    document.getElementById('voiceSection').style.display = 'flex';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('textInputFallback').style.display = 'none';
}

function showError(text) {
    document.getElementById('aiSection').style.display = 'flex';
    document.getElementById('voiceSection').style.display = 'none';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('aiQuestion').textContent = '错误: ' + text;
    document.getElementById('textInputFallback').style.display = 'block';
}

function updateAIText(text) {
    document.getElementById('aiQuestion').textContent = text;
}

function updateVoiceHint(text) {
    document.getElementById('voiceHint').textContent = text;
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

function switchToTextMode() {
    // 实时对话模式暂不支持文字输入
    alert('实时对话模式暂不支持文字输入');
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

    showLoading('正在保存');

    try {
        await api.conversation.end(conversationId);

        if (confirm('是否要把这次对话整理成回忆录？')) {
            const userId = storage.get('userId');
            await api.memoir.generate(userId, conversationId);
            alert('回忆录已生成！');
        }

        goHome();
    } catch (error) {
        console.error('结束对话失败:', error);
        alert('操作失败: ' + error.message);
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
