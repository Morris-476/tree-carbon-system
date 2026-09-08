-- 用途：依樹種係數表照片，填入 Species_Ref.allo_param_a / allo_param_b
-- 開發日期：2026/09/08
--
-- 背景：
--   - allo_param_a/b 欄位（異速生長方程式參數：biomass = a × dbh^b）是 8/29
--     從 Biomass_Parameters 併入 Species_Ref 時新增的，當時來源資料全部是 NULL，
--     這次補上實際查到的係數。
--   - 美人樹（species_id 11）目前找不到對應係數資料，維持 NULL，不動。
--   - carbon_fraction（碳係數）維持 services/db.py 現有的全域常數 0.47，
--     不採用照片裡各樹種不同的 carbon_fraction 數值，也不在 Species_Ref 新增此欄位。

UPDATE Species_Ref SET allo_param_a = 0.1345, allo_param_b = 2.348 WHERE species_id = 1;  -- 榕樹
UPDATE Species_Ref SET allo_param_a = 0.0821, allo_param_b = 2.451 WHERE species_id = 2;  -- 龍柏
UPDATE Species_Ref SET allo_param_a = 0.0984, allo_param_b = 2.426 WHERE species_id = 3;  -- 樟樹
UPDATE Species_Ref SET allo_param_a = 0.1250, allo_param_b = 2.300 WHERE species_id = 4;  -- 垂榕
UPDATE Species_Ref SET allo_param_a = 0.0763, allo_param_b = 2.512 WHERE species_id = 5;  -- 小葉南洋杉
UPDATE Species_Ref SET allo_param_a = 0.0621, allo_param_b = 2.485 WHERE species_id = 6;  -- 木棉
UPDATE Species_Ref SET allo_param_a = 0.1052, allo_param_b = 2.384 WHERE species_id = 7;  -- 山櫻花
UPDATE Species_Ref SET allo_param_a = 0.1124, allo_param_b = 2.415 WHERE species_id = 8;  -- 茄苳
UPDATE Species_Ref SET allo_param_a = 0.0584, allo_param_b = 2.562 WHERE species_id = 9;  -- 鳳凰木
UPDATE Species_Ref SET allo_param_a = 0.0452, allo_param_b = 2.624 WHERE species_id = 10; -- 黑板樹
-- species_id 11（美人樹）：無資料，維持 NULL，不下 UPDATE
