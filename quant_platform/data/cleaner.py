"""
数据清洗模块。
自动清洗空值、异常值、涨跌停无效数据，标准化时间、价格、成交量单位。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from quant_platform.utils.logger import get_logger

logger = get_logger("data.cleaner")


class DataCleaner:
    """行情与 K 线数据清洗器。"""

    @staticmethod
    def clean_kline_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗 K 线 DataFrame。

        处理：
        - 删除空值行
        - 过滤价格为 0 或负数的异常数据
        - 过滤 high < low 的逻辑错误
        - 标准化 datetime 列
        - 按时间升序排列
        """
        if df.empty:
            return df

        df = df.copy()

        # 标准化 datetime
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
            df = df.dropna(subset=["datetime"])

        # 数值列转 float
        numeric_cols = [
            "open", "close", "high", "low", "volume", "amount",
            "change_pct", "turnover_rate",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 删除 OHLC 空值
        ohlc = [c for c in ["open", "close", "high", "low"] if c in df.columns]
        if ohlc:
            df = df.dropna(subset=ohlc)

        # 过滤无效价格
        if "close" in df.columns:
            df = df[df["close"] > 0]

        # 过滤 high < low
        if "high" in df.columns and "low" in df.columns:
            df = df[df["high"] >= df["low"]]

        # 过滤成交量为负
        if "volume" in df.columns:
            df = df[df["volume"] >= 0]

        # 去重
        if "datetime" in df.columns:
            df = df.drop_duplicates(subset=["datetime"], keep="last")
            df = df.sort_values("datetime").reset_index(drop=True)

        return df

    @staticmethod
    def filter_limit_up_down(
        df: pd.DataFrame, threshold: float = 0.095
    ) -> pd.DataFrame:
        """
        标记涨跌停数据（不删除，添加 is_limit 列）。

        A 股普通股票涨跌幅限制约 ±10%（ST 为 ±5%）。
        """
        if df.empty or "change_pct" not in df.columns:
            return df

        df = df.copy()
        df["is_limit"] = df["change_pct"].abs() >= threshold * 100
        return df

    @staticmethod
    def clean_quote(quote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """清洗单条实时行情，无效则返回 None。"""
        price = quote.get("price", 0)
        if not price or float(price) <= 0:
            logger.debug("无效行情数据，已过滤: %s", quote.get("code"))
            return None

        cleaned = quote.copy()
        for key in ["price", "open", "high", "low", "pre_close",
                     "change", "change_pct", "volume", "amount"]:
            if key in cleaned and cleaned[key] is not None:
                try:
                    cleaned[key] = float(cleaned[key])
                except (ValueError, TypeError):
                    cleaned[key] = 0.0
        return cleaned

    @staticmethod
    def kline_bars_to_df(bars: List[Any]) -> pd.DataFrame:
        """将 KlineBar 列表转为 DataFrame。"""
        if not bars:
            return pd.DataFrame()

        records = []
        for bar in bars:
            if hasattr(bar, "to_dict"):
                records.append(bar.to_dict())
            elif isinstance(bar, dict):
                records.append(bar)

        df = pd.DataFrame(records)
        return DataCleaner.clean_kline_df(df)

    @staticmethod
    def fill_missing_ohlc(df: pd.DataFrame) -> pd.DataFrame:
        """使用前收盘价填充缺失 OHLC（前向填充）。"""
        if df.empty:
            return df
        df = df.copy()
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col].ffill()
        return df

    @staticmethod
    def normalize_volume(df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化成交量单位。
        东方财富返回的 volume 通常为手（100股），统一转为股。
        """
        if df.empty or "volume" not in df.columns:
            return df
        df = df.copy()
        # 若成交量均值较小，可能已是手，乘以 100
        if df["volume"].median() < 1e6:
            df["volume"] = df["volume"] * 100
        return df
