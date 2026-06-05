"""
东方财富扩展数据 API。
免费公开接口：三大报表、盈利预测、北向资金、龙虎榜、股东研究。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.settings import get_settings
from quant_platform.api.client import HttpClient
from quant_platform.api.models import SecurityInfo
from quant_platform.utils.logger import get_logger

logger = get_logger("api.extended_data")

BASE_DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"
BASE_F10 = "https://emweb.securities.eastmoney.com/PC_HSF10"
BASE_REPORT = "https://reportapi.eastmoney.com/report/list"
CNINFO_SEARCH = "http://www.cninfo.com.cn/new/disclosure/search"


class EastMoneyExtendedAPI:
    """扩展免费数据接口封装。"""

    REPORT_MAP = {
        "income": "RPT_DMSK_FN_INCOME",
        "balance": "RPT_DMSK_FN_BALANCE",
        "cashflow": "RPT_DMSK_FN_CASHFLOW",
    }

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()
        self.config = get_settings().data_source

    def _datacenter(
        self,
        report_name: str,
        filter_expr: str,
        page_size: int = 20,
        sort_col: str = "REPORT_DATE",
    ) -> List[Dict[str, Any]]:
        params = {
            "reportName": report_name,
            "columns": "ALL",
            "filter": filter_expr,
            "pageNumber": 1,
            "pageSize": page_size,
            "sortColumns": sort_col,
            "sortTypes": "-1",
            "source": "WEB",
            "client": "WEB",
        }
        data = self.client.get(BASE_DATACENTER, params=params)
        return (data.get("result") or {}).get("data") or []

    @staticmethod
    def _pick(row: Dict[str, Any], *keys: str) -> Any:
        for k in keys:
            if k in row and row[k] not in (None, "", "-"):
                return row[k]
        return None

    @staticmethod
    def _fmt_money(val: Any) -> Optional[str]:
        try:
            v = float(val)
        except (TypeError, ValueError):
            return None
        if abs(v) >= 1e8:
            return f"{v / 1e8:.2f}亿"
        if abs(v) >= 1e4:
            return f"{v / 1e4:.2f}万"
        return f"{v:.2f}"

    def get_financial_statements(self, code: str, limit: int = 8) -> Dict[str, List[Dict]]:
        """三大财务报表摘要。"""
        if not self.config.enable_financial_statements:
            return {}

        result: Dict[str, List[Dict]] = {}
        field_map = {
            "income": [
                ("report_date", "REPORT_DATE"),
                ("total_revenue", "TOTAL_OPERATE_INCOME"),
                ("net_profit", "PARENT_NETPROFIT"),
                ("operate_profit", "OPERATE_PROFIT"),
            ],
            "balance": [
                ("report_date", "REPORT_DATE"),
                ("total_assets", "TOTAL_ASSETS"),
                ("total_liabilities", "TOTAL_LIABILITIES"),
                ("parent_equity", "PARENT_EQUITY"),
            ],
            "cashflow": [
                ("report_date", "REPORT_DATE"),
                ("net_operate_cf", "NETCASH_OPERATE"),
                ("net_invest_cf", "NETCASH_INVEST"),
                ("net_finance_cf", "NETCASH_FINANCE"),
            ],
        }

        for stmt_type, report_name in self.REPORT_MAP.items():
            rows = self._datacenter(
                report_name, f'(SECURITY_CODE="{code}")', page_size=limit
            )
            parsed = []
            for row in rows:
                item: Dict[str, Any] = {"report_type": stmt_type}
                for out_key, src_key in field_map[stmt_type]:
                    val = row.get(src_key)
                    if out_key.endswith("_date"):
                        item[out_key] = str(val)[:10] if val else ""
                    else:
                        item[out_key] = self._fmt_money(val)
                        item[f"{out_key}_raw"] = self._pick(row, src_key)
                parsed.append(item)
            result[stmt_type] = parsed
        return result

    def get_analyst_forecast(self, code: str) -> Dict[str, Any]:
        """机构盈利预测汇总。"""
        if not self.config.enable_analyst_forecast:
            return {}

        summary_rows = self._datacenter(
            "RPT_WEB_RESPREDICT",
            f'(SECURITY_CODE="{code}")',
            page_size=1,
            sort_col="RATING_ORG_NUM",
        )
        summary = summary_rows[0] if summary_rows else {}

        reports: List[Dict[str, Any]] = []
        try:
            resp = self.client.get(
                BASE_REPORT,
                params={
                    "code": code,
                    "pageNo": 1,
                    "pageSize": 10,
                    "beginTime": "2024-01-01",
                    "endTime": "2027-12-31",
                    "qType": 0,
                },
            )
            for item in (resp.get("data") or [])[:10]:
                reports.append({
                    "title": item.get("title", ""),
                    "org": item.get("orgSName", item.get("orgName", "")),
                    "rating": item.get("emRatingName", item.get("rating", "")),
                    "publish_date": str(item.get("publishDate", ""))[:10],
                    "target_price": item.get("indvAimPriceT", item.get("aimPrice", "")),
                    "report_url": item.get("infoCode", ""),
                })
        except Exception as exc:
            logger.debug("研报列表获取失败: %s", exc)

        return {
            "rating_org_num": summary.get("RATING_ORG_NUM"),
            "rating_buy": summary.get("RATING_BUY_NUM"),
            "rating_add": summary.get("RATING_ADD_NUM"),
            "rating_neutral": summary.get("RATING_NEUTRAL_NUM"),
            "rating_reduce": summary.get("RATING_REDUCE_NUM"),
            "rating_sell": summary.get("RATING_SELL_NUM"),
            "predict_eps": {
                "year1": summary.get("PREDICT_YEAR1"),
                "eps1": summary.get("EPS1"),
                "year2": summary.get("PREDICT_YEAR2"),
                "eps2": summary.get("EPS2"),
                "year3": summary.get("PREDICT_YEAR3"),
                "eps3": summary.get("EPS3"),
            },
            "reports": reports,
        }

    def get_northbound_flow(self, days: int = 30) -> List[Dict[str, Any]]:
        """北向资金历史流向（沪股通 001）。"""
        if not self.config.enable_northbound:
            return []

        rows = self._datacenter(
            "RPT_MUTUAL_DEAL_HISTORY",
            '(MUTUAL_TYPE="001")',
            page_size=days,
            sort_col="TRADE_DATE",
        )
        return [
            {
                "date": str(r.get("TRADE_DATE", ""))[:10],
                "net_buy": self._fmt_money(r.get("NET_DEAL_AMT")),
                "net_buy_raw": r.get("NET_DEAL_AMT"),
                "buy_amount": self._fmt_money(r.get("BUY_AMT")),
                "sell_amount": self._fmt_money(r.get("SELL_AMT")),
                "index_close": r.get("INDEX_CLOSE_PRICE"),
                "index_change_pct": r.get("INDEX_CHANGE_RATE"),
            }
            for r in rows
        ]

    def get_stock_northbound(self, code: str, days: int = 30) -> List[Dict[str, Any]]:
        """个股北向持股/流向（若接口有数据）。"""
        if not self.config.enable_northbound:
            return []
        rows = self._datacenter(
            "RPT_MUTUAL_HOLDSTOCKNDATE_STA",
            f'(SECURITY_CODE="{code}")',
            page_size=days,
            sort_col="TRADE_DATE",
        )
        if not rows:
            return []
        return [
            {
                "date": str(r.get("TRADE_DATE", ""))[:10],
                "hold_shares": self._fmt_money(r.get("HOLD_SHARES")),
                "hold_ratio": r.get("HOLD_RATIO"),
                "change_shares": self._fmt_money(r.get("CHANGE_SHARES")),
            }
            for r in rows
        ]

    def get_dragon_tiger(self, code: str, limit: int = 20) -> List[Dict[str, Any]]:
        """个股龙虎榜记录。"""
        if not self.config.enable_dragon_tiger:
            return []

        rows = self._datacenter(
            "RPT_BILLBOARD_DAILYDETAILS",
            f'(SECURITY_CODE="{code}")',
            page_size=limit,
            sort_col="TRADE_DATE",
        )
        return [
            {
                "date": str(r.get("TRADE_DATE", ""))[:10],
                "close_price": r.get("CLOSE_PRICE"),
                "change_pct": r.get("CHANGE_RATE"),
                "turnover": self._fmt_money(r.get("ACCUM_AMOUNT")),
                "reason": r.get("EXPLANATION", r.get("EXPLAIN", "")),
            }
            for r in rows
        ]

    def get_shareholder_research(self, code: str) -> Dict[str, Any]:
        """十大股东与股东人数。"""
        if not self.config.enable_shareholder:
            return {}

        security = SecurityInfo.from_code(code)
        mc = f"{security.market}{code}"
        url = f"{BASE_F10}/ShareholderResearch/PageAjax"
        data = self.client.get(url, params={"code": mc})

        holders = []
        for item in (data.get("sdgd") or data.get("top10") or [])[:10]:
            holders.append({
                "name": item.get("HOLDER_NAME", item.get("HOLDERS_NAME", "")),
                "shares": self._fmt_money(item.get("HOLD_NUM", item.get("SHARES"))),
                "ratio": item.get("HOLD_RATIO", item.get("RATIO")),
            })

        return {
            "holder_count": data.get("holder_num", data.get("HOLDER_NUM")),
            "holder_count_change": data.get("holder_num_change"),
            "top10_holders": holders,
        }

    @staticmethod
    def get_cninfo_links(code: str) -> Dict[str, str]:
        """巨潮资讯网免费公告检索链接（官方披露平台）。"""
        security = SecurityInfo.from_code(code)
        market = "szse" if security.market == "SZ" else "sse"
        return {
            "disclosure_search": f"{CNINFO_SEARCH}?keyWord={code}",
            "company_page": f"http://www.cninfo.com.cn/new/disclosure/stock?stockCode={code}&orgId={market}{code}",
            "note": "PDF 公告原文请在巨潮资讯网免费查阅下载，无需 API Key",
        }

    def get_extended_bundle(self, code: str) -> Dict[str, Any]:
        """聚合所有已启用的扩展数据。"""
        cfg = self.config
        bundle: Dict[str, Any] = {
            "code": code,
            "data_sources": {
                "primary": cfg.primary,
                "platform": "东方财富公开接口 + 巨潮资讯链接",
                "requires_api_key": False,
            },
            "availability": {
                "minute_kline": cfg.enable_minute_kline,
                "financial_statements": cfg.enable_financial_statements,
                "analyst_forecast": cfg.enable_analyst_forecast,
                "northbound": cfg.enable_northbound,
                "dragon_tiger": cfg.enable_dragon_tiger,
                "shareholder": cfg.enable_shareholder,
                "cninfo_pdf": cfg.enable_cninfo_link,
                "level2": cfg.enable_level2,
            },
        }

        if cfg.enable_financial_statements:
            bundle["financial_statements"] = self.get_financial_statements(code)
        if cfg.enable_analyst_forecast:
            bundle["analyst_forecast"] = self.get_analyst_forecast(code)
        if cfg.enable_northbound:
            bundle["northbound_market"] = self.get_northbound_flow(30)
            bundle["northbound_stock"] = self.get_stock_northbound(code, 30)
        if cfg.enable_dragon_tiger:
            bundle["dragon_tiger"] = self.get_dragon_tiger(code)
        if cfg.enable_shareholder:
            bundle["shareholder"] = self.get_shareholder_research(code)
        if cfg.enable_cninfo_link:
            bundle["cninfo"] = self.get_cninfo_links(code)

        if not cfg.enable_level2:
            bundle["level2_note"] = "Level-2 十档行情无免费合规数据源，需券商或付费行情"

        return bundle

    def close(self) -> None:
        self.client.close()
