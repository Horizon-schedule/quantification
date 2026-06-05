"""RSI 策略：超买超卖 / 背离。"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class RSIStrategy(BaseStrategy):
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default = {"period": 14, "oversold": 30, "overbought": 70, "mode": "threshold"}
        if params:
            default.update(params)
        super().__init__(name="RSI策略", params=default)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = TechnicalIndicators.rsi(df, period=self.params["period"])
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        rsi = result["rsi"]
        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        if self.params["mode"] == "threshold":
            cross_up = (rsi.shift(1) < oversold) & (rsi >= oversold)
            cross_down = (rsi.shift(1) > overbought) & (rsi <= overbought)
            result.loc[cross_up, "signal"] = SignalType.BUY.value
            result.loc[cross_up, "signal_reason"] = f"RSI超卖反弹(<{oversold})"
            result.loc[cross_down, "signal"] = SignalType.SELL.value
            result.loc[cross_down, "signal_reason"] = f"RSI超买回落(>{overbought})"
        else:
            result.loc[rsi < oversold, "signal"] = SignalType.BUY.value
            result.loc[rsi < oversold, "signal_reason"] = "RSI超卖"
            result.loc[rsi > overbought, "signal"] = SignalType.SELL.value
            result.loc[rsi > overbought, "signal_reason"] = "RSI超买"

        return result
