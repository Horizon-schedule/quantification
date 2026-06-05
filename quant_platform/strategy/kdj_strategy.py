"""
KDJ 策略模块。
支持：超买超卖、金叉死叉共振。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class KDJStrategy(BaseStrategy):
    """
    KDJ 策略。

    模式:
    - cross: K 线与 D 线金叉/死叉
    - oversold: J < 20 超卖买入，J > 80 超买卖出
    - resonance: 金叉 + 超卖共振买入，死叉 + 超买共振卖出
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "n": 9,
            "m1": 3,
            "m2": 3,
            "mode": "resonance",
            "oversold": 20,
            "overbought": 80,
        }
        if params:
            default_params.update(params)
        super().__init__(name="KDJ策略", params=default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = TechnicalIndicators.kdj(
            df, n=self.params["n"], m1=self.params["m1"], m2=self.params["m2"]
        )
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        k = result["kdj_k"]
        d = result["kdj_d"]
        j = result["kdj_j"]
        oversold = self.params["oversold"]
        overbought = self.params["overbought"]
        mode = self.params["mode"]

        golden = TechnicalIndicators.detect_golden_cross(k, d)
        death = TechnicalIndicators.detect_death_cross(k, d)

        if mode == "cross":
            result.loc[golden, "signal"] = SignalType.BUY.value
            result.loc[golden, "signal_reason"] = "KDJ金叉"
            result.loc[death, "signal"] = SignalType.SELL.value
            result.loc[death, "signal_reason"] = "KDJ死叉"

        elif mode == "oversold":
            result.loc[j < oversold, "signal"] = SignalType.BUY.value
            result.loc[j < oversold, "signal_reason"] = f"KDJ超卖(J<{oversold})"
            result.loc[j > overbought, "signal"] = SignalType.SELL.value
            result.loc[j > overbought, "signal_reason"] = f"KDJ超买(J>{overbought})"

        elif mode == "resonance":
            buy = golden & (j < oversold + 10)
            sell = death & (j > overbought - 10)
            result.loc[buy, "signal"] = SignalType.BUY.value
            result.loc[buy, "signal_reason"] = "KDJ金叉+超卖共振"
            result.loc[sell, "signal"] = SignalType.SELL.value
            result.loc[sell, "signal_reason"] = "KDJ死叉+超买共振"

        return result
