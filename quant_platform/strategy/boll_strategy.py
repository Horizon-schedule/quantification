"""布林带策略：突破 / 均值回归。"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class BOLLStrategy(BaseStrategy):
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default = {"period": 20, "std_dev": 2.0, "mode": "breakout"}
        if params:
            default.update(params)
        super().__init__(name="BOLL策略", params=default)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = TechnicalIndicators.boll(
            df, period=self.params["period"], std_dev=self.params["std_dev"]
        )
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        close = result["close"]
        upper = result["boll_upper"]
        lower = result["boll_lower"]
        mid = result["boll_mid"]

        if self.params["mode"] == "breakout":
            buy = (close > upper) & (close.shift(1) <= upper.shift(1))
            sell = (close < lower) & (close.shift(1) >= lower.shift(1))
            result.loc[buy, "signal"] = SignalType.BUY.value
            result.loc[buy, "signal_reason"] = "突破布林上轨"
            result.loc[sell, "signal"] = SignalType.SELL.value
            result.loc[sell, "signal_reason"] = "跌破布林下轨"
        else:
            # 均值回归：触及下轨买，触及上轨卖
            buy = close <= lower
            sell = close >= upper
            result.loc[buy, "signal"] = SignalType.BUY.value
            result.loc[buy, "signal_reason"] = "触及布林下轨"
            result.loc[sell, "signal"] = SignalType.SELL.value
            result.loc[sell, "signal_reason"] = "触及布林上轨"

        return result
