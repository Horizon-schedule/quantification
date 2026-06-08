"""
东方财富公开免费 API 统一封装。
仅使用官方公开接口，合规获取 A 股、指数、ETF 行情数据。

接口来源说明：
- 实时行情：push2.eastmoney.com
- 历史 K 线：push2his.eastmoney.com
- 股票列表：push2.eastmoney.com
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from quant_platform.api.client import HttpClient
from quant_platform.api.models import (
    AdjustType,
    IntradayPoint,
    KlineBar,
    KlinePeriod,
    QuoteData,
    SecurityInfo,
    SecurityType,
)
from quant_platform.utils.logger import get_logger

logger = get_logger("api.eastmoney")


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换东方财富 K 线字段（空值 / '-' 常见于周K、月K）。"""
    if value is None:
        return default
    text = str(value).strip()
    if not text or text == "-":
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


# 东方财富公开 API 基础地址
BASE_QUOTE_URL = "https://push2.eastmoney.com/api/qt"
BASE_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
BASE_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
BASE_INTRADAY_URL = "https://push2.eastmoney.com/api/qt/stock/trends2/get"


class EastMoneyAPI:
    """
    东方财富行情 API 统一封装类。

    支持：实时行情、历史 K 线、分时数据、股票/指数/ETF 列表。
    """

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    @staticmethod
    def _parse_quote_item(item: Dict[str, Any]) -> QuoteData:
        """解析单条实时行情。"""
        code = str(item.get("f12", ""))
        pre_close = float(item.get("f18", 0) or 0)
        price = float(item.get("f2", 0) or 0)
        change = price - pre_close if pre_close else 0
        change_pct = float(item.get("f3", 0) or 0)

        return QuoteData(
            code=code,
            name=str(item.get("f14", "")),
            price=price,
            open=float(item.get("f17", 0) or 0),
            high=float(item.get("f15", 0) or 0),
            low=float(item.get("f16", 0) or 0),
            pre_close=pre_close,
            change=change,
            change_pct=change_pct,
            volume=float(item.get("f5", 0) or 0),
            amount=float(item.get("f6", 0) or 0),
            turnover_rate=float(item.get("f8", 0) or 0),
            volume_ratio=float(item.get("f10", 0) or 0),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def get_realtime_quote(
        self, securities: List[SecurityInfo]
    ) -> List[QuoteData]:
        """
        批量获取实时行情。

        参数:
            securities: 证券信息列表

        返回:
            实时行情列表
        """
        if not securities:
            return []

        secids = ",".join(s.secid for s in securities)
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": "f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18",
            "secids": secids,
        }
        url = f"{BASE_QUOTE_URL}/ulist.np/get"
        data = self.client.get(url, params=params)

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            logger.warning("实时行情返回为空: %s", secids)
            return []

        return [self._parse_quote_item(item) for item in diff]

    def get_kline(
        self,
        security: SecurityInfo,
        period: KlinePeriod = KlinePeriod.DAILY,
        adjust: AdjustType = AdjustType.FORWARD,
        limit: int = 500,
    ) -> List[KlineBar]:
        """
        获取历史 K 线数据。

        参数:
            security: 证券信息
            period: K 线周期（日/周/月/分钟）
            adjust: 复权类型（不复权/前复权/后复权）
            limit: 最大返回条数

        返回:
            K 线列表（时间升序）
        """
        params = {
            "secid": security.secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": period.value,
            "fqt": adjust.value,
            "end": "20500101",
            "lmt": str(limit),
        }
        data = self.client.get(BASE_KLINE_URL, params=params)

        raw = data.get("data") or {}
        klines_raw = raw.get("klines") or []
        if not klines_raw:
            logger.warning("K 线数据为空: %s period=%s", security.code, period.value)
            return []

        bars: List[KlineBar] = []
        for line in klines_raw:
            parts = line.split(",")
            if len(parts) < 7:
                continue
            try:
                bars.append(
                    KlineBar(
                        datetime=parts[0],
                        open=_safe_float(parts[1]),
                        close=_safe_float(parts[2]),
                        high=_safe_float(parts[3]),
                        low=_safe_float(parts[4]),
                        volume=_safe_float(parts[5]),
                        amount=_safe_float(parts[6]),
                        change_pct=_safe_float(parts[8]) if len(parts) > 8 else 0.0,
                        turnover_rate=_safe_float(parts[10]) if len(parts) > 10 else 0.0,
                    )
                )
            except (IndexError, TypeError) as exc:
                logger.debug("跳过无效 K 线行 %s: %s", security.code, exc)
        return bars

    def get_intraday(self, security: SecurityInfo) -> List[IntradayPoint]:
        """
        获取当日分时数据。

        参数:
            security: 证券信息

        返回:
            分时数据点列表
        """
        params = {
            "secid": security.secid,
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "iscr": "0",
            "ndays": "1",
        }
        data = self.client.get(BASE_INTRADAY_URL, params=params)

        trends = data.get("data", {}).get("trends", [])
        points: List[IntradayPoint] = []
        for trend in trends:
            parts = trend.split(",")
            if len(parts) < 3:
                continue
            points.append(
                IntradayPoint(
                    time=parts[0],
                    price=float(parts[1]),
                    volume=float(parts[2]) if len(parts) > 2 else 0,
                    avg_price=float(parts[3]) if len(parts) > 3 else 0,
                )
            )
        return points

    def get_stock_list(
        self,
        page: int = 1,
        page_size: int = 100,
        market: str = "all",
    ) -> List[SecurityInfo]:
        """
        获取 A 股股票列表。

        参数:
            page: 页码
            page_size: 每页数量
            market: 市场筛选 all/sh/sz

        返回:
            证券信息列表
        """
        # fs 参数：m:0+t:6 深圳A股, m:1+t:2 上海A股
        fs_map = {
            "all": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "sh": "m:1+t:2,m:1+t:23",
            "sz": "m:0+t:6,m:0+t:80",
        }
        params = {
            "pn": str(page),
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": fs_map.get(market, fs_map["all"]),
            "fields": "f12,f14",
        }
        data = self.client.get(BASE_LIST_URL, params=params)

        diff = data.get("data", {}).get("diff", [])
        result: List[SecurityInfo] = []
        for item in diff:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", ""))
            if code:
                result.append(SecurityInfo.from_code(code, name))
        return result

    def get_index_list(self) -> List[SecurityInfo]:
        """获取主要指数列表。"""
        params = {
            "pn": "1",
            "pz": "50",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:1+t:1,m:0+t:1",
            "fields": "f12,f14",
        }
        data = self.client.get(BASE_LIST_URL, params=params)
        diff = data.get("data", {}).get("diff", [])

        result: List[SecurityInfo] = []
        for item in diff:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", ""))
            if code:
                info = SecurityInfo.from_code(code, name)
                info.sec_type = SecurityType.INDEX
                result.append(info)
        return result

    def get_etf_list(self, page: int = 1, page_size: int = 100) -> List[SecurityInfo]:
        """获取场内 ETF 基金列表。"""
        params = {
            "pn": str(page),
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "b:MK0021,b:MK0022,b:MK0023,b:MK0024",
            "fields": "f12,f14",
        }
        data = self.client.get(BASE_LIST_URL, params=params)
        diff = data.get("data", {}).get("diff", [])

        result: List[SecurityInfo] = []
        for item in diff:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", ""))
            if code:
                info = SecurityInfo.from_code(code, name)
                info.sec_type = SecurityType.ETF
                result.append(info)
        return result

    def get_sector_list(self) -> List[SecurityInfo]:
        """获取行业板块列表。"""
        params = {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f12,f14",
        }
        data = self.client.get(BASE_LIST_URL, params=params)
        diff = data.get("data", {}).get("diff", [])

        result: List[SecurityInfo] = []
        for item in diff:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", ""))
            if code:
                info = SecurityInfo(code=code, name=name, market="SH")
                info.sec_type = SecurityType.SECTOR
                result.append(info)
        return result

    def close(self) -> None:
        """关闭 HTTP 客户端。"""
        self.client.close()
