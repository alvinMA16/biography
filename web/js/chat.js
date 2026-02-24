// 聊天页面逻辑 - 自动语音对话 + 两阶段响应

let conversationId = null;

// 语音相关 - 持久化的媒体流
let mediaStream = null;
let audioContext = null;
let analyser = null;
let microphone = null;
let recordingProcessor = null;

// 录音状态
let audioChunks = [];
let isRecording = false;
let silenceTimer = null;
let isMonitoring = false;
let hasStartedSpeaking = false;  // 用户是否已开始说话

// 配置
const SILENCE_THRESHOLD = 15;           // 静音阈值（0-255）
const SPEAKING_THRESHOLD = 20;          // 说话阈值（稍高一点）
const FINAL_SILENCE_DURATION = 4000;    // 最终停止判定（4秒静音）
const MIN_SPEAKING_DURATION = 1000;     // 最短有效说话时长（1秒）
const SEGMENT_DURATION = 20000;         // 分段时长（20秒）
const OVERLAP_DURATION = 3000;          // 重叠时长（3秒）
let recordingStartTime = 0;
let speakingStartTime = 0;              // 开始说话的时间
let segmentTimer = null;
let recognizedTexts = [];
let overlapChunks = [];

// 页面加载
window.onload = async function() {
    conversationId = storage.get('currentConversationId');

    if (!conversationId) {
        alert('未找到对话');
        goHome();
        return;
    }

    const micReady = await initMicrophone();
    if (!micReady) {
        return;
    }

    await loadLatestQuestion();
};

// ========== 麦克风初始化 ==========

async function initMicrophone() {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        audioContext = new AudioContext({ sampleRate: 16000 });
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;

        microphone = audioContext.createMediaStreamSource(mediaStream);
        microphone.connect(analyser);

        recordingProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        recordingProcessor.onaudioprocess = function(e) {
            if (isRecording) {
                const channelData = e.inputBuffer.getChannelData(0);
                const pcmData = new Int16Array(channelData.length);
                for (let i = 0; i < channelData.length; i++) {
                    const s = Math.max(-1, Math.min(1, channelData[i]));
                    pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                audioChunks.push(pcmData);
            }
        };

        microphone.connect(recordingProcessor);
        recordingProcessor.connect(audioContext.destination);

        console.log('麦克风初始化成功');
        return true;

    } catch (error) {
        console.error('无法访问麦克风:', error);
        alert('无法访问麦克风，请检查权限设置。您可以使用文字输入。');
        showAIQuestion();
        return false;
    }
}

function releaseMicrophone() {
    if (recordingProcessor) {
        recordingProcessor.disconnect();
        recordingProcessor = null;
    }
    if (microphone) {
        microphone.disconnect();
        microphone = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    console.log('麦克风资源已释放');
}

async function loadLatestQuestion() {
    try {
        const conversation = await api.conversation.get(conversationId);

        if (conversation.messages && conversation.messages.length > 0) {
            const messages = conversation.messages;
            let lastAiMessage = null;

            for (let i = messages.length - 1; i >= 0; i--) {
                if (messages[i].role === 'assistant') {
                    lastAiMessage = messages[i];
                    break;
                }
            }

            if (lastAiMessage) {
                document.getElementById('aiQuestion').textContent = lastAiMessage.content;
            }
        }

        showAIQuestion();

        setTimeout(() => {
            startListening();
        }, 1000);

    } catch (error) {
        console.error('加载失败:', error);
        alert('加载失败，请重试');
    }
}

// ========== 界面切换 ==========

function showAIQuestion() {
    document.getElementById('aiSection').style.display = 'flex';
    document.getElementById('voiceSection').style.display = 'none';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('textInputFallback').style.display = 'block';
}

function showVoiceInput() {
    document.getElementById('aiSection').style.display = 'flex';
    document.getElementById('voiceSection').style.display = 'flex';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('textInputFallback').style.display = 'none';
}

function showLoading(text = '正在思考') {
    document.getElementById('aiSection').style.display = 'none';
    document.getElementById('voiceSection').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('loadingText').innerHTML = text + '<span class="loading-dots"></span>';
    document.getElementById('textInputFallback').style.display = 'none';
}

// ========== 录音控制 ==========

function startListening() {
    if (!mediaStream || !audioContext) {
        console.error('麦克风未初始化');
        return;
    }

    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }

    // 重置状态
    audioChunks = [];
    recognizedTexts = [];
    overlapChunks = [];
    recordingStartTime = Date.now();
    speakingStartTime = 0;
    hasStartedSpeaking = false;

    isRecording = true;
    showVoiceInput();
    updateVoiceHint('正在聆听...');

    startSegmentTimer();

    if (!isMonitoring) {
        isMonitoring = true;
        monitorVolume();
    }
}

