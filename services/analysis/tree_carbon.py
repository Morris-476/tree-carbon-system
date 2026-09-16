# 負責人：Morris
# 開發日期：2026/09/12
# 用途：固碳量計算批次腳本，跟 tree_diameter.py 同一種模式——離線執行，
#      排在樹徑換算、樹種辨識都完成之後。讀取已知樹種、已算出樹徑、但
#      固碳量還沒算的代表紀錄，呼叫 services/core/carbon.py 的異速生長公式，
#      把結果寫回 Measurements.biomass／carbon_absorpation。
import os

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from services.core import db as db_service
from services.core.carbon import calculate_carbon


def calculate_pending_carbon() -> dict:
    """對所有符合條件的代表紀錄計算固碳量。
    回傳 {'calculated': int, 'failed': int}。"""
    rows = db_service.get_measurements_needing_carbon()
    calculated, failed = 0, 0

    for row in rows:
        result = calculate_carbon(
            dbh=float(row['dbh']),
            allo_param_a=float(row['allo_param_a']),
            allo_param_b=float(row['allo_param_b']),
            carbon_fraction=float(row['carbon_fraction']),
        )
        if result.error is not None:
            print(f"⚠ record_id={row['record_id']} 略過：{result.error}")
            failed += 1
            continue

        db_service.update_measurement_carbon(row['record_id'], result.biomass_kg, result.carbon_kg)
        print(f"✓ record_id={row['record_id']} → 固碳量={result.carbon_kg:.2f}kg"
              f"（CO2當量={result.co2_kg:.2f}kg）")
        calculated += 1

    print(f"\n共計算 {calculated} 筆固碳量（略過 {failed} 筆）")
    return {'calculated': calculated, 'failed': failed}


if __name__ == '__main__':
    calculate_pending_carbon()
