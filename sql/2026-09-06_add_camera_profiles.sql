-- 用途：新增 Camera_Profiles 表，管理「資料上傳」頁可選擇的拍攝設備型號
--       （焦距、感光元件寬度），供樹徑焦距公式換算使用。
-- 開發日期：2026/09/06
--
-- 說明：在這張表建好、資料匯入前，services/db.py 的 get_camera_profiles()
--       會自動回傳內建的預設清單（跟 static/measure/app.js 的 CAMERA_PRESETS
--       一致），不影響功能先上線；這支腳本跑完後會自動改吃這張表的資料。

BEGIN TRANSACTION;

CREATE TABLE Camera_Profiles (
    profile_id   INT IDENTITY(1,1) PRIMARY KEY,
    name         NVARCHAR(100) NOT NULL,
    focal_mm     DECIMAL(6,2) NOT NULL,
    sensor_width DECIMAL(6,2) NOT NULL
);

INSERT INTO Camera_Profiles (name, focal_mm, sensor_width) VALUES
    (N'iPhone 13', 5.7, 7.5),
    (N'iPhone 13 Pro', 5.8, 7.8),
    (N'iPhone 14', 5.7, 7.5),
    (N'iPhone 14 Pro', 6.9, 10.0),
    (N'iPhone 15', 6.2, 8.2),
    (N'iPhone 15 Pro', 6.9, 10.0),
    (N'iPhone 16', 6.2, 8.2),
    (N'iPhone 16 Pro', 6.9, 10.0),
    (N'Samsung Galaxy S24 Ultra', 6.5, 9.9);

COMMIT TRANSACTION;
