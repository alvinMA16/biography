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
