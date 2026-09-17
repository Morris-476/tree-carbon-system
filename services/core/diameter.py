# 負責人：Morris
# 開發日期：2026/09/12
# 用途：像素寬度換算真實樹徑（cm）的共用公式模組，供上傳流程與 /measure 共用

"""純計算模組，不可查資料庫、不做 YOLO 偵測，參數皆由呼叫端量測好再傳入。

針孔成像公式：真實寬度(cm) = (像素寬度/照片寬度) × 感光元件寬度(mm) × (距離(cm)/焦距(mm))
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


@dataclass
class ScaleResult:
    """比例尺換算結果（每像素代表幾公分），供 services/measure/pipeline.py 使用。
    是 calculate_diameter_cm() 反過來解的版本：那支函式是「已經量到像素寬度，
    直接算出真實公分數」；這支函式是「還沒量像素寬度前，先算出比例尺」，
    讓 geometry.py 可以拿這個比例尺去掃描切片、換算寬度。

    error 為 None 代表計算成功；不為 None 時代表參數無效，此時 scale_cm_per_px
    維持預設值 0.0，呼叫端應先檢查 error 再使用數值。
    """
    scale_cm_per_px: float = 0.0
    error: Optional[str] = None


def calculate_scale_cm_per_px(image_width_px, distance_cm, focal_mm, sensor_width_mm) -> ScaleResult:
    """依拍攝距離與相機參數，算出「每像素代表幾公分」的比例尺（針孔成像公式）。
    四個參數任一個是 None 或 <= 0 時不會拋例外，改回傳 error 有值的 ScaleResult。
    """
    params = {
        'image_width_px': image_width_px,
        'distance_cm': distance_cm,
        'focal_mm': focal_mm,
        'sensor_width_mm': sensor_width_mm,
    }
    for name, value in params.items():
        if value is None or value <= 0:
            return ScaleResult(error=f'{name} 無效（必須是大於 0 的數字），無法計算比例尺')

    scale_cm_per_px = (sensor_width_mm * distance_cm) / (focal_mm * image_width_px)
    return ScaleResult(scale_cm_per_px=round(scale_cm_per_px, 6))