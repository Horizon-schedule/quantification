"""
统一数据模型。
标准化东方财富 API 入参、出参结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AdjustType(str, Enum):
    """K 线复权类型。"""

    NONE = "0"       # 不复权
    FORWARD = "1"    # 前复权
    BACKWARD = "2"   # 后复权


class KlinePeriod(str, Enum):
    """K 线周期。"""

    MIN1 = "1"
    MIN5 = "5"
    MIN15 = "15"
    MIN30 = "30"
    MIN60 = "60"
    DAILY = "101"
    WEEKLY = "102"
    MONTHLY = "103"


class SecurityType(str, Enum):
    """标的类型。"""

    STOCK = "stock"
    INDEX = "index"
    ETF = "etf"
    SECTOR = "sector"


@dataclass
class SecurityInfo:
    """证券基本信息。"""

    code: str
    name: str
    market: str  # SH / SZ
    sec_type: SecurityType = SecurityType.STOCK

    @property
    def secid(self) -> str:
        """东方财富 secid 格式：市场.代码"""
        market_map = {"SH": "1", "SZ": "0", "BJ": "0"}
        prefix = market_map.get(self.market.upper(), "0")
        return f"{prefix}.{self.code}"

    @classmethod
    def from_code(cls, code: str, name: str = "") -> "SecurityInfo":
        """根据代码自动推断市场。"""
        code = code.strip()
        if code.startswith(("5", "6", "9")):
            market = "SH"
        elif code.startswith(("0", "1", "2", "3")):
            market = "SZ"
        else:
            market = "SZ"
        return cls(code=code, name=name, market=market)


@dataclass
class QuoteData:
    """实时行情快照。"""

    code: str
    name: str
    price: float
    open: float
    high: float
    low: float
    pre_close: float
    change: float
    change_pct: float
    volume: float
    amount: float
    turnover_rate: float = 0.0
    volume_ratio: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "price": self.price,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "pre_close": self.pre_close,
            "change": self.change,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "amount": self.amount,
            "turnover_rate": self.turnover_rate,
            "volume_ratio": self.volume_ratio,
            "timestamp": self.timestamp,
        }


@dataclass
class KlineBar:
    """单根 K 线。"""

    datetime: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    change_pct: float = 0.0
    turnover_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "datetime": self.datetime,
            "open": self.open,
            "close": self.close,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "amount": self.amount,
            "change_pct": self.change_pct,
            "turnover_rate": self.turnover_rate,
        }


@dataclass
class IntradayPoint:
    """分时数据点。"""

    time: str
    price: float
    volume: float
    avg_price: float = 0.0
