-- 用途：新增 Camera_Calibration 表，存放各手機型號的相機校正參數
-- 開發日期：2026/09/08
--
-- 資料來源：Tree-Trunk-Segmentation 桌面工具的 config.py 裡的 CAMERA_PRESETS 字典
-- （焦距換算樹徑用：實際物理焦距 focal_mm，感光元件寬度 sensor_width_mm）。
-- 不包含 config.py 裡的 PHONE_MODEL_OTHER=「其他」選項——那是給使用者選擇「其他廠牌/
-- 機型」時，讓他自行輸入實際焦距與感光元件寬度用的 UI 選項，沒有固定數值可存。

CREATE TABLE Camera_Calibration (
    phone_model      NVARCHAR(50) NOT NULL PRIMARY KEY,
    focal_mm         DECIMAL(5,2) NOT NULL,
    sensor_width_mm  DECIMAL(5,2) NOT NULL
);

INSERT INTO Camera_Calibration (phone_model, focal_mm, sensor_width_mm) VALUES
    ('iPhone 13',               5.7, 7.5),
    ('iPhone 13 Pro',           5.8, 7.8),
    ('iPhone 14',               5.7, 7.5),
    ('iPhone 14 Pro',           6.9, 10.0),
    ('iPhone 15',               6.2, 8.2),
    ('iPhone 15 Pro',           6.9, 10.0),
    ('iPhone 16',               6.2, 8.2),
    ('iPhone 16 Pro',           6.9, 10.0),
    ('Samsung Galaxy S24 Ultra', 6.5, 9.9);
