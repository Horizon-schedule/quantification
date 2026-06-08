"""
K 线数据聚合：东方财富主源 + 腾讯备用源。
"""

from __future__ import annotations

import os
from typing import List, Optional

from quant_platform.api.eastmoney import EastMoneyAPI
from quant_platform.api.models import AdjustType, KlineBar, KlinePeriod, SecurityInfo
from quant_platform.api.tencent_kline import TencentKlineAPI
from quant_platform.utils.logger import get_logger

logger = get_logger("api.kline_provider")


def _fallback_enabled() -> bool:
    return os.getenv("ENABLE_TENCENT_FALLBACK", "true").lower() == "true"


class KlineProvider:
    """K 线多数据源提供者。"""

    def __init__(
        self,
        primary: Optional[EastMoneyAPI] = None,
        fallback: Optional[TencentKlineAPI] = None,
    ):
        self.primary = primary or EastMoneyAPI()
        self.fallback = fallback or TencentKlineAPI()

    def get_kline(
        self,
        security: SecurityInfo,
        period: KlinePeriod = KlinePeriod.DAILY,
        adjust: AdjustType = AdjustType.FORWARD,
        limit: int = 500,
    ) -> List[KlineBar]:
        source = "eastmoney"

        try:
            bars = self.primary.get_kline(security, period, adjust, limit=limit)
            if bars:
                return bars
            logger.warning(
                "东方财富 K 线为空 %s period=%s，尝试备用源",
                security.code,
                period.value,
            )
        except Exception as exc:
            logger.warning(
                "东方财富 K 线失败 %s period=%s: %s",
                security.code,
                period.value,
                exc,
            )

        if not _fallback_enabled():
            return []

        # 备用源使用独立请求，不受东方财富熔断影响
        try:
            bars = self.fallback.get_kline(security, period, adjust, limit=limit)
            if bars:
                logger.info(
                    "已使用腾讯备用 K 线 %s period=%s (%d 条)",
                    security.code,
                    period.value,
                    len(bars),
                )
            return bars
        except Exception as exc:
            logger.error(
                "腾讯 K 线备用也失败 %s period=%s: %s",
                security.code,
                period.value,
                exc,
            )
            return []

    def close(self) -> None:
        self.primary.close()
        self.fallback.close()
