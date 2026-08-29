# 淡江樹木碳匯檢測網 — 開發規範文件

> 本文件依照與團隊及 AI 開發者遵守，確保程式碼風格與格式一致。

---

## 0. 開始編寫前必須確認

AI 在開始編寫任何程式碼前，必須先詢問開發者以下三點，**全部確認後才能開始編寫**：

1. 目前開發環境是否正常（Python 版本、套件是否安裝完成）
2. 是否位於正確分支（例如：`feature/admin-auth`）
3. 是否已 pull 最新的程式碼（確保接到最新版本後開始）

---

## 1. 專案基本資訊

| 項目 | 內容 |
|---|---|
| 專案名稱 | 淡江樹木碳匯檢測網 |
| 後端框架 | Python Flask |
| 資料庫 | Azure SQL Server（pyodbc 連線） |
| 前端地圖 | Leaflet.js |
| 前端語言 | 純 HTML / CSS / JavaScript（不使用 React 等框架） |
| Python 版本 | 3.x |

### 專案資料夾結構

```
project/
├── app.py
├── config.py
├── routes/
│   ├── pages.py
│   ├── api.py
│   └── admin.py
├── services/
│   ├── db.py
│   ├── yolo.py
│   ├── data_pipeline.py
│   ├── analysis/
│   │   ├── detector.py
│   │   ├── tracker.py
│   │   ├── time_sync.py
│   │   ├── diameter_calc.py
│   │   └── visualizer.py
│   └── parsers/
│       ├── rtk_parser.py
│       └── csv_parser.py
├── static/
│   ├── css/style.css
│   └── js/
│       ├── map.js
│       └── admin.js
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── map.html
│   ├── about.html
│   └── admin/
│       ├── login.html
│       └── dashboard.html
├── uploads/
├── measured_result/
└── Tree-Trunk-Segmentation/
    └── best.pt
```

---

## 2. 給 AI 的起始提示詞

**每次開新對話時，必須在開頭貼上以下內容：**

```
我的專案是淡江樹木碳匯檢測網。
後端：Python Flask
資料庫：Azure SQL Server（pyodbc）
前端：純 HTML / CSS / JavaScript + Leaflet.js

專案資料夾結構：
  routes/（pages.py、api.py、admin.py）
  services/（db.py、yolo.py、data_pipeline.py）
  services/analysis/（detector.py、tracker.py、time_sync.py、diameter_calc.py、visualizer.py）
  services/parsers/（rtk_parser.py、csv_parser.py）
  templates/（base.html、index.html、map.html、about.html、admin/login.html、admin/dashboard.html）
  static/（css/style.css、js/map.js、js/admin.js）

資料表：Sites、Trees、Measurements、Species_Ref、Users
Measurements 的 status 只能是 pending 或 confirmed

請遵守 CONTRIBUTING.md 的開發規範撰寫程式碼。
```

---

## 3. 程式碼風格規範

### 縮排

- Python：**4 個空格**
- JavaScript：**2 個空格**
- HTML：**2 個空格**

### 字串

- Python：使用**單引號** `'`
- JavaScript：使用**單引號** `'`

### 注解規範

每個檔案開頭**必須**加以下格式：

```python
# 負責人：Morris
# 開發日期：2026/07/25
# 用途：管理員登入驗證，比對帳號密碼並建立 session
```

- 共同編輯的檔案，負責人列所有人：`# 負責人：Morris、Ray`
- 函式開頭給一句精簡的用途說明
- 程式碼片段只在**必要時**加註解，不需要每行都加
- 注解語言統一使用**中文**，盡可能精簡明瞭

### 範例

```python
# 負責人：Morris
# 開發日期：2026/07/25
# 用途：管理員帳號查詢，供登入驗證使用

def get_user_by_username(username):
    # 去 Users 資料表查帳號
    cursor.execute('SELECT * FROM Users WHERE username = ?', username)
    return cursor.fetchone()
```

---

## 4. API 規範

### 完整 API 清單

| 方法 | 網址 | 說明 | 輸入 | 輸出 |
|---|---|---|---|---|
| GET | /api/trees | 所有樹木資料 | 無 | JSON 陣列 |
| GET | /api/trees/\<id\> | 單棵樹詳細資料 | id（網址） | JSON 實體 |
| GET | /api/trees?species= | 依樹種篩選 | species（字串） | JSON 陣列 |
| GET | /api/trees?site= | 依路段篩選 | site（字串） | JSON 陣列 |
| GET | /api/stats | 首頁統計數字 | 無 | JSON（total_trees, total_carbon） |
| GET | /api/sites | 所有路段列表 | 無 | JSON 陣列 |
| POST | /api/upload | 上傳照片辨識 | 照片檔案 | JSON 結果 |
| POST | /api/admin/login | 登入驗證 | username, password | 成功或 401 |
| POST | /api/admin/logout | 登出 | 無 | 成功 |
| GET | /api/admin/trees | 得到所有資料 | 無 | JSON 陣列（含 status） |
| PUT | /api/admin/trees/\<id\> | 修改審核狀態 | id（網址）, status | 成功或 400 |
| DELETE | /api/admin/trees/\<id\> | 刪除審核 | id（網址） | 成功或 404 |

