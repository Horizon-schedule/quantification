"""
基础因子引擎。
对标 Qlib Alpha158 / 米筐因子库（轻量版）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from quant_platform.indicators.technical import TechnicalIndicators


class FactorEngine:
    """量价因子计算与简单检验。"""

    @staticmethod
    def calc_momentum(df: pd.DataFrame, periods: tuple = (5, 10, 20, 60)) -> pd.DataFrame:
        """动量因子：N 日收益率。"""
        result = df.copy()
        for p in periods:
            result[f"mom_{p}d"] = result["close"].pct_change(p) * 100
        return result

    @staticmethod
    def calc_volatility(df: pd.DataFrame, periods: tuple = (5, 20, 60)) -> pd.DataFrame:
        """波动率因子：N 日收益率标准差。"""
        result = df.copy()
        ret = result["close"].pct_change()
        for p in periods:
            result[f"vol_{p}d"] = ret.rolling(p, min_periods=1).std() * np.sqrt(252) * 100
        return result

    @staticmethod
    def calc_turnover_factor(df: pd.DataFrame) -> pd.DataFrame:
        """换手率因子。"""
        result = df.copy()
        if "turnover_rate" in result.columns:
            result["turnover_ma5"] = result["turnover_rate"].rolling(5, min_periods=1).mean()
            result["turnover_ma20"] = result["turnover_rate"].rolling(20, min_periods=1).mean()
        return result

    @staticmethod
    def calc_all_factors(df: pd.DataFrame) -> pd.DataFrame:
        """计算全部内置因子。"""
        result = TechnicalIndicators.calc_all(df)
        result = FactorEngine.calc_momentum(result)
        result = FactorEngine.calc_volatility(result)
        result = FactorEngine.calc_turnover_factor(result)
        return result

    @staticmethod
    def factor_ic(
        df: pd.DataFrame,
        factor_col: str,
        forward_days: int = 5,
    ) -> Dict[str, float]:
        """
        因子 IC 检验（信息系数）。
        衡量因子值与未来 N 日收益的相关性。
        """
        if factor_col not in df.columns or df.empty:
            return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0}

        work = df.copy()
        work["forward_ret"] = work["close"].shift(-forward_days) / work["close"] - 1
        work = work.dropna(subset=[factor_col, "forward_ret"])

        if len(work) < 10:
            return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0}

        ic_series = work[factor_col].rolling(20, min_periods=10).corr(work["forward_ret"])
        ic_series = ic_series.dropna()

        if ic_series.empty:
            return {"ic_mean": 0, "ic_std": 0, "ic_ir": 0}

        ic_mean = float(ic_series.mean())
        ic_std = float(ic_series.std())
        ic_ir = ic_mean / ic_std if ic_std > 1e-10 else 0

        return {
            "factor": factor_col,
            "forward_days": forward_days,
            "ic_mean": round(ic_mean, 4),
            "ic_std": round(ic_std, 4),
            "ic_ir": round(ic_ir, 4),
        }

    @staticmethod
    def factor_summary(df: pd.DataFrame) -> List[Dict]:
        """批量因子 IC 检验。"""
        factor_cols = [
            c for c in df.columns
            if c.startswith(("mom_", "vol_", "rsi", "macd_hist", "vol_ratio"))
        ]
        return [FactorEngine.factor_ic(df, col) for col in factor_cols[:8]]
