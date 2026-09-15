# 負責人：張恆輔
# 開發日期：2026/09/04
# 用途：/measure 頁面用，把樹徑量測結果包裝成 MeasurementResult

import datetime

from services.measure.models import MeasurementResult


class Validator:
    """把焦距公式算出的樹徑，包裝成 MeasurementResult。"""

    def validate(self, result_b: float) -> MeasurementResult:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return MeasurementResult(
            diameter_cm=round(result_b, 2),
            method='focal_only',
            status='measured',
            result_a=None,
            result_b=round(result_b, 2),
            timestamp=now,
        )