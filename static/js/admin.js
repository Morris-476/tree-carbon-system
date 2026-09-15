// 陳信睿 8/28修改
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
            alert(`時間對齊完成，共 ${data.total_count} 筆，其中 ${data.matched_gps_count} 筆配對到 GPS 座標，已寫入 ${data.inserted} 筆量測資料（案場：${data.site_name || '未提供影片'}）`);
            form.reset();
            resetFilePills();
        } else {
            errorEl.textContent = data.error || '上傳失敗';
            errorEl.hidden = false;
        }
    });
});

// 2026/09/06新增：資料上傳頁的拍攝設備下拉選單，串接 GET /api/camera-profiles
// 資料表 Camera_Profiles 尚未建立，後端會先回傳內建清單，介面照樣可用
document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('camera-profile-select');
    if (!select) return;

    const manualFields = document.getElementById('camera-manual-fields');
    const focalInput = document.getElementById('camera-focal-input');
    const sensorWidthInput = document.getElementById('camera-sensor-width-input');

    const applySelection = () => {
        const isOther = select.value === '其他';
        manualFields.hidden = !isOther;
        focalInput.required = isOther;
        sensorWidthInput.required = isOther;

        if (isOther) {
            focalInput.value = '';
            sensorWidthInput.value = '';
            return;
        }

        // 選了預設機型：把該選項存的 focal_mm/sensor_width 帶進隱藏欄位一起送出，
        // 「其他」以外都不用使用者自己填數字
        const selectedOption = select.options[select.selectedIndex];
        focalInput.value = selectedOption.dataset.focalMm || '';
        sensorWidthInput.value = selectedOption.dataset.sensorWidth || '';
    };

    select.addEventListener('change', applySelection);
    applySelection();

    fetch('/api/camera-profiles')
        .then((res) => { if (!res.ok) throw new Error('請求失敗'); return res.json(); })
        .then((profiles) => {
            profiles.forEach((profile) => {
                const opt = document.createElement('option');
                opt.value = profile.name;
                opt.textContent = profile.name;
                opt.dataset.focalMm = profile.focal_mm;
                opt.dataset.sensorWidth = profile.sensor_width;
                select.insertBefore(opt, select.querySelector('option[value="其他"]'));
            });
        })
        .catch((err) => console.error('拍攝設備清單載入失敗', err));
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

    // 2026/09/12新增：雙擊編輯樹種／樹徑，暫存在畫面上，跟著「確認」一起送出，
    // 不會每改一次就打一次 API。key 是 tree.id，value 是 {species?, dbh?}。
    const pendingEdits = {};

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

            // 張恆輔 8/29修正：補回「編號」欄（原本被誤換成 tree_id），Tree_ID 改成獨立一欄
            tr.innerHTML = `
                <td>${tree.id}</td>
                <td>${tree.tree_id}</td>
                <td><select class="species-select">${speciesOptionsHtml}</select></td>
                <td class="editable-cell" data-field="dbh">${tree.dbh}</td>
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

    // 2026/09/12新增：雙擊樹徑儲存格，換成輸入框讓管理員修改。
    // 失焦或按 Enter 時把新值存進 pendingEdits，畫面文字跟著換成新值，
    // 但還不會打 API——要等按下「確認」才會真的送出。
    tbody.addEventListener('dblclick', (event) => {
        const cell = event.target.closest('.editable-cell[data-field="dbh"]');
        if (!cell || cell.querySelector('input')) return;

        const row = cell.closest('tr');
        const id = Number(row.dataset.id);
        const originalValue = cell.textContent.trim();

        const input = document.createElement('input');
        input.type = 'number';
        input.step = '0.01';
        input.className = 'cell-input';
        input.value = originalValue;

        const finishEdit = () => {
            const newValue = input.value.trim();
            cell.textContent = newValue;
            if (newValue !== '' && Number(newValue) !== Number(originalValue)) {
                pendingEdits[id] = { ...pendingEdits[id], dbh: Number(newValue) };
            }
        };

        input.addEventListener('blur', finishEdit);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
        });

        cell.textContent = '';
        cell.appendChild(input);
        input.focus();
        input.select();
    });

    // 2026/09/12新增：樹種下拉選單改變時，先暫存，跟樹徑一樣等「確認」才送出
    tbody.addEventListener('change', (event) => {
        if (!event.target.classList.contains('species-select')) return;
        const row = event.target.closest('tr');
        const id = Number(row.dataset.id);
        pendingEdits[id] = { ...pendingEdits[id], species: event.target.value };
    });

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
        // 2026/09/12修改：把 pendingEdits 裡暫存的樹種／樹徑修改一起送出，
        // 後端會用最新的樹徑＋樹種重新算一次固碳量。
        if (target.dataset.action === 'confirm') {
            fetch(`/api/admin/trees/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'Approved', ...pendingEdits[id] })
            })
                .then((res) => { if (!res.ok) throw new Error('請求失敗'); return res.json(); })
                .then(() => {
                    delete pendingEdits[id];
                    trees = trees.filter((tree) => tree.id !== id);
                    renderTrees();
                })
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
