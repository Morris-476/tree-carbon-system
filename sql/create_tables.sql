-- 負責人：蔡宗倫
-- 開發日期：2026/08/22
-- 用意：暫存「Arduino(ToF) / RTK 時間對齊」結果，供之後影像追蹤（tracker）與
--       樹徑計算完成後，配合 track_id 寫入正式的 Trees / Measurements。
--       ⚠️ 此表為感測器原始資料的中繼表，不是 CONTRIBUTING.md 第 1 節列出的
--          Sites / Trees / Measurements / Species_Ref / Users 正式資料表，
--          那五張表的建表語法尚未收錄於此檔案，需由負責該功能的組員補上。
CREATE TABLE Sensor_Sync_Records (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    merge_batch_id    UNIQUEIDENTIFIER NOT NULL,      -- 同一次合併作業的批次編號
    arduino_tree_id   INT NOT NULL,                   -- Arduino CSV 檔名中的 Tree_ID（僅為現場流水編號，非 Trees.id）
    recorded_at       DATETIME2 NOT NULL,              -- 對齊後的真實時間（以 Arduino 時間戳記為準）
    latitude          FLOAT NULL,                      -- 配對到的 RTK 緯度，容忍誤差內無配對則為 NULL
    longitude         FLOAT NULL,                      -- 配對到的 RTK 經度，容忍誤差內無配對則為 NULL
    rtk_height_m      FLOAT NULL,
    rtk_speed_mps     FLOAT NULL,
    rtk_heading_deg   FLOAT NULL,
    rtk_tag           VARCHAR(4) NULL,                 -- RTK 原始 TAG 欄位（如 T/C）
    laser_status      VARCHAR(16) NULL,
    led_status        VARCHAR(16) NULL,
    tof_dist1_cm      FLOAT NULL,
    tof_dist2_cm      FLOAT NULL,
    rtk_gap_ms        INT NULL,                        -- 配對到的 RTK 紀錄與此筆時間差（毫秒），供偵錯用
    video_offset_ms   INT NOT NULL,                     -- 相對於影片第 0 影格的毫秒數（影片起始時間見 merge_data.py 說明）
    video_filename    VARCHAR(255) NULL,
    created_at        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
