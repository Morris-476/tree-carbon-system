# 負責人：陳政雍 09/05 固碳量計算，供 data_pipeline.py（網站上傳流程）與
# services/measure/pipeline.py（/measure 簡易固碳匯測頁面）共用

"""
純計算模組，絕對不可以自己查資料庫。樹種參數（allo_param_a、allo_param_b、
carbon_fraction）一律由呼叫端傳入，呼叫端應先用 services/db.py 的
get_species_list() 查出樹種資料後再傳進來。

計算公式：
    生物量(kg)        = allo_param_a × DBH(cm)^allo_param_b
    碳儲存量(kg)      = 生物量 × carbon_fraction
    固碳量CO2當量(kg) = 碳儲存量 × 3.67
"""

from dataclasses import dataclass
from typing import Optional

# 碳轉換成CO2當量的係數（CO2 與碳的分子量比 44/12，四捨五入）
CO2_EQUIVALENT_FACTOR = 3.67


@dataclass
class CarbonResult:
    """固碳量計算結果，欄位命名對齊 services/measure/models.py 的
    MeasurementResult（biomass_kg / carbon_kg / co2_kg）。

    error 為 None 代表計算成功；不為 None 時代表參數無效、算不出來，
    此時 biomass_kg / carbon_kg / co2_kg 一律維持預設值 0.0，
    呼叫端應該先檢查 error 再使用數值。
    """
    biomass_kg: float = 0.0
    carbon_kg: float = 0.0
    co2_kg: float = 0.0
    error: Optional[str] = None


def calculate_carbon(dbh, allo_param_a, allo_param_b, carbon_fraction) -> CarbonResult:
    """依樹徑（cm）與樹種異速生長參數計算固碳量。
    dbh、allo_param_a、allo_param_b、carbon_fraction 任一個是 None 或 <= 0
    時不會拋例外炸掉呼叫端，改回傳 error 有值的 CarbonResult，由呼叫端決定
    如何呈現這個錯誤（例如網頁上傳流程回傳 400，/measure 頁面顯示警告）。
    """
    invalid_param = _find_invalid_param(dbh, allo_param_a, allo_param_b, carbon_fraction)
    if invalid_param is not None:
        return CarbonResult(
            error=f'{invalid_param} 無效（必須是大於 0 的數字），無法計算固碳量'
        )

    biomass_kg = allo_param_a * (dbh ** allo_param_b)
    carbon_kg = biomass_kg * carbon_fraction
    co2_kg = carbon_kg * CO2_EQUIVALENT_FACTOR

    return CarbonResult(biomass_kg=biomass_kg, carbon_kg=carbon_kg, co2_kg=co2_kg)


def _find_invalid_param(dbh, allo_param_a, allo_param_b, carbon_fraction) -> Optional[str]:
    """依序檢查四個參數，回傳第一個無效的參數名稱；全部有效則回傳 None。"""
    params = {
        'dbh': dbh,
        'allo_param_a': allo_param_a,
        'allo_param_b': allo_param_b,
        'carbon_fraction': carbon_fraction,
    }
    for name, value in params.items():
        if value is None or value <= 0:
            return name
    return None
