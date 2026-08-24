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
            window.location.href = form.dataset.next || '/';
        } else {
            errorEl.textContent = data.error || '登入失敗';
            errorEl.hidden = false;
        }
    });
});

// 張恆輔 8/15新增：資料上傳頁（RTK／Arduino／MP4）
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('upload-form');
    if (!form) return;

    const errorEl = document.getElementById('upload-error');
    const cancelBtn = document.getElementById('upload-cancel-btn');
    const filePills = form.querySelectorAll('.file-pill-input');

    const resetFilePills = () => {
        filePills.forEach((input) => {
            const textEl = input.previousElementSibling;
            textEl.textContent = textEl.dataset.placeholder;
        });
    };

    filePills.forEach((input) => {
        const textEl = input.previousElementSibling;
        input.addEventListener('change', () => {
            textEl.textContent = input.files[0] ? input.files[0].name : textEl.dataset.placeholder;
        });
    });

    cancelBtn.addEventListener('click', () => {
        form.reset();
        resetFilePills();
        errorEl.hidden = true;
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorEl.hidden = true;
        errorEl.textContent = '';

        const formData = new FormData(form);

        let res;
        try {
            res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
        } catch (err) {
            errorEl.textContent = '無法連線到伺服器';
            errorEl.hidden = false;
            return;
        }

        const data = await res.json().catch(() => ({}));

        if (res.ok) {
            alert('上傳成功，已送交管理員審核');
            form.reset();
            resetFilePills();
        } else {
            errorEl.textContent = data.error || '上傳失敗';
            errorEl.hidden = false;
        }
    });
});
