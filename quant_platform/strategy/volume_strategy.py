"""
成交量策略模块。
支持：放量突破、缩量回调、量价共振。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.strategy.base import BaseStrategy, SignalType


class VolumeStrategy(BaseStrategy):
    """
    成交量策略。

    模式:
    - breakout: 放量突破（量比 > 阈值 且 价格上涨）
    - pullback: 缩量回调（量比 < 阈值 且 价格回调）
    - resonance: 量价共振（价涨量增买入，价跌量增卖出）
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "vol_period": 5,
            "vol_ratio_high": 2.0,
            "vol_ratio_low": 0.5,
            "mode": "resonance",
            "price_change_threshold": 0.01,
        }
        if params:
            default_params.update(params)
        super().__init__(name="成交量策略", params=default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = TechnicalIndicators.volume_indicators(
            df, period=self.params["vol_period"]
        )
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""

        vol_ratio = result["vol_ratio"]
        price_change = result["close"].pct_change()
        threshold = self.params["price_change_threshold"]
        mode = self.params["mode"]

        if mode == "breakout":
            cond = (vol_ratio > self.params["vol_ratio_high"]) & (
                price_change > threshold
            )
            result.loc[cond, "signal"] = SignalType.BUY.value
            result.loc[cond, "signal_reason"] = "放量突破"

        elif mode == "pullback":
            cond = (vol_ratio < self.params["vol_ratio_low"]) & (
                price_change < -threshold
            )
            result.loc[cond, "signal"] = SignalType.SELL.value
            result.loc[cond, "signal_reason"] = "缩量回调"

        elif mode == "resonance":
            buy = (vol_ratio > 1.5) & (price_change > threshold)
            sell = (vol_ratio > 1.5) & (price_change < -threshold)
            result.loc[buy, "signal"] = SignalType.BUY.value
            result.loc[buy, "signal_reason"] = "量价共振买入"
            result.loc[sell, "signal"] = SignalType.SELL.value
            result.loc[sell, "signal_reason"] = "量价共振卖出"

        return result
