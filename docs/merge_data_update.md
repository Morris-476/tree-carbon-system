# 功能名稱
實作 Arduino 與 RTK 數據對齊合併函式（支援動態上傳與錯誤處理）

## 負責人
蔡宗倫

## 開發日期
2026/08/16

## 完成的檔案
- scripts/merge_data.py

## 函式 / API 說明
| 函式 / API | 用途 | 輸入 | 輸出 |
|---|---|---|---|
| merge_sensor_data() | 對齊並合併 Arduino 與 RTK 數據檔案 | arduino_path (字串), rtk_path (字串), output_dir (字串) | 包含執行狀態 (status)、訊息 (message) 與輸出路徑 (file_path) 的 JSON 格式字典 |

## 需要手動填入的內容
- 無

## 依賴其他人尚未完成的功能
- 等待網頁後端實作「檔案上傳 API」，以便在上傳完成後，動態將檔案路徑傳遞給 `merge_sensor_data()` 執行合併。
- 等待影像處理模組萃取 MP4 影片起始時間，以進行最終的時間軸對接。

## 測試方式
1. 確保專案根目錄下存在 `data/raw/` 資料夾，並放入 `TREE_019.CSV` 與 `30174930.CSV` 測試檔案。
2. 開啟終端機，執行 `python scripts/merge_data.py`。
3. 若終端機印出「成功」，請至 `data/processed/` 確認是否產生合併好的 CSV 檔案。
4. 故意將 `test_arduino` 路徑寫錯並執行，確認是否能正確捕捉並印出 `FileNotFoundError` 的錯誤訊息。