-- 用途：(1) 將 Biomass_Parameters 併入 Species_Ref，關聯鍵由 species_name 改為 species_id
--       (2) 刪除全專案無程式碼使用的舊測試表 tree_records
-- 開發日期：2026/08/29
--
-- 背景確認（執行前已用 INFORMATION_SCHEMA / sys.foreign_keys / sys.sql_modules 查證）：
--   - Biomass_Parameters 與 Species_Ref 為一對一關係，原本用 species_name（nvarchar）
--     互相關聯（Biomass_Parameters.species_name 為 PK 兼 FK），存在打錯字/改名對不起來的風險。
--   - Species_Ref 本身已有原生數字主鍵 species_id，合併後直接用它，不需要額外關聯鍵。
--   - tree_records 沒有任何 FK 指向/來自它，也沒有 view、預存程序、trigger 引用它，
--     全部都是可安全直接刪除的舊測試資料。
--
-- 執行前請先確認：已對這兩張表做好備份（Azure SQL 可用「還原到某時間點」，
-- 或先 SELECT * INTO Biomass_Parameters_backup_20260829 FROM Biomass_Parameters 之類的手動備份）。

BEGIN TRANSACTION;

-- ── 1. Species_Ref 新增異速生長方程式參數欄位 ─────────────────────
--    biomass = allo_param_a × dbh ^ allo_param_b
ALTER TABLE Species_Ref
    ADD allo_param_a DECIMAL(18,6) NULL,
        allo_param_b DECIMAL(18,6) NULL;

-- ── 2. 搬資料：這是最後一次用 species_name 做對應 ──────────────────
--    （搬完之後 allo_param_a/b 就跟著 species_id 走，不再需要字串比對）
UPDATE sr
SET sr.allo_param_a = bp.parameter_a,
    sr.allo_param_b = bp.parameter_b
FROM Species_Ref sr
JOIN Biomass_Parameters bp ON sr.species_name = bp.species_name;

-- ── 3. 刪除 Biomass_Parameters ─────────────────────────────────────
--    Biomass_Parameters.species_name 上的 FK 屬於這張表自己，
--    DROP TABLE 會一併移除，不需要另外下 DROP CONSTRAINT。
DROP TABLE Biomass_Parameters;

-- ── 4. 刪除未使用的 tree_records（舊測試資料）──────────────────────
DROP TABLE tree_records;

COMMIT TRANSACTION;