### JSON 本體命名規範

前後端統一使用以下本體名稱，**不可自行更改**：

```json
{
  "id": 1,
  "species": "樟樹",
  "dbh": 35.2,
  "carbon": 12.5,
  "lat": 25.1734,
  "lng": 121.4546,
  "site": "英專路",
  "status": "pending",
  "recorded_at": "2026/07/10 14:23",
  "img": "measured_result/track_1_result.jpg"
}
```

### 回應格式規範

**成功：**
```json
{"success": true}
```

**失敗：**
```json
{"error": "錯誤說明"}
```
搭配對應的 HTTP 狀態碼：
- `400` 請求格式錯誤
- `401` 未授權（未登入）
- `404` 找不到資料
- `500` 伺服器錯誤

---

## 5. 前端規範

- 打 API 統一使用 `fetch`，**不使用** axios 或 jQuery
- 錯誤處理統一格式：

```javascript
fetch('/api/trees')
  .then(res => {
    if (!res.ok) throw new Error('請求失敗')
    return res.json()
  })
  .then(data => {
    // 處理資料
  })
  .catch(err => {
    console.error(err)
    alert('發生錯誤，請稍後再試')
  })
```

- HTML `class` 命名使用 **kebab-case**，例如：`tree-list`、`admin-table`
- HTML `id` 命名使用 **camelCase**，例如：`treeMap`、`loginForm`

---

## 6. 資料庫規範

### 資料處理管線順序（時間先後）

1. 使用者上傳 RTK / Arduino(ToF) / 影片三個檔案（`/api/upload`）
2. **時間對齊**：`services/merge_data.py` 的 `align_sensor_data()`，把 Arduino(ToF) 跟 RTK 依時間戳記對齊，算出每筆資料對應影片第幾毫秒（`video_offset_ms`）
3. **影片切幀**：依 ToF 取樣間隔（500ms）把影片切成一張張照片，用 `video_offset_ms` 對回步驟 2 對齊好的資料，取得該幀對應的 ToF 距離、RTK 座標
4. **多物件追蹤**：`services/analysis/tracker.py` 對每一幀跑 YOLO-seg + ByteTrack，輸出每幀的 `track_id`（同一棵樹全程不變）與 `pixel_width`（像素寬度，尚非公分）
5. **樹徑換算**：同一個 `track_id` 的多幀資料，依「樹徑計算邏輯」（見下方）算出這棵樹最終的樹徑（cm）
6. **座標換算**：依「樹木座標計算邏輯」（見下方）算出這棵樹的真實座標
7. **寫入資料庫**：呼叫 `save_pipeline_record()`，內部呼叫 `_get_or_create_tree_id()` 比對/建立 `Tree_ID`，寫入一筆 `Measurements`，`status` 固定為 `Pending`
8. **後台審核**：管理員在「數據管理維護」頁面確認，`status` 改為 `Approved` 後才會出現在地圖／資料表頁面

⚠️ 步驟 3～6（切幀腳本、樹徑/座標換算邏輯）目前**尚未實作**，`services/data_pipeline.py` 的 `process_upload()` 仍是空殼，是整合以上步驟的入口函式。

- 所有查詢邏輯統一寫在 `services/db.py`，**不可在 routes/ 裡直接查資料庫**
- ⚠️ **`Measurements.status` 資料庫實際存的值是 `'Pending'` / `'Approved'`**（注意大小寫，跟本文件其他地方寫的 `pending`/`confirmed` 不同字）。後端 API 回傳給前端時統一轉換成小寫 `pending`／`confirmed` 對外，但**寫入資料庫時要用資料庫實際接受的 `'Pending'`/`'Approved'`**，比對時建議用 `LOWER(status) = 'pending'` 這種不分大小寫的寫法，避免大小寫不一致造成查詢漏資料
- 欄位命名對照（依實際資料庫為準）：

| 資料表 | 欄位 | 說明 |
|---|---|---|
| Trees | tracker_id | `NOT NULL`。ByteTrack 追蹤編號，是目前判斷「同一棵樹」的主要依據（見下方「樹木身分比對邏輯」） |
| Trees | LATITUDE N/S / LONGITUDE E/W | 樹木座標欄位，字串格式（如 `"25.0883747N"`），需用 `_parse_coord()` 轉成數字，S/W 為負值 |
| Measurements | status | `Pending` / `Approved`（注意大小寫） |
| Measurements | dbh | 樹徑（公分） |
| Measurements | carbon_absorpation | 固碳量 |
| Measurements | image_data | 樹木照片二進位（VARBINARY），用 `_img_bin_to_data_uri()` 轉成前端可用的 data URI，不寫檔到 static/img/ |
| Species_Ref | allo_param_a / allo_param_b | 異速生長方程式參數（`biomass = a × dbh^b`）。規劃併入 `Species_Ref`，不要另開新表 |

### 樹木身分比對邏輯（Tree_ID）

