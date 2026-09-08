-- 用途：Species_Ref 依樹種係數表照片填入各樹種的 carbon_fraction（含碳率）
-- 開發日期：2026/09/08
--
-- 背景：
--   - carbon_fraction 欄位（DECIMAL NOT NULL DEFAULT 0.47）已存在於共用的 Azure SQL
--     資料庫中（非本次新增，執行時發現已有此欄位）。若在還沒有這個欄位的環境執行，
--     請先補上：
--       ALTER TABLE Species_Ref ADD carbon_fraction DECIMAL(4,3) NOT NULL DEFAULT 0.47;
--   - 美人樹（species_id 11）維持預設值 0.47，不下 UPDATE。
--   - services/db.py 已同步修改：save_pipeline_record() 改用
--     _get_carbon_fraction(cursor, species_id) 依樹種查詢，不再使用單一全域常數；
--     查無資料或未辨識出樹種時，退回 DEFAULT_CARBON_FRACTION = 0.47。

UPDATE Species_Ref SET carbon_fraction = 0.47 WHERE species_id = 1;   -- 榕樹
UPDATE Species_Ref SET carbon_fraction = 0.51 WHERE species_id = 2;   -- 龍柏
UPDATE Species_Ref SET carbon_fraction = 0.48 WHERE species_id = 3;   -- 樟樹
UPDATE Species_Ref SET carbon_fraction = 0.47 WHERE species_id = 4;   -- 垂榕
UPDATE Species_Ref SET carbon_fraction = 0.51 WHERE species_id = 5;   -- 小葉南洋杉
UPDATE Species_Ref SET carbon_fraction = 0.45 WHERE species_id = 6;   -- 木棉
UPDATE Species_Ref SET carbon_fraction = 0.47 WHERE species_id = 7;   -- 山櫻花
UPDATE Species_Ref SET carbon_fraction = 0.48 WHERE species_id = 8;   -- 茄苳
UPDATE Species_Ref SET carbon_fraction = 0.47 WHERE species_id = 9;   -- 鳳凰木
UPDATE Species_Ref SET carbon_fraction = 0.45 WHERE species_id = 10;  -- 黑板樹
-- species_id 11（美人樹）：維持 DEFAULT 0.47，不下 UPDATE
