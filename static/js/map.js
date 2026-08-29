//陳政雍 8/18新增Map功能
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

        const title = document.createElement('h3');
        title.className = 'tree-info-card-title';
        title.textContent = formatValue(tree.species_name);
        card.appendChild(title);

        const imageBox = document.createElement('div');
        imageBox.className = 'tree-info-card-image';
        if (tree.img) {
            const img = document.createElement('img');
            img.src = tree.img;
            img.alt = tree.species_name || '';
            imageBox.appendChild(img);
        }
        card.appendChild(imageBox);

        const info = document.createElement('div');
        info.className = 'tree-info-card-info';

        const coordText = (isEmpty(tree.latitude) || isEmpty(tree.longitude))
            ? '尚無資料'
            : `${tree.latitude}, ${tree.longitude}`;

        const rows = [
            ['樹種名：', formatValue(tree.species_name)],
            ['樹木固碳量：', formatValue(tree.carbon_absorpation)],
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