- **同一次匯入（同一段影片）內**：用 `tracker_id` 判斷是不是同一棵樹。同一個 `tracker_id` 第二次出現 = 同一棵樹的另一次測量，共用同一個 `Tree_ID`（見 `services/db.py` 的 `_get_or_create_tree_id()`）
- ⚠️ **跨次匯入必須做 offset**：`tracker_id` 只在單一次追蹤（單一影片）裡唯一，每次重新追蹤都從頭編號。匯入前必須先查詢資料庫目前最大的 `tracker_id`，把這次所有的 track_id 加上這個 offset，才能保證跨批匯入不會撞號、被誤判成同一棵樹
- **跨次辨識同一棵實體樹**（例如下個月複測同一條路，是否認得出是同一棵樹）：**尚未實作**。規劃是改用樹木座標比對（找資料庫裡座標相近的既有 `Tree_ID`），而不是比對 `tracker_id`（`tracker_id` 無法跨次沿用）。需等下方「樹木座標計算邏輯」完成後才能接上

### 樹徑計算邏輯

1. `services/analysis/tracker.py` 對每一幀輸出 `pixel_width`（分割遮罩量出的像素寬度，**還不是公分**）
2. 同一個 `tracker_id` 通常會有多幀資料（例如 10 幀），對各幀配對到的 **ToF 距離** 做 IQR 去除離群值，取代表性距離（如中位數）
3. 在原始資料裡找出**實際距離最接近代表值的那一筆真實紀錄**（不是用合成值），取該筆自己的 `pixel_width` 與距離
4. `真正樹徑(cm) = pixel_width × k值`，k值（cm/pixel）隨距離變化，且需要用已知直徑物體在已知距離實際拍照校正相機硬體才能得到，**目前尚未校正**

### 樹木座標計算邏輯

- ⚠️ **目前資料庫存的座標是拍攝當下的原始 RTK 座標（車輛位置），不是樹木實際位置**，校正邏輯尚未實作
- 規劃邏輯：感測器與車輛前進方向垂直（90 度）安裝，樹木真實座標 = 拍攝點座標，往感測器朝向那一側，依「方位角(HEADING) ± 90 度」的方向，偏移「ToF 距離」那麼遠（標準地理座標平移公式）
- `Measurements` 已有 `HEADING`、`ToF_Dist1_cm`／`ToF_Dist2_cm` 欄位，**不需要新增資料庫欄位**，只需要在寫入 `Trees` 前補上這段計算邏輯，並讓 `_get_or_create_tree_id()` 多接收一個 `heading` 參數
- 感測器朝哪一側（左/右）是固定的硬體安裝方式，建議存在 `config.py` 當常數，不需要資料庫欄位

---

## 7. AI 發現問題或衝突時的處理規範

遇到以下狀況，**AI 必須先向開發者確認，不可自行假設或臆測**：

- 發現既有程式碼有衝突
- 不確定欄位命名或格式
- 需要引擎其他尚未實作的函式
- 發現規範文件跟現有程式碼有出入

**AI 必須向開發者提供具體建議：**

1. 說明問題是什麼
2. 提供至少一個解決方向
3. 說明選擇不同方向的影響
4. 若需要跟其他組員確認，明確指出要確認什麼

**給開發者的建議解決方式：**

- 本體名稱衝突 → 參照第 6 點的本體名稱規範，以規範為準
- 函式尚未實作 → 先寫 `raise NotImplementedError('待實作')` 佔位，完成後再補
- 架構衝突 → 回報給專案負責人討論，不自行修改架構
- 規範文件不吻合現況的欄位 → 查詢本文件，查不到詢問負責人

---

## 8. AI 完成後必須輸出的說明文件

每次完成一個任務後，AI **必須產出一份 .md 說明文件**給開發者確認，內容包含：

```markdown
# 功能名稱

## 負責人
Morris

## 開發日期
2026/07/25

## 完成的檔案
- routes/admin.py
- services/db.py
- templates/admin/login.html
- static/js/admin.js

## 函式 / API 說明
| 函式 / API | 用途 | 輸入 | 輸出 |
|---|---|---|---|
| api_login() | 登入驗證 | username, password | 成功或 401 |
| get_user_by_username() | 查帳戶 | username | user 資料或 None |

## 需要手動填入的內容
- .env 的 DB_SERVER、DB_NAME、DB_USER、DB_PASSWORD
- scripts/create_admin.py 的帳號密碼

## 依賴其他人尚未完成的功能
- 無（此功能獨立）

## 測試方式
1. 執行 scripts/create_admin.py 建立帳號
2. 開瀏覽器輸入 /admin/login
3. 輸入正確帳密，確認跳到 /admin/dashboard
4. 輸入錯誤帳密，確認顯示「帳戶或密碼錯誤」
```

---

## 9. Commit 訊息規範

統一選中文或英文，整個專案保持一致。

**中文範例：**
```bash
git commit -m "實作管理員登入 API"
git commit -m "新增登入表單頁面"
git commit -m "修正密碼比對邏輯錯誤"
```

**英文範例：**
```bash
git commit -m "implement admin login API"
git commit -m "add login form template"
git commit -m "fix password verification logic"
```
