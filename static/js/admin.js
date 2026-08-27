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

// 張恆輔 8/25新增：數據管理維護頁（待審核資料表格 + 辨識結果圖彈窗）
document.addEventListener('DOMContentLoaded', () => {
    const tbody = document.getElementById('manage-tbody');
    if (!tbody) return;

    const badge = document.getElementById('pending-badge');
    const table = document.querySelector('.manage-table');
    const emptyEl = document.getElementById('manage-empty');
    const modal = document.getElementById('img-modal');
    const modalImg = document.getElementById('img-modal-img');
    const modalPlaceholder = document.getElementById('img-modal-placeholder');
    const modalCloseBtn = document.getElementById('img-modal-close');

    let trees = [];

    // 張恆輔 8/25新增：樹種清單，「未知」為預設值（species 尚未辨識時顯示）
    const speciesOptions = ['未知', '龍柏', '樟樹', '鳳凰木', '榕樹', '黑板樹', '茄苳', '美人樹', '小葉南洋杉'];

    const renderTrees = () => {
        tbody.innerHTML = '';
        badge.textContent = `${trees.length} 筆待審查`;

        if (trees.length === 0) {
            table.hidden = true;
            emptyEl.hidden = false;
            return;
        }
        table.hidden = false;
        emptyEl.hidden = true;

        trees.forEach((tree) => {
            const tr = document.createElement('tr');
            tr.dataset.id = tree.id;

            const currentSpecies = tree.species || '未知';
            const speciesOptionsHtml = speciesOptions
                .map((name) => `<option value="${name}"${name === currentSpecies ? ' selected' : ''}>${name}</option>`)
                .join('');

            tr.innerHTML = `
                <td>${tree.id}</td>
                <td><select class="species-select">${speciesOptionsHtml}</select></td>
                <td>${tree.carbon}</td>
                <td>${tree.lat}, ${tree.lng}</td>
                <td>${tree.site}</td>
                <td><button type="button" class="img-thumb" aria-label="查看辨識結果圖"></button></td>
                <td class="manage-actions">
                    <button type="button" class="confirm-btn" data-action="confirm">確認</button>
                    <button type="button" class="delete-btn" data-action="delete">刪除</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    };

    const closeModal = () => {
        modal.hidden = true;
        modalImg.hidden = true;
        modalImg.removeAttribute('src');
        modalPlaceholder.hidden = false;
    };

    const openModal = (imgSrc) => {
        modalPlaceholder.hidden = false;
        modalImg.hidden = true;
        if (imgSrc) {
            modalImg.onload = () => {
                modalPlaceholder.hidden = true;
                modalImg.hidden = false;
            };
            modalImg.onerror = () => {
                modalImg.hidden = true;
                modalPlaceholder.hidden = false;
            };
            modalImg.src = imgSrc;
        }
        modal.hidden = false;
    };

    tbody.addEventListener('click', (event) => {
        const target = event.target;
        const row = target.closest('tr');
        if (!row) return;
        const id = Number(row.dataset.id);

        if (target.classList.contains('img-thumb')) {
            const tree = trees.find((t) => t.id === id);
            openModal(tree ? tree.img : null);
            return;
        }

        // 負責人：陳政雍 8/27 串接確認／刪除 API
        if (target.dataset.action === 'confirm') {
            fetch(`/api/admin/trees/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'Approved' })
            })
                .then((res) => { if (!res.ok) throw new Error('請求失敗'); return res.json(); })
                .then(() => { trees = trees.filter((tree) => tree.id !== id); renderTrees(); })
                .catch((err) => { console.error(err); alert('確認失敗，請稍後再試'); });
            return;
        }
        if (target.dataset.action === 'delete') {
            fetch(`/api/admin/trees/${id}`, { method: 'DELETE' })
                .then((res) => { if (!res.ok) throw new Error('請求失敗'); return res.json(); })
                .then(() => { trees = trees.filter((tree) => tree.id !== id); renderTrees(); })
                .catch((err) => { console.error(err); alert('刪除失敗，請稍後再試'); });
            return;
        }
    });

    modalCloseBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) closeModal();
    });

    fetch('/api/admin/trees')
        .then((res) => {
            if (!res.ok) throw new Error('請求失敗');
            return res.json();
        })
        .then((data) => {
            trees = data;
            renderTrees();
        })
        .catch((err) => {
            console.error(err);
            alert('讀取待審核資料失敗，請稍後再試');
        });
});