function stopListening() {
    isRecording = false;

    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }
    if (segmentTimer) {
        clearTimeout(segmentTimer);
        segmentTimer = null;
    }
}

function monitorVolume() {
    if (!analyser) return;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;

    if (isRecording) {
        updateVisualization(average);

        // 检测用户是否开始说话
        if (!hasStartedSpeaking) {
            if (average >= SPEAKING_THRESHOLD) {
                // 用户开始说话
                hasStartedSpeaking = true;
                speakingStartTime = Date.now();
                updateVoiceHint('正在聆听...');
            }
            // 还没开始说话，不启动静音计时器
        } else {
            // 用户已经开始说话，检测静音
            if (average < SILENCE_THRESHOLD) {
                if (!silenceTimer) {
                    silenceTimer = setTimeout(() => {
                        // 检查是否说了足够长的时间
                        const speakingDuration = Date.now() - speakingStartTime;
                        if (speakingDuration >= MIN_SPEAKING_DURATION) {
                            stopListeningAndSend();
                        } else {
                            // 说话太短，重置状态继续等待
                            hasStartedSpeaking = false;
                            speakingStartTime = 0;
                            silenceTimer = null;
                            updateVoiceHint('正在聆听...');
                        }
                    }, FINAL_SILENCE_DURATION);
                }
                updateVoiceHint('静音中...');
            } else {
                if (silenceTimer) {
                    clearTimeout(silenceTimer);
                    silenceTimer = null;
                }
                updateVoiceHint('正在聆听...');
            }
        }
    }

    if (isMonitoring) {
        requestAnimationFrame(monitorVolume);
    }
}

function updateVisualization(volume) {
    const bars = document.querySelectorAll('.voice-bars .bar');
    const normalizedVolume = Math.min(volume / 100, 1);

    bars.forEach((bar, index) => {
        const centerIndex = 2;
        const distance = Math.abs(index - centerIndex);
        const baseHeight = 15;
        const maxHeight = 50;
        const height = baseHeight + (maxHeight - baseHeight) * normalizedVolume * (1 - distance * 0.2);
        bar.style.height = `${height}px`;
    });
}

function updateVoiceHint(text) {
    document.getElementById('voiceHint').textContent = text;
}

// ========== 分段处理 ==========

function startSegmentTimer() {
    segmentTimer = setTimeout(async () => {
        if (!isRecording || audioChunks.length === 0) {
            if (isRecording) startSegmentTimer();
            return;
        }

        const samplesPerSecond = 16000;
        const overlapSamples = samplesPerSecond * (OVERLAP_DURATION / 1000);
        const chunksToRecognize = [...audioChunks];

        let sampleCount = 0;
        let overlapStartIndex = audioChunks.length;
        for (let i = audioChunks.length - 1; i >= 0; i--) {
            sampleCount += audioChunks[i].length;
            if (sampleCount >= overlapSamples) {
                overlapStartIndex = i;
                break;
            }
        }

        overlapChunks = audioChunks.slice(overlapStartIndex);
        audioChunks = [...overlapChunks];

        recognizeSegment(chunksToRecognize);

        if (isRecording) startSegmentTimer();

    }, SEGMENT_DURATION);
}

async function recognizeSegment(chunks) {
    if (chunks.length === 0) return;

    const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
    const pcmData = new Int16Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        pcmData.set(chunk, offset);
        offset += chunk.length;
    }

    const wavBlob = createWavBlob(pcmData, 16000);

    try {
        const result = await api.asr.recognize(wavBlob);
        if (result.text && result.text.trim()) {
            recognizedTexts.push(result.text.trim());
        }
    } catch (error) {
        console.error('分段识别失败:', error);
    }
}

