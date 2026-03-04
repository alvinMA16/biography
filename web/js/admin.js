// Admin 页面逻辑
const API_BASE = '/api';
let adminKey = '';
let usersData = [];
let logsLoaded = false;

// ========== Admin Key 验证 ==========

function getAdminKey() {
    return adminKey || sessionStorage.getItem('adminKey') || '';
}

function setAdminKey(key) {
    adminKey = key;
    sessionStorage.setItem('adminKey', key);
}

async function adminRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const key = getAdminKey().replace(/[^\x00-\xff]/g, '');
    const headers = {
        'X-Admin-Key': key,
        ...(options.headers || {}),
    };
    if (options.body) {
        headers['Content-Type'] = 'application/json';
    }
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(err.detail || '请求失败');
    }
    return response.json();
}

async function verifyKey() {
    const input = document.getElementById('adminKeyInput');
    const key = input.value.trim();
    if (!key) return;

    setAdminKey(key);
    try {
        await loadUsers();
        document.getElementById('authSection').style.display = 'none';
        document.getElementById('mainSection').style.display = 'flex';
    } catch (e) {
        setAdminKey('');
        sessionStorage.removeItem('adminKey');
        alert('Admin Key 验证失败');
    }
}

function logout() {
    adminKey = '';
    sessionStorage.removeItem('adminKey');
    usersData = [];
    logsLoaded = false;
    llmHealthLoaded = false;
    llmModelsData = [];
    llmTestResults = {};
    document.getElementById('mainSection').style.display = 'none';
    document.getElementById('authSection').style.display = 'flex';
    document.getElementById('adminKeyInput').value = '';
    // 重置 tab 到用户管理
    switchTab('users');
}

// ========== Tab 切换 ==========

let eraMemoriesLoaded = false;
let welcomeMessagesLoaded = false;
let presetTopicsLoaded = false;
let monitoringLoaded = false;
let monitoringData = null;
let llmHealthLoaded = false;
let llmModelsData = [];
let llmTestResults = {};

