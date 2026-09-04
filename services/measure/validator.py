# 負責人：張恆輔
# 開發日期：2026/09/04
# 用途：/measure 頁面用，把樹徑量測結果包裝成 MeasurementResult
#
# 注意：本頁未串接 QR code 比例尺（方法一，qr_detector.py/qr_calculator.py 未搬入），
#      只有焦距公式（方法二）可用，故不保留原本「比對兩種方法差異」的邏輯，
#      避免留下永遠不會被執行到的分支。

import datetime

from services.measure.models import MeasurementResult


class Validator:
    """把焦距公式（方法二）算出的樹徑，包裝成 MeasurementResult。"""

    def validate(self, result_b: float) -> MeasurementResult:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return MeasurementResult(
            diameter_cm=round(result_b, 2),
            method='focal_only',
            status='qr_failed',
            result_a=None,
            result_b=round(result_b, 2),
            timestamp=now,
            warnings=['QR code 比例尺尚未啟用，已使用焦距公式量測']
        )
