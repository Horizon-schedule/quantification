"""基本面数据服务。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from quant_platform.api.fundamental import EastMoneyFundamentalAPI
from quant_platform.api.extended_data import EastMoneyExtendedAPI
from quant_platform.utils.logger import get_logger

logger = get_logger("data.fundamental_service")


class FundamentalService:
    """基本面数据查询服务。"""

    def __init__(
        self,
        api: Optional[EastMoneyFundamentalAPI] = None,
        extended: Optional[EastMoneyExtendedAPI] = None,
    ):
        self.api = api or EastMoneyFundamentalAPI()
        self.extended = extended or EastMoneyExtendedAPI()

    def get_full(self, code: str, name: str = "") -> Dict[str, Any]:
        """获取完整基本面数据（含图表数据 + 扩展免费数据）。"""
        data = self.api.get_fundamental(code, name=name)
        result = data.to_dict()
        result["revenue_chart"] = self.api.get_revenue_chart_data(data.financial_reports)
        result["extended"] = self.extended.get_extended_bundle(code)
        return result

    def get_extended_only(self, code: str) -> Dict[str, Any]:
        """仅获取扩展数据模块。"""
        return self.extended.get_extended_bundle(code)

    def close(self) -> None:
        self.api.close()
        self.extended.close()
