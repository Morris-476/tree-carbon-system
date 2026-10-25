-- 用途：Measurements.rtk_gap_ms 改名為 gnss_gap_ms
-- 開發日期：2026/09/09
--
-- 背景確認：
--   - 這欄位存的是「配對到的 GPS 定位紀錄」與 Arduino 紀錄的時間差，
--     GPS 定位資料其實是 GNSS（RTK 只是其中一種定位技術），改名較準確。
--   - 用 sp_rename 就地改名，保留既有資料，不是新增欄位再搬資料。

IF COL_LENGTH('dbo.Measurements', 'rtk_gap_ms') IS NOT NULL
   AND COL_LENGTH('dbo.Measurements', 'gnss_gap_ms') IS NULL
    EXEC sp_rename 'dbo.Measurements.rtk_gap_ms', 'gnss_gap_ms', 'COLUMN';
