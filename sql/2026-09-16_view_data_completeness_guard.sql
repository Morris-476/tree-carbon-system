-- 用途：v_TreeCompleteData／v_AdminPendingQueue 補上資料完整性檢查
-- 開發日期：2026/09/16
--
-- 背景：後端 admin_update_measurement() 已在核准前檢查照片/樹徑/座標/
-- Tree_ID 對應關係，這裡是第二層防護——就算有資料繞過該檢查被設成
-- Approved，前端實際查詢的 v_TreeCompleteData 也絕不會顯示不完整的物件。
-- v_AdminPendingQueue 維持不濾照片/樹徑（後台本就需要看到「缺什麼」），
-- 只加上跟 get_all_trees_admin() 一致的 Tree_ID 對應關係檢查。

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
JOIN Trees t ON m.tree_id = t.tree_id
LEFT JOIN Species_Ref sp ON t.species_id = sp.species_id
WHERE m.status = N'Approved'
  AND m.image_data IS NOT NULL
  AND m.dbh > 0
  AND t.[LATITUDE N/S] IS NOT NULL
  AND t.[LONGITUDE E/W] IS NOT NULL
  AND m.track_id IS NOT NULL
  AND t.tracker_id = m.track_id;
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
JOIN Trees t ON m.tree_id = t.tree_id
LEFT JOIN Species_Ref sp ON t.species_id = sp.species_id
WHERE m.status = N'Pending'
  AND m.track_id IS NOT NULL
  AND t.tracker_id = m.track_id;
GO
