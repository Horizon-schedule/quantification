"""
Flask Web 应用模块。
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from flask import Flask, Response, jsonify, render_template, request

from config.settings import BacktestConfig, get_settings, reload_settings
from quant_platform.backtest.comparator import StrategyComparator
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.optimizer import ParameterOptimizer
from quant_platform.backtest.visualizer import BacktestVisualizer
from quant_platform.data.database import DatabaseManager
from quant_platform.data.db_backend import DatabaseBackend
from quant_platform.data.repository import DataRepository
from quant_platform.factors.basic import FactorEngine
from quant_platform.indicators.technical import TechnicalIndicators
from quant_platform.monitor.watcher import MarketWatcher
from quant_platform.data.fundamental_service import FundamentalService
from quant_platform.strategy import (
    BOLLStrategy,
    ComboStrategy,
    KDJStrategy,
    MACDStrategy,
    MAStrategy,
    RSIStrategy,
    VolumeStrategy,
)
from quant_platform.utils.logger import get_logger, setup_logging

logger = get_logger("ui.app")

STRATEGY_MAP = {
    "ma": MAStrategy,
    "macd": MACDStrategy,
    "kdj": KDJStrategy,
    "volume": VolumeStrategy,
    "boll": BOLLStrategy,
    "rsi": RSIStrategy,
    "combo": ComboStrategy,
}


def _build_engine(data: dict) -> BacktestEngine:
    cfg = BacktestConfig()
    if data.get("initial_capital"):
        cfg.initial_capital = float(data["initial_capital"])
    if data.get("slippage") is not None:
        cfg.slippage = float(data["slippage"])
    if data.get("benchmark"):
        cfg.benchmark_code = data["benchmark"]
    return BacktestEngine(config=cfg)


def _get_benchmark_df(repo: DataRepository, benchmark_code: str, limit: int = 500):
    if not benchmark_code:
        return None
    return repo.get_kline_df(benchmark_code, limit=limit)


def create_app() -> Flask:
    settings = reload_settings()
    setup_logging(settings.log_dir, settings.log_level)

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = settings.secret_key

    repo = DataRepository()
    db = DatabaseManager()
    watcher = MarketWatcher(repository=repo)
    screener = StockScreener(repository=repo)
    fundamental = FundamentalService()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health")
    def api_health():
        db_ok = DatabaseBackend.check_connection()
        return jsonify({"status": "ok" if db_ok else "degraded", "database": db_ok,
                        "dialect": DatabaseBackend.dialect_name()}), 200 if db_ok else 503

    @app.route("/api/quote/<code>")
    def api_quote(code: str):
        df = repo.get_realtime_quotes([code])
        if df.empty:
            return jsonify({"error": "无数据"}), 404
        return jsonify(df.iloc[0].to_dict())

    @app.route("/api/kline/<code>")
    def api_kline(code: str):
        limit = request.args.get("limit", 200, type=int)
        df = repo.get_kline_df(code, limit=limit)
        if df.empty:
            return jsonify({"error": "无 K 线数据"}), 404
        df = TechnicalIndicators.calc_all(df)
        return jsonify(_df_to_records(df))

    @app.route("/api/intraday/<code>")
    def api_intraday(code: str):
        df = repo.get_intraday_df(code)
        if df.empty:
            return jsonify({"error": "无分时数据"}), 404
        return jsonify(df.to_dict("records"))

    @app.route("/api/indices")
    def api_indices():
        return jsonify(repo.get_index_list())

    @app.route("/api/etfs")
    def api_etfs():
        return jsonify(repo.get_etf_list())

    @app.route("/api/backtest", methods=["POST"])
    def api_backtest():
        data = request.get_json() or {}
        code = data.get("code", "000001")
        strategy_key = data.get("strategy", "ma")
        params = data.get("params", {})
        benchmark = data.get("benchmark", "000300")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        strategy_cls = STRATEGY_MAP.get(strategy_key)
        if not strategy_cls:
            return jsonify({"error": f"未知策略: {strategy_key}"}), 400

        df = repo.get_kline_df(code, limit=500)
        if df.empty:
            return jsonify({"error": "无 K 线数据"}), 404

        benchmark_df = _get_benchmark_df(repo, benchmark)
        engine = _build_engine(data)
        strategy = strategy_cls(params=params)
        result = engine.run(
            strategy, df, code=code, benchmark_df=benchmark_df,
            start_date=start_date, end_date=end_date,
        )
        record_id = engine.save_result(result, db, params=strategy.get_params())

        viz = BacktestVisualizer()
        viz.plot_equity_curve(result)
        viz.plot_signals(result)

        equity = _series_to_json(result.equity_curve)
        benchmark_json = _series_to_json(result.benchmark_curve) if not result.benchmark_curve.empty else None

        return jsonify({
            "record_id": record_id,
            "summary": result.summary(),
            "metrics": result.metrics,
            "trades": result.trades,
            "equity_curve": equity,
            "benchmark_curve": benchmark_json,
        })

    @app.route("/api/backtest/compare", methods=["POST"])
    def api_backtest_compare():
        """多策略对比回测。"""
        data = request.get_json() or {}
        code = data.get("code", "000001")
        strategies = data.get("strategies", ["ma", "macd", "combo"])
        benchmark = data.get("benchmark", "000300")

        df = repo.get_kline_df(code, limit=500)
        if df.empty:
            return jsonify({"error": "无 K 线数据"}), 404

        benchmark_df = _get_benchmark_df(repo, benchmark)
        engine = _build_engine(data)
        comparator = StrategyComparator(engine)

        instances = []
        for key in strategies:
            cls = STRATEGY_MAP.get(key)
            if cls:
                instances.append(cls())

        results = comparator.compare(instances, df, code, benchmark_df)
        return jsonify({
            "comparison": StrategyComparator.to_comparison_table(results),
            "equity_curves": StrategyComparator.equity_curves_json(results),
        })

    @app.route("/api/backtest/optimize", methods=["POST"])
    def api_backtest_optimize():
        """策略参数网格搜索。"""
        data = request.get_json() or {}
        code = data.get("code", "000001")
        strategy_key = data.get("strategy", "ma")
        metric = data.get("metric", "sharpe_ratio")
        param_grid = data.get("param_grid")

        strategy_cls = STRATEGY_MAP.get(strategy_key)
        if not strategy_cls:
            return jsonify({"error": f"未知策略: {strategy_key}"}), 400

        df = repo.get_kline_df(code, limit=500)
        if df.empty:
            return jsonify({"error": "无 K 线数据"}), 404

        if not param_grid:
            param_grid = ParameterOptimizer.default_grids().get(strategy_key, {})

        optimizer = ParameterOptimizer(_build_engine(data))
        results = optimizer.grid_search(strategy_cls, param_grid, df, code, metric=metric)
        return jsonify({"strategy": strategy_key, "metric": metric, "results": results[:20]})

    @app.route("/api/factors/<code>")
    def api_factors(code: str):
        """因子计算与 IC 检验。"""
        df = repo.get_kline_df(code, limit=300)
        if df.empty:
            return jsonify({"error": "无数据"}), 404
        df = FactorEngine.calc_all_factors(df)
        ic_results = FactorEngine.factor_summary(df)
        latest = df.iloc[-1]
        factor_values = {
            k: round(float(latest[k]), 4)
            for k in df.columns
            if k.startswith(("mom_", "vol_", "rsi", "macd_hist", "vol_ratio", "turnover_"))
            and latest[k] == latest[k]
        }
        return jsonify({"code": code, "factors": factor_values, "ic_analysis": ic_results})

    @app.route("/api/fundamental/<code>")
    def api_fundamental(code: str):
        """获取个股基本面与财务数据。"""
        try:
            return jsonify(fundamental.get_full(code))
        except Exception as exc:
            logger.error("基本面数据获取失败 %s: %s", code, exc)
            return jsonify({"error": f"基本面数据获取失败: {exc}"}), 500

    @app.route("/api/screener", methods=["POST"])
    def api_screener():
        """条件选股。"""
        data = request.get_json() or {}
        condition = data.get("condition", "ma_golden_cross")
        codes = data.get("codes")
        if not codes:
            codes = repo.get_default_stock_pool(size=data.get("pool_size", 30))
        results = screener.screen(codes, condition=condition)
        return jsonify({"condition": condition, "count": len(results), "results": results})

    @app.route("/api/screener/presets")
    def api_screener_presets():
        return jsonify(StockScreener.list_presets())

    @app.route("/api/export/kline/<code>")
    def api_export_kline(code: str):
        """导出 K 线 CSV。"""
        limit = request.args.get("limit", 500, type=int)
        df = repo.get_kline_df(code, limit=limit)
        if df.empty:
            return jsonify({"error": "无数据"}), 404
        df = TechnicalIndicators.calc_all(df)
        return _df_to_csv_response(df, f"kline_{code}.csv")

    @app.route("/api/export/backtest/<int:record_id>")
    def api_export_backtest(record_id: int):
        """导出回测交易明细 CSV。"""
        with DatabaseBackend.connect() as conn:
            from sqlalchemy import text
            trades = conn.execute(
                text("SELECT * FROM backtest_trades WHERE backtest_id = :id ORDER BY id"),
                {"id": record_id},
            ).fetchall()
        if not trades:
            return jsonify({"error": "无交易记录"}), 404
        output = io.StringIO()
        rows = [DatabaseBackend.row_to_dict(t) for t in trades]
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=backtest_{record_id}.csv"},
        )

    @app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
    def api_watchlist():
        if request.method == "GET":
            return jsonify(watcher.get_watchlist())
        data = request.get_json() or {}
        code = data.get("code", "")
        if not code:
            return jsonify({"error": "缺少 code"}), 400
        if request.method == "POST":
            watcher.add_watch(code, data.get("name", ""))
            return jsonify({"ok": True})
        watcher.remove_watch(code)
        return jsonify({"ok": True})

    @app.route("/api/watchlist/poll")
    def api_watch_poll():
        return jsonify(watcher.poll_once())

    @app.route("/api/backtest/history")
    def api_backtest_history():
        return jsonify(db.get_backtest_records(limit=30))

    @app.route("/api/search")
    def api_search():
        keyword = request.args.get("q", "")
        if not keyword:
            return jsonify([])
        return jsonify(repo.search_stock(keyword))

    return app


def _df_to_records(df) -> List[Dict[str, Any]]:
    records = []
    for _, row in df.iterrows():
        dt = row.get("datetime")
        dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
        record: Dict[str, Any] = {"datetime": dt_str}
        for col in df.columns:
            if col == "datetime":
                continue
            val = row[col]
            if hasattr(val, "item"):
                val = val.item()
            try:
                record[col] = round(float(val), 4) if val == val else None
            except (TypeError, ValueError):
                record[col] = val
        records.append(record)
    return records


def _series_to_json(series) -> Dict[str, Any]:
    dates, values = [], []
    for dt, val in series.items():
        dates.append(dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10])
        values.append(round(float(val), 2))
    return {"dates": dates, "values": values}


def _df_to_csv_response(df, filename: str) -> Response:
    output = io.StringIO()
    df.to_csv(output, index=False)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
