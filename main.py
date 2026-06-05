#!/usr/bin/env python3
"""
StopQuant 个人量化研究平台 - 主入口。

用法:
    python main.py                  # 启动 Web 界面
    python main.py --backtest       # 命令行回测示例
    python main.py --quote 600519   # 查询实时行情
    python main.py --kline 000001   # 获取 K 线数据
"""

from __future__ import annotations

import argparse
import sys

from config.settings import get_settings
from quant_platform.utils.logger import setup_logging, get_logger


def run_web(host: str = "0.0.0.0", port: int = 8000) -> None:
    """启动 Flask Web 界面（开发模式）。"""
    from quant_platform.ui.app import create_app

    settings = get_settings()
    host = settings.host if host == "0.0.0.0" else host
    port = settings.port if port == 5000 else port

    app = create_app()
    logger = get_logger("main")
    logger.info("StopQuant Web 服务启动: http://%s:%d", host, port)
    app.run(host=host, port=port, debug=False)


def run_backtest_demo() -> None:
    """命令行回测示例。"""
    from quant_platform.data.repository import DataRepository
    from quant_platform.strategy import MAStrategy, MACDStrategy
    from quant_platform.backtest.engine import BacktestEngine
    from quant_platform.backtest.visualizer import BacktestVisualizer
    from quant_platform.data.database import DatabaseManager

    logger = get_logger("main")
    repo = DataRepository()
    code = "600519"

    logger.info("获取 %s K 线数据...", code)
    df = repo.get_kline_df(code, limit=500)
    if df.empty:
        logger.error("无数据，请检查网络连接")
        return

    logger.info("K 线数据 %d 条，开始回测...", len(df))

    # 高价股需更大初始资金（A 股最小买入 100 股）
    from config.settings import get_settings
    bt_config = get_settings().backtest
    bt_config.initial_capital = 200_000.0

    for strategy_cls, name in [(MAStrategy, "均线"), (MACDStrategy, "MACD")]:
        strategy = strategy_cls()
        engine = BacktestEngine()
        result = engine.run(strategy, df, code=code)
        print(f"\n{'='*50}")
        print(result.summary())

        viz = BacktestVisualizer()
        viz.plot_equity_curve(result)
        viz.plot_signals(result)

        db = DatabaseManager()
        engine.save_result(result, db, params=strategy.get_params())

    repo.close()
    logger.info("回测完成，图表已保存至 output/ 目录")


def run_quote(code: str) -> None:
    """查询实时行情。"""
    from quant_platform.data.repository import DataRepository

    repo = DataRepository()
    df = repo.get_realtime_quotes([code])
    if df.empty:
        print(f"未获取到 {code} 的行情数据")
    else:
        row = df.iloc[0]
        print(f"代码: {row['code']}")
        print(f"名称: {row.get('name', '')}")
        print(f"最新价: {row['price']}")
        print(f"涨跌幅: {row['change_pct']}%")
        print(f"成交量: {row['volume']}")
        print(f"成交额: {row['amount']}")
    repo.close()


def run_kline(code: str, limit: int = 10) -> None:
    """获取 K 线数据。"""
    from quant_platform.data.repository import DataRepository
    from quant_platform.indicators.technical import TechnicalIndicators

    repo = DataRepository()
    df = repo.get_kline_df(code, limit=500)
    if df.empty:
        print(f"未获取到 {code} 的 K 线数据")
        return

    df = TechnicalIndicators.calc_all(df)
    print(f"\n{code} 最近 {limit} 条 K 线:")
    print(df.tail(limit).to_string())
    repo.close()


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="StopQuant 个人量化研究平台",
    )
    parser.add_argument("--web", action="store_true", help="启动 Web 界面")
    parser.add_argument("--backtest", action="store_true", help="运行回测示例")
    parser.add_argument("--quote", type=str, help="查询实时行情，如 --quote 600519")
    parser.add_argument("--kline", type=str, help="获取 K 线，如 --kline 000001")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Web 服务地址")
    parser.add_argument("--port", type=int, default=5000, help="Web 服务端口")

    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_dir, settings.log_level)

    if args.backtest:
        run_backtest_demo()
    elif args.quote:
        run_quote(args.quote)
    elif args.kline:
        run_kline(args.kline)
    else:
        # 默认启动 Web
        run_web(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
