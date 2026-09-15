-- 用途：刪除 Measurements.video_fps 欄位
-- 開發日期：2026/08/29
--
-- 背景確認：
--   - video_fps 是在 2026-08-29_add_capture_fields_to_measurements.sql 加的，
--     原本規劃要用來把 video_offset_ms 換算成實際影格編號，
--     但目前全專案沒有任何程式碼會寫入或讀取這個欄位，一直是 NULL，可以安全刪除。

IF COL_LENGTH('dbo.Measurements', 'video_fps') IS NOT NULL
    ALTER TABLE dbo.Measurements DROP COLUMN video_fps;
