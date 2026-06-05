# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')

from quant_platform.api.fundamental import EastMoneyFundamentalAPI

api = EastMoneyFundamentalAPI()
data = api.get_fundamental("600519")
print("name:", data.name)
print("profile:", data.profile.to_dict() if data.profile else {})
print("latest:", data.latest_summary)
print("reports:", len(data.financial_reports))
for r in data.financial_reports[:4]:
    d = r.to_dict()
    print(f"  {d['report_type']} rev={d['total_revenue']} yoy={d['revenue_yoy']} profit={d['net_profit']}")

print("contracts:", len(data.contracts))
print("bids:", len(data.bid_wins))
for b in data.bid_wins[:3]:
    print(" ", b.to_dict())

data2 = api.get_fundamental("601390")
print("\n601390 bids:", len(data2.bid_wins))
for b in data2.bid_wins[:3]:
    print(" ", b.to_dict())
api.close()
