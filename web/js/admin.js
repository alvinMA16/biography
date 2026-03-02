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
    document.getElementById('mainSection').style.display = 'none';
    document.getElementById('authSection').style.display = 'flex';
    document.getElementById('adminKeyInput').value = '';
    // 重置 tab 到用户管理
    switchTab('users');
}

// ========== Tab 切换 ==========

let eraMemoriesLoaded = false;
let monitoringLoaded = false;
let monitoringData = null;

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
    } else if (tab === 'monitoring') {
        document.getElementById('tabMonitoring').classList.add('active');
        if (!monitoringLoaded) loadMonitoringData();
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
        tbody.innerHTML = '<tr><td colspan="10" class="admin-table-empty">暂无用户</td></tr>';
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
            <td>${u.hometown || '<span class="text-muted">-</span>'}</td>
            <td>${u.main_city || '<span class="text-muted">-</span>'}</td>
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
    if (!phone || !password) {
        alert('请填写手机号和密码');
        return;
    }

    const payload = { phone, password };

    const nickname = document.getElementById('createNickname').value.trim();
    const birthYear = document.getElementById('createBirthYear').value.trim();
    const hometown = document.getElementById('createHometown').value.trim();
    const mainCity = document.getElementById('createMainCity').value.trim();

    if (nickname) payload.nickname = nickname;
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

// ========== 数据监控 ==========

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
    // 总体概览
    document.getElementById('statTotalUsers').textContent = data.overview.total_users;
    document.getElementById('statProfileCompleted').textContent = data.overview.profile_completed_users;
    document.getElementById('statProfileRate').textContent = `完成率 ${(data.overview.profile_completion_rate * 100).toFixed(0)}%`;
    document.getElementById('statTotalConversations').textContent = data.overview.total_conversations;
    document.getElementById('statTotalMemoirs').textContent = data.overview.total_memoirs;

    // 活跃度
    document.getElementById('statTodayActive').textContent = data.activity.today_active_users;
    document.getElementById('statWeekActive').textContent = data.activity.week_active_users;
    document.getElementById('statMonthActive').textContent = data.activity.month_active_users;
    document.getElementById('statTodayConv').textContent = data.activity.today_new_conversations;
    document.getElementById('statTodayMemoir').textContent = data.activity.today_new_memoirs;

    // 留存率
    document.getElementById('statRetention1').textContent = formatRetention(data.retention.day1);
    document.getElementById('statRetention7').textContent = formatRetention(data.retention.day7);
    document.getElementById('statRetention30').textContent = formatRetention(data.retention.day30);

    // 分布图
    renderDistribution('distConversations', data.distributions.conversations_per_user, 'avgConversations', data.overview.total_conversations, data.overview.total_users, '次对话/人');
    renderDistribution('distMemoirs', data.distributions.memoirs_per_user, 'avgMemoirs', data.overview.total_memoirs, data.overview.total_users, '篇回忆/人');
    renderDistribution('distMessages', data.distributions.messages_per_conversation, 'avgMessages', null, null, null);
    renderDistribution('distBirthDecade', data.distributions.birth_decade);
    renderDistribution('distHometown', data.distributions.hometown_province);
}

function formatRetention(value) {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(0)}%`;
}

function renderDistribution(containerId, items, avgId, totalItems, totalUsers, avgUnit) {
    const container = document.getElementById(containerId);
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="admin-empty-state">暂无数据</div>';
        return;
    }

    const maxCount = Math.max(...items.map(i => i.count));

    container.innerHTML = items.map(item => {
        const percent = maxCount > 0 ? (item.count / maxCount * 100) : 0;
        return `
            <div class="admin-dist-row">
                <div class="admin-dist-label">${item.label}</div>
                <div class="admin-dist-bar-wrap">
                    <div class="admin-dist-bar" style="width: ${percent}%"></div>
                </div>
                <div class="admin-dist-count">${item.count}</div>
            </div>
        `;
    }).join('');

    // 平均值
    if (avgId && totalItems !== null && totalUsers !== null && totalUsers > 0) {
        const avg = (totalItems / totalUsers).toFixed(1);
        document.getElementById(avgId).textContent = `平均 ${avg} ${avgUnit}`;
    }
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

    // 账号信息
    document.getElementById('detailPhone').textContent = detail.phone || '-';
    document.getElementById('detailStatus').innerHTML = detail.is_active
        ? '<span class="admin-badge badge-yes">正常</span>'
        : '<span class="admin-badge badge-no">已禁用</span>';
    document.getElementById('detailProfileStatus').innerHTML = detail.profile_completed
        ? '<span class="admin-badge badge-yes">已完成</span>'
        : '<span class="admin-badge badge-no">未完成</span>';
    document.getElementById('detailCreatedAt').textContent = detail.created_at
        ? new Date(detail.created_at).toLocaleString('zh-CN')
        : '-';

    // 基础信息
    document.getElementById('detailNickname').textContent = detail.nickname || '-';
    document.getElementById('detailBirthYear').textContent = detail.birth_year ? `${detail.birth_year}年` : '-';
    document.getElementById('detailHometown').textContent = detail.hometown || '-';
    document.getElementById('detailMainCity').textContent = detail.main_city || '-';

    // 回忆列表
    document.getElementById('memoirCount').textContent = detail.memoirs.length;
    renderMemoirList(detail.memoirs, detail.conversations);
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

    container.innerHTML = memoirs.map(m => {
        const isGenerating = m.status === 'generating';
        const yearText = formatYearRange(m.year_start, m.year_end, m.time_period);
        const timeText = formatTimeRange(m.conversation_start, m.conversation_end);

        return `
            <div class="admin-memoir-item ${isGenerating ? 'generating' : ''}" onclick="showMemoirDetail('${m.id}')">
                <div class="admin-memoir-item-main">
                    <div class="admin-memoir-item-title">
                        <span class="title-text">${escapeHtml(m.title)}</span>
                        ${isGenerating ? '<span class="admin-memoir-status">撰写中...</span>' : ''}
                    </div>
                    ${yearText ? `<div class="admin-memoir-item-year">${yearText}</div>` : ''}
                    ${timeText ? `<div class="admin-memoir-item-time">${timeText}</div>` : ''}
                </div>
                <div class="admin-memoir-item-arrow">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 18l6-6-6-6"/>
                    </svg>
                </div>
            </div>
        `;
    }).join('');
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
