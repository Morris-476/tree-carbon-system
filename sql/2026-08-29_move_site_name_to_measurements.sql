-- 用途：把 site_name 從 Sites 移到 Measurements，之後不再需要 Sites 表
-- 開發日期：2026/08/29
--
-- 背景確認：
--   - Sites 目前是空表（0 筆），Trees.site_id 全部是 NULL——專案裡沒有任何程式碼
--     真的建立過 Sites 資料或設定過 Trees.site_id（_get_or_create_tree_id() 的
--     site_id 參數從未被呼叫端帶入過值），這個關聯目前是完全沒在用的殼子。
--   - 因為沒有資料，這裡不需要資料搬遷（UPDATE），直接改結構即可。
--   - v_AdminPendingQueue / v_TreeCompleteData 這兩個 view 原本用
--     Trees.site_id LEFT JOIN Sites 撈 site_name，改成直接讀 Measurements.site_name。

BEGIN TRANSACTION;

-- ── 1. Measurements 新增 site_name ─────────────────────────────
ALTER TABLE Measurements
    ADD site_name NVARCHAR(50) NULL;

-- ── 2. Trees 移除 site_id（連同其 FK）────────────────────────────
ALTER TABLE Trees DROP CONSTRAINT FK__Trees__site_id__03F0984C;
ALTER TABLE Trees DROP COLUMN site_id;

-- ── 3. 刪除 Sites ───────────────────────────────────────────────
DROP TABLE Sites;

-- ── 4. 改寫兩個 view，改從 Measurements.site_name 撈 ──────────────
GO
CREATE OR ALTER VIEW v_TreeCompleteData AS
SELECT
    m.record_id AS 紀錄編號,
    t.Tree_ID AS Tree_ID,
    ISNULL(m.site_name, N'尚未定案場') AS 巡檢案場,
    ISNULL(sp.species_name, N'尚未辨識') AS 樹木種類,
    m.dbh AS 樹徑cm,
    m.carbon_absorpation AS 固碳量,
    t.[LATITUDE N/S] AS 緯度,
    t.[LONGITUDE E/W] AS 經度,
    m.image_data AS 樹木照片二進位
FROM Measurements m
LEFT JOIN Trees t ON m.tree_id = t.tree_id
LEFT JOIN Species_Ref sp ON t.species_id = sp.species_id
WHERE m.status = N'Approved';
GO

CREATE OR ALTER VIEW v_AdminPendingQueue AS
SELECT
    m.record_id AS 紀錄編號,
    t.Tree_ID AS Tree_ID,
    ISNULL(m.site_name, N'尚未定案場') AS 巡檢案場,
    ISNULL(sp.species_name, N'尚未辨識') AS 樹木種類,
    m.dbh AS 樹徑cm,
    m.carbon_absorpation AS 固碳量,
    t.[LATITUDE N/S] AS 緯度,
    t.[LONGITUDE E/W] AS 經度,
    m.image_data AS 樹木照片二進位
FROM Measurements m
LEFT JOIN Trees t ON m.tree_id = t.tree_id
LEFT JOIN Species_Ref sp ON t.species_id = sp.species_id
WHERE m.status = N'Pending';
GO

COMMIT TRANSACTION;
