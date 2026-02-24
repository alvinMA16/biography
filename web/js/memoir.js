// 回忆录页面逻辑

// 页面加载
window.onload = async function() {
    await loadMemoirs();
};

// 加载回忆录列表
async function loadMemoirs() {
    const userId = storage.get('userId');

    if (!userId) {
        showEmptyState();
        return;
    }

    try {
        const memoirs = await api.memoir.list(userId);

        if (memoirs.length === 0) {
            showEmptyState();
            return;
        }

        renderMemoirs(memoirs);
    } catch (error) {
        console.error('加载回忆录失败:', error);
        showEmptyState();
    }
}

// 渲染回忆录列表
function renderMemoirs(memoirs) {
    const listContainer = document.getElementById('memoirList');
    document.getElementById('emptyState').style.display = 'none';

    listContainer.innerHTML = memoirs.map(memoir => `
        <div class="memoir-item" onclick="viewMemoir('${memoir.id}')">
            <h3>${memoir.title}</h3>
        </div>
    `).join('');
}

// 显示空状态
function showEmptyState() {
    document.getElementById('memoirList').innerHTML = '';
    document.getElementById('emptyState').style.display = 'block';
}

// 查看回忆录详情
async function viewMemoir(memoirId) {
    try {
        const memoir = await api.memoir.get(memoirId);

        document.getElementById('memoirTitle').textContent = memoir.title;
        document.getElementById('memoirContent').textContent = memoir.content;
        document.getElementById('memoirModal').style.display = 'flex';
    } catch (error) {
        console.error('加载回忆录失败:', error);
        alert('加载失败: ' + error.message);
    }
}

// 关闭弹窗
function closeModal() {
    document.getElementById('memoirModal').style.display = 'none';
}

// 返回首页
function goHome() {
    window.location.href = 'index.html';
}

// 点击弹窗外部关闭
document.addEventListener('click', function(event) {
    const modal = document.getElementById('memoirModal');
    if (event.target === modal) {
        closeModal();
    }
});
