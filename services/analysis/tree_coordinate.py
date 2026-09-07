# 樹木座標計算：讀取 Measurements 的推車 GNSS 座標／方位角／Final_Dist_cm，
# 用 services/geo.py 的大圓公式推算樹木本身的地理座標，寫入 Trees。
"""
不比對 Measurements.Tree_ID 或 track_id 是否已有對應的 Trees 記錄
（分群邏輯還在調整中，詳見 9/7 討論），每一筆 latitude、longitude、
HEADING、Final_Dist_cm 都有值的量測，都直接在 Trees 新增一筆記錄，
Tree_ID（IDENTITY）自動接續現有最大值往下遞增。
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
    """讀取可用於座標推算的量測資料：record_id、track_id、推車 GNSS 座標、
    方位角、Final_Dist_cm。latitude／longitude／HEADING／Final_Dist_cm 缺一不可，
    依 record_id 排序，新增到 Trees 的順序才會跟 Measurements 一致。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError("資料庫連線失敗，無法讀取 Measurements 資料")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT record_id, track_id, latitude, longitude, HEADING, Final_Dist_cm
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
    """依推車座標＋方位角＋ToF 測距，推算每筆符合條件的量測對應的地理座標，
    每筆都在 Trees 新增一筆新記錄（不覆蓋、不比對既有 Tree_ID／tracker_id）。"""
    rows = load_measurements_for_coordinate()
    inserted, skipped = 0, 0

    for row in rows:
        result = compute_tree_coordinate(
            row['latitude'], row['longitude'], row['HEADING'], row['Final_Dist_cm']
        )
        if result.error is not None:
            print(f"⚠ record_id={row['record_id']} 略過：{result.error}")
            skipped += 1
            continue
        tree_id = db_service.insert_tree_coordinate(
            result.latitude, result.longitude, tracker_id=row['track_id']
        )
        print(f"✓ record_id={row['record_id']} → 新增 Tree_ID={tree_id}："
              f"{result.latitude:.7f}, {result.longitude:.7f}")
        inserted += 1

    print(f"\n共新增 {inserted} 筆 Trees 記錄（略過 {skipped} 筆）")
    return {'inserted': inserted, 'skipped': skipped}


if __name__ == '__main__':
    recalculate_tree_coordinates()
