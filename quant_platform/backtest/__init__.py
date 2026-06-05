"""回测层 - 回测引擎与可视化。"""

from quant_platform.backtest.engine import BacktestEngine, BacktestResult
from quant_platform.backtest.metrics import PerformanceMetrics
from quant_platform.backtest.visualizer import BacktestVisualizer
from quant_platform.backtest.comparator import StrategyComparator
from quant_platform.backtest.optimizer import ParameterOptimizer

__all__ = [
    "BacktestEngine", "BacktestResult", "PerformanceMetrics",
    "BacktestVisualizer", "StrategyComparator", "ParameterOptimizer",
]
