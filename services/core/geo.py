# 樹木座標推算：純計算模組，依推車 GNSS 座標、方位角與 ToF 測距結果，
# 用球面大圓（Great Circle）目的地推算公式，算出樹木本身的地理座標。
# 絕對不可以自己查資料庫，量測資料一律由呼叫端（services/analysis/tree_coordinate.py）傳入。

"""
計算公式（Veness, n.d. 之大圓航線目的地推算公式）：
    θ = 推車方位角 + 90°                                                 ...(5)
    δ = D / R                                                            ...(6)
    φ2 = asin( sin φ1 × cos δ + cos φ1 × sin δ × cos θ )                ...(7)
    λ2 = λ1 + atan2( sin θ × sin δ × cos φ1, cos δ − sin φ1 × sin φ2 )  ...(8)

φ1、λ1 為推車當下的 GNSS 緯度／經度，D 為 ToF 測距儀量測所得之相機至樹幹
距離，R 為地球半徑（取近似值 6,371 km），δ 為 D 換算而成的角距離，θ 為樹木
相對於推車的方位角——本系統採側向連續掃描，相機朝向與推車行進方向垂直，
故以推車行進方位角 + 90° 偏移推算而得。
"""

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin
from typing import Optional

EARTH_RADIUS_KM = 6371.0
CAMERA_OFFSET_DEG = 90.0


@dataclass
class TreeCoordinate:
    """樹木座標推算結果，latitude／longitude 為十進位度。

    error 為 None 代表計算成功；不為 None 時代表輸入參數無效，
    此時 latitude／longitude 一律維持預設值 0.0，呼叫端應先檢查 error 再使用數值。
    """
    latitude: float = 0.0
    longitude: float = 0.0
    error: Optional[str] = None


def compute_tree_coordinate(cart_lat, cart_lon, heading_deg, distance_cm) -> TreeCoordinate:
    """依推車 GNSS 座標（十進位度）、方位角（度）與 ToF 測距（cm），
    推算樹木的地理座標（十進位度）。對應公式(5)~(8)。
    """
    invalid_param = _find_invalid_param(cart_lat, cart_lon, heading_deg, distance_cm)
    if invalid_param is not None:
        return TreeCoordinate(error=f'{invalid_param} 無效，無法推算樹木座標')

    theta = radians(heading_deg + CAMERA_OFFSET_DEG)          # (5)
    delta = (distance_cm / 100000.0) / EARTH_RADIUS_KM        # (6)，cm 換算成 km 後再除以地球半徑

    phi1 = radians(cart_lat)
    lambda1 = radians(cart_lon)

    phi2 = asin(                                               # (7)
        sin(phi1) * cos(delta) + cos(phi1) * sin(delta) * cos(theta)
    )
    lambda2 = lambda1 + atan2(                                 # (8)
        sin(theta) * sin(delta) * cos(phi1),
        cos(delta) - sin(phi1) * sin(phi2)
    )

    return TreeCoordinate(latitude=degrees(phi2), longitude=degrees(lambda2))


def _find_invalid_param(cart_lat, cart_lon, heading_deg, distance_cm) -> Optional[str]:
    """依序檢查四個參數，回傳第一個無效的參數名稱；全部有效則回傳 None。"""
    params = {
        'cart_lat': cart_lat,
        'cart_lon': cart_lon,
        'heading_deg': heading_deg,
        'distance_cm': distance_cm,
    }
    for name, value in params.items():
        if value is None:
            return name
    if distance_cm <= 0:
        return 'distance_cm'
    return None
