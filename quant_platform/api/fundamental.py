"""
东方财富基本面与财务数据 API。
数据来源：datacenter-web（财务指标）、F10（公司概况）、公告 API（合同/中标）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from quant_platform.api.client import HttpClient
from quant_platform.api.models import SecurityInfo
from quant_platform.api.models_fundamental import (
    BusinessEvent,
    CompanyProfile,
    FinancialReport,
    FundamentalData,
)
from quant_platform.utils.logger import get_logger

logger = get_logger("api.fundamental")

BASE_DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"
BASE_F10 = "https://emweb.securities.eastmoney.com/PC_HSF10"
BASE_ANNOUNCE = "https://np-anotice-stock.eastmoney.com/api/security/ann"

# 公告关键词分类
CONTRACT_KEYWORDS = ["重大合同", "签订合同", "签约", "订单", "框架协议", "采购合同", "销售合同"]
BID_KEYWORDS = ["中标", "中标公告", "中标结果", "工程项目中标", "重大项目中标"]

# 金额提取正则
AMOUNT_PATTERNS = [
    re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*亿(?:元|人民币|元)?"),
    re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*万(?:元|人民币|元)?"),
    re.compile(r"金额(?:为|约|达)?([0-9,]+(?:\.[0-9]+)?)\s*(?:亿|万)?元"),
    re.compile(r"合同金额(?:为|约|达)?([0-9,]+(?:\.[0-9]+)?)\s*(?:亿|万)?元"),
    re.compile(r"中标金额(?:为|约|达)?([0-9,]+(?:\.[0-9]+)?)\s*(?:亿|万)?元"),
]


class EastMoneyFundamentalAPI:
    """东方财富基本面数据封装。"""

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    @staticmethod
    def _market_code(security: SecurityInfo) -> str:
        return f"{security.market}{security.code}"

    @staticmethod
    def _safe_float(val: Any) -> Optional[float]:
        if val is None or val == "" or val == "-":
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_amount_from_title(title: str) -> Optional[str]:
        """从公告标题中尝试提取金额。"""
        for pat in AMOUNT_PATTERNS:
            m = pat.search(title)
            if m:
                return m.group(0)
        return None

    def _datacenter_query(
        self,
        report_name: str,
        code: str,
        page_size: int = 20,
        sort_col: str = "REPORT_DATE",
    ) -> List[Dict[str, Any]]:
        params = {
            "reportName": report_name,
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": 1,
            "pageSize": page_size,
            "sortColumns": sort_col,
            "sortTypes": "-1",
        }
        data = self.client.get(BASE_DATACENTER, params=params)
        result = data.get("result") or {}
        return result.get("data") or []

    def get_financial_reports(
        self, code: str, limit: int = 12
    ) -> List[FinancialReport]:
        """获取历史财务报告（季度+年度）。"""
        rows = self._datacenter_query(
            "RPT_F10_FINANCE_MAINFINADATA", code, page_size=limit
        )
        reports: List[FinancialReport] = []
        for row in rows:
            reports.append(
                FinancialReport(
                    report_date=str(row.get("REPORT_DATE", ""))[:10],
                    report_type=str(row.get("REPORT_DATE_NAME") or row.get("REPORT_TYPE") or ""),
                    total_revenue=self._safe_float(row.get("TOTALOPERATEREVE")),
                    revenue_yoy=self._safe_float(row.get("TOTALOPERATEREVETZ")),
                    net_profit=self._safe_float(row.get("PARENTNETPROFIT")),
                    net_profit_yoy=self._safe_float(row.get("PARENTNETPROFITTZ")),
                    deduct_net_profit=self._safe_float(row.get("DEDUCTPARENTNETPROFIT")),
                    eps=self._safe_float(row.get("EPSJB")),
                    roe=self._safe_float(row.get("ROEJQ")),
                    gross_margin=self._safe_float(row.get("XSMLL")),
                    net_margin=self._safe_float(row.get("XSJLL")),
                    total_assets=self._safe_float(row.get("TOTAL_ASSETS_PK") or row.get("TOTALASSETS")),
                    net_operate_cashflow=self._safe_float(row.get("NETCASH_OPERATE_PK")),
                )
            )
        return reports

    def get_company_profile(self, security: SecurityInfo) -> CompanyProfile:
        """获取公司基本概况。"""
        mc = self._market_code(security)
        url = f"{BASE_F10}/CompanySurvey/PageAjax"
        data = self.client.get(url, params={"code": mc})

        profile = CompanyProfile(code=security.code, name=security.name)
        jbzl_list = data.get("jbzl") or []
        if jbzl_list:
            jb = jbzl_list[0]
            profile.name = str(jb.get("SECURITY_NAME_ABBR") or profile.name)
            profile.industry = str(jb.get("EM2016") or jb.get("INDUSTRY") or "")
            profile.main_business = str(jb.get("MAIN_BUSINESS") or jb.get("MAINFORM") or "")
            profile.business_scope = str(jb.get("BUSINESS_SCOPE") or "")
            profile.listing_date = str(jb.get("LISTING_DATE") or jb.get("FOUND_DATE") or "")[:10]
            profile.total_shares = str(jb.get("TOTAL_SHARES") or jb.get("TOTALSHARE") or "")
            profile.company_intro = str(jb.get("ORG_PROFILE") or jb.get("COMPANY_PROFILE") or "")[:500]
            profile.region = str(jb.get("PROVINCE") or jb.get("REG_ADDRESS") or "")[:50]

        # 补充主营业务描述
        try:
            biz_url = f"{BASE_F10}/BusinessAnalysis/PageAjax"
            biz = self.client.get(biz_url, params={"code": mc})
            zyfw = biz.get("zyfw") or []
            if zyfw and not profile.main_business:
                profile.main_business = str(zyfw[0].get("BUSINESS_SCOPE") or "")[:300]
        except Exception as exc:
            logger.debug("主营业务补充失败: %s", exc)

        return profile

    def get_announcements(
        self, code: str, page_size: int = 80
    ) -> List[Dict[str, Any]]:
        """获取个股公告列表。"""
        params = {
            "sr": -1,
            "page_size": page_size,
            "page_index": 1,
            "ann_type": "A",
            "client_source": "web",
            "stock_list": code,
            "f_node": "0",
            "s_node": "0",
        }
        data = self.client.get(BASE_ANNOUNCE, params=params)
        return (data.get("data") or {}).get("list") or []

    def _classify_announcements(
        self, announcements: List[Dict[str, Any]]
    ) -> tuple[List[BusinessEvent], List[BusinessEvent], List[BusinessEvent]]:
        """将公告分类为合同、中标、其他。"""
        contracts: List[BusinessEvent] = []
        bid_wins: List[BusinessEvent] = []
        others: List[BusinessEvent] = []

        for ann in announcements:
            title = str(ann.get("title") or ann.get("title_ch") or "")
            notice_date = str(ann.get("notice_date") or ann.get("display_time") or "")
            art_code = str(ann.get("art_code") or "")
            detail_url = (
                f"https://data.eastmoney.com/notices/detail/{art_code}/{art_code}.html"
                if art_code else ""
            )
            amount = self._parse_amount_from_title(title)

            if any(kw in title for kw in BID_KEYWORDS):
                bid_wins.append(BusinessEvent(
                    event_type="中标", title=title, notice_date=notice_date,
                    amount=amount, art_code=art_code, detail_url=detail_url,
                ))
            elif any(kw in title for kw in CONTRACT_KEYWORDS):
                contracts.append(BusinessEvent(
                    event_type="重大合同", title=title, notice_date=notice_date,
                    amount=amount, art_code=art_code, detail_url=detail_url,
                ))
            else:
                others.append(BusinessEvent(
                    event_type="公告", title=title, notice_date=notice_date,
                    amount=amount, art_code=art_code, detail_url=detail_url,
                ))

        return contracts, bid_wins, others

    def get_fundamental(self, code: str, name: str = "") -> FundamentalData:
        """
        获取个股完整基本面数据。

        包含：公司概况、财务报告（季度/年度营收利润）、重大合同、中标公告。
        """
        security = SecurityInfo.from_code(code, name)

        profile = self.get_company_profile(security)
        reports = self.get_financial_reports(code, limit=16)
        announcements = self.get_announcements(code)
        contracts, bid_wins, others = self._classify_announcements(announcements)

        latest_summary: Dict[str, Any] = {}
        if reports:
            latest = reports[0]
            latest_summary = {
                "report_date": latest.report_date,
                "report_type": latest.report_type,
                "total_revenue": latest.to_dict()["total_revenue"],
                "revenue_yoy": latest.to_dict()["revenue_yoy"],
                "net_profit": latest.to_dict()["net_profit"],
                "net_profit_yoy": latest.to_dict()["net_profit_yoy"],
                "eps": latest.eps,
                "roe": latest.to_dict()["roe"],
                "gross_margin": latest.to_dict()["gross_margin"],
                "total_assets": latest.to_dict()["total_assets"],
            }

        return FundamentalData(
            code=code,
            name=profile.name or name,
            profile=profile,
            latest_summary=latest_summary,
            financial_reports=reports,
            contracts=contracts[:20],
            bid_wins=bid_wins[:20],
            announcements=others[:10],
        )

    def get_revenue_chart_data(
        self, reports: List[FinancialReport]
    ) -> Dict[str, Any]:
        """生成营收/利润趋势图数据（按报告期）。"""
        # 按时间升序
        sorted_reports = sorted(reports, key=lambda r: r.report_date)
        return {
            "dates": [r.report_type or r.report_date for r in sorted_reports],
            "revenue": [round(r.total_revenue / 1e8, 2) if r.total_revenue else None for r in sorted_reports],
            "net_profit": [round(r.net_profit / 1e8, 2) if r.net_profit else None for r in sorted_reports],
            "revenue_yoy": [r.revenue_yoy for r in sorted_reports],
        }

    def close(self) -> None:
        self.client.close()
