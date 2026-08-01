document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    if (!form) return;

    const errorEl = document.getElementById('login-error');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorEl.hidden = true;
        errorEl.textContent = '';

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        let res;
        try {
            res = await fetch('/api/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
        } catch (err) {
            errorEl.textContent = '無法連線到伺服器';
            errorEl.hidden = false;
            return;
        }

        const data = await res.json().catch(() => ({}));

        if (res.ok) {
            window.location.href = '/admin/dashboard';
        } else {
            errorEl.textContent = data.error || '登入失敗';
            errorEl.hidden = false;
        }
    });
});
