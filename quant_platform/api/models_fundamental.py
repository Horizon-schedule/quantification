"""
基本面与财务数据模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CompanyProfile:
    """公司基本概况。"""

    code: str
    name: str = ""
    industry: str = ""
    main_business: str = ""
    business_scope: str = ""
    listing_date: str = ""
    total_shares: str = ""
    company_intro: str = ""
    region: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "industry": self.industry,
            "main_business": self.main_business,
            "business_scope": self.business_scope,
            "listing_date": self.listing_date,
            "total_shares": self.total_shares,
            "company_intro": self.company_intro,
            "region": self.region,
        }


@dataclass
class FinancialReport:
    """单期财务报告摘要。"""

    report_date: str
    report_type: str
    total_revenue: Optional[float] = None
    revenue_yoy: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_yoy: Optional[float] = None
    deduct_net_profit: Optional[float] = None
    eps: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    total_assets: Optional[float] = None
    net_operate_cashflow: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_date": self.report_date,
            "report_type": self.report_type,
            "total_revenue": self._fmt_money(self.total_revenue),
            "total_revenue_raw": self.total_revenue,
            "revenue_yoy": self._fmt_pct(self.revenue_yoy),
            "revenue_yoy_raw": self.revenue_yoy,
            "net_profit": self._fmt_money(self.net_profit),
            "net_profit_raw": self.net_profit,
            "net_profit_yoy": self._fmt_pct(self.net_profit_yoy),
            "net_profit_yoy_raw": self.net_profit_yoy,
            "deduct_net_profit": self._fmt_money(self.deduct_net_profit),
            "eps": self.eps,
            "roe": self._fmt_pct(self.roe),
            "roe_raw": self.roe,
            "gross_margin": self._fmt_pct(self.gross_margin),
            "net_margin": self._fmt_pct(self.net_margin),
            "total_assets": self._fmt_money(self.total_assets),
            "net_operate_cashflow": self._fmt_money(self.net_operate_cashflow),
        }

    @staticmethod
    def _fmt_money(val: Optional[float]) -> Optional[str]:
        if val is None:
            return None
        av = abs(val)
        if av >= 1e8:
            return f"{val / 1e8:.2f}亿"
        if av >= 1e4:
            return f"{val / 1e4:.2f}万"
        return f"{val:.2f}"

    @staticmethod
    def _fmt_pct(val: Optional[float]) -> Optional[str]:
        if val is None:
            return None
        return f"{val:.2f}%"


@dataclass
class BusinessEvent:
    """重大合同/中标等业务事件（来自公告）。"""

    event_type: str
    title: str
    notice_date: str
    amount: Optional[str] = None
    art_code: str = ""
    detail_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "title": self.title,
            "notice_date": self.notice_date[:10] if self.notice_date else "",
            "amount": self.amount,
            "detail_url": self.detail_url,
        }


@dataclass
class FundamentalData:
    """个股基本面数据聚合。"""

    code: str
    name: str = ""
    profile: Optional[CompanyProfile] = None
    latest_summary: Dict[str, Any] = field(default_factory=dict)
    financial_reports: List[FinancialReport] = field(default_factory=list)
    contracts: List[BusinessEvent] = field(default_factory=list)
    bid_wins: List[BusinessEvent] = field(default_factory=list)
    announcements: List[BusinessEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "profile": self.profile.to_dict() if self.profile else {},
            "latest_summary": self.latest_summary,
            "financial_reports": [r.to_dict() for r in self.financial_reports],
            "contracts": [e.to_dict() for e in self.contracts],
            "bid_wins": [e.to_dict() for e in self.bid_wins],
            "announcements": [e.to_dict() for e in self.announcements[:10]],
        }
