-- 用途：Measurements 新增拍攝地經緯度、RTK 配對誤差、影片幀率四個欄位
-- 開發日期：2026/08/29
--
-- 背景：
--   - latitude/longitude 是「拍攝當下」的座標（RTK 原始定位），跟 Trees.[LATITUDE N/S]/
--     [LONGITUDE E/W]（樹木校正後的真實座標）是不同概念、不同數值：同一棵樹可能有多筆
--     Measurements，每筆的拍攝地點都可能不同，但 Trees 只存一組最終校正後的座標。
--     型別用 FLOAT（已是帶正負號的十進位度數），跟 Trees 存的帶方向字母字串（如
--     "25.0883747N"）不同，不需要再用 _parse_coord() 轉換。
--   - rtk_gap_ms 沿用 services/merge_data.py align_sensor_data() 已經在算的同名欄位：
--     這筆 Arduino 紀錄時間，與 merge_asof 配對到的 RTK 紀錄時間，實際差了幾毫秒。
--     數值越大代表這筆 GPS 座標是用時間差較遠的 RTK 紀錄湊過來的，可信度較低，
--     供之後座標異常時回頭查是不是配對誤差造成的（品質檢查用）。目前 align_sensor_data()
--     只回傳這個值、還沒有地方能存起來，這次補上對應欄位。
--   - video_fps 存來源影片的幀率，供之後用 video_offset_ms 換算成實際影格編號。
--
-- 已確認 v_AdminPendingQueue / v_TreeCompleteData 這兩個 view 都是明確寫
-- t.[LATITUDE N/S] AS 緯度、t.[LONGITUDE E/W] AS 經度（從 Trees 撈，不是 SELECT *），
-- 不會跟這裡新增的 Measurements.latitude/longitude 衝突或撞名，view 不需要改。

ALTER TABLE Measurements
    ADD latitude    FLOAT NULL,
        longitude   FLOAT NULL,
        rtk_gap_ms  INT NULL,
        video_fps   FLOAT NULL;
