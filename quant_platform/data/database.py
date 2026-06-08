"""
数据库管理模块。
基于 SQLAlchemy，支持 SQLite / PostgreSQL / MySQL。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from config.settings import get_settings
from quant_platform.data.db_backend import DatabaseBackend
from quant_platform.utils.logger import get_logger

logger = get_logger("data.database")


class DatabaseManager:
    """统一数据库 CRUD 管理器。"""

    def __init__(self, db_url: Optional[str] = None):
        if db_url:
            DatabaseBackend.reset_engine()
            get_settings().database.url = db_url
        DatabaseBackend.init_schema()
        self._dialect = DatabaseBackend.dialect_name()
        logger.info("数据库就绪 [%s]", self._dialect)

    def upsert_klines(
        self,
        code: str,
        period: str,
        adjust_type: str,
        rows: List[Dict[str, Any]],
    ) -> int:
        if not rows:
            return 0

        sql = text(DatabaseBackend.upsert_kline_sql())
        count = 0
        with DatabaseBackend.connect() as conn:
            for row in rows:
                conn.execute(
                    sql,
                    {
                        "code": code,
                        "period": period,
                        "adjust_type": adjust_type,
                        "datetime": str(row["datetime"]),
                        "open": row.get("open"),
                        "close": row.get("close"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "volume": row.get("volume"),
                        "amount": row.get("amount"),
                        "change_pct": row.get("change_pct", 0),
                        "turnover_rate": row.get("turnover_rate", 0),
                    },
                )
                count += 1
        return count

    def get_klines(
        self,
        code: str,
        period: str = "101",
        adjust_type: str = "1",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        dt_col = DatabaseBackend.quote_col("datetime")
        sql = f"""
            SELECT {dt_col} AS datetime, open, close, high, low, volume, amount,
                   change_pct, turnover_rate
            FROM kline_history
            WHERE code = :code AND period = :period AND adjust_type = :adjust_type
        """
        params: Dict[str, Any] = {
            "code": code,
            "period": period,
            "adjust_type": adjust_type,
        }
        if start_date:
            sql += f" AND {dt_col} >= :start_date"
            params["start_date"] = start_date
        if end_date:
            sql += f" AND {dt_col} <= :end_date"
            params["end_date"] = end_date
        sql += f" ORDER BY {dt_col} ASC"
        if limit:
            sql += f" LIMIT {int(limit)}"

        with DatabaseBackend.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [DatabaseBackend.row_to_dict(r) for r in rows]

    def get_latest_kline_date(
        self, code: str, period: str = "101", adjust_type: str = "1"
    ) -> Optional[str]:
        dt_col = DatabaseBackend.quote_col("datetime")
        with DatabaseBackend.connect() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT MAX({dt_col}) AS max_dt FROM kline_history
                    WHERE code = :code AND period = :period AND adjust_type = :adjust_type
                    """
                ),
                {"code": code, "period": period, "adjust_type": adjust_type},
            ).fetchone()
        result = DatabaseBackend.row_to_dict(row)
        return result.get("max_dt")

    def save_quote(self, quote: Dict[str, Any]) -> None:
        sql = text(DatabaseBackend.upsert_quote_sql())
        with DatabaseBackend.connect() as conn:
            conn.execute(
                sql,
                {
                    "code": quote["code"],
                    "name": quote.get("name", ""),
                    "price": quote.get("price"),
                    "open": quote.get("open"),
                    "high": quote.get("high"),
                    "low": quote.get("low"),
                    "pre_close": quote.get("pre_close"),
                    "change_val": quote.get("change"),
                    "change_pct": quote.get("change_pct"),
                    "volume": quote.get("volume"),
                    "amount": quote.get("amount"),
                    "turnover_rate": quote.get("turnover_rate", 0),
                    "volume_ratio": quote.get("volume_ratio", 0),
                    "snapshot_time": quote.get(
                        "timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ),
                },
            )

    def upsert_intraday(
        self, code: str, trade_date: str, rows: List[Dict[str, Any]]
    ) -> int:
        if self._dialect == "postgresql":
            sql = text(
                """
                INSERT INTO intraday_data
                (code, trade_date, time, price, volume, avg_price)
                VALUES (:code, :trade_date, :time, :price, :volume, :avg_price)
                ON CONFLICT (code, trade_date, time) DO UPDATE SET
                    price=EXCLUDED.price, volume=EXCLUDED.volume, avg_price=EXCLUDED.avg_price
                """
            )
        elif self._dialect == "mysql":
            sql = text(
                """
                INSERT INTO intraday_data
                (code, trade_date, time, price, volume, avg_price)
                VALUES (:code, :trade_date, :time, :price, :volume, :avg_price)
                ON DUPLICATE KEY UPDATE
                    price=VALUES(price), volume=VALUES(volume), avg_price=VALUES(avg_price)
                """
            )
        else:
            sql = text(
                """
                INSERT OR REPLACE INTO intraday_data
                (code, trade_date, time, price, volume, avg_price)
                VALUES (:code, :trade_date, :time, :price, :volume, :avg_price)
                """
            )

        count = 0
        with DatabaseBackend.connect() as conn:
            for row in rows:
                conn.execute(
                    sql,
                    {
                        "code": code,
                        "trade_date": trade_date,
                        "time": row["time"],
                        "price": row.get("price"),
                        "volume": row.get("volume"),
                        "avg_price": row.get("avg_price", 0),
                    },
                )
                count += 1
        return count

    def save_backtest_record(self, record: Dict[str, Any]) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseBackend.connect() as conn:
            if self._dialect == "postgresql":
                result = conn.execute(
                    text(
                        """
                        INSERT INTO backtest_records
                        (strategy_name, code, start_date, end_date, initial_capital,
                         final_capital, total_return, annual_return, max_drawdown,
                         sharpe_ratio, win_rate, profit_loss_ratio, trade_count,
                         params_json, created_at)
                        VALUES
                        (:strategy_name, :code, :start_date, :end_date, :initial_capital,
                         :final_capital, :total_return, :annual_return, :max_drawdown,
                         :sharpe_ratio, :win_rate, :profit_loss_ratio, :trade_count,
                         :params_json, :created_at)
                        RETURNING id
                        """
                    ),
                    {**record, "created_at": now},
                )
                row = result.fetchone()
                return int(DatabaseBackend.row_to_dict(row).get("id", 0))

            result = conn.execute(
                text(
                    """
                    INSERT INTO backtest_records
                    (strategy_name, code, start_date, end_date, initial_capital,
                     final_capital, total_return, annual_return, max_drawdown,
                     sharpe_ratio, win_rate, profit_loss_ratio, trade_count,
                     params_json, created_at)
                    VALUES
                    (:strategy_name, :code, :start_date, :end_date, :initial_capital,
                     :final_capital, :total_return, :annual_return, :max_drawdown,
                     :sharpe_ratio, :win_rate, :profit_loss_ratio, :trade_count,
                     :params_json, :created_at)
                    """
                ),
                {**record, "created_at": now},
            )
            return int(result.lastrowid or 0)

    def save_backtest_trades(
        self, backtest_id: int, trades: List[Dict[str, Any]]
    ) -> None:
        with DatabaseBackend.connect() as conn:
            for trade in trades:
                conn.execute(
                    text(
                        """
                        INSERT INTO backtest_trades
                        (backtest_id, trade_date, action, price, shares, amount, signal_reason)
                        VALUES
                        (:backtest_id, :trade_date, :action, :price, :shares, :amount, :signal_reason)
                        """
                    ),
                    {
                        "backtest_id": backtest_id,
                        "trade_date": trade.get("trade_date"),
                        "action": trade.get("action"),
                        "price": trade.get("price"),
                        "shares": trade.get("shares"),
                        "amount": trade.get("amount"),
                        "signal_reason": trade.get("signal_reason", ""),
                    },
                )

    def get_backtest_records(self, limit: int = 20) -> List[Dict[str, Any]]:
        with DatabaseBackend.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT * FROM backtest_records
                    ORDER BY created_at DESC LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).fetchall()
        return [DatabaseBackend.row_to_dict(r) for r in rows]

    def save_signal(self, signal: Dict[str, Any]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseBackend.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO strategy_signals
                    (strategy_name, code, signal_type, signal_time, price, reason, created_at)
                    VALUES
                    (:strategy_name, :code, :signal_type, :signal_time, :price, :reason, :created_at)
                    """
                ),
                {**signal, "created_at": now},
            )

    def add_to_watchlist(self, code: str, name: str = "") -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self._dialect == "postgresql":
            sql = text(
                """
                INSERT INTO watchlist (code, name, added_at)
                VALUES (:code, :name, :added_at)
                ON CONFLICT (code) DO NOTHING
                """
            )
        elif self._dialect == "mysql":
            sql = text(
                """
                INSERT IGNORE INTO watchlist (code, name, added_at)
                VALUES (:code, :name, :added_at)
                """
            )
        else:
            sql = text(
                """
                INSERT OR IGNORE INTO watchlist (code, name, added_at)
                VALUES (:code, :name, :added_at)
                """
            )
        with DatabaseBackend.connect() as conn:
            conn.execute(sql, {"code": code, "name": name, "added_at": now})

    def remove_from_watchlist(self, code: str) -> None:
        with DatabaseBackend.connect() as conn:
            conn.execute(
                text("DELETE FROM watchlist WHERE code = :code"),
                {"code": code},
            )

    def get_watchlist(self) -> List[Dict[str, Any]]:
        with DatabaseBackend.connect() as conn:
            rows = conn.execute(
                text("SELECT code, name, added_at FROM watchlist ORDER BY added_at")
            ).fetchall()
        return [DatabaseBackend.row_to_dict(r) for r in rows]

    def log_system(self, level: str, module: str, message: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseBackend.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO system_logs (level, module, message, created_at)
                    VALUES (:level, :module, :message, :created_at)
                    """
                ),
                {"level": level, "module": module, "message": message, "created_at": now},
            )
