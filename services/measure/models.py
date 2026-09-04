# 負責人：張恆輔
# 開發日期：2026/09/04
# 用途：/measure 頁面用，定義量測結果在各模組間傳遞的統一格式

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MeasurementResult:
    # 核心結果
    diameter_cm: float = 0.0
    method: str = 'unknown'
    status: str = 'unknown'

    # 驗證細節
    result_a: Optional[float] = None
    result_b: float = 0.0

    # 信心度資訊
    confidence: float = 0.0
    diameter_std: float = 0.0
    warnings: list = field(default_factory=list)

    # 固碳量
    species_name: str = ''
    biomass_kg: float = 0.0
    carbon_kg: float = 0.0
    co2_kg: float = 0.0

    # 紀錄
    timestamp: str = ''
    image_file: str = ''
    measurement_y: float = 0.0
