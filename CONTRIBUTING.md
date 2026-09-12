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
| 影像辨識 | YOLOv8-seg（樹幹分割）＋ ByteTrack（多物件追蹤）＋ CLIP（樹種比對） |
| Python 版本 | 3.x |

### 專案資料夾結構

```
project/
├── app.py                       # 建立 Flask app、登記 Blueprint，不含任何路由/查詢邏輯
├── config.py                    # 所有環境變數與模型參數集中讀取處
├── routes/
│   ├── pages.py                 # 一般頁面：首頁、/map、/measure
│   ├── api.py                   # 一般 API：/api/upload、/api/trees、/api/stats
│   └── admin.py                 # 後台頁面 + 登入／登出／審核 API
├── services/
│   ├── db.py                    # 所有 SQL 查詢／寫入邏輯，routes/ 一律不可直接查資料庫
│   ├── data_pipeline.py         # 上傳流程整合入口（run_upload_and_save）
│   ├── merge_data.py            # RTK／Arduino(ToF) 時間對齊（align_sensor_data）
│   ├── carbon.py                # 固碳量純計算，不可查資料庫，供上傳流程與 /measure 共用
│   ├── geo.py                   # 地理座標推算（大圓公式）
│   ├── species_classifier.py    # YOLO 去背 + CLIP 樹種向量比對
│   ├── yolo.py                  # ⚠️ 目前沒有任何檔案 import，非管線實際使用的模組
│   ├── analysis/
│   │   ├── tracker.py               # ByteTrack 樹幹追蹤（TreeTracker）
│   │   ├── tree_analysis.py         # IQR 去極端值，寫回 Measurements.Final_Dist_cm
│   │   ├── tree_coordinate.py       # 依 Final_Dist_cm＋方位角推算樹木座標，寫入 Trees
│   │   ├── tree_species.py          # 批次樹種辨識（classify_pending_trees）
│   │   ├── visualizer.py
│   │   └── bytetrack_custom.yaml
│   └── measure/                 # /measure 簡易固碳測量頁面用；尚未接上路由（見第 6 節）
│       ├── models.py
│       ├── geometry.py
│       ├── trunk_detector.py
│       ├── validator.py
│       ├── pipeline.py
│       └── visualizer.py
├── static/
│   ├── css/style.css
│   ├── js/
│   │   ├── map.js
│   │   ├── admin.js
│   │   ├── dashboard.js
│   │   └── nav.js
│   └── measure/
│       ├── app.js
│       └── styles.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── map.html
│   ├── about.html
│   ├── measure.html
│   └── admin/
│       ├── login.html
│       ├── dashboard.html
│       ├── upload.html
│       └── manage.html
├── scripts/
│   └── create_admin.py
├── sql/                          # 資料庫結構變更紀錄，檔名格式 YYYY-MM-DD_說明.sql
├── docs/
│   └── merge_data_update.md
├── uploads/
├── measured_result/
├── Tree-Trunk-Segmentation/
│   └── best.pt
└── Tree-Species-Vectors/
    └── tree_vectors.pkl
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
  services/（db.py、data_pipeline.py、merge_data.py、carbon.py、geo.py、species_classifier.py）
  services/analysis/（tracker.py、tree_analysis.py、tree_coordinate.py、tree_species.py、visualizer.py）
  services/measure/（/measure 頁面用，尚未接上路由）
  templates/（base.html、index.html、map.html、about.html、measure.html、admin/login.html、admin/dashboard.html、admin/upload.html、admin/manage.html）
  static/（css/style.css、js/map.js、js/admin.js、js/dashboard.js、js/nav.js、measure/app.js、measure/styles.css）

資料表：Trees、Measurements、Species_Ref、Admins、Camera_Profiles、Sensor_Sync_Records
Measurements 的 status 資料庫實際存的值是 Pending／Approved（注意大小寫，詳見第 6 節）

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

| 方法 | 網址 | 說明 | 輸入 | 輸出 | 需登入 |
|---|---|---|---|---|---|
| POST | /api/upload | 上傳 RTK／Arduino(ToF)／影片，執行時間對齊並寫入資料庫 | multipart：rtk_file、arduino_file（必填）、mp4_file（選填） | JSON 結果（見下） | ✅ |
| GET | /api/trees | 地圖頁用，回傳所有 `Approved` 樹木資料 | 無 | `{success, trees: [...]}` | |
| GET | /api/stats | 首頁統計數字 | 無 | `{success, total_trees, total_carbon}` | |
| POST | /api/admin/login | 登入驗證 | `{username, password}` | 成功 200 或 401 | |
| POST | /api/admin/logout | 登出 | 無 | 成功 200 | |
| GET | /api/admin/trees | 後台待審核清單（含 `Pending`） | 無 | JSON 陣列（見下） | ✅ |
| PUT | /api/admin/trees/\<id\> | 更新審核狀態，可一併修正 dbh／carbon | `{status（必填）, dbh?, carbon?}` | 成功或 400 | ✅ |
| DELETE | /api/admin/trees/\<id\> | 刪除該筆 Measurements 記錄 | id（網址） | 成功或 400 | ✅ |
| GET | /api/camera-profiles | 拍攝設備清單（上傳頁下拉選單用） | 無 | JSON 陣列 | ✅ |

⚠️ 原規劃的 `/api/trees/<id>`、`/api/trees?species=`、`/api/trees?site=`、`/api/sites` 目前都**尚未實作**。`templates/measure.html` 對應的 `/api/species`、`/api/measure`（見 `static/measure/app.js`）也還沒有對應的路由，`services/measure/` 底下的計算模組目前沒有被任何路由呼叫。要新增以上任一個 API 前，請先跟負責人確認命名與回傳格式。

### JSON 本體命名規範

⚠️ 目前 `/api/trees`（地圖）與 `/api/admin/trees`（後台）兩個端點各自回傳不同的欄位命名，**尚未統一**，新增功能前請先看清楚是要接哪一個端點：

**`/api/admin/trees`**（`services/db.py` 的 `get_all_trees_admin()`）：

```json
{
  "id": 1,
  "tree_id": 3,
  "species": "樟樹",
  "dbh": 35.2,
  "carbon": 12.5,
  "lat": 25.1734,
  "lng": 121.4546,
  "site": "英專路",
  "status": "pending",
  "recorded_at": "2026-07-10 14:23:00",
  "img": "data:image/jpeg;base64,..."
}
```

**`/api/trees`**（`services/db.py` 的 `get_tree_map_data()`，只含 `Approved` 資料、不含 `status`）：

```json
{
  "record_id": 1,
  "tree_id": 3,
  "species_name": "樟樹",
  "dbh": 35.2,
  "carbon_absorpation": 12.5,
  "latitude": 25.1734,
  "longitude": 121.4546,
  "site_name": "英專路",
  "img": "data:image/jpeg;base64,..."
}
```

- `img` 一律是資料庫 `image_data`（VARBINARY）轉出來的 data URI（`_img_bin_to_data_uri()`），不是檔案路徑
- 若要新增欄位或調整命名，先確認是否會影響 `static/js/map.js`、`static/js/admin.js` 既有的讀取方式

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

實際入口是 `services/data_pipeline.py` 的 `run_upload_and_save()`（`/api/upload` 呼叫它，不是文件命名相近的 `process_upload()`）：

1. 使用者上傳 RTK / Arduino(ToF) / 影片三個檔案（`/api/upload`）
2. **時間對齊**：`services/merge_data.py` 的 `align_sensor_data()`，把 Arduino(ToF) 跟 RTK 依時間戳記對齊，算出每筆資料對應影片第幾毫秒（`video_offset_ms`）
3. **多物件追蹤 + 影格截圖**：對整支影片跑一次 `TreeTracker`（`services/analysis/tracker.py`，YOLO-seg + ByteTrack），取得每幀的 `track_id`、`pixel_width`；再用 `video_offset_ms` 換算回幀號，把對到的 `track_id`／`pixel_width` 與該時間點的影格截圖（JPEG）配回步驟 2 對齊好的每一筆資料
4. **寫入原始量測**：`save_time_synced_measurements()` 把每筆（含 track_id、pixel_width、影格截圖、RTK 座標、HEADING 等）寫入 `Measurements`，`status` 固定為 `Pending`
5. **去極端值**：`services/analysis/tree_analysis.py` 的 `analyze_and_write_final_distances()`，依 `site_name + track_id` 分群（沒有 track_id 的舊式資料才退回用時間間隔分群），對群內 ToF 距離做 IQR 去極端值，代表列的距離寫回 `Measurements.Final_Dist_cm`
6. **座標換算**：`services/analysis/tree_coordinate.py` 的 `recalculate_tree_coordinates()`，用推車 RTK 座標＋`HEADING`＋`Final_Dist_cm`（`services/geo.py` 的大圓公式）算出樹木真實座標，寫入／更新 `Trees`，並把該筆 `Measurements.Tree_ID` 導向正確的 `Tree_ID`
7. **樹種辨識**：`services/analysis/tree_species.py` 的 `classify_pending_trees()`，對剛才算出真實 `Tree_ID` 的樹跑 YOLO 去背 + CLIP 樹種向量比對（`services/species_classifier.py`），信心度不足時 `Trees.species_id` 留空
8. **後台審核**：管理員在「數據管理維護」頁面（`/admin/manage`）確認，`status` 改為 `Approved` 後才會出現在地圖／首頁統計

⚠️ **樹徑（DBH）換算尚未接上管線**：`pixel_width → 公分` 需要的 k 值（cm/pixel）要用已知直徑物體在已知距離實際拍照校正相機硬體，**目前尚未校正**，所以 `Measurements.dbh`／`carbon_absorpation` 不會被管線自動算出，須由管理員在後台審核時透過 `PUT /api/admin/trees/<id>` 手動填入。`services/carbon.py` 的固碳量公式已完成，等 dbh 有值即可直接呼叫。

⚠️ `services/data_pipeline.py` 裡的 `process_upload()` 仍是 `raise NotImplementedError` 的空殼，**不是**目前實際使用的入口，不要被相似的函式名稱誤導。

- 所有查詢邏輯統一寫在 `services/db.py`，**不可在 routes/ 裡直接查資料庫**
- ⚠️ **`Measurements.status` 資料庫實際存的值是 `'Pending'` / `'Approved'`**（注意大小寫，跟本文件其他地方寫的 `pending`/`confirmed` 不同字）。後端 API 回傳給前端時統一轉換成小寫 `pending`／`confirmed` 對外，但**寫入資料庫時要用資料庫實際接受的 `'Pending'`/`'Approved'`**，比對時建議用 `LOWER(status) = 'pending'` 這種不分大小寫的寫法，避免大小寫不一致造成查詢漏資料
- 資料表現況：`Sites`、`Biomass_Parameters`、`tree_records` 已被刪除（`site_name` 併入 `Measurements`、異速生長參數併入 `Species_Ref`），目前實際存在的表為 `Trees`、`Measurements`、`Species_Ref`、`Admins`、`Camera_Profiles`、`Sensor_Sync_Records`；異動歷史見 `sql/` 底下依日期命名的 `.sql` 檔
- 欄位命名對照（依實際資料庫為準）：

| 資料表 | 欄位 | 說明 |
|---|---|---|
| Trees | tracker_id | `NOT NULL`。目前直接沿用該樹的 `track_id` 當值；沒有 track_id 的舊式資料才自動遞增取號（見下方「樹木身分比對邏輯」） |
| Trees | LATITUDE N/S / LONGITUDE E/W | 樹木座標欄位，字串格式（如 `"25.0883747N"`），需用 `_parse_coord()` 轉成數字，S/W 為負值 |
| Trees | species_id | 樹種辨識結果，`tree_species.classify_pending_trees()` 寫入，信心不足時為 `NULL` |
| Measurements | status | `Pending` / `Approved`（注意大小寫） |
| Measurements | site_name | 匯入批次名稱，預設取上傳影片檔名（去副檔名） |
| Measurements | track_id / Final_Dist_cm | 追蹤編號、IQR 去極端值後的代表距離，是座標換算與 Tree_ID 比對的依據 |
| Measurements | dbh | 樹徑（公分），目前僅能由後台手動填入 |
| Measurements | carbon_absorpation | 固碳量 |
| Measurements | image_data | 樹木照片二進位（VARBINARY），用 `_img_bin_to_data_uri()` 轉成前端可用的 data URI，不寫檔到 static/img/ |
| Species_Ref | allo_param_a / allo_param_b | 異速生長方程式參數（`biomass = a × dbh^b`），已併入 `Species_Ref`（原 `Biomass_Parameters` 表已刪除） |

### 樹木身分比對邏輯（Tree_ID）

- **同一次匯入（同一段影片）內**：用 `track_id` 判斷是不是同一棵樹，配對邏輯見上方「去極端值」步驟（`tree_analysis._assign_tree_key()`，依 `site_name + track_id` 分群）
- **座標換算階段的去重**：`tree_coordinate.recalculate_tree_coordinates()` 呼叫 `db_service.find_linked_tree_id(site_name, track_id)`，同一個 `site_name + track_id` 組合已經算過真實座標就沿用既有 `Tree_ID`，否則才新增一筆 `Trees`（`tracker_id` 直接設為該筆的 `track_id`）。這解決了重跑管線導致 `Trees` 重複新增的問題
- ⚠️ **跨次辨識同一棵實體樹**（例如下個月複測同一條路，能否認出是同一棵樹）：**尚未實作**。`track_id` 每次重新追蹤都從頭編號，不能跨次沿用；規劃是改用樹木座標比對（找資料庫裡座標相近的既有 `Tree_ID`），目前 `insert_tree_coordinate()` 對每筆符合條件的量測都是直接新增新 `Trees` 記錄，還沒有這層比對
- 沒有 `track_id` 的舊式資料（純 ToF、無影片追蹤）沒有可靠欄位判斷「同一棵樹」，目前每次都會新增一筆，重複問題只在有 `track_id` 的資料上被解決

### 樹徑計算邏輯

1. `services/analysis/tracker.py` 對每一幀輸出 `pixel_width`（分割遮罩量出的像素寬度，**還不是公分**），`data_pipeline.run_upload_and_save()` 已經把它配對回每筆 `Measurements`
2. 同一個 `track_id` 通常會有多幀資料，對各幀配對到的 **ToF 距離** 做 IQR 去除離群值，取代表性距離（`tree_analysis.py` 已實作此步驟，寫回 `Final_Dist_cm`）
3. `真正樹徑(cm) = pixel_width × k值`，k值（cm/pixel）隨距離變化，且需要用已知直徑物體在已知距離實際拍照校正相機硬體才能得到，**目前尚未校正**，所以最後這一步（把 `pixel_width` 換算成 `dbh` 並寫回資料庫）**尚未實作**

### 樹木座標計算邏輯

- 已實作：`services/geo.py` 的大圓公式，感測器與車輛前進方向垂直安裝，樹木真實座標 = 拍攝點座標，往感測器朝向那一側，依「方位角(HEADING) ± 90 度」的方向，偏移 `Final_Dist_cm` 那麼遠，由 `tree_coordinate.recalculate_tree_coordinates()` 呼叫並寫回 `Trees`
- 感測器朝哪一側（左/右）是固定的硬體安裝方式，若尚未存在 `config.py` 常數，新增時不需要對應的資料庫欄位

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
