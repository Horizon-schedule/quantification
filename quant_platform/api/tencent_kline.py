"""
腾讯财经 K 线备用数据源（免费公开接口）。
当东方财富 push2his 在 ECS 等环境不可用时自动降级使用。
"""

from __future__ import annotations

import json
from typing import List, Optional

import requests

from config.settings import get_settings
from quant_platform.api.eastmoney import _safe_float
from quant_platform.api.models import AdjustType, KlineBar, KlinePeriod, SecurityInfo
from quant_platform.utils.logger import get_logger

logger = get_logger("api.tencent_kline")

TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 东方财富周期 -> 腾讯 param 周期名
PERIOD_MAP = {
    KlinePeriod.DAILY: "day",
    KlinePeriod.WEEKLY: "week",
    KlinePeriod.MONTHLY: "month",
    KlinePeriod.MIN1: "m1",
    KlinePeriod.MIN5: "m5",
    KlinePeriod.MIN15: "m15",
    KlinePeriod.MIN30: "m30",
    KlinePeriod.MIN60: "m60",
}

# 腾讯仅日/周/月稳定支持；分钟线仍优先东方财富
TENCENT_SUPPORTED = {
    KlinePeriod.DAILY,
    KlinePeriod.WEEKLY,
    KlinePeriod.MONTHLY,
}

ADJUST_SUFFIX = {
    AdjustType.FORWARD: "qfq",
    AdjustType.BACKWARD: "hfq",
    AdjustType.NONE: "",
}


class TencentKlineAPI:
    """腾讯财经 K 线 API。"""

    def __init__(self):
        cfg = get_settings().api
        self._session = requests.Session()
        self._session.trust_env = False
        self._session.headers.update(
            {
                "User-Agent": cfg.user_agent,
                "Referer": "https://finance.qq.com/",
            }
        )

    @staticmethod
    def _symbol(security: SecurityInfo) -> str:
        prefix = "sh" if security.market.upper() == "SH" else "sz"
        return f"{prefix}{security.code}"

    @staticmethod
    def _parse_jsonp(text: str) -> dict:
        text = text.strip()
        if not text:
            return {}
        if text[0] in "{[":
            return json.loads(text)
        if "=" in text:
            text = text.split("=", 1)[1].strip().rstrip(";")
        return json.loads(text)

    def get_kline(
        self,
        security: SecurityInfo,
        period: KlinePeriod = KlinePeriod.DAILY,
        adjust: AdjustType = AdjustType.FORWARD,
        limit: int = 500,
    ) -> List[KlineBar]:
        if period not in TENCENT_SUPPORTED:
            logger.debug("腾讯不支持该周期 %s，跳过", period.value)
            return []

        period_key = PERIOD_MAP[period]
        adj = ADJUST_SUFFIX.get(adjust, "qfq")
        symbol = self._symbol(security)
        param = f"{symbol},{period_key},,,{limit},{adj}" if adj else f"{symbol},{period_key},,,{limit}"

        try:
            resp = self._session.get(
                TENCENT_KLINE_URL,
                params={"param": param, "_var": "kline_tencent"},
                timeout=get_settings().api.timeout,
            )
            resp.raise_for_status()
            payload = self._parse_jsonp(resp.text)
        except Exception as exc:
            logger.warning("腾讯 K 线请求失败 %s: %s", security.code, exc)
            return []

        stock_data = (payload.get("data") or {}).get(symbol) or {}
        field_key = f"{adj}{period_key}" if adj else period_key
        rows = stock_data.get(field_key) or stock_data.get(period_key) or []

        bars: List[KlineBar] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                continue
            bars.append(
                KlineBar(
                    datetime=str(row[0]),
                    open=_safe_float(row[1]),
                    close=_safe_float(row[2]),
                    high=_safe_float(row[3]),
                    low=_safe_float(row[4]),
                    volume=_safe_float(row[5]),
                    amount=0.0,
                    change_pct=0.0,
                    turnover_rate=0.0,
                )
            )

        logger.info(
            "腾讯 K 线 %s period=%s 获取 %d 条",
            security.code,
            period.value,
            len(bars),
        )
        return bars

    def close(self) -> None:
        self._session.close()
