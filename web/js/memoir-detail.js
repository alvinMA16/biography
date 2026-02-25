// 回忆录详情页逻辑

let currentMemoir = null;
let conversationMessages = null;
let currentPerspective = '第一人称';

// 页面加载
window.onload = async function() {
    const memoirId = new URLSearchParams(window.location.search).get('id');

    if (!memoirId) {
        alert('未找到回忆录');
        goBack();
        return;
    }

    await loadMemoir(memoirId);
};

// 加载回忆录
async function loadMemoir(memoirId) {
    try {
        currentMemoir = await api.memoir.get(memoirId);

        document.getElementById('memoirTitle').textContent = currentMemoir.title;
        document.getElementById('memoirContent').textContent = currentMemoir.content || '（内容为空）';

        // 如果有关联的对话，加载对话记录
        if (currentMemoir.conversation_id) {
            loadTranscript(currentMemoir.conversation_id);
        }
    } catch (error) {
        console.error('加载回忆录失败:', error);
        alert('加载失败: ' + error.message);
        goBack();
    }
}

// 加载对话记录
async function loadTranscript(conversationId) {
    try {
        const conversation = await api.conversation.get(conversationId);
        conversationMessages = conversation.messages || [];

        renderTranscript();
    } catch (error) {
        console.error('加载对话记录失败:', error);
        document.getElementById('transcriptContent').innerHTML =
            '<div class="no-transcript">无法加载对话记录</div>';
    }
}

// 渲染对话记录
function renderTranscript() {
    const container = document.getElementById('transcriptContent');

    if (!conversationMessages || conversationMessages.length === 0) {
        container.innerHTML = '<div class="no-transcript">暂无对话记录</div>';
        return;
    }

    container.innerHTML = conversationMessages.map(msg => {
        const roleText = msg.role === 'user' ? '用户' : '记录师';
        const roleClass = msg.role === 'user' ? 'user' : 'assistant';
        return `
            <div class="transcript-message ${roleClass}">
                <div class="role">${roleText}</div>
                <div class="content">${msg.content}</div>
            </div>
        `;
    }).join('');
}

// 切换对话记录面板
function toggleTranscript() {
    const panel = document.getElementById('transcriptPanel');
    const overlay = document.getElementById('transcriptOverlay');

    panel.classList.toggle('open');
    overlay.classList.toggle('open');
}

// 切换人称选择器
function togglePerspective() {
    const selector = document.getElementById('perspectiveSelector');
    selector.classList.toggle('open');
}

// 选择人称
function selectPerspective(value) {
    currentPerspective = value;
    document.getElementById('perspectiveLabel').textContent = value;

    // 更新选中状态
    document.querySelectorAll('.perspective-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.value === value);
    });

    // 关闭下拉菜单
    document.getElementById('perspectiveSelector').classList.remove('open');
}

// 点击其他地方关闭下拉菜单
document.addEventListener('click', function(e) {
    const selector = document.getElementById('perspectiveSelector');
    if (selector && !selector.contains(e.target)) {
        selector.classList.remove('open');
    }
});

// 重新生成回忆录
async function regenerateMemoir() {
    if (!currentMemoir) return;

    const btn = document.getElementById('regenerateBtn');
    const originalHTML = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = `
        <div class="spinner"></div>
        <span>生成中</span>
    `;

    try {
        const memoir = await api.memoir.regenerate(currentMemoir.id, currentPerspective);

        // 更新显示
        document.getElementById('memoirContent').textContent = memoir.content;
        currentMemoir = memoir;

        btn.innerHTML = originalHTML;
        btn.disabled = false;
    } catch (error) {
        console.error('重新生成失败:', error);
        alert('重新生成失败: ' + error.message);
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

// 返回
function goBack() {
    window.location.href = 'memoir.html';
}
