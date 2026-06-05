"""
均线策略模块。
支持：5/10/20 日均线金叉死叉、多头排列、空头排列。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class MAStrategy(BaseStrategy):
    """
    均线策略。

    模式:
    - cross: 短期均线上穿/下穿长期均线（金叉/死叉）
    - bull_align: 多头排列（MA5 > MA10 > MA20）买入
    - bear_align: 空头排列（MA5 < MA10 < MA20）卖出
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_period": 5,
            "mid_period": 10,
            "slow_period": 20,
            "mode": "cross",  # cross / bull_align / bear_align
        }
        if params:
            default_params.update(params)
        super().__init__(name="均线策略", params=default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        fast = self.params["fast_period"]
        mid = self.params["mid_period"]
        slow = self.params["slow_period"]
        mode = self.params["mode"]

        result = TechnicalIndicators.ma(df, periods=(fast, mid, slow))
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        ma_fast = result[f"ma{fast}"]
        ma_mid = result[f"ma{mid}"]
        ma_slow = result[f"ma{slow}"]

        if mode == "cross":
            golden = TechnicalIndicators.detect_golden_cross(ma_fast, ma_slow)
            death = TechnicalIndicators.detect_death_cross(ma_fast, ma_slow)
            result.loc[golden, "signal"] = SignalType.BUY.value
            result.loc[golden, "signal_reason"] = f"MA{fast}金叉MA{slow}"
            result.loc[death, "signal"] = SignalType.SELL.value
            result.loc[death, "signal_reason"] = f"MA{fast}死叉MA{slow}"

        elif mode == "bull_align":
            bull = (ma_fast > ma_mid) & (ma_mid > ma_slow)
            bear = (ma_fast < ma_mid) & (ma_mid < ma_slow)
            result.loc[bull & ~bull.shift(1).fillna(False), "signal"] = SignalType.BUY.value
            result.loc[bull & ~bull.shift(1).fillna(False), "signal_reason"] = "均线多头排列"
            result.loc[bear & ~bear.shift(1).fillna(False), "signal"] = SignalType.SELL.value
            result.loc[bear & ~bear.shift(1).fillna(False), "signal_reason"] = "均线空头排列"

        elif mode == "bear_align":
            death = TechnicalIndicators.detect_death_cross(ma_fast, ma_mid)
            golden = TechnicalIndicators.detect_golden_cross(ma_fast, ma_mid)
            result.loc[death, "signal"] = SignalType.SELL.value
            result.loc[death, "signal_reason"] = f"MA{fast}死叉MA{mid}"
            result.loc[golden, "signal"] = SignalType.BUY.value
            result.loc[golden, "signal_reason"] = f"MA{fast}金叉MA{mid}"

        return result
