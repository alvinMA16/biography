// 聊天页面逻辑 - 自动语音对话

let conversationId = null;

// 语音相关
let audioContext = null;
let analyser = null;
let microphone = null;
let audioChunks = [];
let isRecording = false;
let silenceTimer = null;
let recordingProcessor = null;

// 配置
const SILENCE_THRESHOLD = 15;      // 静音阈值（0-255）
const SILENCE_DURATION = 2000;     // 静音多久后结束（毫秒）
const MIN_RECORDING_TIME = 500;    // 最短录音时间（毫秒）
const SEGMENT_DURATION = 20000;    // 分段时长（20秒）
const OVERLAP_DURATION = 3000;     // 重叠时长（3秒）
let recordingStartTime = 0;
let segmentTimer = null;
let recognizedTexts = [];          // 存储各段识别结果
let overlapChunks = [];            // 存储重叠部分的音频数据

// 页面加载
window.onload = async function() {
    conversationId = storage.get('currentConversationId');

    if (!conversationId) {
        alert('未找到对话');
        goHome();
        return;
    }

    // 加载最新的AI问题
    await loadLatestQuestion();
};

// 加载最新的AI问题，然后自动开始录音
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

        // 延迟一下再开始录音，让用户有时间看问题
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

// ========== 语音录制 ==========

async function startListening() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
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

        microphone = audioContext.createMediaStreamSource(stream);
        microphone.connect(analyser);

        // 用于录制PCM数据
        recordingProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        audioChunks = [];

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

        // 保存stream引用
        window.currentStream = stream;

        isRecording = true;
        recordingStartTime = Date.now();
        recognizedTexts = [];
        overlapChunks = [];
        showVoiceInput();
        updateVoiceHint('正在聆听...');

        // 设置分段定时器
        startSegmentTimer();

        // 开始监测音量
        monitorVolume();

    } catch (error) {
        console.error('无法访问麦克风:', error);
        alert('无法访问麦克风，请检查权限设置。您可以使用文字输入。');
        showAIQuestion();
    }
}

function monitorVolume() {
    if (!analyser || !isRecording) return;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);

    // 计算平均音量
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;

    // 更新可视化
    updateVisualization(average);

    // 检测静音
    if (average < SILENCE_THRESHOLD) {
        // 静音中
        if (!silenceTimer) {
            silenceTimer = setTimeout(() => {
                // 检查是否录了足够长的时间
                if (Date.now() - recordingStartTime > MIN_RECORDING_TIME) {
                    stopListeningAndSend();
                } else {
                    // 录音太短，继续监听
                    silenceTimer = null;
                }
            }, SILENCE_DURATION);
        }
        updateVoiceHint('静音中...');
    } else {
        // 有声音，重置静音计时器
        if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
        }
        updateVoiceHint('正在聆听...');
    }

    // 继续监测
    if (isRecording) {
        requestAnimationFrame(monitorVolume);
    }
}

function updateVisualization(volume) {
    const bars = document.querySelectorAll('.voice-bars .bar');
    const normalizedVolume = Math.min(volume / 100, 1); // 0-1

    bars.forEach((bar, index) => {
        // 中间的bar最高，两边递减
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

        // 计算重叠部分需要保留多少数据
        // 16000采样率 * 2字节 * 3秒 = 96000字节 = 约3000个chunk（每个chunk 4096采样）
        const samplesPerSecond = 16000;
        const overlapSamples = samplesPerSecond * (OVERLAP_DURATION / 1000);

        // 保存当前所有数据用于识别
        const chunksToRecognize = [...audioChunks];

        // 计算需要保留多少chunk作为overlap
        let sampleCount = 0;
        let overlapStartIndex = audioChunks.length;
        for (let i = audioChunks.length - 1; i >= 0; i--) {
            sampleCount += audioChunks[i].length;
            if (sampleCount >= overlapSamples) {
                overlapStartIndex = i;
                break;
            }
        }

        // 保留overlap部分，清空其余
        overlapChunks = audioChunks.slice(overlapStartIndex);
        audioChunks = [...overlapChunks];

        // 异步识别这一段（不阻塞录音）
        recognizeSegment(chunksToRecognize);

        // 继续下一个分段定时器
        if (isRecording) startSegmentTimer();

    }, SEGMENT_DURATION);
}

async function recognizeSegment(chunks) {
    if (chunks.length === 0) return;

    // 合并音频数据
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

    isRecording = false;

    // 清理计时器
    if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
    }
    if (segmentTimer) {
        clearTimeout(segmentTimer);
        segmentTimer = null;
    }

    if (window.currentStream) {
        window.currentStream.getTracks().forEach(track => track.stop());
    }

    if (recordingProcessor) {
        recordingProcessor.disconnect();
    }

    if (microphone) {
        microphone.disconnect();
    }

    if (audioContext) {
        audioContext.close();
    }

    // 检查是否有录音数据
    if (audioChunks.length === 0 && recognizedTexts.length === 0) {
        showAIQuestion();
        setTimeout(startListening, 1000);
        return;
    }

    showLoading('正在识别语音');

    // 识别最后一段（如果有）
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

    // 合并所有识别结果
    const fullText = recognizedTexts.join('');

    if (fullText.trim()) {
        await sendMessage(fullText);
    } else {
        showAIQuestion();
        setTimeout(startListening, 1000);
    }
}

// ========== 发送消息 ==========

async function sendMessage(message) {
    showLoading('正在思考');

    const aiQuestion = document.getElementById('aiQuestion');
    aiQuestion.textContent = '';

    try {
        await api.conversation.chatStream(conversationId, message, (chunk, fullText) => {
            aiQuestion.textContent = fullText;
            // 显示AI区域，让用户看到流式输出
            document.getElementById('aiSection').style.display = 'flex';
            document.getElementById('loadingState').style.display = 'none';
        });

        // AI回复完成，延迟后开始下一轮录音
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
    // 停止录音
    if (isRecording) {
        isRecording = false;
        if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
        }
        if (window.currentStream) {
            window.currentStream.getTracks().forEach(track => track.stop());
        }
        if (audioContext) {
            audioContext.close();
        }
    }

    document.getElementById('textModal').style.display = 'flex';
    document.getElementById('messageInput').focus();
}

function closeTextModal() {
    document.getElementById('textModal').style.display = 'none';
    // 重新开始语音
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

    // 停止录音
    if (isRecording) {
        isRecording = false;
        if (window.currentStream) {
            window.currentStream.getTracks().forEach(track => track.stop());
        }
        if (audioContext) {
            audioContext.close();
        }
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
        showAIQuestion();
    }
}

function goHome() {
    // 确保停止录音
    if (isRecording) {
        isRecording = false;
        if (window.currentStream) {
            window.currentStream.getTracks().forEach(track => track.stop());
        }
    }

    storage.remove('currentConversationId');
    window.location.href = 'index.html';
}

// 页面关闭时清理
window.onbeforeunload = function() {
    if (isRecording && window.currentStream) {
        window.currentStream.getTracks().forEach(track => track.stop());
    }
};
