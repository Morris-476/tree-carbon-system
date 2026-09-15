// 檢視資料表頁：串接 GET /api/trees，動態填入表格
document.addEventListener('DOMContentLoaded', () => {
    const table = document.querySelector('.dashboard-table');
    if (!table) return;

    const tbody = table.querySelector('tbody');

    const modal = document.getElementById('dashboard-img-modal');
    const modalImg = document.getElementById('dashboard-img-modal-img');
    const modalPlaceholder = document.getElementById('dashboard-img-modal-placeholder');
    const modalCloseBtn = document.getElementById('dashboard-img-modal-close');

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

    modalCloseBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) closeModal();
    });

    const showError = (message) => {
        console.error(message);
        let errorEl = document.querySelector('.dashboard-error');
        if (!errorEl) {
            errorEl = document.createElement('p');
            errorEl.className = 'dashboard-error login-error';
            table.parentNode.insertBefore(errorEl, table);
        }
        errorEl.textContent = '資料載入失敗，請稍後再試';
    };

    const isEmpty = (value) => value === null || value === undefined || value === '';
    const formatValue = (value) => (isEmpty(value) ? '尚無資料' : value);

    const buildRow = (tree) => {
        const tr = document.createElement('tr');

        const idCell = document.createElement('td');
        idCell.textContent = formatValue(tree.record_id);
        tr.appendChild(idCell);

        const treeIdCell = document.createElement('td');
        treeIdCell.textContent = formatValue(tree.tree_id);
        tr.appendChild(treeIdCell);

        const speciesCell = document.createElement('td');
        speciesCell.textContent = formatValue(tree.species_name);
        tr.appendChild(speciesCell);

        const dbhCell = document.createElement('td');
        dbhCell.textContent = isEmpty(tree.dbh) ? '尚無資料' : `${tree.dbh} cm`;
        tr.appendChild(dbhCell);

        const carbonCell = document.createElement('td');
        carbonCell.textContent = isEmpty(tree.carbon_absorpation) ? '尚無資料' : `${tree.carbon_absorpation} kg`;
        tr.appendChild(carbonCell);

        const coordCell = document.createElement('td');
        coordCell.textContent = (isEmpty(tree.latitude) || isEmpty(tree.longitude))
            ? '尚無資料'
            : `${tree.latitude}, ${tree.longitude}`;
        tr.appendChild(coordCell);

        const siteCell = document.createElement('td');
        siteCell.textContent = formatValue(tree.site_name);
        tr.appendChild(siteCell);

        const imgCell = document.createElement('td');
        const imgThumb = document.createElement('button');
        imgThumb.type = 'button';
        imgThumb.className = 'img-thumb';
        imgThumb.setAttribute('aria-label', '查看照片');
        imgThumb.addEventListener('click', () => openModal(tree.img));
        imgCell.appendChild(imgThumb);
        tr.appendChild(imgCell);

        return tr;
    };

    const loadTrees = async () => {
        let res;
        try {
            res = await fetch('/api/trees');
        } catch (err) {
            showError('無法連線到伺服器');
            return;
        }

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            showError(data.error || '樹木資料載入失敗');
            return;
        }

        (data.trees || []).forEach((tree) => {
            tbody.appendChild(buildRow(tree));
        });
    };

    loadTrees();
});
