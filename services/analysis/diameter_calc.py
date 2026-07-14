"""
services/diameter_calc.py
ToF / 像素 → 樹徑換算，以及固碳量估算。
搬移自 Tree-Trunk-Segmentation/src/calculator.py。

⚠️  固碳公式目前在多個地方存在不同版本，實作前請先統一確認正確公式，
    再於此處實作，並同步更新 routes/api.py 的上傳路由。
"""


class TreeCalculator:

    @staticmethod
    def calculate_diameter(pixel_width, k_value):
        """DBH（cm）= 像素寬度 × k 值（cm/pixel）。
        pixel_width 為 0 或負值時應回傳 0.0。
        """
        # TODO: 待實作 — 負責人：____
        raise NotImplementedError("此函式尚未實作")

    @staticmethod
    def calculate_carbon(dbh_cm, species):
        """
        估算固碳量（CO₂ 當量，單位 kg）。
        Species_Ref 表中各樹種有對應的異速生長係數（a, b）與碳分率，
        實作前請先確認公式版本，並與 routes/api.py 保持一致。
        """
        # TODO: 待實作 — 負責人：____
        raise NotImplementedError("此函式尚未實作")

class TreeCalculator:
    @staticmethod
    def calculate_diameter(pixel_width, k_value):
        # DBH 計算公式 [cite: 49]
        return pixel_width * k_value if pixel_width > 0 else 0.0

    @staticmethod
    def calculate_carbon(dbh_cm, species):
        # 預設參數 (a, b) 依樹種而異 [cite: 50]
        params = {
            "樟樹": {"a": 0.1, "b": 2.4},
            "榕樹": {"a": 0.12, "b": 2.3},
            "default": {"a": 0.1, "b": 2.4}
        }
        p = params.get(species, params["default"])
        
        # 1. 計算生物量 (Biomass) [cite: 50]
        biomass = p["a"] * (dbh_cm ** p["b"])
        # 2. 計算固碳量 (CO2 當量) [cite: 50]
        co2_equivalent = biomass * 0.5 * 3.67
        return co2_equivalent