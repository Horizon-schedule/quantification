"""
回测绩效指标统计模块。
对标聚宽/米筐：基准超额、Sortino、Calmar、信息比率等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class PerformanceMetrics:
    """回测绩效指标计算器。"""

    @staticmethod
    def calc_returns(
        equity_curve: pd.Series,
        benchmark_curve: Optional[pd.Series] = None,
    ) -> Dict[str, float]:
        """计算核心绩效指标，可选基准对比。"""
        if equity_curve.empty or len(equity_curve) < 2:
            return PerformanceMetrics._empty_metrics()

        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]
        total_return = (final - initial) / initial if initial else 0

        daily_returns = equity_curve.pct_change().dropna()
        trading_days = len(equity_curve)
        annual_return = (1 + total_return) ** (252 / max(trading_days, 1)) - 1

        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        max_drawdown = abs(drawdown.min()) if len(drawdown) else 0

        rf_daily = 0.03 / 252
        excess = daily_returns - rf_daily
        std = excess.std()
        sharpe = float(np.sqrt(252) * excess.mean() / std) if std > 1e-10 else 0.0

        # Sortino（仅下行波动）
        downside = daily_returns[daily_returns < 0]
        down_std = downside.std()
        sortino = (
            float(np.sqrt(252) * daily_returns.mean() / down_std)
            if down_std and down_std > 1e-10
            else 0.0
        )

        # Calmar = 年化收益 / 最大回撤
        calmar = (
            float(annual_return / max_drawdown) if max_drawdown > 1e-10 else 0.0
        )

        metrics = {
            "total_return": round(total_return * 100, 2),
            "annual_return": round(annual_return * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            "trading_days": trading_days,
            "final_capital": round(final, 2),
        }

        if benchmark_curve is not None and len(benchmark_curve) >= 2:
            bench_metrics = PerformanceMetrics._calc_benchmark_metrics(
                equity_curve, benchmark_curve
            )
            metrics.update(bench_metrics)

        return metrics

    @staticmethod
    def _calc_benchmark_metrics(
        equity_curve: pd.Series, benchmark_curve: pd.Series
    ) -> Dict[str, float]:
        """计算相对基准的超额收益、Alpha、信息比率。"""
        eq_ret = equity_curve.pct_change().dropna()
        bench_ret = benchmark_curve.pct_change().dropna()

        min_len = min(len(eq_ret), len(bench_ret))
        if min_len < 2:
            return {}

        eq_ret = eq_ret.iloc[-min_len:]
        bench_ret = bench_ret.iloc[-min_len:]

        bench_total = (
            benchmark_curve.iloc[-1] / benchmark_curve.iloc[0] - 1
        ) * 100
        strategy_total = (
            equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
        ) * 100
        excess_return = strategy_total - bench_total

        active_ret = eq_ret - bench_ret
        tracking_error = active_ret.std()
        info_ratio = (
            float(np.sqrt(252) * active_ret.mean() / tracking_error)
            if tracking_error > 1e-10
            else 0.0
        )

        # 简化 Alpha（年化超额）
        alpha = excess_return * (252 / max(min_len, 1))

        return {
            "benchmark_return": round(bench_total, 2),
            "excess_return": round(excess_return, 2),
            "alpha": round(alpha, 2),
            "info_ratio": round(info_ratio, 4),
        }

    @staticmethod
    def calc_trade_stats(trades: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算交易统计：胜率、盈亏比、交易次数、平均持仓周期。"""
        if not trades:
            return {
                "trade_count": 0,
                "win_rate": 0,
                "profit_loss_ratio": 0,
                "avg_holding_days": 0,
            }

        profits: List[float] = []
        buy_price = None
        buy_date = None
        holding_days: List[int] = []

        for trade in trades:
            if trade["action"] == "buy":
                buy_price = trade["price"]
                buy_date = trade.get("trade_date")
            elif trade["action"] == "sell" and buy_price is not None:
                profit = (trade["price"] - buy_price) / buy_price
                profits.append(profit)
                if buy_date and trade.get("trade_date"):
                    try:
                        d1 = pd.to_datetime(buy_date)
                        d2 = pd.to_datetime(trade["trade_date"])
                        holding_days.append((d2 - d1).days)
                    except Exception:
                        pass
                buy_price = None

        if not profits:
            return {
                "trade_count": len(trades),
                "win_rate": 0,
                "profit_loss_ratio": 0,
                "avg_holding_days": 0,
            }

        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        win_rate = len(wins) / len(profits) * 100
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss else 0

        return {
            "trade_count": len(profits),
            "win_rate": round(win_rate, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 4),
            "avg_holding_days": round(np.mean(holding_days), 1) if holding_days else 0,
        }

    @staticmethod
    def _empty_metrics() -> Dict[str, float]:
        return {
            "total_return": 0,
            "annual_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "calmar_ratio": 0,
            "trading_days": 0,
            "final_capital": 0,
        }
