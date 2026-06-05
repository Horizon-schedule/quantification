"""
MACD 策略模块。
支持：MACD 金叉死叉、顶底背离检测。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class MACDStrategy(BaseStrategy):
    """
    MACD 策略。

    模式:
    - cross: DIF 与 DEA 金叉/死叉
    - divergence: 价格与 MACD 柱顶底背离
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "mode": "cross",
            "lookback": 20,
        }
        if params:
            default_params.update(params)
        super().__init__(name="MACD策略", params=default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = TechnicalIndicators.macd(
            df,
            fast=self.params["fast"],
            slow=self.params["slow"],
            signal=self.params["signal"],
        )
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        dif = result["macd_dif"]
        dea = result["macd_dea"]

        if self.params["mode"] == "cross":
            golden = TechnicalIndicators.detect_golden_cross(dif, dea)
            death = TechnicalIndicators.detect_death_cross(dif, dea)
            result.loc[golden, "signal"] = SignalType.BUY.value
            result.loc[golden, "signal_reason"] = "MACD金叉"
            result.loc[death, "signal"] = SignalType.SELL.value
            result.loc[death, "signal_reason"] = "MACD死叉"

        elif self.params["mode"] == "divergence":
            lookback = self.params["lookback"]
            result = self._detect_divergence(result, lookback)

        return result

    def _detect_divergence(self, df: pd.DataFrame, lookback: int) -> pd.DataFrame:
        """
        检测顶底背离。

        底背离：价格创新低，MACD 柱未创新低 → 买入
        顶背离：价格创新高，MACD 柱未创新高 → 卖出
        """
        close = df["close"]
        hist = df["macd_hist"]

        for i in range(lookback, len(df)):
            window_close = close.iloc[i - lookback : i + 1]
            window_hist = hist.iloc[i - lookback : i + 1]

            # 底背离
            if (
                close.iloc[i] <= window_close.min()
                and hist.iloc[i] > window_hist.min()
                and hist.iloc[i] < 0
            ):
                df.iloc[i, df.columns.get_loc("signal")] = SignalType.BUY.value
                df.iloc[i, df.columns.get_loc("signal_reason")] = "MACD底背离"

            # 顶背离
            elif (
                close.iloc[i] >= window_close.max()
                and hist.iloc[i] < window_hist.max()
                and hist.iloc[i] > 0
            ):
                df.iloc[i, df.columns.get_loc("signal")] = SignalType.SELL.value
                df.iloc[i, df.columns.get_loc("signal_reason")] = "MACD顶背离"

        return df
