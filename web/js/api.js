// API 配置
const API_BASE_URL = '/api';

// API 请求封装
const api = {
    // 通用请求方法
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const token = storage.get('token');
        const headers = {
            'Content-Type': 'application/json',
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const config = {
            headers,
            ...options,
            // 确保自定义 headers 与默认 headers 合并
            headers: { ...headers, ...(options.headers || {}) },
        };

        try {
            const response = await fetch(url, config);
            if (response.status === 401) {
                // token 无效或过期，跳转登录页
                storage.remove('token');
                storage.remove('userId');
                window.location.href = 'login.html';
                return;
            }
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

    // 认证相关
    auth: {
        async login(phone, password) {
            return api.request('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ phone, password }),
            });
        },
    },

    // 用户相关
    user: {
        async get() {
            return api.request('/user/me');
        },

        async updateSettings(settings) {
            return api.request('/user/me/settings', {
                method: 'PUT',
                body: JSON.stringify(settings),
            });
        },

        async getProfile() {
            return api.request('/user/me/profile');
        },

        async completeProfile() {
            return api.request('/user/me/complete-profile', {
                method: 'POST',
            });
        },

        async delete() {
            return api.request('/user/me', {
                method: 'DELETE',
            });
        },

        async getEraMemories() {
            return api.request('/user/me/era-memories');
        },

        async regenerateEraMemories() {
            return api.request('/user/me/era-memories/regenerate', {
                method: 'POST',
            });
        },
    },

    // 对话相关
    conversation: {
        async start() {
            return api.request('/conversation/start', {
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
            const token = storage.get('token');
            const headers = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            const response = await fetch(`${API_BASE_URL}/conversation/${conversationId}/chat/stream`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ message }),
            });

            if (response.status === 401) {
                storage.remove('token');
                storage.remove('userId');
                window.location.href = 'login.html';
                return;
            }

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

        async list() {
            return api.request('/conversation/list');
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

    // 话题相关
    topic: {
        async getOptions() {
            return api.request('/topic/options');
        },

        async refresh() {
            return api.request('/topic/refresh', {
                method: 'POST',
            });
        },

        async get(topicId) {
            return api.request(`/topic/${topicId}`);
        },
    },

    // 回忆录相关
    memoir: {
        async generate(conversationId, title = null, perspective = '第一人称') {
            return api.request('/memoir/generate', {
                method: 'POST',
                body: JSON.stringify({ conversation_id: conversationId, title, perspective }),
            });
        },

        // 异步生成回忆录（不等待完成）
        generateAsync(conversationId, title = null, perspective = '第一人称') {
            const token = storage.get('token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            fetch(`${API_BASE_URL}/memoir/generate-async`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ conversation_id: conversationId, title, perspective }),
            }).catch(err => console.error('异步生成回忆录失败:', err));
        },

        async list() {
            return api.request('/memoir/list');
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

        async regenerate(memoirId, perspective = '第一人称') {
            return api.request(`/memoir/${memoirId}/regenerate`, {
                method: 'POST',
                body: JSON.stringify({ perspective }),
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
