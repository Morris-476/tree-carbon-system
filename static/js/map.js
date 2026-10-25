// static/js/map.js
// 負責人：陳政雍、陳信睿
// 用途：地圖初始化、讀取樹木資料並在 Leaflet 地圖彈出樹木卡片資訊 (整合 Azure Blob Storage)

document.addEventListener('DOMContentLoaded', () => {
    const mapEl = document.getElementById('treeMap');
    if (!mapEl) return;

    // 淡江大學校園座標
    const map = L.map('treeMap').setView([25.1745, 121.4502], 19);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    const pinIcon = L.divIcon({
        className: 'tree-pin',
        html: '<div class="tree-pin-body"></div>',
        iconSize: [24, 24],
        iconAnchor: [12, 24],
        popupAnchor: [0, -24]
    });

    const showError = (message) => {
        console.error(message);
    };

    const isEmpty = (value) => value === null || value === undefined || value === '';
    const formatValue = (value) => (isEmpty(value) ? '尚無資料' : value);

    const buildTreeCard = (tree, marker) => {
        const card = document.createElement('div');
        card.className = 'tree-info-card';

        // 標題：樹種名稱
        const title = document.createElement('h3');
        title.className = 'tree-info-card-title';
        title.textContent = formatValue(tree.species_name);
        card.appendChild(title);

        // 圖片外框：優先載入 Azure Blob 的 image_url 或 tree.img
        const imageBox = document.createElement('div');
        imageBox.className = 'tree-info-card-image';
        const imgUrl = tree.image_url || tree.img;

        if (imgUrl) {
            const img = document.createElement('img');
            img.src = imgUrl;
            img.alt = tree.species_name || '樹木照片';
            // 🎯 若 Blob 圖片載入失敗，自動替換為預設防呆圖片
            img.onerror = () => {
                img.onerror = null;
                img.src = '/static/img/no-image.png';
            };
            imageBox.appendChild(img);
        } else {
            const noImgText = document.createElement('span');
            noImgText.textContent = '暫無照片';
            noImgText.style.color = '#777';
            noImgText.style.fontSize = '0.85rem';
            imageBox.appendChild(noImgText);
        }
        card.appendChild(imageBox);

        // 樹木詳細資訊
        const info = document.createElement('div');
        info.className = 'tree-info-card-info';

        const coordText = (isEmpty(tree.latitude) || isEmpty(tree.longitude))
            ? '尚無資料'
            : `${tree.latitude}, ${tree.longitude}`;

        const carbonText = !isEmpty(tree.carbon_absorpation)
            ? `${tree.carbon_absorpation} kg`
            : '尚無資料';

        const dbhText = !isEmpty(tree.dbh)
            ? `${tree.dbh} cm`
            : '尚無資料';

        // 欄位清單（加入案場、胸徑與固碳量）
        const rows = [
            ['巡檢案場：', formatValue(tree.site_name)],
            ['樹種名：', formatValue(tree.species_name)],
            ['樹木胸徑：', dbhText],
            ['樹木固碳量：', carbonText],
            ['經緯度：', coordText]
        ];

        rows.forEach(([label, value]) => {
            const row = document.createElement('p');
            row.className = 'tree-info-card-row';

            const labelEl = document.createElement('span');
            labelEl.className = 'tree-info-card-label';
            labelEl.textContent = label;
            row.appendChild(labelEl);
            row.appendChild(document.createTextNode(value));

            info.appendChild(row);
        });

        card.appendChild(info);

        // 關閉按鈕
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'tree-info-card-close';
        closeBtn.textContent = '關閉';
        closeBtn.addEventListener('click', () => marker.closePopup());
        card.appendChild(closeBtn);

        return card;
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
            if (tree.latitude == null || tree.longitude == null) return;

            const marker = L.marker([tree.latitude, tree.longitude], { icon: pinIcon }).addTo(map);
            const card = buildTreeCard(tree, marker);
            marker.bindPopup(card, { closeButton: false });
        });
    };

    loadTrees();
});