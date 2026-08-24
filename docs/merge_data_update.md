# 功能名稱
Arduino(ToF) / RTK / 影片 時間對齊（純運算邏輯，透過資料上傳頁觸發）

## 負責人
蔡宗倫（原作者）；2026/08/24 依討論結果修改

## 開發日期
2026/08/24

## 完成的檔案
- services/merge_data.py（改寫：`align_sensor_data()` 純運算邏輯，不寫資料庫、不輸出檔案）
- services/data_pipeline.py（`run_sensor_time_sync()` 改呼叫 `align_sensor_data()`）
- routes/api.py（新增 `POST /api/upload`，接收 RTK/Arduino/影片檔案並回傳對齊結果）
- static/js/admin.js（上傳成功訊息改顯示對齊結果，不再顯示「已送交管理員審核」）
- config.py（新增 `UPLOAD_FOLDER` 設定）

## 決策紀錄
1. **不寫資料庫、不輸出檔案**：這次先聚焦「時間對齊」的運算邏輯本身，`merge_data.py` 的
   `align_sensor_data()` 只回傳合併後的資料（list of dict），呼叫端（`/api/upload`）決定
   要不要進一步儲存。之前討論過的 `Sensor_Sync_Records` 暫存表、`Measurements` 欄位對應
   等資料庫相關設計先擱置，不影響這次邏輯。
2. **影片起始時間基準**：沿用先前確認的作法——以 Arduino(ToF) CSV 最早一筆時間戳記，作為
   影片第 0 影格的真實時間（不用 RTK 最早時間戳記，原因是 GPS 定位延遲；不解析影片檔本身
   的 metadata）。
3. **觸發流程**：對應到網頁的「系統管理 → 數據管理維護 → 資料上傳」頁面
   （`templates/admin/upload.html`），管理員上傳 RTK／Arduino／影片三個檔案，
   前端 `fetch('/api/upload', ...)` 送出後，後端執行對齊運算並回傳結果 JSON。
4. **`/api/upload` 需要登入**：沿用 `routes/admin.py` 的 `login_required` 裝飾器，
   未登入呼叫會回傳 401（跟其他 `/api/admin/*` 路由一致的保護方式）。

## 函式 / API 說明
| 函式 / API | 用途 | 輸入 | 輸出 |
|---|---|---|---|
| merge_data.align_sensor_data() | 對齊 Arduino(ToF) 與 RTK 時間戳記，回傳合併結果 | arduino_path, rtk_path, video_filename, video_start_at, max_gap_seconds | dict（status, records, total_count, matched_gps_count, video_start_at, video_filename） |
| data_pipeline.run_sensor_time_sync() | 管線入口，包裝 align_sensor_data() | rtk_file_path, csv_file_path, video_path, video_start_at, max_rtk_gap_seconds | 同 align_sensor_data() |
| POST /api/upload | 接收上傳檔案並執行時間對齊 | multipart/form-data：rtk_file, arduino_file, mp4_file（選填） | `{success, total_count, matched_gps_count, video_start_at, video_filename, records}` 或 `{error}` |

## 合併/對齊邏輯摘要
- Arduino(ToF) CSV 前兩行是空白雜訊列，自動偵測 `Tree_ID` 開頭的表頭列再讀取。
- 以 Arduino 紀錄（每秒一筆）為主軸，用 `pandas.merge_asof`（最近時間、預設容忍 3 秒）
  抓最接近的 RTK 紀錄；超過容忍範圍的那幾秒（例如 RTK 尚未取得定位前）`latitude`/`longitude`
  會是 `null`，不會硬湊錯的座標。
- 兩份檔案都有的 `DATE`/`TIME` 欄位，合併後只保留一份 `recorded_at`（重複欄位收斂為 1 個）。
- RTK 的 `INDEX` 欄位依需求整個捨棄，不出現在回傳結果中。
- 每筆紀錄額外算出 `video_offset_ms`（相對影片起始時間的毫秒數）與 `rtk_gap_ms`
  （配對到的 RTK 紀錄時間差，供之後偵錯用）。
- 上傳的檔案會暫存到 `uploads/<隨機資料夾>/`（已在 `.gitignore` 排除，不進版控）。
- 用實際的 TREE_015.CSV（47 筆）與 01182401.CSV（33 筆）驗證過完整 `/api/upload` 流程：
  回傳 47 筆，其中 39 筆配對到 GPS 座標，前 8 筆（RTK 尚未定位前）座標為 `null`，符合預期；
  未登入呼叫回傳 401；缺檔案回傳 400。

## 需要手動填入的內容
- 無（這次不涉及資料庫，不需要額外環境變數）

## 依賴其他人尚未完成的功能
- 之後若要把對齊結果落地存起來（不論是 `Trees`/`Measurements` 還是其他表），需要另外討論
  資料庫欄位對應；目前 `/api/upload` 只回傳結果，不做任何寫入。
- `services/tracker.py`、`services/data_pipeline.py` 的 `process_upload()` 仍是
  `NotImplementedError` 佔位，待影像追蹤與樹徑計算完成後再串接。

## 測試方式
1. 啟動網頁：`python app.py`，瀏覽器開 `http://127.0.0.1:5000/`。
2. 登入管理員帳號，點「系統管理」→「數據管理維護」→「資料上傳」。
3. 上傳 RTK 檔（如 `01182401.CSV`）、Arduino 檔（如 `TREE_015.CSV`），影片檔可選填。
4. 按「上傳辨識」，應顯示「時間對齊完成，共 N 筆，其中 M 筆配對到 GPS 座標」的提示。
5. 故意不選 RTK 或 Arduino 檔案送出，應顯示對應的錯誤訊息（「請上傳 RTK 檔案」等）。
6. 未登入時直接呼叫 `POST /api/upload`，應回傳 401。
