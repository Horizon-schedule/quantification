# -*- coding: utf-8 -*-
import sys, requests
sys.stdout.reconfigure(encoding='utf-8')
s = requests.Session(); s.trust_env = False
s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"})
base = "https://datacenter-web.eastmoney.com/api/data/v1/get"
code = "600519"

tests = [
    ("balance", "RPT_DMSK_FN_BALANCE", f'(SECURITY_CODE="{code}")', "REPORT_DATE"),
    ("cashflow", "RPT_DMSK_FN_CASHFLOW", f'(SECURITY_CODE="{code}")', "REPORT_DATE"),
    ("forecast", "RPT_WEB_RESPREDICT", f'(SECURITY_CODE="{code}")', "RATING_ORG_NUM"),
    ("north_hist", "RPT_MUTUAL_DEAL_HISTORY", '(MUTUAL_TYPE="001")', "TRADE_DATE"),
    ("lhb_stock", "RPT_BILLBOARD_DAILYDETAILS", f'(SECURITY_CODE="{code}")', "TRADE_DATE"),
    ("lhb_date", "RPT_DAILYBILLBOARD_DETAILS", '(TRADE_DATE>=\'2026-01-01\')', "TRADE_DATE"),
]

for name, rn, filt, sort in tests:
    r = s.get(base, params={"reportName": rn, "columns": "ALL", "filter": filt, "pageNumber": 1, "pageSize": 3, "sortColumns": sort, "sortTypes": "-1"}, timeout=15)
    d = r.json()
    data = (d.get("result") or {}).get("data") or []
    print(name, "rows", len(data), "keys", list(data[0].keys())[:8] if data else "none")

# report api
r2 = s.get("https://reportapi.eastmoney.com/report/list", params={"pageNo": 1, "pageSize": 3, "code": "600519", "industryCode": "*", "industry": "*", "rating": "*", "ratingChange": "*", "beginTime": "2024-01-01", "endTime": "2026-12-31", "pageIndex": 1, "fields": "", "qType": 0, "orgCode": "", "p": 1, "pageNum": 1, "pageNumber": 1}, timeout=15)
print("reportapi", r2.status_code, list(r2.json().keys()) if r2.ok else r2.text[:100])
