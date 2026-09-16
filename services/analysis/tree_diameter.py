# 負責人：Morris
# 開發日期：2026/09/12
# 用途：樹徑換算批次腳本，跟 tree_coordinate.py／tree_species.py 同一種模式——
#      離線執行，不是 /api/upload 即時流程的一部分。讀取已經有代表距離
#      （Final_Dist_cm）、但樹徑（dbh）還沒算出來的代表紀錄，呼叫
#      services/core/diameter.py 的針孔成像公式，把結果寫回 Measurements.dbh。
import os

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from services.core import db as db_service
from services.core.diameter import calculate_diameter_cm


def calculate_pending_diameters() -> dict:
    """對所有符合條件的代表紀錄換算樹徑。
    回傳 {'calculated': int, 'failed': int}。"""
    rows = db_service.get_measurements_needing_diameter()
    calculated, failed = 0, 0

    for row in rows:
        result = calculate_diameter_cm(
            pixel_width_px=row['pixel_width'],
            image_width_px=row['mask_width'],
            distance_cm=row['distance_cm'],
            focal_mm=float(row['focal_mm']),
            sensor_width_mm=float(row['sensor_width_mm']),
        )
        if result.error is not None:
            print(f"⚠ record_id={row['record_id']} 略過：{result.error}")
            failed += 1
            continue

        db_service.update_measurement_dbh(row['record_id'], result.diameter_cm)
        print(f"✓ record_id={row['record_id']} → dbh={result.diameter_cm}cm")
        calculated += 1

    print(f"\n共換算 {calculated} 筆樹徑（略過 {failed} 筆）")
    return {'calculated': calculated, 'failed': failed}


if __name__ == '__main__':
    calculate_pending_diameters()
