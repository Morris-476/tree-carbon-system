// static/js/map.js
// Leaflet 地圖初始化與樹木標記邏輯。
// 依賴：templates/map.html 在載入此檔案前先注入全域變數 TREES_DATA。

document.addEventListener('DOMContentLoaded', function () {
    var map = L.map('map').setView([25.1748, 121.4505], 18);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 20,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    TREES_DATA.forEach(function (t) {
        if (t.lat == null || t.lng == null) return;

        var imgHtml = t.img
            ? '<img src="/static/' + t.img + '" alt="縮圖">'
            : '';

        var popup = '<div class="tree-popup-card">'
            + imgHtml
            + '<div class="tree-info-row"><span class="info-label">樹種</span><span class="info-value">' + t.species + '</span></div>'
            + '<div class="tree-info-row"><span class="info-label">編號</span><span class="info-value">#' + t.id + '</span></div>'
            + '<div class="tree-info-row"><span class="info-label">DBH</span><span class="info-value">' + t.dbh + ' cm</span></div>'
            + '<div class="tree-info-row"><span class="info-label">固碳量</span><span class="info-value">' + t.carbon + ' kg</span></div>'
            + '<div class="tree-info-row"><span class="info-label">時間</span><span class="info-value">' + (t.time || '—') + '</span></div>'
            + '</div>';

        L.marker([t.lat, t.lng]).addTo(map).bindPopup(popup);
    });
});
