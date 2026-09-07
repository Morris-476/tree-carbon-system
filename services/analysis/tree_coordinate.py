# 樹木座標計算：讀取 Measurements 的推車 GNSS 座標／方位角／Final_Dist_cm，
# 用 services/geo.py 的大圓公式推算樹木本身的地理座標，覆蓋寫回 Trees。
"""
每筆 Measurements 只有帶 Final_Dist_cm 的那列（tree_analysis.py 篩出的
每棵樹代表列）才拿來推算座標，避免同一棵樹的其他量測列（Final_Dist_cm 為
NULL）被誤算成不同座標。
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
    """讀取可用於座標推算的量測資料：Tree_ID、推車 GNSS 座標、方位角、
    Final_Dist_cm 缺一不可。"""
    conn = db_service.get_db_connection()
    if conn is None:
        raise RuntimeError("資料庫連線失敗，無法讀取 Measurements 資料")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Tree_ID, latitude, longitude, HEADING, Final_Dist_cm
            FROM Measurements
            WHERE Tree_ID IS NOT NULL
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND HEADING IS NOT NULL
              AND Final_Dist_cm IS NOT NULL
        """)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def recalculate_tree_coordinates() -> dict:
    """依推車座標＋方位角＋ToF 測距，推算每棵樹的地理座標並覆蓋寫回
    Trees.[LATITUDE N/S] / [LONGITUDE E/W]（原本存的舊座標直接蓋掉）。"""
    rows = load_measurements_for_coordinate()
    updated, skipped = 0, 0

    for row in rows:
        result = compute_tree_coordinate(
            row['latitude'], row['longitude'], row['HEADING'], row['Final_Dist_cm']
        )
        if result.error is not None:
            print(f"⚠ Tree_ID={row['Tree_ID']} 略過：{result.error}")
            skipped += 1
            continue
        db_service.update_tree_coordinate(row['Tree_ID'], result.latitude, result.longitude)
        updated += 1

    print(f"✓ 已推算並寫回 {updated} 棵樹的座標（略過 {skipped} 筆）")
    return {'updated': updated, 'skipped': skipped}


if __name__ == '__main__':
    recalculate_tree_coordinates()
