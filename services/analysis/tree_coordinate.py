# 樹木座標計算：讀取 Measurements 的推車 GNSS 座標／方位角／Final_Dist_cm，
# 用 services/geo.py 的大圓公式推算樹木本身的地理座標，寫入 Trees。
"""
2026/09/12修正：這支函式被 data_pipeline.run_upload_and_save() 接上後，
每次上傳資料都會自動執行一次，掃描的又是整張 Measurements 表，原本「每一筆
都直接新增」的做法會讓同一批舊資料在每次上傳時被重複新增到 Trees，筆數隨
上傳次數線性增加。修正後：track_id 有值時，先用 find_linked_tree_id() 查
這個 site_name + track_id 組合是不是已經算過真實座標，算過就沿用既有
Tree_ID，沒有才新增；算完（不管沿用或新增）都用 link_measurement_to_tree()
把這筆代表紀錄的 Measurements.Tree_ID 改成真正的 Tree_ID，取代上傳當下的
佔位值。

已知限制：track_id 為 None 的舊式無追蹤資料，沒有可靠的欄位能判斷兩筆
「同一棵樹」，這種資料維持原本的行為——每次都新增一筆，未解決重複問題，
影響範圍限定在沒有 track_id 的舊式資料。
"""
import os

if __name__ == '__main__':
    # config.py 在 import 當下就會用 os.environ.get() 讀取 DB_SERVER 等連線設定，
    # 所以 load_dotenv() 一定要在 import services.db（進而 import config）之前執行，
    # 不然會讀到空字串，拼出無效的連線字串。
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from services import db as db_service
from services.geo import compute_tree_coordinate


def load_measurements_for_coordinate() -> list:
    """讀取可用於座標推算的量測資料：record_id、site_name、track_id、推車
    GNSS 座標、方位角、Final_Dist_cm。latitude／longitude／HEADING／
    Final_Dist_cm 缺一不可，依 record_id 排序，新增到 Trees 的順序才會跟
    Measurements 一致。site_name 是判斷「這棵樹算過了沒」必要的欄位
    （見 find_linked_tree_id() 說明）。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError("資料庫連線失敗，無法讀取 Measurements 資料")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT record_id, site_name, track_id, latitude, longitude, HEADING, Final_Dist_cm
            FROM Measurements
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND HEADING IS NOT NULL
              AND Final_Dist_cm IS NOT NULL
            ORDER BY record_id
        """)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def recalculate_tree_coordinates() -> dict:
    """依推車座標＋方位角＋ToF 測距，推算每筆符合條件的量測對應的地理座標。
    track_id 有值時，同一棵樹（site_name + track_id 相同）只會新增一次
    Trees 記錄，之後都沿用；並把每筆代表紀錄的 Measurements.Tree_ID 改成
    真正的 Tree_ID（見檔案開頭 2026/09/12修正 說明）。"""
    rows = load_measurements_for_coordinate()
    inserted, reused, skipped = 0, 0, 0

    for row in rows:
        result = compute_tree_coordinate(
            row['latitude'], row['longitude'], row['HEADING'], row['Final_Dist_cm']
        )
        if result.error is not None:
            print(f"⚠ record_id={row['record_id']} 略過：{result.error}")
            skipped += 1
            continue

        tree_id = None
        if row['track_id'] is not None:
            tree_id = db_service.find_linked_tree_id(row['site_name'], row['track_id'])

        if tree_id is not None:
            print(f"= record_id={row['record_id']} → 沿用既有 Tree_ID={tree_id}")
            reused += 1
        else:
            tree_id = db_service.insert_tree_coordinate(
                result.latitude, result.longitude, tracker_id=row['track_id']
            )
            print(f"✓ record_id={row['record_id']} → 新增 Tree_ID={tree_id}："
                  f"{result.latitude:.7f}, {result.longitude:.7f}")
            inserted += 1

        db_service.link_measurement_to_tree(row['record_id'], tree_id)

    print(f"\n共新增 {inserted} 筆、沿用 {reused} 筆 Trees 記錄（略過 {skipped} 筆）")
    return {'inserted': inserted, 'reused': reused, 'skipped': skipped}


if __name__ == '__main__':
    recalculate_tree_coordinates()
