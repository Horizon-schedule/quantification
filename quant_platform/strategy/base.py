"""
策略基类模块。
预留自定义策略开发接口，所有内置策略均继承此基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd


class SignalType(str, Enum):
    """交易信号类型。"""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """策略信号。"""

    signal_type: SignalType
    datetime: str
    price: float
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "datetime": self.datetime,
            "price": self.price,
            "reason": self.reason,
        }


class BaseStrategy(ABC):
    """
    量化策略抽象基类。

    自定义策略步骤：
    1. 继承 BaseStrategy
    2. 实现 generate_signals() 方法
    3. 可选重写 on_bar() 进行逐 bar 处理
    """

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成策略信号。

        参数:
            df: 含 OHLCV 及指标的 DataFrame

        返回:
            原 DataFrame 附加 signal 列（buy/sell/hold）和 signal_reason 列
        """

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数。"""
        return self.params.copy()

    def set_params(self, **kwargs: Any) -> None:
        """更新策略参数。"""
        self.params.update(kwargs)

    @staticmethod
    def _format_datetime(dt: Any) -> str:
        """统一 datetime 格式为字符串。"""
        if hasattr(dt, "strftime"):
            return dt.strftime("%Y-%m-%d")
        return str(dt)
