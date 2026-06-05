"""
技术指标计算模块。
内置 MA、MACD、KDJ、BOLL、RSI、成交量、量比、换手率等主流指标。
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


class TechnicalIndicators:
    """
    技术指标计算器。
    所有方法均为静态方法，输入输出均为 pandas DataFrame/Series。
    """

    @staticmethod
    def ma(df: pd.DataFrame, periods: Tuple[int, ...] = (5, 10, 20, 60)) -> pd.DataFrame:
        """
        计算移动平均线 MA。

        参数:
            df: 含 close 列的 DataFrame
            periods: 均线周期元组
        """
        result = df.copy()
        for p in periods:
            result[f"ma{p}"] = result["close"].rolling(window=p, min_periods=1).mean()
        return result

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """指数移动平均线 EMA。"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def macd(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.DataFrame:
        """
        计算 MACD 指标。

        返回列: macd_dif, macd_dea, macd_hist
        """
        result = df.copy()
        ema_fast = TechnicalIndicators.ema(result["close"], fast)
        ema_slow = TechnicalIndicators.ema(result["close"], slow)
        result["macd_dif"] = ema_fast - ema_slow
        result["macd_dea"] = TechnicalIndicators.ema(result["macd_dif"], signal)
        result["macd_hist"] = 2 * (result["macd_dif"] - result["macd_dea"])
        return result

    @staticmethod
    def kdj(
        df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3
    ) -> pd.DataFrame:
        """
        计算 KDJ 指标。

        返回列: kdj_k, kdj_d, kdj_j
        """
        result = df.copy()
        low_min = result["low"].rolling(window=n, min_periods=1).min()
        high_max = result["high"].rolling(window=n, min_periods=1).max()

        rsv = (result["close"] - low_min) / (high_max - low_min + 1e-10) * 100
        result["kdj_k"] = rsv.ewm(com=m1 - 1, adjust=False).mean()
        result["kdj_d"] = result["kdj_k"].ewm(com=m2 - 1, adjust=False).mean()
        result["kdj_j"] = 3 * result["kdj_k"] - 2 * result["kdj_d"]
        return result

    @staticmethod
    def boll(
        df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """
        计算布林带 BOLL。

        返回列: boll_mid, boll_upper, boll_lower
        """
        result = df.copy()
        result["boll_mid"] = result["close"].rolling(window=period, min_periods=1).mean()
        std = result["close"].rolling(window=period, min_periods=1).std()
        result["boll_upper"] = result["boll_mid"] + std_dev * std
        result["boll_lower"] = result["boll_mid"] - std_dev * std
        return result

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算 RSI 相对强弱指标。

        返回列: rsi
        """
        result = df.copy()
        delta = result["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        result["rsi"] = 100 - (100 / (1 + rs))
        return result

    @staticmethod
    def volume_indicators(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
        """
        计算成交量相关指标。

        返回列: vol_ma（成交量均线）, vol_ratio（量比）
        """
        result = df.copy()
        if "volume" not in result.columns:
            return result

        result["vol_ma"] = result["volume"].rolling(window=period, min_periods=1).mean()
        result["vol_ratio"] = result["volume"] / (result["vol_ma"] + 1e-10)

        if "turnover_rate" not in result.columns:
            result["turnover_rate"] = 0.0

        return result

    @staticmethod
    def calc_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        一次性计算所有内置指标。

        参数:
            df: 含 open/high/low/close/volume 的 K 线 DataFrame

        返回:
            附加所有指标列的 DataFrame
        """
        if df.empty:
            return df

        result = TechnicalIndicators.ma(df)
        result = TechnicalIndicators.macd(result)
        result = TechnicalIndicators.kdj(result)
        result = TechnicalIndicators.boll(result)
        result = TechnicalIndicators.rsi(result)
        result = TechnicalIndicators.volume_indicators(result)
        result = TechnicalIndicators.atr(result)
        result = TechnicalIndicators.obv(result)
        result = TechnicalIndicators.cci(result)
        result = TechnicalIndicators.williams_r(result)
        return result

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """平均真实波幅 ATR。"""
        result = df.copy()
        high, low, close = result["high"], result["low"], result["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        result["atr"] = tr.rolling(window=period, min_periods=1).mean()
        return result

    @staticmethod
    def obv(df: pd.DataFrame) -> pd.DataFrame:
        """能量潮 OBV。"""
        result = df.copy()
        if "volume" not in result.columns:
            return result
        direction = np.sign(result["close"].diff()).fillna(0)
        result["obv"] = (direction * result["volume"]).cumsum()
        return result

    @staticmethod
    def cci(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """商品通道指数 CCI。"""
        result = df.copy()
        tp = (result["high"] + result["low"] + result["close"]) / 3
        ma = tp.rolling(window=period, min_periods=1).mean()
        md = tp.rolling(window=period, min_periods=1).apply(
            lambda x: np.abs(x - x.mean()).mean(), raw=True
        )
        result["cci"] = (tp - ma) / (0.015 * md + 1e-10)
        return result

    @staticmethod
    def williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """威廉指标 WR。"""
        result = df.copy()
        high_max = result["high"].rolling(window=period, min_periods=1).max()
        low_min = result["low"].rolling(window=period, min_periods=1).min()
        result["wr"] = -100 * (high_max - result["close"]) / (high_max - low_min + 1e-10)
        return result

    @staticmethod
    def detect_golden_cross(
        series_fast: pd.Series, series_slow: pd.Series
    ) -> pd.Series:
        """
        检测金叉：快线从下方穿越慢线。

        返回布尔 Series。
        """
        prev_below = series_fast.shift(1) <= series_slow.shift(1)
        curr_above = series_fast > series_slow
        return prev_below & curr_above

    @staticmethod
    def detect_death_cross(
        series_fast: pd.Series, series_slow: pd.Series
    ) -> pd.Series:
        """检测死叉：快线从上方穿越慢线。"""
        prev_above = series_fast.shift(1) >= series_slow.shift(1)
        curr_below = series_fast < series_slow
        return prev_above & curr_below
