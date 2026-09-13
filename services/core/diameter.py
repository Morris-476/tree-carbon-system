# 負責人：Morris
# 開發日期：2026/09/12
# 用途：像素寬度換算成真實樹徑（cm）的共用公式模組，供 data_pipeline.py（網站上傳流程）
#      與 services/measure/pipeline.py（/measure 簡易固碳繪測頁面）共用

"""
純計算模組，絕對不可以自己查資料庫、不做任何 YOLO 偵測。所有參數（像素寬度、
照片寬度、拍攝距離、焦距、感光元件寬度）一律由呼叫端量測/查詢好再傳入。

計算公式（針孔成像，相似三角形關係）：
    真實寬度(cm) = (像素寬度 / 照片寬度) × 感光元件寬度(mm) × (拍攝距離(cm) / 焦距(mm))
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DiameterResult:
    """樹徑換算結果，欄位命名對齊 services/carbon.py 的 CarbonResult。

    error 為 None 代表計算成功；不為 None 時代表參數無效、算不出來，
    此時 diameter_cm 維持預設值 0.0，呼叫端應該先檢查 error 再使用數值。
    """
    diameter_cm: float = 0.0
    error: Optional[str] = None


def calculate_diameter_cm(pixel_width_px, image_width_px, distance_cm,
                           focal_mm, sensor_width_mm) -> DiameterResult:
    """依像素寬度與拍攝參數換算真實樹徑（cm）。
    五個參數任一個是 None 或 <= 0 時不會拋例外炸掉呼叫端，改回傳 error 有值的
    DiameterResult，由呼叫端決定如何處理（例如網站上傳流程維持 dbh=0、
    /measure 頁面顯示警告）。
    """
    invalid_param = _find_invalid_param(
        pixel_width_px, image_width_px, distance_cm, focal_mm, sensor_width_mm
    )
    if invalid_param is not None:
        return DiameterResult(
            error=f'{invalid_param} 無效（必須是大於 0 的數字），無法換算樹徑'
        )

    diameter_cm = (pixel_width_px / image_width_px) * sensor_width_mm * (distance_cm / focal_mm)
    return DiameterResult(diameter_cm=round(diameter_cm, 2))


def _find_invalid_param(pixel_width_px, image_width_px, distance_cm,
                         focal_mm, sensor_width_mm) -> Optional[str]:
    """依序檢查五個參數，回傳第一個無效的參數名稱；全部有效則回傳 None。"""
    params = {
        'pixel_width_px': pixel_width_px,
        'image_width_px': image_width_px,
        'distance_cm': distance_cm,
        'focal_mm': focal_mm,
        'sensor_width_mm': sensor_width_mm,
    }
    for name, value in params.items():
        if value is None or value <= 0:
            return name
    return None
