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

// 陳信睿 8/18新增(系統管理下拉選單)
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.querySelector('.nav-dropdown-toggle');
    const menu = document.querySelector('.nav-dropdown-menu');
    if (!toggle || !menu) return;

    toggle.addEventListener('click', (event) => {
        event.stopPropagation();
        menu.hidden = !menu.hidden;
    });

    document.addEventListener('click', (event) => {
        if (!menu.hidden && !menu.contains(event.target) && event.target !== toggle) {
            menu.hidden = true;
        }
    });
});