async function stopListeningAndSend() {
    if (!isRecording) return;

    stopListening();

    // 检查是否有录音数据
    if (audioChunks.length === 0 && recognizedTexts.length === 0) {
        // 没有数据，直接继续录音（不切换界面，避免闪烁）
        setTimeout(startListening, 500);
        return;
    }

    showLoading('正在识别语音');

    // 识别最后一段
    if (audioChunks.length > 0) {
        const totalLength = audioChunks.reduce((acc, chunk) => acc + chunk.length, 0);
        const pcmData = new Int16Array(totalLength);
        let offset = 0;
        for (const chunk of audioChunks) {
            pcmData.set(chunk, offset);
            offset += chunk.length;
        }

        const wavBlob = createWavBlob(pcmData, 16000);

        try {
            const result = await api.asr.recognize(wavBlob);
            if (result.text && result.text.trim()) {
                recognizedTexts.push(result.text.trim());
            }
        } catch (error) {
            console.error('最后一段识别失败:', error);
        }
    }

    const fullText = recognizedTexts.join('');

    if (fullText.trim()) {
        await sendMessageWithEmpathy(fullText);
    } else {
        // 识别为空，直接继续录音（不切换界面，避免闪烁）
        setTimeout(startListening, 500);
    }
}

// ========== 发送消息（两阶段分屏显示） ==========

async function sendMessageWithEmpathy(message) {
    const aiQuestion = document.getElementById('aiQuestion');

    // 第一阶段：显示"正在思考..."
    showLoading('正在思考');

    try {
        // 发送共情请求
        console.log('发送共情请求...');
        const empathyResult = await api.conversation.empathy(message);
        const empathyResponse = empathyResult.response;
        console.log('收到共情回应:', empathyResponse);

        // 第二阶段：全屏显示共情内容 + 下方"正在思考..."
        aiQuestion.innerHTML = empathyResponse + '<div class="thinking-indicator">正在思考<span class="loading-dots"></span></div>';
        document.getElementById('aiSection').style.display = 'flex';
        document.getElementById('loadingState').style.display = 'none';

        // 发送追问请求
        console.log('发送追问请求...');
        let isFirstChunk = true;

        await api.conversation.chatStream(conversationId, message, (chunk, fullText) => {
            if (isFirstChunk) {
                isFirstChunk = false;
                // 追问开始返回，切换到全屏显示追问内容
                aiQuestion.textContent = fullText;
            } else {
                // 继续流式显示追问内容
                aiQuestion.textContent = fullText;
            }
        });

        // 完成，准备下一轮
        showAIQuestion();
        setTimeout(startListening, 1500);

    } catch (error) {
        console.error('发送失败:', error);
        alert('发送失败: ' + error.message);
        showAIQuestion();
        setTimeout(startListening, 2000);
    }
}

// 纯文字发送
async function sendMessage(message) {
    const aiQuestion = document.getElementById('aiQuestion');

    showLoading('正在思考');
    aiQuestion.textContent = '';

    try {
        await api.conversation.chatStream(conversationId, message, (chunk, fullText) => {
            aiQuestion.textContent = fullText;
            document.getElementById('aiSection').style.display = 'flex';
            document.getElementById('loadingState').style.display = 'none';
        });

        showAIQuestion();
        setTimeout(startListening, 1500);

    } catch (error) {
        console.error('发送失败:', error);
        alert('发送失败: ' + error.message);
        showAIQuestion();
        setTimeout(startListening, 2000);
    }
}

// ========== 工具函数 ==========

function createWavBlob(pcmData, sampleRate) {
    const buffer = new ArrayBuffer(44 + pcmData.length * 2);
    const view = new DataView(buffer);

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + pcmData.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, pcmData.length * 2, true);

    const dataView = new Int16Array(buffer, 44);
    dataView.set(pcmData);

    return new Blob([buffer], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

// ========== 文字输入模式 ==========

function switchToTextMode() {
    stopListening();

    document.getElementById('textModal').style.display = 'flex';
    document.getElementById('messageInput').focus();
}

function closeTextModal() {
    document.getElementById('textModal').style.display = 'none';
    setTimeout(startListening, 500);
}

async function sendTextMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message) return;

    input.value = '';
    document.getElementById('textModal').style.display = 'none';

    await sendMessage(message);
}

// ========== 结束对话 ==========

async function endChat() {
    if (!confirm('确定要结束这次对话吗？')) {
        return;
    }

    stopListening();
    isMonitoring = false;
    releaseMicrophone();

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
        showAIQuestion();
    }
}

function goHome() {
    stopListening();
    isMonitoring = false;
    releaseMicrophone();

    storage.remove('currentConversationId');
    window.location.href = 'index.html';
}

window.onbeforeunload = function() {
    isMonitoring = false;
    releaseMicrophone();
};
