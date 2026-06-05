"""
条件选股器。
对标聚宽/米筐选股器：按技术指标条件筛选标的。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from quant_platform.data.repository import DataRepository
from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.utils.logger import get_logger

logger = get_logger("screener")


# 预置选股条件
PRESET_SCREENS = {
    "ma_golden_cross": {
        "name": "均线金叉",
        "description": "MA5 上穿 MA20",
    },
    "macd_golden_cross": {
        "name": "MACD金叉",
        "description": "DIF 上穿 DEA",
    },
    "rsi_oversold": {
        "name": "RSI超卖",
        "description": "RSI < 30",
    },
    "volume_breakout": {
        "name": "放量突破",
        "description": "量比 > 2 且收阳",
    },
    "boll_lower_touch": {
        "name": "布林下轨",
        "description": "收盘价触及布林下轨",
    },
}


class StockScreener:
    """技术指标条件选股。"""

    def __init__(self, repository: Optional[DataRepository] = None):
        self.repo = repository or DataRepository()

    def screen(
        self,
        codes: List[str],
        condition: str = "ma_golden_cross",
    ) -> List[Dict[str, Any]]:
        """
        对代码列表执行选股筛选。

        参数:
            codes: 待筛选股票代码列表
            condition: 预置条件名

        返回:
            满足条件的标的列表
        """
        results = []
        for code in codes:
            try:
                df = self.repo.get_kline_df(code, limit=60)
                if df.empty or len(df) < 20:
                    continue
                df = TechnicalIndicators.calc_all(df)
                last = df.iloc[-1]
                prev = df.iloc[-2]

                matched = False
                reason = ""

                if condition == "ma_golden_cross":
                    matched = (
                        prev.get("ma5", 0) <= prev.get("ma20", 0)
                        and last.get("ma5", 0) > last.get("ma20", 0)
                    )
                    reason = "MA5金叉MA20"

                elif condition == "macd_golden_cross":
                    matched = (
                        prev.get("macd_dif", 0) <= prev.get("macd_dea", 0)
                        and last.get("macd_dif", 0) > last.get("macd_dea", 0)
                    )
                    reason = "MACD金叉"

                elif condition == "rsi_oversold":
                    matched = last.get("rsi", 50) < 30
                    reason = f"RSI={last.get('rsi', 0):.1f}"

                elif condition == "volume_breakout":
                    matched = (
                        last.get("vol_ratio", 0) > 2
                        and last.get("close", 0) > last.get("open", 0)
                    )
                    reason = f"量比={last.get('vol_ratio', 0):.1f}"

                elif condition == "boll_lower_touch":
                    matched = last.get("close", 0) <= last.get("boll_lower", 0) * 1.01
                    reason = "触及布林下轨"

                if matched:
                    results.append({
                        "code": code,
                        "close": round(float(last["close"]), 2),
                        "change_pct": round(float(last.get("change_pct", 0)), 2),
                        "reason": reason,
                        "datetime": str(last.get("datetime", ""))[:10],
                    })
            except Exception as exc:
                logger.debug("选股跳过 %s: %s", code, exc)

        return results

    @staticmethod
    def list_presets() -> Dict[str, Dict]:
        return PRESET_SCREENS
