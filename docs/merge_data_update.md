# 功能名稱
Arduino(ToF) / RTK / 影片 三者時間對齊，直接寫入資料庫

## 負責人
蔡宗倫（原作者）；2026/08/22 由 AI 依討論結果修改

## 開發日期
2026/08/22

## 完成的檔案
- services/merge_data.py（改寫：不再輸出 CSV，改為對齊後直接寫入資料庫）
- services/db.py（新增 save_sensor_sync_records()）
- services/data_pipeline.py（新增 run_sensor_time_sync()；修掉會讓整個模組 ImportError 的頂層 import）
- sql/create_tables.sql（新增 Sensor_Sync_Records 建表語法；原本是空檔案）

## 決策紀錄（與撰寫者討論後拍板）
1. **合併後資料寫入位置**：新增 `Sensor_Sync_Records` 暫存表，不直接寫入 `Trees`/`Measurements`。
   因為這次合併只有感測器原始資料（時間、GPS、ToF 距離），沒有 `species_id`、真正的
   `dbh`（樹徑要由影像追蹤+ 樹徑換算才能得到，`tracker.py`／`diameter_calc.py` 目前都還是
   `NotImplementedError` 佔位），若硬塞進正式表會污染欄位語意。
2. **影片起始時間基準**：以 Arduino(ToF) CSV 最早一筆時間戳記，作為影片第 0 影格的真實時間，
   不使用 RTK 最早時間戳記，也不解析影片檔本身的 metadata。
   原因：Arduino 開機記錄與錄影幾乎同時開始（撰寫者確認）；RTK 需要數秒到十幾秒才能拿到
   第一筆有效 GPS 座標（樣本中 RTK 檔名顯示 18:24:01 開機，但第一筆有效定位是 18:24:12，
   晚了 11 秒），用 RTK 當基準會系統性偏移。影片檔本身也無法從二進位內容可靠取得建立時間
   （上傳的是同一支影片的縮小版，mvhd/metadata 內未寫入建立時間字串，MediaInfo 顯示的
   「18:23:03」應是從影片內建 Timed Metadata 軌讀出，格式複雜，本次不解析）。
3. **merge 呼叫方式**：`services/merge_data.py` 保留合併/對齊/寫入資料庫的完整邏輯；
   `services/data_pipeline.py` 新增 `run_sensor_time_sync()` 呼叫它，對應架構文件裡
   ①csv_parser ②rtk_parser ③time_sync 三個步驟，讓時間對齊功能不用等 ④~⑦
   （影像追蹤、樹徑計算）完成就能先運作。

## 函式 / API 說明
| 函式 | 用途 | 輸入 | 輸出 |
|---|---|---|---|
| merge_data.merge_and_store_sensor_data() | 對齊 Arduino(ToF) 與 RTK 時間戳記並寫入資料庫 | arduino_path, rtk_path, video_filename, video_start_at, max_gap_seconds | dict（status, inserted, merge_batch_id, matched_gps_count...） |
| db.save_sensor_sync_records() | 批次寫入 Sensor_Sync_Records | records（list of dict） | dict（status, inserted） |
| data_pipeline.run_sensor_time_sync() | 管線入口，包裝 merge_and_store_sensor_data() | rtk_file_path, csv_file_path, video_path, video_start_at, max_rtk_gap_seconds | 同 merge_and_store_sensor_data() |

## 合併/對齊邏輯摘要
- Arduino(ToF) CSV 前兩行是空白雜訊列，自動偵測 `Tree_ID` 開頭的表頭列再讀取。
- 以 Arduino 紀錄（每秒一筆）為主軸，用 `pandas.merge_asof`（最近時間、預設容忍 3 秒）
  抓最接近的 RTK 紀錄；超過容忍範圍的那幾秒（例如 RTK 尚未取得定位前）`latitude`/`longitude`
  會是 `NULL`，不會硬湊錯的座標。
- 兩份檔案都有的 `DATE`/`TIME` 欄位，合併後只保留一份 `recorded_at`（重複欄位收斂為 1 個）。
- RTK 的 `INDEX` 欄位依需求整個刪除，不寫入資料庫。
- 每筆紀錄額外算出 `video_offset_ms`（相對影片起始時間的毫秒數）與 `rtk_gap_ms`
  （配對到的 RTK 紀錄時間差，供之後偵錯用）。
- 用實際上傳的 TREE_015.CSV（47 筆）與 01182401.CSV（33 筆）驗證過：47 筆全部寫入，
  其中 39 筆在容忍誤差內配對到 GPS 座標，前 8 筆（RTK 尚未定位前）座標為 NULL，符合預期。

## 需要手動填入的內容
- 需在 Azure SQL 上實際執行 `sql/create_tables.sql` 建立 `Sensor_Sync_Records` 表
  （目前該檔案只有這張新表，CONTRIBUTING.md 列出的 Sites/Trees/Measurements/Species_Ref/Users
  五張正式表尚未收錄在此檔案中，需要負責該功能的組員補上，或告知它們已經建在別處）。
- `.env` 的 DB_SERVER / DB_NAME / DB_USER / DB_PASSWORD。

## 依賴其他人尚未完成的功能
- 之後要把 `Sensor_Sync_Records` 的資料轉成正式的 `Trees`/`Measurements`，需要
  `services/tracker.py`（影像追蹤/track_id）與尚未建立的 `diameter_calc.py`
  （樹徑換算）先完成；`services/data_pipeline.py` 的 `process_upload()` 仍是
  `NotImplementedError` 佔位，待這兩塊完成後再串接。
- `services/data_pipeline.py` 原本頂層 import 了不存在的 `services.rtk_parser`、
  `services.csv_parser`、`services.tracker`、`services.diameter_calc`，會讓整個模組
  一 import 就 ImportError。這次先移除這些 import 讓 `run_sensor_time_sync()` 可以正常運作，
  ④~⑦ 步驟實際開發時，請在 `process_upload()` 內補回對應 import。

## 測試方式
1. 在專案根目錄放入 Arduino(ToF) CSV（如 `data/raw/TREE_015.CSV`）與 RTK CSV
   （如 `data/raw/01182401.CSV`）。
2. 設定好 `.env` 的資料庫連線後，於 Python 執行：
   ```python
   from services.data_pipeline import run_sensor_time_sync
   result = run_sensor_time_sync(
       rtk_file_path='data/raw/01182401.CSV',
       csv_file_path='data/raw/TREE_015.CSV',
       video_path='IMG_4631.MOV',
   )
   print(result)
   ```
3. 確認回傳 `status == 'success'`，並到資料庫的 `Sensor_Sync_Records` 表確認筆數與內容。
4. 故意將其中一個路徑寫錯，確認會回傳 `status == 'error'` 且 `message` 說明找不到檔案。
