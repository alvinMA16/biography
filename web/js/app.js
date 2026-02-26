// 首页逻辑

// Debug 模式检测
const DEBUG_MODE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

// 初始化应用
async function initApp() {
    // 如果是 debug 模式，显示时代记忆入口
    if (DEBUG_MODE) {
        const eraMemoriesBtn = document.getElementById('eraMemoriesBtn');
        if (eraMemoriesBtn) {
            eraMemoriesBtn.style.display = 'block';
        }
    }
    // 确保弹窗初始状态是关闭的
    closeRecorderModal();

    let userId = storage.get('userId');

    // 如果没有用户，创建一个新用户并启动引导流程
    if (!userId) {
        await createNewUser();
        return;
    }

    // 检查用户是否存在且完成了信息收集
    try {
        const profile = await api.user.getProfile(userId);

        if (profile.profile_completed) {
            // 用户已完成信息收集，清除临时标记，正常显示主页
            storage.remove('profileJustCompleted');
            return;
        }

        // profile_completed 还是 false
        // 检查是否有 profileJustCompleted 标记（说明刚从信息收集对话返回，后台还在处理）
        if (storage.get('profileJustCompleted')) {
            console.log('信息收集刚完成，后台正在处理，跳过引导流程');
            // 不清除标记，等下次 profile_completed 变为 true 时再清除
            return;
        }

        // 未完成信息收集，也没有临时标记，启动引导流程
        startOnboarding();

    } catch (error) {
        console.error('获取用户信息失败:', error);
        // 用户不存在（可能数据库重置了），重新创建
        if (error.message.includes('不存在')) {
            storage.remove('userId');
            storage.remove('currentConversationId');
            storage.remove('selectedRecorder');
            storage.remove('profileJustCompleted');
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

    // 不默认选中，让用户自己选择
    pendingRecorder = null;
    updateRecorderSelection(null);
}

// 开始新对话 - 先选择话题
async function startNewChat() {
    const userId = storage.get('userId');
    if (!userId) {
        alert('请先刷新页面');
        return;
    }

    // 显示话题选择弹窗
    openTopicModal();
}

// ========== 话题选择 ==========

// 话题弹窗标题候选
const TOPIC_MODAL_TITLES = [
    "这次想聊聊哪段经历？",
    "您想从哪里开始讲起？",
    "今天想回忆点什么？",
    "咱们聊聊什么好？",
    "您想讲讲哪方面的事？",
];

function openTopicModal() {
    const modal = document.getElementById('topicModal');
    modal.style.display = 'flex';

    // 随机选择标题
    const title = TOPIC_MODAL_TITLES[Math.floor(Math.random() * TOPIC_MODAL_TITLES.length)];
    document.getElementById('topicModalTitle').textContent = title;

    loadTopicOptions();
}

function closeTopicModal() {
    document.getElementById('topicModal').style.display = 'none';
}

async function loadTopicOptions() {
    const userId = storage.get('userId');
    if (!userId) return;

    const container = document.getElementById('topicOptions');
    container.innerHTML = `
        <div class="topic-loading">
            <div class="loading-dots"><span></span><span></span><span></span></div>
            <p>正在回顾您的故事，请稍等</p>
        </div>
    `;

    try {
        const data = await api.topic.getOptions(userId);
        const options = data.options || [];

        if (options.length === 0) {
            container.innerHTML = '<p class="topic-empty">暂时没有准备好话题，请稍后再试</p>';
            return;
        }

        // 保存选项数据供点击时使用
        window._topicOptions = options;

        container.innerHTML = options.map((opt, index) => `
            <div class="topic-option" onclick="selectTopicByIndex(${index})">
                <div class="topic-title">${escapeHtml(opt.topic)}</div>
            </div>
        `).join('');

    } catch (error) {
        console.error('加载话题失败:', error);
        container.innerHTML = '<p class="topic-empty">加载失败，请稍后重试</p>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 通过索引选择话题（避免 HTML 转义问题）
async function selectTopicByIndex(index) {
    const options = window._topicOptions || [];
    if (index < 0 || index >= options.length) return;

    const opt = options[index];
    await selectTopic(opt.id, opt.topic, opt.greeting, opt.context);
}

async function selectTopic(topicId, topic, greeting, context) {
    const userId = storage.get('userId');
    if (!userId) {
        alert('请先刷新页面');
        return;
    }

    closeTopicModal();

    try {
        // 创建新对话
        const result = await api.conversation.start(userId);
        storage.set('currentConversationId', result.conversation_id);

        // 存储选择的话题信息
        storage.set('selectedTopic', topic);
        storage.set('selectedTopicGreeting', greeting);
        storage.set('selectedTopicContext', context || '');

        // 跳转到对话页面
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

    // 不默认选中，让用户必须手动点击
    pendingRecorder = null;
    updateRecorderSelection(null);
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
    // 必须选择一个记录师
    if (!pendingRecorder) {
        alert('请先选择一位记录师');
        return;
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

// ========== 时代记忆 ==========

async function viewEraMemories() {
    const dropdown = document.getElementById('userDropdown');
    dropdown.classList.remove('show');

    const modal = document.getElementById('eraMemoriesModal');
    modal.style.display = 'flex';

    // 加载时代记忆
    await loadEraMemories();
}

function closeEraMemoriesModal() {
    stopEraMemoriesPolling();
    document.getElementById('eraMemoriesModal').style.display = 'none';
}

// 轮询检查时代记忆状态
let eraMemoriesPollingTimer = null;

async function loadEraMemories() {
    const userId = storage.get('userId');
    if (!userId) {
        return;
    }

    const contentEl = document.getElementById('eraMemoriesContent');
    const statusEl = document.getElementById('eraMemoriesStatus');
    const birthYearEl = document.getElementById('eraInfoBirthYear');
    const hometownEl = document.getElementById('eraInfoHometown');
    const mainCityEl = document.getElementById('eraInfoMainCity');
    const regenerateBtn = document.getElementById('regenerateBtn');

    contentEl.innerHTML = '<p class="loading-text">加载中...</p>';

    try {
        const data = await api.user.getEraMemories(userId);

        // 更新用户信息
        birthYearEl.textContent = data.birth_year || '-';
        hometownEl.textContent = data.hometown || '-';
        mainCityEl.textContent = data.main_city || '-';

        // 根据状态显示不同内容
        const status = data.era_memories_status || 'none';
        updateEraMemoriesStatus(status);

        if (status === 'completed' && data.era_memories) {
            contentEl.textContent = data.era_memories;
            regenerateBtn.disabled = false;
            regenerateBtn.textContent = '重新生成';
            stopEraMemoriesPolling();
        } else if (status === 'generating') {
            contentEl.innerHTML = '<p class="loading-text">正在生成中，请稍候...</p>';
            regenerateBtn.disabled = true;
            regenerateBtn.textContent = '生成中...';
            // 启动轮询
            startEraMemoriesPolling();
        } else if (status === 'pending') {
            contentEl.innerHTML = '<p class="empty-text">已收集基础信息，等待生成时代记忆</p>';
            regenerateBtn.disabled = false;
            regenerateBtn.textContent = '开始生成';
            stopEraMemoriesPolling();
        } else if (status === 'failed') {
            contentEl.innerHTML = '<p class="empty-text">生成失败，请点击下方按钮重试</p>';
            regenerateBtn.disabled = false;
            regenerateBtn.textContent = '重新生成';
            stopEraMemoriesPolling();
        } else {
            // none - 未收集基础信息
            contentEl.innerHTML = '<p class="empty-text">请先完成信息收集（出生年份）后再查看</p>';
            regenerateBtn.disabled = true;
            regenerateBtn.textContent = '重新生成';
            stopEraMemoriesPolling();
        }
    } catch (error) {
        console.error('加载时代记忆失败:', error);
        contentEl.innerHTML = '<p class="empty-text">加载失败，请稍后重试</p>';
    }
}

function updateEraMemoriesStatus(status) {
    const statusEl = document.getElementById('eraMemoriesStatus');
    const statusMap = {
        'none': { text: '未收集', class: 'status-none' },
        'pending': { text: '待生成', class: 'status-pending' },
        'generating': { text: '生成中', class: 'status-generating' },
        'completed': { text: '已完成', class: 'status-completed' },
        'failed': { text: '生成失败', class: 'status-failed' }
    };
    const info = statusMap[status] || statusMap['none'];
    statusEl.textContent = info.text;
    statusEl.className = 'era-status-badge ' + info.class;
}

function startEraMemoriesPolling() {
    if (eraMemoriesPollingTimer) return;
    eraMemoriesPollingTimer = setInterval(() => {
        loadEraMemories();
    }, 3000);
}

function stopEraMemoriesPolling() {
    if (eraMemoriesPollingTimer) {
        clearInterval(eraMemoriesPollingTimer);
        eraMemoriesPollingTimer = null;
    }
}

async function regenerateEraMemories() {
    const userId = storage.get('userId');
    if (!userId) {
        return;
    }

    const contentEl = document.getElementById('eraMemoriesContent');
    const regenerateBtn = document.getElementById('regenerateBtn');

    contentEl.innerHTML = '<p class="loading-text">正在生成...</p>';
    updateEraMemoriesStatus('generating');
    regenerateBtn.disabled = true;
    regenerateBtn.textContent = '生成中...';

    try {
        const data = await api.user.regenerateEraMemories(userId);

        if (data.era_memories) {
            contentEl.textContent = data.era_memories;
            updateEraMemoriesStatus('completed');
            regenerateBtn.disabled = false;
            regenerateBtn.textContent = '重新生成';
        } else {
            contentEl.innerHTML = '<p class="empty-text">生成失败，请确保已填写出生年份</p>';
            updateEraMemoriesStatus('failed');
            regenerateBtn.disabled = false;
            regenerateBtn.textContent = '重新生成';
        }
    } catch (error) {
        console.error('重新生成时代记忆失败:', error);
        contentEl.innerHTML = '<p class="empty-text">生成失败: ' + error.message + '</p>';
        updateEraMemoriesStatus('failed');
        regenerateBtn.disabled = false;
        regenerateBtn.textContent = '重新生成';
    }
}
