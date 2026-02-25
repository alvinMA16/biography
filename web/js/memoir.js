// 回忆录页面逻辑

let refreshTimer = null;

// 页面加载
window.onload = async function() {
    await loadMemoirs();
};

// 页面卸载时清除定时器
window.onbeforeunload = function() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
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
            stopAutoRefresh();
            return;
        }

        renderMemoirs(memoirs);

        // 如果有撰写中的回忆录，启动自动刷新
        const hasGenerating = memoirs.some(m => m.status === 'generating');
        if (hasGenerating) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    } catch (error) {
        console.error('加载回忆录失败:', error);
        showEmptyState();
    }
}

// 启动自动刷新
function startAutoRefresh() {
    if (refreshTimer) return;
    refreshTimer = setInterval(() => {
        loadMemoirs();
    }, 5000); // 每5秒刷新一次
}

// 停止自动刷新
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// 渲染回忆录列表
function renderMemoirs(memoirs) {
    const listContainer = document.getElementById('memoirList');
    document.getElementById('emptyState').style.display = 'none';

    listContainer.innerHTML = memoirs.map(memoir => {
        const isGenerating = memoir.status === 'generating';
        const timeText = formatTimeRange(memoir.conversation_start, memoir.conversation_end);

        return `
            <div class="memoir-item ${isGenerating ? 'generating' : ''}"
                 ${isGenerating ? '' : `onclick="viewMemoir('${memoir.id}')"`}>
                <div class="memoir-item-header">
                    <h3>${memoir.title}</h3>
                    ${isGenerating ? '<span class="memoir-status">撰写中...</span>' : ''}
                </div>
                ${timeText ? `<p class="memoir-time">${timeText}</p>` : ''}
            </div>
        `;
    }).join('');
}

// 格式化时间范围
function formatTimeRange(start, end) {
    if (!start) return '';

    // 如果开始和结束在同一天，只显示日期一次
    if (start && end) {
        const startDate = start.split(' ')[0];
        const endDate = end.split(' ')[0];
        const startTime = start.split(' ')[1];
        const endTime = end.split(' ')[1];

        if (startDate === endDate) {
            return `${startDate} ${startTime} - ${endTime}`;
        } else {
            return `${start} - ${end}`;
        }
    }

    return start;
}

// 显示空状态
function showEmptyState() {
    document.getElementById('memoirList').innerHTML = '';
    document.getElementById('emptyState').style.display = 'block';
}

// 查看回忆录详情 - 跳转到详情页
function viewMemoir(memoirId) {
    window.location.href = `memoir-detail.html?id=${memoirId}`;
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
