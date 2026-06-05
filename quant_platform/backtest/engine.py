"""
专业回测引擎模块。
对标聚宽/米筐：T+1、涨跌停限制、基准对比、印花税。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import BacktestConfig, get_settings
from quant_platform.backtest.metrics import PerformanceMetrics
from quant_platform.strategy.base import BaseStrategy, SignalType
from quant_platform.utils.logger import get_logger

logger = get_logger("backtest.engine")

# 默认基准：沪深300
DEFAULT_BENCHMARK = "000300"


@dataclass
class BacktestResult:
    """回测结果。"""

    strategy_name: str
    code: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_curve: pd.Series = field(default_factory=pd.Series)
    benchmark_curve: pd.Series = field(default_factory=pd.Series)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    signal_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    def summary(self) -> str:
        m = self.metrics
        lines = [
            f"策略: {self.strategy_name}",
            f"标的: {self.code}",
            f"累计收益率: {m.get('total_return', 0)}%",
            f"年化收益率: {m.get('annual_return', 0)}%",
            f"最大回撤: {m.get('max_drawdown', 0)}%",
            f"夏普比率: {m.get('sharpe_ratio', 0)}",
            f"Sortino: {m.get('sortino_ratio', 0)}",
            f"Calmar: {m.get('calmar_ratio', 0)}",
        ]
        if m.get("benchmark_return") is not None:
            lines.extend([
                f"基准收益: {m.get('benchmark_return', 0)}%",
                f"超额收益: {m.get('excess_return', 0)}%",
                f"信息比率: {m.get('info_ratio', 0)}",
            ])
        lines.extend([
            f"胜率: {m.get('win_rate', 0)}%",
            f"盈亏比: {m.get('profit_loss_ratio', 0)}",
            f"交易次数: {m.get('trade_count', 0)}",
            f"平均持仓: {m.get('avg_holding_days', 0)} 天",
        ])
        return "\n".join(lines)


class BacktestEngine:
    """
    回测引擎。

    A 股规则模拟：
    - 100 股整数倍
    - T+1（当日买入不可当日卖出）
    - 涨跌停不可成交（可配置）
    - 佣金 + 卖出印花税
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or get_settings().backtest

    def run(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        code: str = "",
        benchmark_df: Optional[pd.DataFrame] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResult:
        if df.empty:
            logger.warning("回测数据为空")
            return BacktestResult(strategy_name=strategy.name, code=code)

        signal_df = strategy.generate_signals(df.copy())
        if "datetime" not in signal_df.columns:
            signal_df = signal_df.reset_index()

        # 日期区间过滤
        if start_date or end_date:
            signal_df["_dt"] = pd.to_datetime(signal_df["datetime"])
            if start_date:
                signal_df = signal_df[signal_df["_dt"] >= pd.to_datetime(start_date)]
            if end_date:
                signal_df = signal_df[signal_df["_dt"] <= pd.to_datetime(end_date)]
            signal_df = signal_df.drop(columns=["_dt"])

        if signal_df.empty:
            return BacktestResult(strategy_name=strategy.name, code=code)

        capital = self.config.initial_capital
        shares = 0.0
        buy_date_str: Optional[str] = None
        equity_list: List[float] = []
        dates: List[Any] = []
        trades: List[Dict[str, Any]] = []

        stamp_tax = getattr(self.config, "stamp_tax_rate", 0.001)
        enable_t1 = getattr(self.config, "enable_t1", True)
        enable_limit = getattr(self.config, "enable_limit", True)

        for _, row in signal_df.iterrows():
            price = float(row["close"])
            dt = row.get("datetime", "")
            dt_str = self._fmt_date(dt)
            signal = row.get("signal", SignalType.HOLD.value)
            change_pct = float(row.get("change_pct", 0) or 0)

            buy_price = price * (1 + self.config.slippage)
            sell_price = price * (1 - self.config.slippage)

            # 涨跌停限制：涨停不可买入，跌停不可卖出
            is_limit_up = abs(change_pct) >= 9.5 and change_pct > 0
            is_limit_down = abs(change_pct) >= 9.5 and change_pct < 0

            if signal == SignalType.BUY.value and shares == 0:
                if enable_limit and is_limit_up:
                    pass  # 涨停无法买入
                else:
                    max_shares = int(
                        capital * self.config.position_size
                        / (buy_price * (1 + self.config.commission_rate))
                        / 100
                    ) * 100
                    if max_shares >= 100:
                        cost = max_shares * buy_price
                        commission = cost * self.config.commission_rate
                        capital -= cost + commission
                        shares = max_shares
                        buy_date_str = dt_str
                        trades.append({
                            "trade_date": dt_str,
                            "action": "buy",
                            "price": round(buy_price, 2),
                            "shares": shares,
                            "amount": round(cost, 2),
                            "signal_reason": row.get("signal_reason", ""),
                        })

            elif signal == SignalType.SELL.value and shares > 0:
                # T+1：买入当日不可卖出
                if enable_t1 and buy_date_str == dt_str:
                    pass
                elif enable_limit and is_limit_down:
                    pass  # 跌停无法卖出
                else:
                    revenue = shares * sell_price
                    commission = revenue * self.config.commission_rate
                    tax = revenue * stamp_tax
                    capital += revenue - commission - tax
                    trades.append({
                        "trade_date": dt_str,
                        "action": "sell",
                        "price": round(sell_price, 2),
                        "shares": shares,
                        "amount": round(revenue, 2),
                        "signal_reason": row.get("signal_reason", ""),
                    })
                    shares = 0
                    buy_date_str = None

            equity = capital + shares * price
            equity_list.append(equity)
            dates.append(dt)

        equity_curve = pd.Series(equity_list, index=dates, name="equity")
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax

        # 基准曲线
        benchmark_curve = pd.Series(dtype=float)
        if benchmark_df is not None and not benchmark_df.empty:
            benchmark_curve = self._align_benchmark(benchmark_df, dates)

        return_metrics = PerformanceMetrics.calc_returns(
            equity_curve,
            benchmark_curve if not benchmark_curve.empty else None,
        )
        trade_metrics = PerformanceMetrics.calc_trade_stats(trades)
        metrics = {**return_metrics, **trade_metrics}
        metrics["initial_capital"] = self.config.initial_capital
        metrics["start_date"] = self._fmt_date(dates[0]) if dates else ""
        metrics["end_date"] = self._fmt_date(dates[-1]) if dates else ""
        metrics["benchmark_code"] = getattr(self.config, "benchmark_code", DEFAULT_BENCHMARK)

        logger.info(
            "回测完成 %s/%s: 收益 %.2f%%, 回撤 %.2f%%",
            strategy.name, code,
            metrics.get("total_return", 0),
            metrics.get("max_drawdown", 0),
        )

        return BacktestResult(
            strategy_name=strategy.name,
            code=code,
            metrics=metrics,
            equity_curve=equity_curve,
            drawdown_curve=drawdown,
            benchmark_curve=benchmark_curve,
            trades=trades,
            signal_df=signal_df,
        )

    @staticmethod
    def _align_benchmark(
        benchmark_df: pd.DataFrame, dates: List[Any]
    ) -> pd.Series:
        """将基准收盘价对齐到回测日期，归一化为净值曲线。"""
        bdf = benchmark_df.copy()
        if "datetime" not in bdf.columns:
            return pd.Series(dtype=float)
        bdf["datetime"] = pd.to_datetime(bdf["datetime"])
        bdf = bdf.set_index("datetime").sort_index()
        close = bdf["close"]

        aligned_dates = pd.to_datetime([pd.Timestamp(d) for d in dates])
        aligned = close.reindex(aligned_dates, method="ffill").dropna()
        if aligned.empty:
            return pd.Series(dtype=float)
        return aligned / aligned.iloc[0] * 100000  # 归一化到初始资金量级

    @staticmethod
    def _fmt_date(dt: Any) -> str:
        if hasattr(dt, "strftime"):
            return dt.strftime("%Y-%m-%d")
        return str(dt)[:10]

    def save_result(
        self, result: BacktestResult, db: Any, params: Optional[Dict] = None
    ) -> int:
        record = {
            "strategy_name": result.strategy_name,
            "code": result.code,
            "start_date": result.metrics.get("start_date"),
            "end_date": result.metrics.get("end_date"),
            "initial_capital": result.metrics.get("initial_capital"),
            "final_capital": result.metrics.get("final_capital"),
            "total_return": result.metrics.get("total_return"),
            "annual_return": result.metrics.get("annual_return"),
            "max_drawdown": result.metrics.get("max_drawdown"),
            "sharpe_ratio": result.metrics.get("sharpe_ratio"),
            "win_rate": result.metrics.get("win_rate"),
            "profit_loss_ratio": result.metrics.get("profit_loss_ratio"),
            "trade_count": result.metrics.get("trade_count"),
            "params_json": json.dumps(
                {**(params or {}), **{
                    k: result.metrics.get(k)
                    for k in ("excess_return", "info_ratio", "sortino_ratio", "calmar_ratio")
                    if result.metrics.get(k) is not None
                }},
                ensure_ascii=False,
            ),
        }
        record_id = db.save_backtest_record(record)
        db.save_backtest_trades(record_id, result.trades)
        return record_id
