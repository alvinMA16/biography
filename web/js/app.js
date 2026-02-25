// 首页逻辑

// 初始化应用
async function initApp() {
    let userId = storage.get('userId');

    // 如果没有用户，创建一个
    if (!userId) {
        try {
            const user = await api.user.create();
            userId = user.id;
            storage.set('userId', userId);
        } catch (error) {
            console.error('创建用户失败:', error);
            alert('连接服务器失败，请确保后端服务已启动');
            return;
        }
    }
}

// 开始新对话
async function startNewChat() {
    const userId = storage.get('userId');
    if (!userId) {
        alert('请先刷新页面');
        return;
    }

    try {
        const result = await api.conversation.start(userId);
        storage.set('currentConversationId', result.conversation_id);
        window.location.href = 'chat.html';
    } catch (error) {
        console.error('开始对话失败:', error);
        alert('开始对话失败: ' + error.message);
    }
}

// 查看回忆录
function viewMemoirs() {
    window.location.href = 'memoir.html';
}

// 切换下拉菜单
function toggleDropdown() {
    const dropdown = document.getElementById('userDropdown');
    dropdown.classList.toggle('show');
}

// 登出
function logout() {
    if (confirm('确定要登出吗？登出后本地数据将被清除。')) {
        storage.remove('userId');
        storage.remove('currentConversationId');
        storage.remove('selectedRecorder');
        window.location.reload();
    }
}

// ========== 记录师选择 ==========

const RECORDERS = {
    female: {
        name: '忆安',
        speaker: 'zh_female_vv_jupiter_bigtts',
        greeting: '您好，我是小安。很高兴能成为您的人生记录师，期待听您讲述那些珍贵的回忆。'
    },
    male: {
        name: '言川',
        speaker: 'zh_male_xiaotian_jupiter_bigtts',
        greeting: '您好，我是小川。能够记录您的人生故事，是我的荣幸。请慢慢讲，我都在听。'
    }
};

// 打开记录师选择弹窗
function openRecorderSelect() {
    const dropdown = document.getElementById('userDropdown');
    dropdown.classList.remove('show');

    const modal = document.getElementById('recorderModal');
    modal.style.display = 'flex';

    // 高亮当前选择的记录师
    const selected = storage.get('selectedRecorder') || 'female';
    pendingRecorder = selected;
    updateRecorderSelection(selected);
}

// 关闭记录师选择弹窗
function closeRecorderModal() {
    document.getElementById('recorderModal').style.display = 'none';
    stopPreviewAudio();
}

// 更新记录师选择的高亮状态
function updateRecorderSelection(gender) {
    document.getElementById('recorderFemale').classList.toggle('selected', gender === 'female');
    document.getElementById('recorderMale').classList.toggle('selected', gender === 'male');
}

// 选择记录师
let previewWs = null;
let previewAudioContext = null;
let previewAudioQueue = [];
let previewNextPlayTime = 0;
let pendingRecorder = null;  // 待确认的选择

async function selectRecorder(gender) {
    pendingRecorder = gender;
    updateRecorderSelection(gender);

    // 播放开场白预览
    await playRecorderGreeting(gender);
}

// 确认选择记录师
function confirmRecorder() {
    if (!pendingRecorder) {
        pendingRecorder = storage.get('selectedRecorder') || 'female';
    }

    storage.set('selectedRecorder', pendingRecorder);
    stopPreviewAudio();
    closeRecorderModal();
}

// 播放记录师开场白
async function playRecorderGreeting(gender) {
    stopPreviewAudio();

    const recorder = RECORDERS[gender];
    const hostname = window.location.hostname || 'localhost';
    const wsUrl = `ws://${hostname}:8001/api/realtime/preview?speaker=${encodeURIComponent(recorder.speaker)}&text=${encodeURIComponent(recorder.greeting)}`;

    try {
        previewAudioContext = new AudioContext({ sampleRate: 24000 });

        previewWs = new WebSocket(wsUrl);

        previewWs.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'audio') {
                const audioData = base64ToArrayBuffer(message.data);
                playPreviewAudio(audioData);
            } else if (message.type === 'done') {
                // 播放完成
            }
        };

        previewWs.onerror = (error) => {
            console.error('预览音频失败:', error);
        };

    } catch (error) {
        console.error('播放开场白失败:', error);
    }
}

function playPreviewAudio(audioData) {
    if (!previewAudioContext) return;

    const floatData = pcm16LEToFloat32Preview(audioData);
    if (floatData.length === 0) return;

    const audioBuffer = previewAudioContext.createBuffer(1, floatData.length, 24000);
    audioBuffer.getChannelData(0).set(floatData);

    const source = previewAudioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(previewAudioContext.destination);

    const currentTime = previewAudioContext.currentTime;
    if (previewNextPlayTime < currentTime) {
        previewNextPlayTime = currentTime + 0.01;
    }

    source.start(previewNextPlayTime);
    previewNextPlayTime += audioBuffer.duration;
}

function pcm16LEToFloat32Preview(arrayBuffer) {
    const dataView = new DataView(arrayBuffer);
    const numSamples = arrayBuffer.byteLength / 2;
    const float32 = new Float32Array(numSamples);
    for (let i = 0; i < numSamples; i++) {
        const int16 = dataView.getInt16(i * 2, true);
        float32[i] = int16 / 32768.0;
    }
    return float32;
}

function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

function stopPreviewAudio() {
    if (previewWs) {
        previewWs.close();
        previewWs = null;
    }
    if (previewAudioContext) {
        previewAudioContext.close();
        previewAudioContext = null;
    }
    previewAudioQueue = [];
    previewNextPlayTime = 0;
}
