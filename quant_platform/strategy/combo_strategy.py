"""
多指标共振策略。
对标聚宽/米筐经典组合：MA + MACD + 成交量三重确认。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class ComboStrategy(BaseStrategy):
    """多指标共振策略。"""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default = {
            "ma_fast": 5,
            "ma_slow": 20,
            "vol_ratio_min": 1.2,
            "require_macd": True,
        }
        if params:
            default.update(params)
        super().__init__(name="多指标共振", params=default)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = TechnicalIndicators.calc_all(df)
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        ma_fast = result[f"ma{self.params['ma_fast']}"]
        ma_slow = result[f"ma{self.params['ma_slow']}"]
        golden = TechnicalIndicators.detect_golden_cross(ma_fast, ma_slow)
        death = TechnicalIndicators.detect_death_cross(ma_fast, ma_slow)

        vol_ok = result["vol_ratio"] >= self.params["vol_ratio_min"]

        if self.params["require_macd"]:
            macd_buy = result["macd_dif"] > result["macd_dea"]
            macd_sell = result["macd_dif"] < result["macd_dea"]
        else:
            macd_buy = macd_sell = True

        buy = golden & vol_ok & macd_buy
        sell = death & macd_sell

        result.loc[buy, "signal"] = SignalType.BUY.value
        result.loc[buy, "signal_reason"] = "MA金叉+放量+MACD确认"
        result.loc[sell, "signal"] = SignalType.SELL.value
        result.loc[sell, "signal_reason"] = "MA死叉+MACD确认"

        return result
