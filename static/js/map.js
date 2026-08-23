//陳政雍 8/18新增Map功能
document.addEventListener('DOMContentLoaded', () => {
    const mapEl = document.getElementById('treeMap');
    if (!mapEl) return;

    // 淡江大學校園座標
    const map = L.map('treeMap').setView([25.1745, 121.4502], 17);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
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
            if (tree.lat == null || tree.lng == null) return;

            const marker = L.marker([tree.lat, tree.lng], { icon: pinIcon }).addTo(map);
            const popupEl = document.createElement('div');

            const speciesLine = document.createElement('p');
            speciesLine.textContent = `樹種：${tree.species}`;
            popupEl.appendChild(speciesLine);

            const dbhLine = document.createElement('p');
            dbhLine.textContent = `樹徑：${tree.dbh} cm`;
            popupEl.appendChild(dbhLine);

            const carbonLine = document.createElement('p');
            carbonLine.textContent = `固碳量：${tree.carbon} kg`;
            popupEl.appendChild(carbonLine);

            if (tree.img) {
                const img = document.createElement('img');
                img.src = tree.img;
                img.alt = tree.species || '';
                img.style.maxWidth = '200px';
                popupEl.appendChild(img);
            }

            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.textContent = '關閉';
            closeBtn.addEventListener('click', () => marker.closePopup());
            popupEl.appendChild(closeBtn);

            marker.bindPopup(popupEl);
        });
    };

    loadTrees();
});
