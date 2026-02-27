// 登录页逻辑

// 如果已有 token，直接跳转首页
if (storage.get('token')) {
    window.location.href = 'index.html';
}

async function handleLogin(event) {
    event.preventDefault();

    const phone = document.getElementById('phone').value.trim();
    const password = document.getElementById('password').value;
    const errorEl = document.getElementById('loginError');
    const btn = document.getElementById('loginBtn');

    errorEl.textContent = '';

    if (!phone || !password) {
        errorEl.textContent = '请输入手机号和密码';
        return;
    }

    btn.disabled = true;
    btn.textContent = '登录中...';

    try {
        const data = await api.auth.login(phone, password);

        // 存储 token 和用户信息
        storage.set('token', data.token);
        storage.set('userId', data.user.id);

        // 跳转首页
        window.location.href = 'index.html';
    } catch (error) {
        errorEl.textContent = error.message || '登录失败，请重试';
    } finally {
        btn.disabled = false;
        btn.textContent = '登录';
    }
}
