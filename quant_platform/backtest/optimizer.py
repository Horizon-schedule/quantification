"""
策略参数优化模块。
对标聚宽/米筐参数扫描、vnpy 参数优化。
"""

from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import pandas as pd

from quant_platform.backtest.engine import BacktestEngine, BacktestResult
from quant_platform.strategy.base import BaseStrategy


class ParameterOptimizer:
    """网格搜索参数优化器。"""

    def __init__(self, engine: Optional[BacktestEngine] = None):
        self.engine = engine or BacktestEngine()

    def grid_search(
        self,
        strategy_cls: Type[BaseStrategy],
        param_grid: Dict[str, List[Any]],
        df: pd.DataFrame,
        code: str,
        metric: str = "sharpe_ratio",
        benchmark_df: Optional[pd.DataFrame] = None,
    ) -> List[Dict[str, Any]]:
        """
        网格搜索最优参数。

        参数:
            strategy_cls: 策略类
            param_grid: 参数网格，如 {"fast_period": [5, 10], "slow_period": [20, 30]}
            df: K 线数据
            code: 证券代码
            metric: 优化目标指标

        返回:
            按目标指标降序排列的结果列表
        """
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        results: List[Dict[str, Any]] = []
        for combo in combinations:
            params = dict(zip(keys, combo))
            strategy = strategy_cls(params=params)
            bt_result = self.engine.run(
                strategy, df, code=code, benchmark_df=benchmark_df
            )
            score = bt_result.metrics.get(metric, 0) or 0
            results.append({
                "params": params,
                "metric": metric,
                "score": score,
                "total_return": bt_result.metrics.get("total_return", 0),
                "max_drawdown": bt_result.metrics.get("max_drawdown", 0),
                "sharpe_ratio": bt_result.metrics.get("sharpe_ratio", 0),
                "win_rate": bt_result.metrics.get("win_rate", 0),
                "trade_count": bt_result.metrics.get("trade_count", 0),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    @staticmethod
    def default_grids() -> Dict[str, Dict[str, List[Any]]]:
        """内置策略默认参数网格。"""
        return {
            "ma": {
                "fast_period": [5, 10],
                "slow_period": [20, 30, 60],
                "mode": ["cross"],
            },
            "macd": {
                "fast": [12, 6],
                "slow": [26, 19],
                "mode": ["cross"],
            },
            "kdj": {
                "oversold": [15, 20, 25],
                "overbought": [75, 80, 85],
                "mode": ["resonance", "cross"],
            },
            "rsi": {
                "oversold": [25, 30, 35],
                "overbought": [65, 70, 75],
            },
            "boll": {
                "period": [15, 20, 26],
                "mode": ["breakout", "reversion"],
            },
        }