function switchTab(tab) {
    // 更新侧边栏选中态
    document.querySelectorAll('.admin-nav-item[data-tab]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    // 显示/隐藏面板
    document.querySelectorAll('.admin-tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    if (tab === 'users') {
        document.getElementById('tabUsers').classList.add('active');
    } else if (tab === 'logs') {
        document.getElementById('tabLogs').classList.add('active');
        if (!logsLoaded) loadLogs();
    } else if (tab === 'era-memories') {
        document.getElementById('tabEraMemories').classList.add('active');
        if (!eraMemoriesLoaded) loadEraMemories();
    } else if (tab === 'welcome-messages') {
        document.getElementById('tabWelcomeMessages').classList.add('active');
        if (!welcomeMessagesLoaded) loadWelcomeMessages();
    } else if (tab === 'preset-topics') {
        document.getElementById('tabPresetTopics').classList.add('active');
        if (!presetTopicsLoaded) loadPresetTopics();
    } else if (tab === 'monitoring') {
        document.getElementById('tabMonitoring').classList.add('active');
        if (!monitoringLoaded) loadMonitoringData();
    } else if (tab === 'llm-health') {
        document.getElementById('tabLlmHealth').classList.add('active');
        if (!llmHealthLoaded) loadLlmModels();
    }
}

// ========== 用户列表 ==========

async function loadUsers() {
    const users = await adminRequest('/admin/users');
    usersData = users;
    renderUserTable(users);
}

function renderUserTable(users) {
    const tbody = document.getElementById('userTableBody');
    if (!users.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="admin-table-empty">暂无用户</td></tr>';
        return;
    }
    tbody.innerHTML = users.map(u => {
        const isActive = u.is_active !== false;
        const label = (u.phone || u.nickname || '').replace(/'/g, "\\'");
        return `
        <tr${!isActive ? ' class="admin-row-disabled"' : ''}>
            <td>${u.phone || '-'}</td>
            <td>${u.nickname || '<span class="text-muted">-</span>'}</td>
            <td>${u.birth_year || '<span class="text-muted">-</span>'}</td>
            <td><span class="admin-badge ${u.profile_completed ? 'badge-yes' : 'badge-no'}">${u.profile_completed ? '已完成' : '未完成'}</span></td>
            <td><span class="admin-badge ${isActive ? 'badge-yes' : 'badge-no'}">${isActive ? '正常' : '已禁用'}</span></td>
            <td>${u.conversation_count} / ${u.memoir_count}</td>
            <td>${u.created_at ? new Date(u.created_at).toLocaleDateString('zh-CN') : '-'}</td>
            <td class="admin-actions-cell">
                <button class="admin-btn admin-btn-sm admin-btn-primary" onclick="viewUserDetail('${u.id}')">详情</button>
                <button class="admin-btn admin-btn-sm" onclick="showEditModal('${u.id}')">编辑</button>
                <button class="admin-btn admin-btn-sm ${isActive ? 'admin-btn-warn' : ''}" onclick="toggleUserActive('${u.id}', '${label}')">${isActive ? '禁用' : '启用'}</button>
                <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="deleteUser('${u.id}', '${label}')">删除</button>
                <button class="admin-btn admin-btn-sm" onclick="resetPassword('${u.id}', '${label}')">重置密码</button>
            </td>
        </tr>`;
    }).join('');
}

// ========== 操作日志 ==========

const ACTION_LABELS = {
    create_user: '创建用户',
    edit_user: '编辑用户',
    reset_password: '重置密码',
    delete_user: '删除用户',
    toggle_user_active: '禁用/启用',
    create_era_memory: '创建时代记忆',
    update_era_memory: '更新时代记忆',
    delete_era_memory: '删除时代记忆',
    create_welcome_message: '新增激励语',
    update_welcome_message: '编辑激励语',
    delete_welcome_message: '删除激励语',
};

async function loadLogs() {
    try {
        const logs = await adminRequest('/admin/logs');
        logsLoaded = true;
        renderLogTable(logs);
    } catch (e) {
        document.getElementById('logTableBody').innerHTML =
            '<tr><td colspan="4" class="admin-table-empty">加载失败</td></tr>';
    }
}

function renderLogTable(logs) {
    const tbody = document.getElementById('logTableBody');
    if (!logs.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="admin-table-empty">暂无操作记录</td></tr>';
        return;
    }
    tbody.innerHTML = logs.map(log => {
        const time = log.created_at
            ? new Date(log.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
            : '-';
        const actionLabel = ACTION_LABELS[log.action] || log.action;
        return `
            <tr>
                <td>${time}</td>
                <td><span class="admin-log-action admin-log-${log.action}">${actionLabel}</span></td>
                <td>${log.target_label || '-'}</td>
                <td class="admin-log-detail">${log.detail || '-'}</td>
            </tr>
        `;
    }).join('');
}

// ========== 创建用户 ==========

function showCreateModal() {
    document.getElementById('createModal').style.display = 'flex';
    document.getElementById('createPhone').value = '';
    document.getElementById('createPassword').value = '';
    document.getElementById('createNickname').value = '';
    document.getElementById('createGender').value = '';
    document.getElementById('createBirthYear').value = '';
    document.getElementById('createHometown').value = '';
    document.getElementById('createMainCity').value = '';
    document.getElementById('createPhone').focus();
}

function closeCreateModal() {
    document.getElementById('createModal').style.display = 'none';
}

async function createUser() {
    const phone = document.getElementById('createPhone').value.trim();
    const password = document.getElementById('createPassword').value.trim();
    const nickname = document.getElementById('createNickname').value.trim();
    const gender = document.getElementById('createGender').value;
    if (!phone || !password || !nickname || !gender) {
        alert('请填写手机号、密码、姓名和性别');
        return;
    }

    const payload = { phone, password, nickname, gender };

    const birthYear = document.getElementById('createBirthYear').value.trim();
    const hometown = document.getElementById('createHometown').value.trim();
    const mainCity = document.getElementById('createMainCity').value.trim();

    if (birthYear) payload.birth_year = parseInt(birthYear, 10);
    if (hometown) payload.hometown = hometown;
    if (mainCity) payload.main_city = mainCity;

    try {
        await adminRequest('/admin/user', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        closeCreateModal();
        await loadUsers();
        logsLoaded = false; // 刷新日志缓存
    } catch (e) {
        alert('创建失败：' + e.message);
    }
}

// ========== 禁用/启用用户 ==========

async function toggleUserActive(userId, label) {
    const user = usersData.find(u => u.id === userId);
    const isActive = user ? user.is_active !== false : true;
    const action = isActive ? '禁用' : '启用';
    if (!confirm(`确定${action}用户 ${label}？`)) return;

    try {
        await adminRequest(`/admin/user/${userId}/toggle-active`, {
            method: 'POST',
        });
        await loadUsers();
        logsLoaded = false;
        // 如果在详情页，刷新详情
        if (currentUserDetail && currentUserDetail.id === userId) {
            viewUserDetail(userId);
        }
    } catch (e) {
        alert(`${action}失败：` + e.message);
    }
}

// ========== 删除用户 ==========

async function deleteUser(userId, label) {
    if (!confirm(`确定删除用户 ${label}？\n\n此操作将删除该用户的所有数据（对话、回忆录等），不可恢复！`)) return;

    try {
        await adminRequest(`/admin/user/${userId}`, {
            method: 'DELETE',
        });
        await loadUsers();
        logsLoaded = false;
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

// ========== 编辑用户 ==========

function showEditModal(userId) {
    const user = usersData.find(u => u.id === userId);
    if (!user) return;

    document.getElementById('editUserId').value = userId;
    document.getElementById('editNickname').value = user.nickname || '';
    document.getElementById('editGender').value = user.gender || '';
    document.getElementById('editBirthYear').value = user.birth_year || '';
    document.getElementById('editHometown').value = user.hometown || '';
    document.getElementById('editMainCity').value = user.main_city || '';
    document.getElementById('editModal').style.display = 'flex';
    document.getElementById('editNickname').focus();
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

async function saveEdit() {
    const userId = document.getElementById('editUserId').value;
    const payload = {
        nickname: document.getElementById('editNickname').value.trim() || null,
        gender: document.getElementById('editGender').value || null,
        birth_year: document.getElementById('editBirthYear').value.trim()
            ? parseInt(document.getElementById('editBirthYear').value.trim(), 10)
            : null,
        hometown: document.getElementById('editHometown').value.trim() || null,
        main_city: document.getElementById('editMainCity').value.trim() || null,
    };

    try {
        await adminRequest(`/admin/user/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
        closeEditModal();
        await loadUsers();
        logsLoaded = false;
        // 如果在详情页，刷新详情
        if (currentUserDetail && currentUserDetail.id === userId) {
            viewUserDetail(userId);
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

// ========== 重置密码 ==========

async function resetPassword(userId, label) {
    if (!confirm(`确定重置用户 ${label} 的密码？`)) return;

    try {
        const res = await adminRequest(`/admin/user/${userId}/reset-password`, {
            method: 'POST',
        });
        showPasswordResult(res.new_password);
        logsLoaded = false;
    } catch (e) {
        alert('重置失败：' + e.message);
    }
}

function showPasswordResult(password) {
    document.getElementById('newPasswordText').textContent = password;
    document.getElementById('passwordModal').style.display = 'flex';
}

function closePasswordModal() {
    document.getElementById('passwordModal').style.display = 'none';
}

function copyPassword() {
    const pw = document.getElementById('newPasswordText').textContent;
    navigator.clipboard.writeText(pw).then(() => {
        const btn = document.getElementById('copyBtn');
        btn.textContent = '已复制';
        setTimeout(() => { btn.textContent = '复制'; }, 1500);
    });
}

// ========== 时代记忆管理 ==========

let eraMemoriesData = [];

async function loadEraMemories() {
    try {
        const memories = await adminRequest('/admin/era-memories');
        eraMemoriesData = memories;
        eraMemoriesLoaded = true;
        renderEraMemoryTable(memories);
    } catch (e) {
        document.getElementById('eraMemoryTableBody').innerHTML =
            '<tr><td colspan="4" class="admin-table-empty">加载失败</td></tr>';
    }
}

function renderEraMemoryTable(memories) {
    const tbody = document.getElementById('eraMemoryTableBody');
    if (!memories.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="admin-table-empty">暂无时代记忆</td></tr>';
        return;
    }
    // 按起始年份排序
    const sorted = [...memories].sort((a, b) => a.start_year - b.start_year);
    tbody.innerHTML = sorted.map(m => `
        <tr>
            <td>${m.start_year}-${m.end_year}</td>
            <td>${m.category || '<span class="text-muted">-</span>'}</td>
            <td class="admin-era-content">${escapeHtml(m.content)}</td>
            <td class="admin-actions-cell">
                <button class="admin-btn admin-btn-sm" onclick="editEraMemory('${m.id}')">编辑</button>
                <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="deleteEraMemory('${m.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showEraMemoryModal() {
    document.getElementById('eraMemoryModalTitle').textContent = '新增时代记忆';
    document.getElementById('eraMemoryId').value = '';
    document.getElementById('eraMemoryStartYear').value = '';
    document.getElementById('eraMemoryEndYear').value = '';
    document.getElementById('eraMemoryCategory').value = '';
    document.getElementById('eraMemoryContent').value = '';
    document.getElementById('eraMemoryModal').style.display = 'flex';
    document.getElementById('eraMemoryStartYear').focus();
}

function editEraMemory(id) {
    const memory = eraMemoriesData.find(m => m.id === id);
    if (!memory) return;

    document.getElementById('eraMemoryModalTitle').textContent = '编辑时代记忆';
    document.getElementById('eraMemoryId').value = id;
    document.getElementById('eraMemoryStartYear').value = memory.start_year;
    document.getElementById('eraMemoryEndYear').value = memory.end_year;
    document.getElementById('eraMemoryCategory').value = memory.category || '';
    document.getElementById('eraMemoryContent').value = memory.content;
    document.getElementById('eraMemoryModal').style.display = 'flex';
    document.getElementById('eraMemoryContent').focus();
}

function closeEraMemoryModal() {
    document.getElementById('eraMemoryModal').style.display = 'none';
}

async function saveEraMemory() {
    const id = document.getElementById('eraMemoryId').value;
    const startYear = document.getElementById('eraMemoryStartYear').value.trim();
    const endYear = document.getElementById('eraMemoryEndYear').value.trim();
    const category = document.getElementById('eraMemoryCategory').value;
    const content = document.getElementById('eraMemoryContent').value.trim();

    if (!startYear || !endYear || !content) {
        alert('请填写起始年份、结束年份和内容');
        return;
    }

    const payload = {
        start_year: parseInt(startYear, 10),
        end_year: parseInt(endYear, 10),
        category: category || null,
        content: content,
    };

    if (payload.start_year > payload.end_year) {
        alert('起始年份不能大于结束年份');
        return;
    }

    try {
        if (id) {
            // 编辑
            await adminRequest(`/admin/era-memories/${id}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
        } else {
            // 新增
            await adminRequest('/admin/era-memories', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }
        closeEraMemoryModal();
        eraMemoriesLoaded = false;
        await loadEraMemories();
        logsLoaded = false;
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function deleteEraMemory(id) {
    const memory = eraMemoriesData.find(m => m.id === id);
    if (!memory) return;

    const preview = memory.content.length > 30 ? memory.content.substring(0, 30) + '...' : memory.content;
    if (!confirm(`确定删除这条时代记忆？\n\n${memory.start_year}-${memory.end_year}: ${preview}`)) return;

    try {
        await adminRequest(`/admin/era-memories/${id}`, {
            method: 'DELETE',
        });
        eraMemoriesLoaded = false;
        await loadEraMemories();
        logsLoaded = false;
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

// ========== 激励语管理 ==========

let welcomeMessagesData = [];

async function loadWelcomeMessages() {
    try {
        const messages = await adminRequest('/admin/welcome-messages');
        welcomeMessagesData = messages;
        welcomeMessagesLoaded = true;
        renderWelcomeMessageTable(messages);
    } catch (e) {
        document.getElementById('welcomeMessageTableBody').innerHTML =
            '<tr><td colspan="5" class="admin-table-empty">加载失败</td></tr>';
    }
}

function renderWelcomeMessageTable(messages) {
    const tbody = document.getElementById('welcomeMessageTableBody');
    if (!messages.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="admin-table-empty">暂无激励语</td></tr>';
        return;
    }
    tbody.innerHTML = messages.map(m => `
        <tr${!m.is_active ? ' class="admin-row-disabled"' : ''}>
            <td>${escapeHtml(m.content)}</td>
            <td><span class="admin-badge ${m.show_greeting !== false ? 'badge-yes' : 'badge-no'}">${m.show_greeting !== false ? '显示' : '隐藏'}</span></td>
            <td>${m.sort_order}</td>
            <td><span class="admin-badge ${m.is_active ? 'badge-yes' : 'badge-no'}">${m.is_active ? '启用' : '禁用'}</span></td>
            <td class="admin-actions-cell">
                <button class="admin-btn admin-btn-sm" onclick="editWelcomeMessage('${m.id}')">编辑</button>
                <button class="admin-btn admin-btn-sm ${m.is_active ? 'admin-btn-warn' : ''}" onclick="toggleWelcomeMessage('${m.id}')">${m.is_active ? '禁用' : '启用'}</button>
                <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="deleteWelcomeMessage('${m.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function showWelcomeMessageModal() {
    document.getElementById('welcomeMessageModalTitle').textContent = '新增激励语';
    document.getElementById('welcomeMessageId').value = '';
    document.getElementById('welcomeMessageContent').value = '';
    document.getElementById('welcomeMessageSortOrder').value = '0';
    document.getElementById('welcomeMessageShowGreeting').checked = true;
    document.getElementById('welcomeMessageModal').style.display = 'flex';
    document.getElementById('welcomeMessageContent').focus();
}

function editWelcomeMessage(id) {
    const msg = welcomeMessagesData.find(m => m.id === id);
    if (!msg) return;

    document.getElementById('welcomeMessageModalTitle').textContent = '编辑激励语';
    document.getElementById('welcomeMessageId').value = id;
    document.getElementById('welcomeMessageContent').value = msg.content;
    document.getElementById('welcomeMessageSortOrder').value = msg.sort_order;
    document.getElementById('welcomeMessageShowGreeting').checked = msg.show_greeting !== false;
    document.getElementById('welcomeMessageModal').style.display = 'flex';
    document.getElementById('welcomeMessageContent').focus();
}

function closeWelcomeMessageModal() {
    document.getElementById('welcomeMessageModal').style.display = 'none';
}

async function saveWelcomeMessage() {
    const id = document.getElementById('welcomeMessageId').value;
    const content = document.getElementById('welcomeMessageContent').value.trim();
    const sortOrder = parseInt(document.getElementById('welcomeMessageSortOrder').value, 10) || 0;

    if (!content) {
        alert('请输入激励语内容');
        return;
    }

    const showGreeting = document.getElementById('welcomeMessageShowGreeting').checked;
    const payload = { content, sort_order: sortOrder, show_greeting: showGreeting };

    try {
        if (id) {
            await adminRequest(`/admin/welcome-messages/${id}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
        } else {
            await adminRequest('/admin/welcome-messages', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }
        closeWelcomeMessageModal();
        welcomeMessagesLoaded = false;
        await loadWelcomeMessages();
        logsLoaded = false;
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function toggleWelcomeMessage(id) {
    const msg = welcomeMessagesData.find(m => m.id === id);
    if (!msg) return;

    const newActive = !msg.is_active;
    try {
        await adminRequest(`/admin/welcome-messages/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: newActive }),
        });
        welcomeMessagesLoaded = false;
        await loadWelcomeMessages();
        logsLoaded = false;
    } catch (e) {
        alert('操作失败：' + e.message);
    }
}

async function deleteWelcomeMessage(id) {
    const msg = welcomeMessagesData.find(m => m.id === id);
    if (!msg) return;

    const preview = msg.content.length > 30 ? msg.content.substring(0, 30) + '...' : msg.content;
    if (!confirm(`确定删除这条激励语？\n\n"${preview}"`)) return;

    try {
        await adminRequest(`/admin/welcome-messages/${id}`, {
            method: 'DELETE',
        });
        welcomeMessagesLoaded = false;
        await loadWelcomeMessages();
        logsLoaded = false;
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

// ========== 数据监控 ==========

const DONUT_COLORS = ['#8b4513', '#cd853f', '#d2691e', '#deb887', '#f4a460', '#c9a86c', '#a0522d', '#bc8f8f'];

async function loadMonitoringData() {
    try {
        const data = await adminRequest('/admin/monitoring');
        monitoringData = data;
        monitoringLoaded = true;
        renderMonitoringData(data);
    } catch (e) {
        console.error('加载监控数据失败:', e);
    }
}

function refreshMonitoring() {
    monitoringLoaded = false;
    loadMonitoringData();
}

function renderMonitoringData(data) {
    // 核心指标
    document.getElementById('statTotalUsers').textContent = data.overview.total_users;
    document.getElementById('statProfileRate').textContent = `${(data.overview.profile_completion_rate * 100).toFixed(0)}%`;
    document.getElementById('statTotalConversations').textContent = data.overview.total_conversations;
    document.getElementById('statTotalMemoirs').textContent = data.overview.total_memoirs;
    document.getElementById('statTodayActive').textContent = data.activity.today_active_users;
    document.getElementById('statWeekActive').textContent = data.activity.week_active_users;
    document.getElementById('statTodayConv').textContent = `+${data.activity.today_new_conversations}`;
    document.getElementById('statTodayMemoir').textContent = `+${data.activity.today_new_memoirs}`;

    // 留存率可视化
    renderRetentionVisual(data.retention);

    // 用户画像图表
    renderDonutChart('birthDecadeDonut', 'birthDecadeLegend', data.distributions.birth_decade);
    renderDonutChart('hometownDonut', 'hometownLegend', data.distributions.hometown_province);

    // 使用情况分布
    renderUsageBars('distConversations', data.distributions.conversations_per_user, 'avgConversations', data.overview.total_conversations, data.overview.total_users, '次/人');
    renderUsageBars('distMemoirs', data.distributions.memoirs_per_user, 'avgMemoirs', data.overview.total_memoirs, data.overview.total_users, '篇/人');
    renderUsageBars('distMessages', data.distributions.messages_per_conversation, 'avgMessages', null, null, null);
}

function renderRetentionVisual(retention) {
    const day1 = retention.day1 ?? 0;
    const day7 = retention.day7 ?? 0;
    const day30 = retention.day30 ?? 0;

    // 文字
    document.getElementById('statRetention1').textContent = formatRetention(day1);
    document.getElementById('statRetention7').textContent = formatRetention(day7);
    document.getElementById('statRetention30').textContent = formatRetention(day30);
    document.getElementById('statRetention7Display').textContent = formatRetention(day7);

    // 环形图 (7日留存)
    const ring = document.getElementById('retention7Ring');
    if (ring) {
        const circumference = 314; // 2 * π * 50
        const offset = circumference * (1 - day7);
        ring.style.strokeDashoffset = offset;
    }

    // 条形图
    setTimeout(() => {
        const bar1 = document.getElementById('retention1Bar');
        const bar7 = document.getElementById('retention7Bar');
        const bar30 = document.getElementById('retention30Bar');
        if (bar1) bar1.style.width = `${day1 * 100}%`;
        if (bar7) bar7.style.width = `${day7 * 100}%`;
        if (bar30) bar30.style.width = `${day30 * 100}%`;
    }, 100);
}

function renderDonutChart(chartId, legendId, items) {
    const chartEl = document.getElementById(chartId);
    const legendEl = document.getElementById(legendId);

    if (!items || items.length === 0) {
        chartEl.innerHTML = '<div class="admin-empty-state" style="padding:40px 0;">暂无数据</div>';
        legendEl.innerHTML = '';
        return;
    }

    const total = items.reduce((sum, i) => sum + i.count, 0);
    if (total === 0) {
        chartEl.innerHTML = '<div class="admin-empty-state" style="padding:40px 0;">暂无数据</div>';
        legendEl.innerHTML = '';
        return;
    }

    // 生成环形图
    const radius = 50;
    const circumference = 2 * Math.PI * radius;
    let offset = 0;

    const paths = items.map((item, idx) => {
        const percent = item.count / total;
        const dashLength = circumference * percent;
        const color = DONUT_COLORS[idx % DONUT_COLORS.length];
        const path = `<circle cx="70" cy="70" r="${radius}" fill="none" stroke="${color}" stroke-width="20"
            stroke-dasharray="${dashLength} ${circumference}" stroke-dashoffset="${-offset}"/>`;
        offset += dashLength;
        return path;
    }).join('');

    chartEl.innerHTML = `<svg viewBox="0 0 140 140">${paths}</svg>`;

    // 生成图例
    legendEl.innerHTML = items.slice(0, 6).map((item, idx) => {
        const color = DONUT_COLORS[idx % DONUT_COLORS.length];
        const percent = ((item.count / total) * 100).toFixed(0);
        return `<div class="admin-legend-item">
            <span class="admin-legend-dot" style="background:${color}"></span>
            <span>${item.label} ${percent}%</span>
        </div>`;
    }).join('');
}

function renderUsageBars(containerId, items, avgId, totalItems, totalUsers, avgUnit) {
    const container = document.getElementById(containerId);
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="admin-empty-state">暂无数据</div>';
        return;
    }

    const maxCount = Math.max(...items.map(i => i.count));

    container.innerHTML = items.map(item => {
        const percent = maxCount > 0 ? (item.count / maxCount * 100) : 0;
        const isNarrow = percent < 15;
        return `
            <div class="admin-usage-row">
                <div class="admin-usage-label">${item.label}</div>
                <div class="admin-usage-bar-wrap">
                    <div class="admin-usage-bar ${isNarrow ? 'narrow' : ''}" style="width: ${percent}%" data-count="${item.count}"></div>
                </div>
                ${isNarrow ? `<div class="admin-usage-count">${item.count}</div>` : ''}
            </div>
        `;
    }).join('');

    // 平均值
    if (avgId && totalItems !== null && totalUsers !== null && totalUsers > 0) {
        const avg = (totalItems / totalUsers).toFixed(1);
        document.getElementById(avgId).textContent = `均 ${avg} ${avgUnit}`;
    }
}

function formatRetention(value) {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(0)}%`;
}

async function showRetentionMatrix() {
    document.getElementById('retentionModal').style.display = 'flex';
    document.getElementById('retentionMatrixBody').innerHTML = '<tr><td colspan="7" class="admin-table-empty">加载中...</td></tr>';

    try {
        const data = await adminRequest('/admin/monitoring/retention-matrix?days=30');
        renderRetentionMatrix(data);
    } catch (e) {
        document.getElementById('retentionMatrixBody').innerHTML = '<tr><td colspan="7" class="admin-table-empty">加载失败</td></tr>';
    }
}

function renderRetentionMatrix(data) {
    const tbody = document.getElementById('retentionMatrixBody');

    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="admin-table-empty">暂无数据</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(row => `
        <tr>
            <td>${row.date}</td>
            <td>${row.new_users}</td>
            <td>${formatRetentionCell(row.day1)}</td>
            <td>${formatRetentionCell(row.day3)}</td>
            <td>${formatRetentionCell(row.day7)}</td>
            <td>${formatRetentionCell(row.day14)}</td>
            <td>${formatRetentionCell(row.day30)}</td>
        </tr>
    `).join('');
}

function formatRetentionCell(value) {
    if (value === null || value === undefined) return '<span class="text-muted">-</span>';
    const percent = (value * 100).toFixed(0);
    const colorClass = getRetentionColorClass(value);
    return `<span class="admin-retention-cell ${colorClass}">${percent}%</span>`;
}

function getRetentionColorClass(value) {
    if (value >= 0.5) return 'retention-high';
    if (value >= 0.3) return 'retention-mid';
    if (value >= 0.1) return 'retention-low';
    return 'retention-very-low';
}

function closeRetentionModal() {
    document.getElementById('retentionModal').style.display = 'none';
}

// ========== 用户详情 ==========

let currentUserDetail = null;
let currentMemoirDetail = null;

async function viewUserDetail(userId) {
    try {
        const detail = await adminRequest(`/admin/user/${userId}/detail`);
        currentUserDetail = detail;
        renderUserDetail(detail);
        showUserDetailTab();
    } catch (e) {
        alert('加载用户详情失败：' + e.message);
    }
}

function showUserDetailTab() {
    // 隐藏所有面板
    document.querySelectorAll('.admin-tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    // 清除侧边栏选中态
    document.querySelectorAll('.admin-nav-item[data-tab]').forEach(btn => {
        btn.classList.remove('active');
    });
    // 显示用户详情面板
    document.getElementById('tabUserDetail').classList.add('active');
}

function backToUserList() {
    currentUserDetail = null;
    switchTab('users');
}

function renderUserDetail(detail) {
    // 标题
    const title = detail.nickname || detail.phone || '用户详情';
    document.getElementById('userDetailTitle').textContent = title;

    // 概览卡片
    document.getElementById('detailName').textContent = detail.nickname || detail.phone || '-';

    // 出生年份和位置
    const birthText = detail.birth_year ? `${detail.birth_year}年生` : '未填写';
    const locationParts = [detail.hometown, detail.main_city].filter(Boolean);
    const locationText = locationParts.length > 0 ? locationParts.join(' → ') : '未填写';

    document.getElementById('detailBirthYearMeta').textContent = birthText;
    document.getElementById('detailLocationMeta').textContent = locationText;

    // 状态徽章
    document.getElementById('detailStatusBadge').className = `admin-badge ${detail.is_active ? 'badge-yes' : 'badge-no'}`;
    document.getElementById('detailStatusBadge').textContent = detail.is_active ? '正常' : '已禁用';
    document.getElementById('detailProfileBadge').className = `admin-badge ${detail.profile_completed ? 'badge-yes' : 'badge-no'}`;
    document.getElementById('detailProfileBadge').textContent = detail.profile_completed ? '资料完整' : '资料未完成';

    // 统计数据
    document.getElementById('detailConvCount').textContent = detail.conversations ? detail.conversations.length : 0;
    document.getElementById('detailMemoirCount').textContent = detail.memoirs ? detail.memoirs.length : 0;

    // 计算活跃天数
    const activeDays = calculateActiveDays(detail.conversations);
    document.getElementById('detailDaysActive').textContent = activeDays;

    // 账号信息
    document.getElementById('detailPhone').textContent = detail.phone || '-';
    document.getElementById('detailCreatedAt').textContent = detail.created_at
        ? new Date(detail.created_at).toLocaleString('zh-CN')
        : '-';

    // 最后活跃时间
    const lastActive = getLastActiveTime(detail.conversations);
    document.getElementById('detailLastActive').textContent = lastActive;

    // 基础信息
    document.getElementById('detailNickname').textContent = detail.nickname || '-';
    document.getElementById('detailGender').textContent = detail.gender || '-';
    document.getElementById('detailPreferredName').textContent = detail.preferred_name || '-';
    document.getElementById('detailBirthYear').textContent = detail.birth_year ? `${detail.birth_year}年` : '-';
    document.getElementById('detailHometown').textContent = detail.hometown || '-';
    document.getElementById('detailMainCity').textContent = detail.main_city || '-';

    // 回忆列表
    document.getElementById('memoirCount').textContent = detail.memoirs.length;
    renderMemoirList(detail.memoirs, detail.conversations);

    // 使用统计
    renderUserStats(detail.stats);

    // 话题池
    renderTopicPool(detail.topic_pool);

    // 时代记忆
    renderEraMemory(detail.era_memories);

    // 头部操作按钮
    const isActive = detail.is_active !== false;
    const label = (detail.phone || detail.nickname || '').replace(/'/g, "\\'");
    document.getElementById('userDetailActions').innerHTML = `
        <button class="admin-btn admin-btn-sm" onclick="showEditModal('${detail.id}')">编辑</button>
        <button class="admin-btn admin-btn-sm ${isActive ? 'admin-btn-warn' : ''}" onclick="toggleUserActive('${detail.id}', '${label}')">${isActive ? '禁用' : '启用'}</button>
    `;
}

function renderUserStats(stats) {
    // 累计数据
    document.getElementById('statTotalConv').textContent = stats?.total_conversations ?? 0;
    document.getElementById('statTotalMemoirs').textContent = stats?.total_memoirs ?? 0;
    document.getElementById('statTotalMessages').textContent = stats?.total_messages ?? 0;
    document.getElementById('statTotalDuration').textContent =
        stats?.total_duration_mins ? formatDuration(stats.total_duration_mins) : '-';
    document.getElementById('statTotalChars').textContent =
        stats?.total_memoir_chars ? formatNumber(stats.total_memoir_chars) : '0';

    // 平均数据
    document.getElementById('statAvgDuration').textContent =
        stats?.avg_conversation_duration_mins ? `${stats.avg_conversation_duration_mins}分钟` : '-';
    document.getElementById('statAvgMessages').textContent =
        stats?.avg_messages_per_conversation ? `${stats.avg_messages_per_conversation}轮` : '-';
    document.getElementById('statConvRate').textContent =
        stats?.conversation_to_memoir_rate != null ? `${(stats.conversation_to_memoir_rate * 100).toFixed(0)}%` : '-';
    document.getElementById('statAvgMemoirLen').textContent =
        stats?.avg_memoir_length ? `${stats.avg_memoir_length}字` : '-';
    document.getElementById('statFirstMemoirDays').textContent =
        stats?.first_memoir_days != null ? `${stats.first_memoir_days}天` : '-';

    // 人生阶段覆盖
    const stages = stats?.life_stages_coverage || {};
    const stageKeys = Object.keys(stages);
    if (stageKeys.length > 0) {
        document.getElementById('statLifeStages').innerHTML = stageKeys.map(stage =>
            `<span class="admin-stage-tag">${stage}<span class="stage-count">${stages[stage]}</span></span>`
        ).join('');
    } else {
        document.getElementById('statLifeStages').innerHTML = '<span class="text-muted">暂无</span>';
    }
}

// 格式化时长（分钟 -> 小时分钟）
function formatDuration(minutes) {
    if (minutes < 60) {
        return `${Math.round(minutes)}分钟`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`;
}

// 格式化数字（添加千分位）
function formatNumber(num) {
    return num.toLocaleString('zh-CN');
}

function renderTopicPool(topics) {
    const container = document.getElementById('topicPoolContainer');
    document.getElementById('topicPoolCount').textContent = topics ? topics.length : 0;

    if (!topics || topics.length === 0) {
        container.innerHTML = '<div class="admin-empty-state">暂无话题</div>';
        return;
    }

    container.innerHTML = `<div class="admin-topic-list">
        ${topics.map(t => {
            const ageText = formatAgeRange(t.age_start, t.age_end);
            return `
                <div class="admin-topic-item">
                    <div class="admin-topic-item-header">
                        <div class="admin-topic-title">${escapeHtml(t.topic)}</div>
                        ${ageText ? `<span class="admin-topic-age">${ageText}</span>` : ''}
                    </div>
                    <div class="admin-topic-greeting">${escapeHtml(t.greeting)}</div>
                </div>
            `;
        }).join('')}
    </div>`;
}

function formatAgeRange(start, end) {
    if (!start && !end) return '';
    if (start && end) {
        if (start === end) return `${start}岁`;
        return `${start}-${end}岁`;
    }
    if (start) return `${start}岁起`;
    return `${end}岁前`;
}

function renderEraMemory(eraMemories) {
    const card = document.getElementById('eraMemoryCard');
    const content = document.getElementById('eraMemoryContent');
    const text = document.getElementById('eraMemoryText');

    if (!eraMemories) {
        card.style.display = 'none';
        return;
    }

    card.style.display = 'block';
    text.textContent = eraMemories;
    content.style.display = 'none';
    document.getElementById('eraMemoryToggle').textContent = '展开';
}

function toggleEraMemory() {
    const content = document.getElementById('eraMemoryContent');
    const toggle = document.getElementById('eraMemoryToggle');
    const isHidden = content.style.display === 'none';

    content.style.display = isHidden ? 'block' : 'none';
    toggle.textContent = isHidden ? '收起' : '展开';
}

function calculateActiveDays(conversations) {
    if (!conversations || conversations.length === 0) return 0;
    const days = new Set();
    conversations.forEach(c => {
        if (c.created_at) {
            const date = new Date(c.created_at).toLocaleDateString('zh-CN');
            days.add(date);
        }
    });
    return days.size;
}

function getLastActiveTime(conversations) {
    if (!conversations || conversations.length === 0) return '暂无活动';
    const sorted = [...conversations].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (sorted[0] && sorted[0].created_at) {
        return new Date(sorted[0].created_at).toLocaleString('zh-CN');
    }
    return '暂无活动';
}

function renderMemoirList(memoirs, conversations) {
    const container = document.getElementById('memoirListContainer');

    if (!memoirs.length) {
        container.innerHTML = '<div class="admin-empty-state">暂无回忆录</div>';
        return;
    }

    // 创建会话ID到会话的映射
    const convMap = {};
    conversations.forEach(c => { convMap[c.id] = c; });

    // 按年代分组
    const grouped = {};
    memoirs.forEach(m => {
        const decade = m.year_start ? `${Math.floor(m.year_start / 10) * 10}年代` : '未知时期';
        if (!grouped[decade]) grouped[decade] = [];
        grouped[decade].push(m);
    });

    // 排序年代
    const decades = Object.keys(grouped).sort((a, b) => {
        if (a === '未知时期') return 1;
        if (b === '未知时期') return -1;
        return parseInt(a) - parseInt(b);
    });

    container.innerHTML = `<div class="admin-memoir-timeline">
        ${decades.map(decade => `
            <div class="admin-timeline-group">
                <div class="admin-timeline-header">${decade}</div>
                <div class="admin-timeline-items">
                    ${grouped[decade].map(m => {
                        const isGenerating = m.status === 'generating';
                        const yearText = formatYearRange(m.year_start, m.year_end, m.time_period);
                        const timeText = formatTimeRange(m.conversation_start, m.conversation_end);

                        return `
                            <div class="admin-timeline-item ${isGenerating ? 'generating' : ''}" onclick="showMemoirDetail('${m.id}')">
                                <div class="admin-timeline-dot"></div>
                                <div class="admin-timeline-content">
                                    <div class="admin-timeline-title">
                                        <span class="title-text">${escapeHtml(m.title)}</span>
                                        ${isGenerating ? '<span class="admin-memoir-status">撰写中...</span>' : ''}
                                    </div>
                                    <div class="admin-timeline-meta">
                                        ${yearText ? `<span class="meta-year">${yearText}</span>` : ''}
                                        ${timeText ? `<span class="meta-time">${timeText}</span>` : ''}
                                    </div>
                                </div>
                                <div class="admin-timeline-arrow">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M9 18l6-6-6-6"/>
                                    </svg>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `).join('')}
    </div>`;
}

function formatYearRange(yearStart, yearEnd, timePeriod) {
    let parts = [];
    if (yearStart && yearEnd) {
        if (yearStart === yearEnd) {
            parts.push(`${yearStart}年`);
        } else {
            parts.push(`${yearStart}-${yearEnd}年`);
        }
    } else if (yearStart) {
        parts.push(`${yearStart}年`);
    }
    if (timePeriod) {
        parts.push(timePeriod);
    }
    return parts.join(' · ');
}

function formatTimeRange(start, end) {
    if (!start) return '';
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

function showMemoirDetail(memoirId) {
    if (!currentUserDetail) return;

    const memoir = currentUserDetail.memoirs.find(m => m.id === memoirId);
    if (!memoir) return;

    currentMemoirDetail = memoir;

    // 查找关联的会话
    const conversation = memoir.conversation_id
        ? currentUserDetail.conversations.find(c => c.id === memoir.conversation_id)
        : null;

    // 设置标题
    document.getElementById('memoirDetailTitle').textContent = memoir.title;

    // 设置元信息
    const yearText = formatYearRange(memoir.year_start, memoir.year_end, memoir.time_period);
    const timeText = formatTimeRange(memoir.conversation_start, memoir.conversation_end);
    let metaHtml = '';
    if (yearText) metaHtml += `<span class="meta-year">${yearText}</span>`;
    if (timeText) metaHtml += `<span class="meta-time">${timeText}</span>`;
    document.getElementById('memoirMeta').innerHTML = metaHtml;

    // 设置回忆录内容
    document.getElementById('memoirText').textContent = memoir.content || '（内容为空）';

    // 设置对话记录
    if (conversation && conversation.messages && conversation.messages.length > 0) {
        document.getElementById('transcriptList').innerHTML = conversation.messages.map(msg => {
            const roleText = msg.role === 'user' ? '用户' : '记录师';
            const roleClass = msg.role === 'user' ? 'user' : 'assistant';
            return `
                <div class="admin-transcript-message ${roleClass}">
                    <div class="admin-transcript-role">${roleText}</div>
                    <div class="admin-transcript-content">${escapeHtml(msg.content)}</div>
                </div>
            `;
        }).join('');
    } else {
        document.getElementById('transcriptList').innerHTML = '<div class="admin-empty-state">暂无对话记录</div>';
    }

    // 默认显示回忆录标签
    switchMemoirTab('memoir');

    // 显示弹窗
    document.getElementById('memoirDetailModal').style.display = 'flex';
}

function closeMemoirDetailModal() {
    document.getElementById('memoirDetailModal').style.display = 'none';
    currentMemoirDetail = null;
}

function switchMemoirTab(tab) {
    // 切换标签按钮状态
    document.querySelectorAll('.admin-memoir-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    // 切换内容面板
    document.querySelectorAll('.admin-memoir-tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    if (tab === 'memoir') {
        document.getElementById('memoirTabContent').classList.add('active');
    } else {
        document.getElementById('transcriptTabContent').classList.add('active');
    }
}

// ========== 预设话题管理 ==========

let presetTopicsData = [];

async function loadPresetTopics() {
    try {
        const topics = await adminRequest('/admin/preset-topics');
        presetTopicsData = topics;
        presetTopicsLoaded = true;
        renderPresetTopicTable(topics);
    } catch (e) {
        document.getElementById('presetTopicTableBody').innerHTML =
            '<tr><td colspan="5" class="admin-table-empty">加载失败</td></tr>';
    }
}

function renderPresetTopicTable(topics) {
    const tbody = document.getElementById('presetTopicTableBody');
    if (!topics.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="admin-table-empty">暂无预设话题</td></tr>';
        return;
    }
    tbody.innerHTML = topics.map(t => `
        <tr${!t.is_active ? ' class="admin-row-disabled"' : ''}>
            <td>${escapeHtml(t.topic)}</td>
            <td title="${escapeHtml(t.greeting)}">${escapeHtml(t.greeting.length > 40 ? t.greeting.substring(0, 40) + '...' : t.greeting)}</td>
            <td>${t.sort_order}</td>
            <td><span class="admin-badge ${t.is_active ? 'badge-yes' : 'badge-no'}">${t.is_active ? '启用' : '禁用'}</span></td>
            <td class="admin-actions-cell">
                <button class="admin-btn admin-btn-sm" onclick="editPresetTopic('${t.id}')">编辑</button>
                <button class="admin-btn admin-btn-sm ${t.is_active ? 'admin-btn-warn' : ''}" onclick="togglePresetTopic('${t.id}')">${t.is_active ? '禁用' : '启用'}</button>
                <button class="admin-btn admin-btn-sm admin-btn-danger" onclick="deletePresetTopic('${t.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function showPresetTopicModal() {
    document.getElementById('presetTopicModalTitle').textContent = '新增初始话题';
    document.getElementById('presetTopicId').value = '';
    document.getElementById('presetTopicName').value = '';
    document.getElementById('presetTopicGreeting').value = '';
    document.getElementById('presetTopicChatContext').value = '';
    document.getElementById('presetTopicAgeStart').value = '';
    document.getElementById('presetTopicAgeEnd').value = '';
    document.getElementById('presetTopicSortOrder').value = '0';
    document.getElementById('presetTopicModal').style.display = 'flex';
    document.getElementById('presetTopicName').focus();
}

function editPresetTopic(id) {
    const t = presetTopicsData.find(t => t.id === id);
    if (!t) return;

    document.getElementById('presetTopicModalTitle').textContent = '编辑初始话题';
    document.getElementById('presetTopicId').value = id;
    document.getElementById('presetTopicName').value = t.topic;
    document.getElementById('presetTopicGreeting').value = t.greeting;
    document.getElementById('presetTopicChatContext').value = t.chat_context || '';
    document.getElementById('presetTopicAgeStart').value = t.age_start != null ? t.age_start : '';
    document.getElementById('presetTopicAgeEnd').value = t.age_end != null ? t.age_end : '';
    document.getElementById('presetTopicSortOrder').value = t.sort_order;
    document.getElementById('presetTopicModal').style.display = 'flex';
    document.getElementById('presetTopicName').focus();
}

function closePresetTopicModal() {
    document.getElementById('presetTopicModal').style.display = 'none';
}

async function savePresetTopic() {
    const id = document.getElementById('presetTopicId').value;
    const topic = document.getElementById('presetTopicName').value.trim();
    const greeting = document.getElementById('presetTopicGreeting').value.trim();
    const chatContext = document.getElementById('presetTopicChatContext').value.trim();
    const ageStartVal = document.getElementById('presetTopicAgeStart').value;
    const ageEndVal = document.getElementById('presetTopicAgeEnd').value;
    const sortOrder = parseInt(document.getElementById('presetTopicSortOrder').value, 10) || 0;

    if (!topic) {
        alert('请输入话题名称');
        return;
    }
    if (!greeting) {
        alert('请输入开场白');
        return;
    }

    const payload = {
        topic,
        greeting,
        chat_context: chatContext || null,
        age_start: ageStartVal !== '' ? parseInt(ageStartVal, 10) : null,
        age_end: ageEndVal !== '' ? parseInt(ageEndVal, 10) : null,
        sort_order: sortOrder,
    };

    try {
        if (id) {
            await adminRequest(`/admin/preset-topics/${id}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
        } else {
            await adminRequest('/admin/preset-topics', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }
        closePresetTopicModal();
        presetTopicsLoaded = false;
        await loadPresetTopics();
        logsLoaded = false;
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function togglePresetTopic(id) {
    const t = presetTopicsData.find(t => t.id === id);
    if (!t) return;

    const newActive = !t.is_active;
    try {
        await adminRequest(`/admin/preset-topics/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: newActive }),
        });
        presetTopicsLoaded = false;
        await loadPresetTopics();
        logsLoaded = false;
    } catch (e) {
        alert('操作失败：' + e.message);
    }
}

async function deletePresetTopic(id) {
    const t = presetTopicsData.find(t => t.id === id);
    if (!t) return;

    if (!confirm(`确定删除预设话题「${t.topic}」？`)) return;

    try {
        await adminRequest(`/admin/preset-topics/${id}`, {
            method: 'DELETE',
        });
        presetTopicsLoaded = false;
        await loadPresetTopics();
        logsLoaded = false;
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

// ========== LLM 健康监控 ==========

async function loadLlmModels() {
    try {
        const data = await adminRequest('/admin/llm-models');
        llmModelsData = data.models || [];
        llmHealthLoaded = true;
        llmTestResults = {};
        renderLlmRoutingOverview(data);
        renderLlmHealthTable(llmModelsData);
    } catch (e) {
        document.getElementById('llmHealthTableBody').innerHTML =
            '<tr><td colspan="8" class="admin-table-empty">加载失败：' + escapeHtml(e.message) + '</td></tr>';
    }
}

function renderLlmRoutingOverview(data) {
    const body = document.getElementById('llmRoutingBody');
    const overrides = data.module_overrides || {};
    const defaultProvider = data.default_provider || 'dashscope';

    const moduleNames = { memoir: '回忆录', summary: '摘要', topic: '话题', profile: '画像', intervention: '干预' };
    const overrideHtml = Object.entries(overrides).map(([mod, prov]) => {
        const isOverridden = prov !== defaultProvider;
        return `<span class="admin-badge ${isOverridden ? 'badge-error' : 'badge-yes'}" style="margin:2px 4px;">${moduleNames[mod] || mod} → ${prov}</span>`;
    }).join('');

    body.innerHTML = `
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;">
            <strong>默认 Provider：</strong>
            <span class="admin-badge badge-yes">${escapeHtml(defaultProvider)}</span>
            <span style="margin-left:16px;"><strong>模块路由：</strong></span>
            ${overrideHtml}
        </div>
    `;
}

function renderLlmHealthTable(models) {
    const tbody = document.getElementById('llmHealthTableBody');
    if (!models.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="admin-table-empty">暂无模型配置</td></tr>';
        return;
    }
    tbody.innerHTML = models.map((m) => {
        const key = `${m.provider}:${m.model}:${m.tier}`;
        const result = llmTestResults[key];
        let statusHtml = '<span class="admin-badge badge-no">未测试</span>';
        let latencyHtml = '-';
        if (result) {
            if (result.loading) {
                statusHtml = '<span class="admin-badge badge-no">测试中...</span>';
            } else if (result.success) {
                statusHtml = '<span class="admin-badge badge-yes">正常</span>';
                latencyHtml = result.latency_ms + ' ms';
            } else {
                const errText = escapeHtml(result.error || '未知错误');
                statusHtml = `<span class="llm-status-error"><span class="admin-badge badge-error">异常</span><span class="llm-error-tooltip">${errText}</span></span>`;
                latencyHtml = result.latency_ms + ' ms';
            }
        }
        // 路由模块：flex 容器，每行最多 3 个
        let modulesHtml = '<span style="color:#999;">-</span>';
        if (m.modules.length) {
            const badges = m.modules.map(mod => `<span class="admin-badge badge-no">${escapeHtml(mod)}</span>`).join('');
            modulesHtml = `<div class="llm-module-tags">${badges}</div>`;
        }
        return `
            <tr>
                <td><strong>${escapeHtml(m.provider)}</strong></td>
                <td><code>${escapeHtml(m.model)}</code></td>
                <td>${modulesHtml}</td>
                <td><span class="admin-badge ${m.api_key_set ? 'badge-yes' : 'badge-error'}">${m.api_key_set ? '已配置' : '未配置'}</span></td>
                <td>${statusHtml}</td>
                <td>${latencyHtml}</td>
                <td>
                    <button class="admin-btn admin-btn-sm" onclick="testSingleModel('${escapeHtml(m.provider)}','${escapeHtml(m.model)}','${escapeHtml(m.tier)}')" ${!m.api_key_set ? 'disabled title="API Key 未配置"' : ''}>测试</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function testSingleModel(provider, model, tier) {
    const key = `${provider}:${model}:${tier}`;
    llmTestResults[key] = { loading: true };
    renderLlmHealthTable(llmModelsData);

    try {
        const result = await adminRequest('/admin/llm-health-check', {
            method: 'POST',
            body: JSON.stringify({ provider, model }),
        });
        llmTestResults[key] = result;
    } catch (e) {
        llmTestResults[key] = { success: false, latency_ms: 0, error: e.message };
    }
    renderLlmHealthTable(llmModelsData);
}

async function testAllModels() {
    const testable = llmModelsData.filter(m => m.api_key_set);
    if (!testable.length) {
        alert('没有可测试的模型（API Key 均未配置）');
        return;
    }
    // 标记所有为 loading
    testable.forEach(m => {
        const key = `${m.provider}:${m.model}:${m.tier}`;
        llmTestResults[key] = { loading: true };
    });
    renderLlmHealthTable(llmModelsData);

    // 并行测试
    await Promise.allSettled(testable.map(async (m) => {
        const key = `${m.provider}:${m.model}:${m.tier}`;
        try {
            const result = await adminRequest('/admin/llm-health-check', {
                method: 'POST',
                body: JSON.stringify({ provider: m.provider, model: m.model }),
            });
            llmTestResults[key] = result;
        } catch (e) {
            llmTestResults[key] = { success: false, latency_ms: 0, error: e.message };
        }
        renderLlmHealthTable(llmModelsData);
    }));
}

// ========== 初始化 ==========

window.onload = function () {
    document.getElementById('adminKeyInput').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') verifyKey();
    });

    const saved = sessionStorage.getItem('adminKey');
    if (saved) {
        adminKey = saved;
        document.getElementById('adminKeyInput').value = saved;
        verifyKey();
    }
};
