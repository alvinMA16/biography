// 聊天页面逻辑 - 沉浸式单轮对话

let conversationId = null;

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

// 加载最新的AI问题
async function loadLatestQuestion() {
    try {
        const conversation = await api.conversation.get(conversationId);

        if (conversation.messages && conversation.messages.length > 0) {
            // 找到最后一条AI消息
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

        showConversation();
    } catch (error) {
        console.error('加载失败:', error);
        alert('加载失败，请重试');
    }
}

// 显示对话区域
function showConversation() {
    document.getElementById('conversationFocus').style.display = 'block';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('messageInput').focus();
}

// 显示加载状态
function showLoading() {
    document.getElementById('conversationFocus').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
}

// 发送消息
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message) return;

    // 清空输入框
    input.value = '';

    // 显示加载
    showLoading();

    try {
        const response = await api.conversation.chat(conversationId, message);

        // 更新AI问题为新的回复
        document.getElementById('aiQuestion').textContent = response.message;

        // 显示对话区域
        showConversation();
    } catch (error) {
        console.error('发送失败:', error);
        alert('发送失败: ' + error.message);
        showConversation();
    }
}

// 处理回车键
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// 结束对话
async function endChat() {
    if (!confirm('确定要结束这次对话吗？')) {
        return;
    }

    showLoading();

    try {
        // 结束对话
        await api.conversation.end(conversationId);

        // 询问是否生成回忆录
        if (confirm('是否要把这次对话整理成回忆录？')) {
            const userId = storage.get('userId');
            await api.memoir.generate(userId, conversationId);
            alert('回忆录已生成！');
        }

        goHome();
    } catch (error) {
        console.error('结束对话失败:', error);
        alert('操作失败: ' + error.message);
        showConversation();
    }
}

// 返回首页
function goHome() {
    storage.remove('currentConversationId');
    window.location.href = 'index.html';
}
