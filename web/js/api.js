// API 配置
const API_BASE_URL = 'http://localhost:8001/api';

// API 请求封装
const api = {
    // 通用请求方法
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '请求失败');
            }
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // 用户相关
    user: {
        async create(nickname = null) {
            return api.request('/user/create', {
                method: 'POST',
                body: JSON.stringify({ nickname }),
            });
        },

        async get(userId) {
            return api.request(`/user/${userId}`);
        },

        async updateSettings(userId, settings) {
            return api.request(`/user/${userId}/settings`, {
                method: 'PUT',
                body: JSON.stringify(settings),
            });
        },
    },

    // 对话相关
    conversation: {
        async start(userId) {
            return api.request(`/conversation/start?user_id=${userId}`, {
                method: 'POST',
            });
        },

        async chat(conversationId, message) {
            return api.request(`/conversation/${conversationId}/chat`, {
                method: 'POST',
                body: JSON.stringify({ message }),
            });
        },

        async chatStream(conversationId, message, onChunk) {
            const response = await fetch(`${API_BASE_URL}/conversation/${conversationId}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message }),
            });

            if (!response.ok) {
                throw new Error('请求失败');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value);
                const lines = text.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') {
                            return fullText;
                        }
                        fullText += data;
                        onChunk(data, fullText);
                    }
                }
            }

            return fullText;
        },

        async end(conversationId) {
            return api.request(`/conversation/${conversationId}/end`, {
                method: 'POST',
            });
        },

        async endQuick(conversationId) {
            return api.request(`/conversation/${conversationId}/end-quick`, {
                method: 'POST',
            });
        },

        async get(conversationId) {
            return api.request(`/conversation/${conversationId}`);
        },

        async list(userId) {
            return api.request(`/conversation/user/${userId}/list`);
        },

        async empathy(text) {
            return api.request('/conversation/empathy', {
                method: 'POST',
                body: JSON.stringify({ text }),
            });
        },
    },

    // 语音识别相关
    asr: {
        async recognize(audioBlob) {
            const formData = new FormData();
            formData.append('file', audioBlob, 'audio.wav');

            const response = await fetch(`${API_BASE_URL}/asr/recognize`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '语音识别失败');
            }

            return await response.json();
        },
    },

    // 回忆录相关
    memoir: {
        async generate(userId, conversationId, title = null, perspective = '第一人称') {
            return api.request(`/memoir/generate?user_id=${userId}`, {
                method: 'POST',
                body: JSON.stringify({ conversation_id: conversationId, title, perspective }),
            });
        },

        // 异步生成回忆录（不等待完成）
        generateAsync(userId, conversationId, title = null, perspective = '第一人称') {
            fetch(`${API_BASE_URL}/memoir/generate-async?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ conversation_id: conversationId, title, perspective }),
            }).catch(err => console.error('异步生成回忆录失败:', err));
        },

        async list(userId) {
            return api.request(`/memoir/user/${userId}/list`);
        },

        async get(memoirId) {
            return api.request(`/memoir/${memoirId}`);
        },

        async update(memoirId, data) {
            return api.request(`/memoir/${memoirId}`, {
                method: 'PUT',
                body: JSON.stringify(data),
            });
        },

        async delete(memoirId) {
            return api.request(`/memoir/${memoirId}`, {
                method: 'DELETE',
            });
        },
    },
};

// 本地存储工具
const storage = {
    get(key) {
        const value = localStorage.getItem(key);
        try {
            return JSON.parse(value);
        } catch {
            return value;
        }
    },

    set(key, value) {
        localStorage.setItem(key, JSON.stringify(value));
    },

    remove(key) {
        localStorage.removeItem(key);
    },
};
