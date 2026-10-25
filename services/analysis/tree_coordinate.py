# 負責人：Morris、justin99lin
# 開發日期：2026/09/07
# 用途：讀取 GNSS 座標與方位角，用大圓公式推算樹木座標寫入 Trees
import os

if __name__ == '__main__':
    # config.py 在 import 當下就會用 os.environ.get() 讀取 DB_SERVER 等連線設定，
    # 所以 load_dotenv() 一定要在 import services.core.db（進而 import config）之前執行，
    # 不然會讀到空字串，拼出無效的連線字串。
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from services.core import db as db_service
from services.core.geo import compute_tree_coordinate


def load_measurements_for_coordinate() -> list:
    """讀取可用於座標推算的量測資料：record_id、site_name、track_id、
    video_seq、推車 GNSS 座標、方位角、Final_Dist_cm。latitude／longitude／
    HEADING／Final_Dist_cm 缺一不可，依 record_id 排序，新增到 Trees 的
    順序才會跟 Measurements 一致。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError('資料庫連線失敗，無法讀取 Measurements 資料')
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT record_id, site_name, track_id, video_seq,
                   latitude, longitude, HEADING, Final_Dist_cm
            FROM Measurements
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND HEADING IS NOT NULL
              AND Final_Dist_cm IS NOT NULL
            ORDER BY record_id
        ''')
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def recalculate_tree_coordinates() -> dict:
    """依推車座標＋方位角＋ToF 測距，推算每筆符合條件的量測對應的地理座標。
    track_id 有值時，同一棵樹（site_name+video_seq+track_id 相同）只會新增
    一次 Trees 記錄，之後都沿用；並把每筆代表紀錄的 Measurements.Tree_ID
    改成真正的 Tree_ID。"""
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
            tree_id = db_service.find_linked_tree_id(
                row['site_name'], row['track_id'], row['video_seq']
            )

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

        db_service.link_measurement_to_tree(
            row['site_name'], row['video_seq'], row['track_id'], tree_id
        )

    print(f'\n共新增 {inserted} 筆、沿用 {reused} 筆 Trees 記錄（略過 {skipped} 筆）')
    return {'inserted': inserted, 'reused': reused, 'skipped': skipped}


if __name__ == '__main__':
    recalculate_tree_coordinates()
