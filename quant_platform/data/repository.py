"""
数据仓库模块。
本地缓存优先，接口补全，支持增量更新。
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from quant_platform.api.eastmoney import EastMoneyAPI
from quant_platform.api.models import AdjustType, KlinePeriod, SecurityInfo
from quant_platform.data.cleaner import DataCleaner
from quant_platform.data.database import DatabaseManager
from quant_platform.utils.logger import get_logger

logger = get_logger("data.repository")


class DataRepository:
    """
    统一数据仓库。

    策略：优先读取本地 SQLite，缺失部分从东方财富 API 增量补全。
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        api: Optional[EastMoneyAPI] = None,
    ):
        self.db = db or DatabaseManager()
        self.api = api or EastMoneyAPI()
        self.cleaner = DataCleaner()

    def get_kline_df(
        self,
        code: str,
        period: KlinePeriod = KlinePeriod.DAILY,
        adjust: AdjustType = AdjustType.FORWARD,
        limit: int = 500,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        获取 K 线 DataFrame（本地优先 + 增量更新）。

        参数:
            code: 证券代码
            period: K 线周期
            adjust: 复权类型
            limit: 最大条数
            force_refresh: 是否强制从 API 刷新

        返回:
            清洗后的 K 线 DataFrame
        """
        security = SecurityInfo.from_code(code)
        period_val = period.value
        adjust_val = adjust.value

        local_rows = [] if force_refresh else self.db.get_klines(
            code, period_val, adjust_val, limit=limit
        )

        need_fetch = force_refresh or len(local_rows) < min(limit, 50)

        if need_fetch:
            logger.info("从 API 获取 K 线: %s period=%s", code, period_val)
            try:
                bars = self.api.get_kline(security, period, adjust, limit=limit)
                if bars:
                    rows = [b.to_dict() for b in bars]
                    self.db.upsert_klines(code, period_val, adjust_val, rows)
                    local_rows = self.db.get_klines(
                        code, period_val, adjust_val, limit=limit
                    )
            except Exception as exc:
                logger.error("API 获取 K 线失败 %s period=%s: %s", code, period_val, exc)

        if not local_rows:
            logger.warning("无 K 线数据: %s", code)
            return pd.DataFrame()

        df = pd.DataFrame(local_rows)
        df = self.cleaner.clean_kline_df(df)
        return df

    def get_realtime_quotes(self, codes: List[str]) -> pd.DataFrame:
        """批量获取实时行情并缓存。"""
        securities = [SecurityInfo.from_code(c) for c in codes]
        try:
            quotes = self.api.get_realtime_quote(securities)
        except Exception as exc:
            logger.error("API 获取行情失败 %s: %s", codes, exc)
            return pd.DataFrame()

        records = []
        for q in quotes:
            cleaned = self.cleaner.clean_quote(q.to_dict())
            if cleaned:
                self.db.save_quote(cleaned)
                records.append(cleaned)

        return pd.DataFrame(records) if records else pd.DataFrame()

    def get_intraday_df(self, code: str) -> pd.DataFrame:
        """获取当日分时数据。"""
        security = SecurityInfo.from_code(code)
        points = self.api.get_intraday(security)
        if not points:
            return pd.DataFrame()

        records = [
            {"time": p.time, "price": p.price, "volume": p.volume, "avg_price": p.avg_price}
            for p in points
        ]
        return pd.DataFrame(records)

    def search_stock(self, keyword: str, limit: int = 20) -> List[dict]:
        """简单关键词搜索股票（本地+API）。"""
        stocks = self.api.get_stock_list(page=1, page_size=100)
        keyword = keyword.strip().lower()
        results = []
        for s in stocks:
            if (
                keyword in s.code.lower()
                or keyword in s.name.lower()
            ):
                results.append({"code": s.code, "name": s.name, "market": s.market})
            if len(results) >= limit:
                break
        return results

    def get_index_list(self) -> List[dict]:
        """获取主要指数列表。"""
        indices = self.api.get_index_list()
        return [{"code": s.code, "name": s.name, "market": s.market} for s in indices]

    def get_etf_list(self, limit: int = 50) -> List[dict]:
        """获取 ETF 列表。"""
        etfs = self.api.get_etf_list(page=1, page_size=limit)
        return [{"code": s.code, "name": s.name, "market": s.market} for s in etfs]

    def get_default_stock_pool(self, size: int = 30) -> List[str]:
        """获取默认选股池（活跃股票）。"""
        stocks = self.api.get_stock_list(page=1, page_size=size)
        return [s.code for s in stocks]

    def close(self) -> None:
        """释放资源。"""
        self.api.close()
