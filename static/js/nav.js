// 陳信睿 8/7新增(登出按鈕動作、路徑)
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('logout-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        try {
            await fetch('/api/admin/logout', { method: 'POST' });
        } catch (err) {
        }
        window.location.href = '/';
    });
});