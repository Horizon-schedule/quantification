"""
回测可视化模块。
生成收益曲线、回撤曲线、交易信号标记图。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from config.settings import get_settings
from quant_platform.backtest.engine import BacktestResult
from quant_platform.utils.logger import get_logger

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
matplotlib.rcParams["axes.unicode_minus"] = False

logger = get_logger("backtest.visualizer")


class BacktestVisualizer:
    """回测结果可视化。"""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or get_settings().output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_equity_curve(
        self, result: BacktestResult, save: bool = True
    ) -> Optional[str]:
        """绘制收益曲线与回撤曲线。"""
        if result.equity_curve.empty:
            return None

        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # 收益曲线
        axes[0].plot(
            result.equity_curve.index,
            result.equity_curve.values,
            color="#2196F3",
            linewidth=1.5,
            label="权益曲线",
        )
        axes[0].set_title(
            f"{result.strategy_name} - {result.code} 回测收益曲线",
            fontsize=14,
        )
        axes[0].set_ylabel("账户权益 (元)")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # 回撤曲线
        axes[1].fill_between(
            result.drawdown_curve.index,
            result.drawdown_curve.values * 100,
            0,
            color="#F44336",
            alpha=0.4,
            label="回撤",
        )
        axes[1].set_ylabel("回撤 (%)")
        axes[1].set_xlabel("日期")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        filepath = None
        if save:
            filepath = str(
                self.output_dir / f"backtest_{result.code}_{result.strategy_name}.png"
            )
            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            logger.info("收益曲线已保存: %s", filepath)

        plt.close(fig)
        return filepath

    def plot_signals(
        self, result: BacktestResult, save: bool = True
    ) -> Optional[str]:
        """绘制 K 线 + 买卖信号标记图。"""
        df = result.signal_df
        if df.empty or "close" not in df.columns:
            return None

        fig, ax = plt.subplots(figsize=(14, 6))

        ax.plot(df.index, df["close"], color="#333", linewidth=1, label="收盘价")

        buy_mask = df.get("signal", pd.Series()) == "buy"
        sell_mask = df.get("signal", pd.Series()) == "sell"

        if buy_mask.any():
            ax.scatter(
                df.index[buy_mask],
                df["close"][buy_mask],
                marker="^",
                color="#4CAF50",
                s=80,
                label="买入",
                zorder=5,
            )
        if sell_mask.any():
            ax.scatter(
                df.index[sell_mask],
                df["close"][sell_mask],
                marker="v",
                color="#F44336",
                s=80,
                label="卖出",
                zorder=5,
            )

        ax.set_title(
            f"{result.strategy_name} - {result.code} 交易信号",
            fontsize=14,
        )
        ax.set_ylabel("价格")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        filepath = None
        if save:
            filepath = str(
                self.output_dir / f"signals_{result.code}_{result.strategy_name}.png"
            )
            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            logger.info("信号图已保存: %s", filepath)

        plt.close(fig)
        return filepath

    def plot_kline_with_indicators(
        self, df: pd.DataFrame, code: str = "", save: bool = True
    ) -> Optional[str]:
        """绘制 K 线 + 均线 + 成交量。"""
        if df.empty:
            return None

        fig, axes = plt.subplots(
            2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]}
        )

        ax_price = axes[0]
        ax_price.plot(df.index, df["close"], color="#333", linewidth=1, label="收盘")

        for col in df.columns:
            if col.startswith("ma"):
                ax_price.plot(df.index, df[col], linewidth=0.8, label=col, alpha=0.7)

        ax_price.set_title(f"{code} K线与均线", fontsize=14)
        ax_price.legend(loc="upper left", fontsize=8)
        ax_price.grid(True, alpha=0.3)

        ax_vol = axes[1]
        if "volume" in df.columns:
            colors = [
                "#F44336" if c < o else "#4CAF50"
                for c, o in zip(df["close"], df["open"])
            ] if "open" in df.columns else "#999"
            ax_vol.bar(df.index, df["volume"], color=colors, alpha=0.6)
        ax_vol.set_ylabel("成交量")
        ax_vol.grid(True, alpha=0.3)

        plt.tight_layout()

        filepath = None
        if save:
            filepath = str(self.output_dir / f"kline_{code}.png")
            fig.savefig(filepath, dpi=150, bbox_inches="tight")

        plt.close(fig)
        return filepath
