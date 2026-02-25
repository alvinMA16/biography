// 首页逻辑

// 初始化应用
async function initApp() {
    // 确保弹窗初始状态是关闭的
    closeRecorderModal();

    let userId = storage.get('userId');

    // 如果没有用户，创建一个新用户并启动引导流程
    if (!userId) {
        await createNewUser();
        return;
    }

    // 检查是否刚完成信息收集（从对话页面返回）
    // 这是为了处理后台异步更新 profile_completed 的竞态条件
    if (storage.get('profileJustCompleted')) {
        storage.remove('profileJustCompleted');
        console.log('信息收集刚完成，跳过引导流程');
        // 不需要再检查 profile_completed，直接显示主页
        return;
    }

    // 检查用户是否存在且完成了信息收集
    try {
        const profile = await api.user.getProfile(userId);
        if (!profile.profile_completed) {
            // 未完成信息收集，继续引导流程
            startOnboarding();
            return;
        }
        // 用户已完成信息收集，正常显示主页
    } catch (error) {
        console.error('获取用户信息失败:', error);
        // 用户不存在（可能数据库重置了），重新创建
        if (error.message.includes('不存在')) {
            storage.remove('userId');
            storage.remove('currentConversationId');
            storage.remove('selectedRecorder');
            await createNewUser();
            return;
        }
    }
}

// 创建新用户
async function createNewUser() {
    try {
        const user = await api.user.create();
        storage.set('userId', user.id);
        // 新用户，启动引导流程
        startOnboarding();
    } catch (error) {
        console.error('创建用户失败:', error);
        alert('连接服务器失败，请确保后端服务已启动');
    }
}

// 启动新用户引导流程
function startOnboarding() {
    // 显示记录师选择弹窗，确认后进入信息收集对话
    const modal = document.getElementById('recorderModal');
    modal.style.display = 'flex';

    // 修改确认按钮的行为
    window.onboardingMode = true;

    // 默认选中女性记录师
    pendingRecorder = 'female';
    updateRecorderSelection('female');
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

// 退出登录（保留服务器数据，只清除本地登录状态）
function logout() {
    if (confirm('确定要退出登录吗？下次登录需要重新创建账号。')) {
        storage.remove('userId');
        storage.remove('currentConversationId');
        storage.remove('selectedRecorder');
        window.location.reload();
    }
}

// 注销账号（删除服务器上的所有数据）
async function deleteAccount() {
    const userId = storage.get('userId');
    if (!userId) {
        alert('当前没有登录账号');
        return;
    }

    if (!confirm('确定要注销账号吗？\n\n注销后，您的所有回忆和对话记录都将被永久删除，无法恢复。')) {
        return;
    }

    // 二次确认
    if (!confirm('请再次确认：真的要删除所有数据吗？')) {
        return;
    }

    try {
        await api.user.delete(userId);
        storage.remove('userId');
        storage.remove('currentConversationId');
        storage.remove('selectedRecorder');
        alert('账号已注销');
        window.location.reload();
    } catch (error) {
        console.error('注销账号失败:', error);
        alert('注销失败: ' + error.message);
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
async function confirmRecorder() {
    if (!pendingRecorder) {
        pendingRecorder = storage.get('selectedRecorder') || 'female';
    }

    storage.set('selectedRecorder', pendingRecorder);
    stopPreviewAudio();
    closeRecorderModal();

    // 如果是引导模式，进入信息收集对话
    if (window.onboardingMode) {
        window.onboardingMode = false;
        await startProfileCollection();
    }
}

// 进入信息收集对话
async function startProfileCollection() {
    const userId = storage.get('userId');
    if (!userId) {
        alert('请先刷新页面');
        return;
    }

    try {
        // 创建新对话
        const result = await api.conversation.start(userId);
        storage.set('currentConversationId', result.conversation_id);
        // 跳转到对话页面（会自动检测到未完成信息收集）
        window.location.href = 'chat.html';
    } catch (error) {
        console.error('开始信息收集失败:', error);
        alert('开始对话失败: ' + error.message);
    }
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
