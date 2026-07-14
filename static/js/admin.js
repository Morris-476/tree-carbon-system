// static/js/admin.js
// 後台儀表板的互動邏輯：載入樹木清單、確認發布、刪除、登出、狀態篩選。

document.addEventListener('DOMContentLoaded', function () {
    // TODO: 待實作 — 負責人：____
    // 實作後台互動功能，包含：
    //   - 頁面載入時呼叫 GET /api/admin/trees 取得清單並渲染表格
    //   - 確認發布：PUT /api/admin/trees/<id>，body: { status: 'confirmed' }
    //   - 刪除記錄：DELETE /api/admin/trees/<id>
    //   - 狀態篩選按鈕（全部 / 待審核 / 已發布）
    //   - 登出按鈕：POST /api/admin/logout，成功後轉址到 /admin/login
    //   - 收到 401 回應時自動轉址到 /admin/login
});
