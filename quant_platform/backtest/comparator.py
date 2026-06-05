"""
策略对比模块。
对标 vnpy cta_backtester / 聚宽多策略对比。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

import pandas as pd

from quant_platform.backtest.engine import BacktestEngine, BacktestResult
from quant_platform.strategy.base import BaseStrategy


class StrategyComparator:
    """多策略并行回测与对比。"""

    def __init__(self, engine: Optional[BacktestEngine] = None):
        self.engine = engine or BacktestEngine()

    def compare(
        self,
        strategies: List[BaseStrategy],
        df: pd.DataFrame,
        code: str,
        benchmark_df: Optional[pd.DataFrame] = None,
    ) -> List[BacktestResult]:
        """对同一标的运行多个策略并返回结果列表。"""
        results = []
        for strategy in strategies:
            result = self.engine.run(strategy, df, code=code, benchmark_df=benchmark_df)
            results.append(result)
        return results

    @staticmethod
    def to_comparison_table(results: List[BacktestResult]) -> List[Dict[str, Any]]:
        """生成策略对比表格数据。"""
        rows = []
        for r in results:
            m = r.metrics
            rows.append({
                "strategy": r.strategy_name,
                "code": r.code,
                "total_return": m.get("total_return", 0),
                "annual_return": m.get("annual_return", 0),
                "max_drawdown": m.get("max_drawdown", 0),
                "sharpe_ratio": m.get("sharpe_ratio", 0),
                "sortino_ratio": m.get("sortino_ratio", 0),
                "win_rate": m.get("win_rate", 0),
                "trade_count": m.get("trade_count", 0),
                "excess_return": m.get("excess_return"),
                "info_ratio": m.get("info_ratio"),
            })
        return rows

    @staticmethod
    def equity_curves_json(results: List[BacktestResult]) -> Dict[str, Any]:
        """导出多条权益曲线供前端对比绘图。"""
        series = {}
        for r in results:
            dates, values = [], []
            for dt, val in r.equity_curve.items():
                dates.append(dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10])
                values.append(round(float(val), 2))
            series[r.strategy_name] = {"dates": dates, "values": values}

        # 基准曲线
        if results and not results[0].benchmark_curve.empty:
            bc = results[0].benchmark_curve
            dates, values = [], []
            for dt, val in bc.items():
                dates.append(dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10])
                values.append(round(float(val), 2))
            series["基准"] = {"dates": dates, "values": values}

        return series
